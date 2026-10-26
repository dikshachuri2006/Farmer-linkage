from datetime import datetime, timezone
from typing import Dict, Optional
from uuid import uuid4
from fastapi.testclient import TestClient
import pytest
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session
from app.core.config import settings
from app.core.security import UserRole, create_access_token, get_password_hash
from app.core.security import verify_password
from app.database.connection import get_db
from app.main import app
from app.models.entities import User
from app.schemas.auth import UserRegisterRequest
from app.services.auth_service import (
    DefaultPostgresUserRepository,
    DuplicateUserError,
    UserRepository,
    get_user_repository,
)

client = TestClient(app)


class MockUser:
    def __init__(
        self,
        id: int,
        email: str,
        phone_number: str,
        full_name: str,
        role: UserRole,
        hashed_password: str,
        is_active: bool = True,
    ):
        self.id = id
        self.email = email
        self.phone_number = phone_number
        self.full_name = full_name
        self.role = role
        self.hashed_password = hashed_password
        self.is_active = is_active
        self.created_at = datetime.now(timezone.utc)


class IsolatedMockUserRepository:
    """Mock repository used only for isolated unit tests without touching a database."""
    def __init__(self):
        self.users_by_id: Dict[int, MockUser] = {}
        self.users_by_email: Dict[str, MockUser] = {}
        self.users_by_phone: Dict[str, MockUser] = {}
        self.next_id = 1

    def get_by_id(self, db, user_id: int) -> Optional[MockUser]:
        return self.users_by_id.get(user_id)

    def get_by_email(self, db, email: str) -> Optional[MockUser]:
        return self.users_by_email.get(email.lower())

    def get_by_phone(self, db, phone_number: str) -> Optional[MockUser]:
        return self.users_by_phone.get(phone_number)

    def create_user(
        self, db, user_in: UserRegisterRequest, password_hash: str
    ) -> MockUser:
        user = MockUser(
            id=self.next_id,
            email=user_in.email.lower(),
            phone_number=user_in.phone_number,
            full_name=user_in.full_name,
            role=user_in.role,
            hashed_password=password_hash,
            is_active=True,
        )
        self.users_by_id[user.id] = user
        self.users_by_email[user.email] = user
        self.users_by_phone[user.phone_number] = user
        self.next_id += 1
        return user


# ==============================================================================
# 1. Registration Input Validation & Admin Prevention Tests
# ==============================================================================

def test_register_invalid_email_returns_422():
    response = client.post(
        "/api/auth/register",
        json={
            "full_name": "Ramesh Patil",
            "email": "not-an-email",
            "phone_number": "9876543210",
            "password": "Password123",
            "role": "FARMER",
        },
    )
    assert response.status_code == 422


def test_register_invalid_phone_returns_422():
    response = client.post(
        "/api/auth/register",
        json={
            "full_name": "Ramesh Patil",
            "email": "ramesh@example.com",
            "phone_number": "12345",  # Invalid phone
            "password": "Password123",
            "role": "FARMER",
        },
    )
    assert response.status_code == 422
    assert "10-digit Indian mobile number" in str(response.json())


def test_register_weak_password_returns_422():
    response = client.post(
        "/api/auth/register",
        json={
            "full_name": "Ramesh Patil",
            "email": "ramesh@example.com",
            "phone_number": "9876543210",
            "password": "simple",  # Too short and no numbers
            "role": "FARMER",
        },
    )
    assert response.status_code == 422


def test_register_prevent_admin_role_returns_422():
    """Security rule: Public registration MUST reject ADMIN accounts."""
    response = client.post(
        "/api/auth/register",
        json={
            "full_name": "Malicious Attacker",
            "email": "hacker@example.com",
            "phone_number": "9876543210",
            "password": "Password123",
            "role": "ADMIN",
        },
    )
    assert response.status_code == 422
    assert "Administrator accounts cannot be created via public registration" in str(response.json())


@pytest.fixture
def auth_db_session():
    """Use the configured PostgreSQL schema inside a rollback-only transaction."""
    engine = create_engine(settings.SQLALCHEMY_DATABASE_URI, echo=False, pool_pre_ping=True)
    try:
        connection = engine.connect()
    except Exception as error:
        pytest.skip(f"Live PostgreSQL database is unreachable: {error}")
    outer_transaction = connection.begin()
    session = Session(bind=connection, join_transaction_mode="create_savepoint")

    def override_get_db():
        yield session

    app.dependency_overrides.clear()
    app.dependency_overrides[get_db] = override_get_db
    try:
        yield session
    finally:
        app.dependency_overrides.clear()
        session.close()
        if outer_transaction.is_active:
            outer_transaction.rollback()
        connection.close()
        engine.dispose()


def _registration_payload(email: str, phone_number: str) -> dict:
    return {
        "full_name": "Database Test User",
        "email": email,
        "phone_number": phone_number,
        "password": "ValidPassword123",
        "role": "FARMER",
    }


def test_register_persists_user_and_rejects_duplicate_email_and_phone(auth_db_session):
    suffix = uuid4().hex
    email = f"auth-{suffix}@example.com"
    phone = f"9{uuid4().int % 1_000_000_000:09d}"

    response = client.post("/api/auth/register", json=_registration_payload(email, phone))
    assert response.status_code == 201
    data = response.json()
    assert data["email"] == email
    assert data["phone_number"] == phone
    assert data["role"] == "FARMER"
    assert "password" not in data
    assert "hashed_password" not in data

    persisted = auth_db_session.scalar(select(User).where(User.email == email))
    assert persisted is not None
    assert verify_password("ValidPassword123", persisted.hashed_password)

    duplicate_email = client.post(
        "/api/auth/register",
        json=_registration_payload(email, f"9{uuid4().int % 1_000_000_000:09d}"),
    )
    assert duplicate_email.status_code == 409
    assert "email address already exists" in duplicate_email.json()["detail"]

    duplicate_phone = client.post(
        "/api/auth/register",
        json=_registration_payload(f"other-{suffix}@example.com", phone),
    )
    assert duplicate_phone.status_code == 409
    assert "phone number already exists" in duplicate_phone.json()["detail"]

    assert auth_db_session.scalar(
        select(func.count()).select_from(User).where(User.email == email)
    ) == 1


@pytest.mark.parametrize("duplicate_field", ["email", "phone"])
def test_user_repository_maps_unique_constraint_races(auth_db_session, duplicate_field):
    suffix = uuid4().hex
    email = f"race-{suffix}@example.com"
    phone = f"9{uuid4().int % 1_000_000_000:09d}"
    repository = DefaultPostgresUserRepository()
    first = UserRegisterRequest(
        full_name="First Test User",
        email=email,
        phone_number=phone,
        password="ValidPassword123",
        role=UserRole.BUYER,
    )
    repository.create_user(auth_db_session, first, get_password_hash(first.password))

    duplicate = UserRegisterRequest(
        full_name="Second Test User",
        email=email if duplicate_field == "email" else f"second-{suffix}@example.com",
        phone_number=phone if duplicate_field == "phone" else f"9{uuid4().int % 1_000_000_000:09d}",
        password="ValidPassword123",
        role=UserRole.FARMER,
    )
    with pytest.raises(DuplicateUserError) as error:
        repository.create_user(auth_db_session, duplicate, get_password_hash(duplicate.password))
    assert error.value.field == duplicate_field

    assert repository.get_by_email(auth_db_session, email) is not None


# ==============================================================================
# 2. Registration Flow with Repository Dependency Override
# ==============================================================================

def test_register_success_with_isolated_repository():
    mock_repo = IsolatedMockUserRepository()
    app.dependency_overrides[get_user_repository] = lambda: mock_repo

    try:
        response = client.post(
            "/api/auth/register",
            json={
                "full_name": "Ramesh Patil",
                "email": "ramesh@example.com",
                "phone_number": "9876543210",
                "password": "ValidPassword123",
                "role": "FARMER",
            },
        )
        assert response.status_code == 201
        data = response.json()
        assert data["id"] == 1
        assert data["full_name"] == "Ramesh Patil"
        assert data["email"] == "ramesh@example.com"
        assert data["phone_number"] == "9876543210"
        assert data["role"] == "FARMER"
        assert data["is_active"] is True
        # Critical security check: password and hash must never be in response
        assert "password" not in data
        assert "hashed_password" not in data

        # Test duplicate email conflict (409)
        dup_email_resp = client.post(
            "/api/auth/register",
            json={
                "full_name": "Another Farmer",
                "email": "ramesh@example.com",
                "phone_number": "9811122233",
                "password": "ValidPassword123",
                "role": "FARMER",
            },
        )
        assert dup_email_resp.status_code == 409
        assert "email address already exists" in dup_email_resp.json()["detail"]

        # Test duplicate phone conflict (409)
        dup_phone_resp = client.post(
            "/api/auth/register",
            json={
                "full_name": "Another Farmer",
                "email": "other@example.com",
                "phone_number": "9876543210",
                "password": "ValidPassword123",
                "role": "FARMER",
            },
        )
        assert dup_phone_resp.status_code == 409
        assert "phone number already exists" in dup_phone_resp.json()["detail"]

    finally:
        app.dependency_overrides.clear()


# ==============================================================================
# 3. Login Scenarios
# ==============================================================================

def test_login_scenarios_with_isolated_repository():
    mock_repo = IsolatedMockUserRepository()
    # Seed mock user
    pwd_hash = get_password_hash("FarmerSecret123")
    user = MockUser(
        id=101,
        email="suresh@example.com",
        phone_number="9876543211",
        full_name="Suresh Kumar",
        role=UserRole.FARMER,
        hashed_password=pwd_hash,
        is_active=True,
    )
    mock_repo.users_by_id[101] = user
    mock_repo.users_by_email["suresh@example.com"] = user
    mock_repo.users_by_phone["9876543211"] = user

    app.dependency_overrides[get_user_repository] = lambda: mock_repo

    try:
        # Successful login via email
        res1 = client.post(
            "/api/auth/login",
            json={
                "username_or_email": "suresh@example.com",
                "password": "FarmerSecret123",
            },
        )
        assert res1.status_code == 200
        data1 = res1.json()
        assert set(data1) == {"access_token", "token_type", "expires_in_minutes", "user"}
        assert "access_token" in data1
        assert data1["token_type"] == "bearer"
        assert data1["user"]["id"] == 101
        assert data1["user"]["role"] == "FARMER"
        assert "hashed_password" not in data1["user"]

        # Successful login via phone number
        res2 = client.post(
            "/api/auth/login",
            json={
                "username_or_email": "9876543211",
                "password": "FarmerSecret123",
            },
        )
        assert res2.status_code == 200
        assert "access_token" in res2.json()

        # Failed login: incorrect password (401)
        res3 = client.post(
            "/api/auth/login",
            json={
                "username_or_email": "suresh@example.com",
                "password": "WrongPassword999",
            },
        )
        assert res3.status_code == 401
        assert "Invalid email/phone or password" in res3.json()["detail"]
        assert res3.json() == {"detail": "Invalid email/phone or password."}
        assert res3.headers["www-authenticate"] == "Bearer"

        # Failed login: user not found (401)
        res4 = client.post(
            "/api/auth/login",
            json={
                "username_or_email": "unknown@example.com",
                "password": "SomePassword123",
            },
        )
        assert res4.status_code == 401

        # Suspended / Inactive user (403)
        user.is_active = False
        res5 = client.post(
            "/api/auth/login",
            json={
                "username_or_email": "suresh@example.com",
                "password": "FarmerSecret123",
            },
        )
        assert res5.status_code == 403
        assert "inactive or suspended" in res5.json()["detail"]

    finally:
        app.dependency_overrides.clear()


def test_oauth2_password_form_login_and_invalid_credentials():
    mock_repo = IsolatedMockUserRepository()
    user = MockUser(
        id=202,
        full_name="OAuth Test Buyer",
        email="oauth.buyer@example.com",
        phone_number="9876543212",
        role=UserRole.BUYER,
        hashed_password=get_password_hash("BuyerSecret123"),
    )
    mock_repo.users_by_id[user.id] = user
    mock_repo.users_by_email[user.email] = user
    mock_repo.users_by_phone[user.phone_number] = user
    app.dependency_overrides[get_user_repository] = lambda: mock_repo

    try:
        response = client.post(
            "/api/auth/token",
            data={"username": user.email, "password": "BuyerSecret123"},
        )
        assert response.status_code == 200
        assert set(response.json()) == {"access_token", "token_type"}
        assert response.json()["access_token"]
        assert response.json()["token_type"] == "bearer"

        me_response = client.get(
            "/api/auth/me",
            headers={"Authorization": f"Bearer {response.json()['access_token']}"},
        )
        assert me_response.status_code == 200
        assert me_response.json()["id"] == user.id
        assert me_response.json()["email"] == user.email

        invalid = client.post(
            "/api/auth/token",
            data={"username": user.email, "password": "IncorrectPassword123"},
        )
        assert invalid.status_code == 401
        assert invalid.json() == {"detail": "Invalid email/phone or password."}
        assert invalid.headers["www-authenticate"] == "Bearer"

        openapi = client.get("/api/openapi.json").json()
        password_flow = next(
            scheme["flows"]["password"]
            for scheme in openapi["components"]["securitySchemes"].values()
            if "password" in scheme.get("flows", {})
        )
        assert password_flow["tokenUrl"] == "/api/auth/token"
        me_security = openapi["paths"]["/api/auth/me"]["get"]["security"]
        assert {"OAuth2PasswordBearer": []} in me_security
    finally:
        app.dependency_overrides.clear()


# ==============================================================================
# 4. /api/auth/me Profile Authorization Tests
# ==============================================================================

def test_get_me_missing_token_returns_401():
    response = client.get("/api/auth/me")
    assert response.status_code == 401


def test_get_me_malformed_token_returns_401():
    response = client.get(
        "/api/auth/me",
        headers={"Authorization": "Bearer not-a-valid-jwt-token"},
    )
    assert response.status_code == 401


def test_get_me_successful_with_valid_jwt():
    mock_repo = IsolatedMockUserRepository()
    mock_user = MockUser(
        id=55,
        full_name="Agro Traders Pvt Ltd",
        email="agro@traders.com",
        phone_number="9822334455",
        role=UserRole.BUYER,
        hashed_password=get_password_hash("FarmerSecret123"),
    )
    mock_repo.users_by_id[mock_user.id] = mock_user
    app.dependency_overrides[get_user_repository] = lambda: mock_repo
    token = create_access_token(
        subject=55,
        role=UserRole.BUYER.value,
        extra_claims={
            "full_name": "Agro Traders Pvt Ltd",
            "email": "agro@traders.com",
            "phone": "9822334455",
        },
    )
    try:
        response = client.get(
            "/api/auth/me",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == 55
        assert data["role"] == "BUYER"
        assert data["full_name"] == "Agro Traders Pvt Ltd"
        assert data["email"] == "agro@traders.com"
    finally:
        app.dependency_overrides.clear()
