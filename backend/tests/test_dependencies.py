from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient
import pytest
from sqlalchemy import create_engine
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool
from app.core.dependencies import (
    AuthenticatedUser,
    get_current_user_claims,
    require_admin,
    require_buyer,
    require_farmer,
)
from app.core.security import UserRole, create_access_token
from app.database.base import Base
from app.database.connection import get_db
from app.models.entities import User

# Dummy app specifically to test security dependencies and RBAC
demo_app = FastAPI()


@demo_app.get("/demo/user")
def demo_user_endpoint(user: AuthenticatedUser = Depends(get_current_user_claims)):
    return {"user_id": user.id, "role": user.role}


@demo_app.get("/demo/farmer-only")
def demo_farmer_endpoint(user: AuthenticatedUser = Depends(require_farmer)):
    return {"status": "success", "user_id": user.id}


@demo_app.get("/demo/buyer-only")
def demo_buyer_endpoint(user: AuthenticatedUser = Depends(require_buyer)):
    return {"status": "success", "user_id": user.id}


@demo_app.get("/demo/admin-only")
def demo_admin_endpoint(user: AuthenticatedUser = Depends(require_admin)):
    return {"status": "success", "user_id": user.id}


client = TestClient(demo_app)


@pytest.fixture(autouse=True)
def isolated_auth_database():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine, tables=[User.__table__])
    db = Session(engine, expire_on_commit=False)
    db.add_all([
        User(id=1, email="admin@test.invalid", phone_number="9000000001", hashed_password="x", full_name="Admin", role=UserRole.ADMIN),
        User(id=10, email="farmer@test.invalid", phone_number="9000000010", hashed_password="x", full_name="Farmer", role=UserRole.FARMER),
        User(id=15, email="farmer15@test.invalid", phone_number="9000000015", hashed_password="x", full_name="Farmer 15", role=UserRole.FARMER),
        User(id=20, email="buyer@test.invalid", phone_number="9000000020", hashed_password="x", full_name="Buyer", role=UserRole.BUYER),
        User(id=25, email="buyer25@test.invalid", phone_number="9000000025", hashed_password="x", full_name="Buyer 25", role=UserRole.BUYER),
    ])
    db.commit()
    demo_app.dependency_overrides[get_db] = lambda: db
    try:
        yield db
    finally:
        demo_app.dependency_overrides.clear()
        db.close()
        engine.dispose()


def test_missing_token_returns_401():
    response = client.get("/demo/user")
    assert response.status_code == 401


def test_invalid_token_returns_401():
    response = client.get(
        "/demo/user", headers={"Authorization": "Bearer invalid.jwt.token"}
    )
    assert response.status_code == 401


def test_authenticated_user_access():
    token = create_access_token(subject=10, role=UserRole.FARMER.value)
    response = client.get(
        "/demo/user", headers={"Authorization": f"Bearer {token}"}
    )
    assert response.status_code == 200
    assert response.json() == {"user_id": 10, "role": "FARMER"}


def test_farmer_role_authorization():
    farmer_token = create_access_token(subject=10, role=UserRole.FARMER.value)
    buyer_token = create_access_token(subject=20, role=UserRole.BUYER.value)

    # Farmer accessing farmer endpoint -> 200 OK
    res1 = client.get(
        "/demo/farmer-only", headers={"Authorization": f"Bearer {farmer_token}"}
    )
    assert res1.status_code == 200
    assert res1.json()["user_id"] == 10

    # Buyer attempting to access farmer endpoint -> 403 Forbidden
    res2 = client.get(
        "/demo/farmer-only", headers={"Authorization": f"Bearer {buyer_token}"}
    )
    assert res2.status_code == 403
    assert "Access forbidden" in res2.json()["detail"]


def test_buyer_role_authorization():
    buyer_token = create_access_token(subject=25, role=UserRole.BUYER.value)
    farmer_token = create_access_token(subject=15, role=UserRole.FARMER.value)

    # Buyer accessing buyer endpoint -> 200 OK
    res1 = client.get(
        "/demo/buyer-only", headers={"Authorization": f"Bearer {buyer_token}"}
    )
    assert res1.status_code == 200
    assert res1.json()["user_id"] == 25

    # Farmer attempting to access buyer endpoint -> 403 Forbidden
    res2 = client.get(
        "/demo/buyer-only", headers={"Authorization": f"Bearer {farmer_token}"}
    )
    assert res2.status_code == 403


def test_admin_role_authorization():
    admin_token = create_access_token(subject=1, role=UserRole.ADMIN.value)
    farmer_token = create_access_token(subject=10, role=UserRole.FARMER.value)

    # Admin accessing admin endpoint -> 200 OK
    res1 = client.get(
        "/demo/admin-only", headers={"Authorization": f"Bearer {admin_token}"}
    )
    assert res1.status_code == 200
    assert res1.json()["user_id"] == 1

    # Farmer attempting to access admin endpoint -> 403 Forbidden
    res2 = client.get(
        "/demo/admin-only", headers={"Authorization": f"Bearer {farmer_token}"}
    )
    assert res2.status_code == 403


def test_database_role_and_active_status_invalidate_stale_tokens(isolated_auth_database):
    farmer_token = create_access_token(subject=10, role=UserRole.FARMER.value)
    assert client.get("/demo/farmer-only", headers={"Authorization": f"Bearer {farmer_token}"}).status_code == 200

    farmer = isolated_auth_database.get(User, 10)
    farmer.role = UserRole.BUYER
    isolated_auth_database.commit()
    stale_role = client.get("/demo/farmer-only", headers={"Authorization": f"Bearer {farmer_token}"})
    assert stale_role.status_code == 401

    buyer_token = create_access_token(subject=20, role=UserRole.BUYER.value)
    buyer = isolated_auth_database.get(User, 20)
    buyer.is_active = False
    isolated_auth_database.commit()
    inactive = client.get("/demo/buyer-only", headers={"Authorization": f"Bearer {buyer_token}"})
    assert inactive.status_code == 401


def test_authentication_database_failure_fails_closed_without_details():
    class FailingSession:
        def __init__(self):
            self.rollback_count = 0

        def get(self, model, user_id):
            raise OperationalError("SELECT", {}, RuntimeError("private database detail"))

        def rollback(self):
            self.rollback_count += 1

    session = FailingSession()
    demo_app.dependency_overrides.clear()
    demo_app.dependency_overrides[get_db] = lambda: session
    token = create_access_token(subject=10, role=UserRole.FARMER.value)
    try:
        response = client.get("/demo/user", headers={"Authorization": f"Bearer {token}"})
        assert response.status_code == 503
        assert response.json() == {"detail": "Authentication service temporarily unavailable."}
        assert "private database detail" not in response.text
        assert session.rollback_count == 1
    finally:
        demo_app.dependency_overrides.clear()
