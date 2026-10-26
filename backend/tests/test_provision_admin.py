import pytest
from sqlalchemy import create_engine, event, func, select
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.core.security import UserRole, get_password_hash, verify_password
from app.database.base import Base
from app.models.entities import User
from provision_admin import (
    AdminProvisioningError,
    _has_explicit_database_configuration,
    provision_admin,
)


@pytest.fixture
def isolated_user_database():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine, tables=[User.__table__])

    # SQLite does not generate the PostgreSQL BigInteger Identity value.
    @event.listens_for(User, "before_insert")
    def assign_sqlite_test_identity(mapper, connection, target):
        if target.id is None:
            target.id = connection.scalar(select(func.coalesce(func.max(User.id), 0) + 1))

    session = Session(engine, expire_on_commit=False)
    try:
        yield session
    finally:
        session.close()
        event.remove(User, "before_insert", assign_sqlite_test_identity)
        engine.dispose()


def _provision(db, email="new-admin@example.com", phone="9876543210", password="StrongPass123"):
    return provision_admin(
        db,
        email=email,
        full_name="New Administrator",
        phone_number=phone,
        password=password,
    )


def test_admin_command_requires_explicit_database_configuration():
    assert not _has_explicit_database_configuration(set())
    assert _has_explicit_database_configuration({"DATABASE_URL"})
    assert _has_explicit_database_configuration(
        {"POSTGRES_SERVER", "POSTGRES_PORT", "POSTGRES_USER", "POSTGRES_PASSWORD", "POSTGRES_DB"}
    )


def test_provision_admin_assigns_admin_role_and_bcrypt_hash(isolated_user_database):
    user = _provision(isolated_user_database)

    assert user.id is not None
    assert user.role is UserRole.ADMIN
    assert user.is_active is True
    assert user.hashed_password != "StrongPass123"
    assert verify_password("StrongPass123", user.hashed_password)
    assert not verify_password("WrongPass123", user.hashed_password)


def test_provision_admin_refuses_existing_email_without_promoting_user(isolated_user_database):
    existing = User(
        email="new-admin@example.com",
        phone_number="9876543210",
        hashed_password=get_password_hash("FarmerPass123"),
        full_name="Existing Farmer",
        role=UserRole.FARMER,
        is_active=True,
    )
    isolated_user_database.add(existing)
    isolated_user_database.commit()
    existing_id = existing.id

    with pytest.raises(AdminProvisioningError, match="email already exists"):
        _provision(isolated_user_database, phone="9123456789")

    unchanged = isolated_user_database.get(User, existing_id)
    assert unchanged.role is UserRole.FARMER
    assert isolated_user_database.scalar(select(func.count(User.id))) == 1


@pytest.mark.parametrize(
    ("email", "phone", "password", "expected_field", "expected_reason"),
    [
        ("not-an-email", "9876543210", "StrongPass123", "email", "valid email address"),
        ("new-admin@example.com", "12345", "StrongPass123", "phone_number", "10-digit Indian mobile"),
        ("new-admin@example.com", "9876543210", "short", "password", "8 to 72 characters"),
    ],
)
def test_invalid_admin_details_report_safe_field_reason(
    isolated_user_database, email, phone, password, expected_field, expected_reason
):
    with pytest.raises(AdminProvisioningError) as raised:
        _provision(
            isolated_user_database,
            email=email,
            phone=phone,
            password=password,
        )

    message = str(raised.value)
    assert expected_field in message
    assert expected_reason in message
    assert email not in message
    assert phone not in message
    assert password not in message
    assert isolated_user_database.scalar(select(func.count(User.id))) == 0


def test_admin_password_over_bcrypt_byte_limit_has_safe_message(isolated_user_database):
    password = "é" * 37 + "A1"
    with pytest.raises(AdminProvisioningError, match="at most 72 UTF-8 bytes") as raised:
        _provision(isolated_user_database, password=password)
    assert password not in str(raised.value)
    assert isolated_user_database.scalar(select(func.count(User.id))) == 0


def test_provision_admin_rolls_back_when_insert_fails():
    class FailingSession:
        def __init__(self):
            self.rollback_count = 0

        def scalar(self, statement):
            return None

        def add(self, value):
            self.pending_user = value

        def flush(self):
            raise RuntimeError("simulated database failure")

        def rollback(self):
            self.rollback_count += 1

    session = FailingSession()
    with pytest.raises(RuntimeError, match="simulated database failure"):
        _provision(session)
    assert session.rollback_count == 1
    assert session.pending_user.role is UserRole.ADMIN
