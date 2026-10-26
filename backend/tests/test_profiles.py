from datetime import datetime, timezone
from types import SimpleNamespace
from typing import Dict, List, Optional
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.schema import CreateTable
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool
import pytest
from app.core.security import UserRole, create_access_token
from app.database.base import Base
from app.database.connection import get_db
from app.main import app
from app.models.entities import BuyerProfile, FarmerProfile, User
from app.schemas.buyer import (
    BuyerBusinessType,
    BuyerProfileResponse,
    BuyerProfileUpdate,
    BuyerVerificationRequest,
    BuyerVerificationStatus,
)
from app.schemas.farmer import FarmerProfileResponse, FarmerProfileUpdate
from app.services.profile_service import (
    BuyerProfileCreationDataError,
    DefaultPostgresBuyerProfileRepository,
    get_buyer_profile_repo,
    get_farmer_profile_repo,
)

client = TestClient(app)


class IdentityOnlySession:
    def get(self, model, user_id):
        roles = {1: UserRole.ADMIN, 10: UserRole.FARMER, 20: UserRole.BUYER, 55: UserRole.BUYER}
        role = roles.get(user_id)
        return SimpleNamespace(id=user_id, role=role, is_active=True) if role else None


# Mock Farmer Profile Data Class
class MockFarmerProfile:
    def __init__(self, id: int, user_id: int, full_name: str, email: str, phone: str):
        self.id = id
        self.user_id = user_id
        self.full_name = full_name
        self.email = email
        self.phone_number = phone
        self.state = "Maharashtra"
        self.district = "Nashik"
        self.taluka = "Niphad"
        self.village = "Pimpalgaon"
        self.pincode = "422209"
        self.land_area_acres = 5.5
        self.preferred_language = "mr"
        self.latitude = 20.17
        self.longitude = 73.98
        self.created_at = datetime.now(timezone.utc)
        self.updated_at = datetime.now(timezone.utc)


# Mock Buyer Profile Data Class
class MockBuyerProfile:
    def __init__(self, id: int, user_id: int, full_name: str, email: str, phone: str):
        self.id = id
        self.user_id = user_id
        self.full_name = full_name
        self.email = email
        self.phone_number = phone
        self.business_name = "Nashik Agro Trading Corp"
        self.business_type = BuyerBusinessType.WHOLESALER
        self.license_number = "APMC-NSK-2026-99"
        self.state = "Maharashtra"
        self.district = "Nashik"
        self.market_address = "Lasalgaon Mandi Yard, Shop #14"
        self.verification_status = BuyerVerificationStatus.PENDING
        self.verification_notes = None
        self.rating = 4.8
        self.total_transactions = 12
        self.latitude = 20.14
        self.longitude = 74.22
        self.created_at = datetime.now(timezone.utc)
        self.updated_at = datetime.now(timezone.utc)


class IsolatedMockFarmerRepo:
    def __init__(self):
        self.profiles: Dict[int, MockFarmerProfile] = {}

    def get_by_user_id(self, db, user_id: int) -> Optional[MockFarmerProfile]:
        return self.profiles.get(user_id)

    def get_by_id(self, db, profile_id: int) -> Optional[MockFarmerProfile]:
        for p in self.profiles.values():
            if p.id == profile_id:
                return p
        return None

    def save_or_update(self, db, user_id: int, profile_in: FarmerProfileUpdate) -> MockFarmerProfile:
        p = self.profiles.get(user_id)
        if not p:
            p = MockFarmerProfile(
                id=1, user_id=user_id, full_name="Farmer Ramesh", email="ramesh@farm.in", phone="9876543210"
            )
            self.profiles[user_id] = p
        if profile_in.district is not None:
            p.district = profile_in.district
        if profile_in.state is not None:
            p.state = profile_in.state
        if profile_in.pincode is not None:
            p.pincode = profile_in.pincode
        if profile_in.land_area_acres is not None:
            p.land_area_acres = profile_in.land_area_acres
        return p

    def list_farmers(self, db, skip=0, limit=50, state=None, district=None) -> List[MockFarmerProfile]:
        res = list(self.profiles.values())
        if state:
            res = [r for r in res if r.state == state]
        if district:
            res = [r for r in res if r.district == district]
        return res[skip : skip + limit]


class IsolatedMockBuyerRepo:
    def __init__(self):
        self.profiles: Dict[int, MockBuyerProfile] = {}

    def get_by_user_id(self, db, user_id: int) -> Optional[MockBuyerProfile]:
        return self.profiles.get(user_id)

    def get_by_id(self, db, profile_id: int) -> Optional[MockBuyerProfile]:
        for p in self.profiles.values():
            if p.id == profile_id:
                return p
        return None


    def save_or_update(self, db, user_id: int, profile_in: BuyerProfileUpdate) -> MockBuyerProfile:
        p = self.profiles.get(user_id)
        if not p:
            p = MockBuyerProfile(
                id=1, user_id=user_id, full_name="Buyer Suresh", email="suresh@agro.in", phone="9876543211"
            )
            self.profiles[user_id] = p
        if profile_in.business_name is not None:
            p.business_name = profile_in.business_name
        if profile_in.license_number is not None:
            p.license_number = profile_in.license_number
        return p

    def submit_verification(self, db, user_id: int, req: BuyerVerificationRequest) -> MockBuyerProfile:
        p = self.profiles.get(user_id)
        if not p:
            p = MockBuyerProfile(
                id=1, user_id=user_id, full_name="Buyer Suresh", email="suresh@agro.in", phone="9876543211"
            )
            self.profiles[user_id] = p
        p.license_number = req.license_number
        p.business_name = req.business_name
        p.business_type = req.business_type
        p.market_address = req.market_address
        p.verification_status = BuyerVerificationStatus.PENDING
        p.verification_notes = req.verification_notes
        return p

    def list_buyers(self, db, status=None, skip=0, limit=50) -> List[MockBuyerProfile]:
        res = list(self.profiles.values())
        if status:
            res = [r for r in res if r.verification_status == status]
        return res[skip : skip + limit]

    def update_verification_status(self, db, profile_id: int, new_status: BuyerVerificationStatus, notes=None):
        for p in self.profiles.values():
            if p.id == profile_id:
                p.verification_status = new_status
                p.verification_notes = notes
                return p
        return None


class FakeProfileQueryResult:
    def __init__(self, row):
        self.row = row

    def one_or_none(self):
        return self.row


class FakeProfileReadSession:
    def __init__(self, row=None, error=None):
        self.row = row
        self.error = error
        self.commit_count = 0
        self.rollback_count = 0
        self.added = []
        self.users = {
            10: SimpleNamespace(
                id=10,
                full_name="Ramesh Patil",
                email="ramesh@farm.in",
                phone_number="9876543210",
            )
        }

    def execute(self, statement):
        if self.error is not None:
            raise self.error
        if self.row is not None:
            profile_user_id = self.row[0].user_id
            requested_ids = statement.compile().params.values()
            if profile_user_id not in requested_ids:
                return FakeProfileQueryResult(None)
        return FakeProfileQueryResult(self.row)

    def scalar(self, statement):
        requested_ids = statement.compile().params.values()
        return next((self.users[user_id] for user_id in requested_ids if user_id in self.users), None)

    def get(self, model, user_id):
        if model is User:
            roles = {1: UserRole.ADMIN, 20: UserRole.BUYER, 55: UserRole.BUYER}
            return SimpleNamespace(
                id=user_id, role=roles.get(user_id, UserRole.FARMER), is_active=True
            )
        return None

    def add(self, instance):
        instance.id = 97
        instance.created_at = datetime.now(timezone.utc)
        instance.updated_at = instance.created_at
        self.added.append(instance)

    def flush(self):
        return None

    def commit(self):
        self.commit_count += 1

    def rollback(self):
        self.rollback_count += 1

    def refresh(self, instance):
        return None


class FakeBuyerProfileSession(FakeProfileReadSession):
    def __init__(self, row=None):
        super().__init__(row=row)
        self.users[20] = SimpleNamespace(
            id=20, full_name="Suresh Buyer", email="buyer@example.in", phone_number="9876543211"
        )
        self.profile = row[0] if row else None

    def execute(self, statement):
        requested_user_id = next(iter(statement.compile().params.values()), None)
        if self.profile is None or self.profile.user_id != requested_user_id:
            return FakeProfileQueryResult(None)
        user = self.users[self.profile.user_id]
        return FakeProfileQueryResult((self.profile, user.full_name, user.email, user.phone_number))

    def add(self, instance):
        super().add(instance)
        if isinstance(instance, BuyerProfile):
            instance.verification_status = BuyerVerificationStatus.PENDING
            instance.rating = 5.0
            instance.total_transactions = 0
            self.profile = instance


def _profile_query_row(user_id: int = 10):
    profile = FarmerProfile(
        id=3,
        user_id=user_id,
        state="Maharashtra",
        district="Nashik",
        taluka="Niphad",
        village="Pimpalgaon",
        pincode="422209",
        land_area_acres=5.5,
        preferred_language="mr",
        latitude=20.17,
        longitude=73.98,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    return profile, "Ramesh Patil", "ramesh@farm.in", "9876543210"


# ==============================================================================
# Farmer Profile Tests
# ==============================================================================

def test_farmer_profile_unauthorized_without_token():
    res = client.get("/api/farmer/profile")
    assert res.status_code == 401


def test_farmer_profile_forbidden_for_buyer():
    app.dependency_overrides.clear()
    app.dependency_overrides[get_db] = lambda: FakeProfileReadSession()
    buyer_token = create_access_token(subject=20, role=UserRole.BUYER.value)
    try:
        res = client.get(
            "/api/farmer/profile",
            headers={"Authorization": f"Bearer {buyer_token}"},
        )
        assert res.status_code == 403
        assert "Access forbidden" in res.json()["detail"]
    finally:
        app.dependency_overrides.clear()


def test_farmer_profile_default_repository_returns_404_when_missing():
    farmer_token = create_access_token(subject=10, role=UserRole.FARMER.value)
    app.dependency_overrides.clear()
    app.dependency_overrides[get_db] = lambda: FakeProfileReadSession()
    try:
        res = client.get(
            "/api/farmer/profile",
            headers={"Authorization": f"Bearer {farmer_token}"},
        )
        assert res.status_code == 404
        assert res.json()["detail"] == "Farmer profile not found. Please initialize your profile."
    finally:
        app.dependency_overrides.clear()


def test_farmer_profile_default_repository_returns_authenticated_users_profile():
    farmer_token = create_access_token(subject=10, role=UserRole.FARMER.value)
    app.dependency_overrides.clear()
    app.dependency_overrides[get_db] = lambda: FakeProfileReadSession(_profile_query_row(10))
    try:
        res = client.get(
            "/api/farmer/profile",
            headers={"Authorization": f"Bearer {farmer_token}"},
        )
        assert res.status_code == 200
        data = res.json()
        assert data["user_id"] == 10
        assert data["full_name"] == "Ramesh Patil"
        assert data["email"] == "ramesh@farm.in"
        assert data["phone_number"] == "9876543210"
        assert data["district"] == "Nashik"
    finally:
        app.dependency_overrides.clear()


def test_farmer_profile_database_error_is_not_reported_as_pending_schema():
    farmer_token = create_access_token(subject=10, role=UserRole.FARMER.value)
    database_error = OperationalError("SELECT", {}, RuntimeError("database unavailable"))
    app.dependency_overrides.clear()
    app.dependency_overrides[get_db] = lambda: FakeProfileReadSession(error=database_error)
    error_client = TestClient(app, raise_server_exceptions=False)
    try:
        res = error_client.get(
            "/api/farmer/profile",
            headers={"Authorization": f"Bearer {farmer_token}"},
        )
        assert res.status_code == 500
        assert res.text == "Internal Server Error"
    finally:
        app.dependency_overrides.clear()


def test_farmer_profile_update_uses_default_repository_and_commits_own_profile():
    farmer_token = create_access_token(subject=10, role=UserRole.FARMER.value)
    row = _profile_query_row(10)
    db_session = FakeProfileReadSession(row)
    app.dependency_overrides.clear()
    app.dependency_overrides[get_db] = lambda: db_session
    try:
        response = client.put(
            "/api/farmer/profile",
            headers={"Authorization": f"Bearer {farmer_token}"},
            json={"district": "Pune", "pincode": "411001"},
        )
        assert response.status_code == 200
        assert response.json()["district"] == "Pune"
        assert response.json()["pincode"] == "411001"
        assert row[0].district == "Pune"
        assert row[0].pincode == "411001"
        assert db_session.commit_count == 1
        assert db_session.rollback_count == 0
    finally:
        app.dependency_overrides.clear()


def test_farmer_profile_put_creates_profile_for_authenticated_user():
    farmer_token = create_access_token(subject=10, role=UserRole.FARMER.value)
    db_session = FakeProfileReadSession()
    app.dependency_overrides.clear()
    app.dependency_overrides[get_db] = lambda: db_session
    try:
        response = client.put(
            "/api/farmer/profile",
            headers={"Authorization": f"Bearer {farmer_token}"},
            json={
                "state": "Maharashtra",
                "district": "Nashik",
                "pincode": "422209",
                "user_id": 11,
            },
        )
        assert response.status_code == 200
        assert response.json()["user_id"] == 10
        assert response.json()["state"] == "Maharashtra"
        assert response.json()["district"] == "Nashik"
        assert response.json()["pincode"] == "422209"
        assert len(db_session.added) == 1
        assert db_session.added[0].user_id == 10
        assert db_session.commit_count == 1
    finally:
        app.dependency_overrides.clear()


def test_farmer_profile_put_requires_creation_fields_when_profile_missing():
    farmer_token = create_access_token(subject=10, role=UserRole.FARMER.value)
    db_session = FakeProfileReadSession()
    app.dependency_overrides.clear()
    app.dependency_overrides[get_db] = lambda: db_session
    try:
        response = client.put(
            "/api/farmer/profile",
            headers={"Authorization": f"Bearer {farmer_token}"},
            json={"district": "Nashik"},
        )
        assert response.status_code == 422
        assert "state, district, and a six-digit pincode" in response.json()["detail"]
        assert db_session.added == []
        assert db_session.commit_count == 0
        assert db_session.rollback_count == 1
    finally:
        app.dependency_overrides.clear()


def test_farmer_profile_put_rejects_invalid_creation_pincode():
    farmer_token = create_access_token(subject=10, role=UserRole.FARMER.value)
    db_session = FakeProfileReadSession()
    app.dependency_overrides.clear()
    app.dependency_overrides[get_db] = lambda: db_session
    try:
        response = client.put(
            "/api/farmer/profile",
            headers={"Authorization": f"Bearer {farmer_token}"},
            json={"state": "Maharashtra", "district": "Nashik", "pincode": "123"},
        )
        assert response.status_code == 422
        assert db_session.added == []
        assert db_session.commit_count == 0
    finally:
        app.dependency_overrides.clear()


def test_farmer_profile_put_without_creation_fields_does_not_create_partial_profile():
    farmer_token = create_access_token(subject=10, role=UserRole.FARMER.value)
    db_session = FakeProfileReadSession()
    app.dependency_overrides.clear()
    app.dependency_overrides[get_db] = lambda: db_session
    try:
        response = client.put(
            "/api/farmer/profile",
            headers={"Authorization": f"Bearer {farmer_token}"},
            json={"district": "Pune"},
        )
        assert response.status_code == 422
        assert "required to create" in response.json()["detail"]
        assert db_session.added == []
        assert db_session.commit_count == 0
    finally:
        app.dependency_overrides.clear()


def test_farmer_profile_update_cannot_modify_another_users_profile():
    farmer_token = create_access_token(subject=10, role=UserRole.FARMER.value)
    row = _profile_query_row(11)
    db_session = FakeProfileReadSession(row)
    original_district = row[0].district
    app.dependency_overrides.clear()
    app.dependency_overrides[get_db] = lambda: db_session
    try:
        response = client.put(
            "/api/farmer/profile",
            headers={"Authorization": f"Bearer {farmer_token}"},
            json={"state": "Maharashtra", "district": "Pune", "pincode": "411001"},
        )
        assert response.status_code == 200
        assert response.json()["user_id"] == 10
        assert row[0].district == original_district
        assert len(db_session.added) == 1
        assert db_session.added[0].user_id == 10
        assert db_session.commit_count == 1
    finally:
        app.dependency_overrides.clear()


def test_farmer_profile_update_database_error_returns_generic_500():
    farmer_token = create_access_token(subject=10, role=UserRole.FARMER.value)
    database_error = OperationalError("UPDATE", {}, RuntimeError("database unavailable"))
    db_session = FakeProfileReadSession(error=database_error)
    app.dependency_overrides.clear()
    app.dependency_overrides[get_db] = lambda: db_session
    error_client = TestClient(app, raise_server_exceptions=False)
    try:
        response = error_client.put(
            "/api/farmer/profile",
            headers={"Authorization": f"Bearer {farmer_token}"},
            json={"district": "Pune"},
        )
        assert response.status_code == 500
        assert response.text == "Internal Server Error"
        assert db_session.rollback_count == 1
    finally:
        app.dependency_overrides.clear()


def test_farmer_profile_get_and_update_with_repo():
    mock_repo = IsolatedMockFarmerRepo()
    farmer = MockFarmerProfile(id=1, user_id=10, full_name="Ramesh Patil", email="ramesh@farm.in", phone="9876543210")
    mock_repo.profiles[10] = farmer
    app.dependency_overrides[get_farmer_profile_repo] = lambda: mock_repo
    app.dependency_overrides[get_db] = lambda: FakeProfileReadSession()

    farmer_token = create_access_token(subject=10, role=UserRole.FARMER.value)

    try:
        # GET profile
        get_res = client.get(
            "/api/farmer/profile",
            headers={"Authorization": f"Bearer {farmer_token}"},
        )
        assert get_res.status_code == 200
        data = get_res.json()
        assert data["user_id"] == 10
        assert data["district"] == "Nashik"

        # PUT profile with invalid pincode
        inv_res = client.put(
            "/api/farmer/profile",
            headers={"Authorization": f"Bearer {farmer_token}"},
            json={"pincode": "123"},
        )
        assert inv_res.status_code == 422

        # PUT profile with valid update
        upd_res = client.put(
            "/api/farmer/profile",
            headers={"Authorization": f"Bearer {farmer_token}"},
            json={"district": "Pune", "pincode": "411001", "land_area_acres": 8.0},
        )
        assert upd_res.status_code == 200
        upd_data = upd_res.json()
        assert upd_data["district"] == "Pune"
        assert upd_data["pincode"] == "411001"
        assert upd_data["land_area_acres"] == 8.0

    finally:
        app.dependency_overrides.clear()


# ==============================================================================
# Buyer Profile & Verification Tests
# ==============================================================================

def test_buyer_profile_forbidden_without_token():
    app.dependency_overrides.clear()
    assert client.put("/api/buyer/profile", json={}).status_code == 401


def test_default_buyer_repository_creates_retrieves_updates_without_duplicates():
    db = FakeBuyerProfileSession()
    repo = DefaultPostgresBuyerProfileRepository()
    create = BuyerProfileUpdate.model_validate({
        "business_name": "Nashik Agro Traders", "state": "Maharashtra",
        "district": "Nashik", "market_address": "Lasalgaon market, shop 14",
    })
    created = repo.save_or_update(db, 20, create)
    assert created["user_id"] == 20
    assert created["business_name"] == "Nashik Agro Traders"
    assert len(db.added) == 1
    assert repo.get_by_user_id(db, 20)["id"] == created["id"]
    updated = repo.save_or_update(db, 20, BuyerProfileUpdate(business_name="Nashik Premium Traders"))
    assert updated["business_name"] == "Nashik Premium Traders"
    assert len(db.added) == 1
    assert db.commit_count == 2


def test_buyer_profile_creation_requires_all_database_fields_and_rolls_back():
    db = FakeBuyerProfileSession()
    with pytest.raises(BuyerProfileCreationDataError):
        DefaultPostgresBuyerProfileRepository().save_or_update(db, 20, BuyerProfileUpdate(district="Nashik"))
    assert db.added == []
    assert db.commit_count == 0
    assert db.rollback_count == 1


def test_buyer_profile_put_creates_with_default_repository_and_gets_profile():
    db = FakeBuyerProfileSession()
    app.dependency_overrides.clear()
    app.dependency_overrides[get_db] = lambda: db
    token = create_access_token(subject=20, role=UserRole.BUYER.value)
    try:
        missing = client.get("/api/buyer/profile", headers={"Authorization": f"Bearer {token}"})
        assert missing.status_code == 404
        response = client.put("/api/buyer/profile", headers={"Authorization": f"Bearer {token}"}, json={
            "business_name": "Suresh Agro", "state": "Maharashtra", "district": "Nashik",
            "market_address": "Lasalgaon market, shop 14",
        })
        assert response.status_code == 200
        assert response.json()["business_name"] == "Suresh Agro"
        fetched = client.get("/api/buyer/profile", headers={"Authorization": f"Bearer {token}"})
        assert fetched.status_code == 200
        assert fetched.json()["user_id"] == 20
        assert len(db.added) == 1
    finally:
        app.dependency_overrides.clear()


def test_buyer_profile_put_rejects_invalid_input_without_writing():
    db = FakeBuyerProfileSession()
    app.dependency_overrides.clear()
    app.dependency_overrides[get_db] = lambda: db
    token = create_access_token(subject=20, role=UserRole.BUYER.value)
    try:
        invalid = client.put("/api/buyer/profile", headers={"Authorization": f"Bearer {token}"}, json={
            "business_name": "A", "state": "Maharashtra", "district": "Nashik",
            "market_address": "Lasalgaon market",
        })
        assert invalid.status_code == 422
        missing = client.put("/api/buyer/profile", headers={"Authorization": f"Bearer {token}"}, json={"district": "Nashik"})
        assert missing.status_code == 422
        assert db.added == []
        assert db.commit_count == 0
    finally:
        app.dependency_overrides.clear()


def test_buyer_profile_put_is_forbidden_for_farmer():
    app.dependency_overrides.clear()
    app.dependency_overrides[get_db] = lambda: FakeProfileReadSession()
    farmer_token = create_access_token(subject=10, role=UserRole.FARMER.value)
    try:
        response = client.put("/api/buyer/profile", headers={"Authorization": f"Bearer {farmer_token}"}, json={})
        assert response.status_code == 403
    finally:
        app.dependency_overrides.clear()


def test_buyer_profile_forbidden_for_farmer():
    app.dependency_overrides.clear()
    app.dependency_overrides[get_db] = lambda: FakeProfileReadSession()
    farmer_token = create_access_token(subject=10, role=UserRole.FARMER.value)
    try:
        res = client.get(
            "/api/buyer/profile",
            headers={"Authorization": f"Bearer {farmer_token}"},
        )
        assert res.status_code == 403
    finally:
        app.dependency_overrides.clear()


def test_buyer_profile_and_verification_flow():
    mock_repo = IsolatedMockBuyerRepo()
    buyer = MockBuyerProfile(id=1, user_id=20, full_name="Suresh Agro", email="suresh@agro.in", phone="9876543211")
    mock_repo.profiles[20] = buyer
    app.dependency_overrides[get_buyer_profile_repo] = lambda: mock_repo
    app.dependency_overrides[get_db] = lambda: FakeProfileReadSession()

    buyer_token = create_access_token(subject=20, role=UserRole.BUYER.value)

    try:
        # GET profile
        get_res = client.get(
            "/api/buyer/profile",
            headers={"Authorization": f"Bearer {buyer_token}"},
        )
        assert get_res.status_code == 200
        assert get_res.json()["business_name"] == "Nashik Agro Trading Corp"

        # PUT update
        upd_res = client.put(
            "/api/buyer/profile",
            headers={"Authorization": f"Bearer {buyer_token}"},
            json={"business_name": "Nashik Premium Agro Export Ltd"},
        )
        assert upd_res.status_code == 200
        assert upd_res.json()["business_name"] == "Nashik Premium Agro Export Ltd"

        # POST verification request
        ver_res = client.post(
            "/api/buyer/verification",
            headers={"Authorization": f"Bearer {buyer_token}"},
            json={
                "license_number": "APMC-MAH-2026-4444",
                "business_name": "Nashik Premium Agro Export Ltd",
                "business_type": "EXPORTER",
                "market_address": "APMC Gate 2, Lasalgaon Yard",
                "verification_notes": "Submitted GSTIN and APMC wholesale license",
            },
        )
        assert ver_res.status_code == 200
        ver_data = ver_res.json()
        assert ver_data["verification_status"] == "PENDING"
        assert ver_data["license_number"] == "APMC-MAH-2026-4444"

    finally:
        app.dependency_overrides.clear()


# ==============================================================================
# Admin Profile Management Tests
# ==============================================================================

def test_admin_endpoints_forbidden_for_non_admins():
    app.dependency_overrides.clear()
    app.dependency_overrides[get_db] = lambda: FakeProfileReadSession()
    farmer_token = create_access_token(subject=10, role=UserRole.FARMER.value)
    buyer_token = create_access_token(subject=20, role=UserRole.BUYER.value)

    try:
        # Farmer accessing admin endpoints
        res1 = client.get("/api/admin/farmers", headers={"Authorization": f"Bearer {farmer_token}"})
        assert res1.status_code == 403

        res2 = client.get("/api/admin/buyers", headers={"Authorization": f"Bearer {farmer_token}"})
        assert res2.status_code == 403

    # Buyer accessing admin endpoints
        res3 = client.get("/api/admin/farmers", headers={"Authorization": f"Bearer {buyer_token}"})
        assert res3.status_code == 403

        res4 = client.put("/api/admin/buyers/1/approve", headers={"Authorization": f"Bearer {buyer_token}"})
        assert res4.status_code == 403
    finally:
        app.dependency_overrides.clear()


def test_admin_buyer_approval_rejection_suspension():
    mock_buyer_repo = IsolatedMockBuyerRepo()
    buyer = MockBuyerProfile(id=5, user_id=50, full_name="Trade Link Ltd", email="tradelink@agro.in", phone="9811223344")
    buyer.verification_status = BuyerVerificationStatus.PENDING
    mock_buyer_repo.profiles[50] = buyer
    app.dependency_overrides[get_buyer_profile_repo] = lambda: mock_buyer_repo

    mock_farmer_repo = IsolatedMockFarmerRepo()
    farmer = MockFarmerProfile(id=1, user_id=10, full_name="Ramesh Patil", email="ramesh@farm.in", phone="9876543210")
    mock_farmer_repo.profiles[10] = farmer
    app.dependency_overrides[get_farmer_profile_repo] = lambda: mock_farmer_repo
    app.dependency_overrides[get_db] = lambda: FakeProfileReadSession()

    admin_token = create_access_token(subject=1, role=UserRole.ADMIN.value)

    try:
        # Admin lists farmers
        f_res = client.get("/api/admin/farmers", headers={"Authorization": f"Bearer {admin_token}"})
        assert f_res.status_code == 200
        assert len(f_res.json()) == 1

        # Admin lists buyers
        b_res = client.get("/api/admin/buyers", headers={"Authorization": f"Bearer {admin_token}"})
        assert b_res.status_code == 200
        assert len(b_res.json()) == 1

        # Admin lists pending buyers
        p_res = client.get("/api/admin/buyers/pending", headers={"Authorization": f"Bearer {admin_token}"})
        assert p_res.status_code == 200
        assert len(p_res.json()) == 1
        assert p_res.json()[0]["verification_status"] == "PENDING"

        # Admin approves buyer -> VERIFIED
        app_res = client.put(
            "/api/admin/buyers/5/approve",
            headers={"Authorization": f"Bearer {admin_token}"},
            json={"notes": "All APMC documents verified and verified valid."},
        )
        assert app_res.status_code == 200
        assert app_res.json()["verification_status"] == "VERIFIED"

        # Admin rejects buyer -> REJECTED
        rej_res = client.put(
            "/api/admin/buyers/5/reject",
            headers={"Authorization": f"Bearer {admin_token}"},
            json={"notes": "Invalid GSTIN number."},
        )
        assert rej_res.status_code == 200
        assert rej_res.json()["verification_status"] == "REJECTED"

        # Admin suspends buyer -> SUSPENDED
        sus_res = client.put(
            "/api/admin/buyers/5/suspend",
            headers={"Authorization": f"Bearer {admin_token}"},
            json={"notes": "Suspended due to repeated payment dispute complaints."},
        )
        assert sus_res.status_code == 200
        assert sus_res.json()["verification_status"] == "SUSPENDED"

    finally:
        app.dependency_overrides.clear()


@pytest.fixture
def isolated_profile_database():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    # The production farmer pincode check uses PostgreSQL's regex operator. Keep
    # its six-character invariant in this SQLite-only schema with portable SQL.
    with engine.begin() as connection:
        for table in (User.__table__, FarmerProfile.__table__, BuyerProfile.__table__):
            ddl = str(CreateTable(table).compile(dialect=engine.dialect))
            ddl = ddl.replace("pincode ~ '^[0-9]{6}$'", "length(pincode) = 6")
            connection.exec_driver_sql(ddl)
    db = Session(engine, expire_on_commit=False)
    db.add_all([
        User(id=1, email="admin-profile@test.invalid", phone_number="9000000101", hashed_password="x", full_name="Admin", role=UserRole.ADMIN),
        User(id=10, email="farmer-profile@test.invalid", phone_number="9000000110", hashed_password="x", full_name="Ramesh Patil", role=UserRole.FARMER),
        User(id=20, email="buyer-profile@test.invalid", phone_number="9000000120", hashed_password="x", full_name="Suresh Buyer", role=UserRole.BUYER),
        User(id=21, email="buyer-no-profile@test.invalid", phone_number="9000000121", hashed_password="x", full_name="New Buyer", role=UserRole.BUYER),
    ])
    db.add_all([
        FarmerProfile(id=301, user_id=10, state="Maharashtra", district="Nashik", pincode="422209"),
        BuyerProfile(id=501, user_id=20, business_name="Suresh Agro", state="Maharashtra", district="Nashik", market_address="Lasalgaon market address", verification_status=BuyerVerificationStatus.PENDING),
    ])
    db.commit()
    app.dependency_overrides.clear()
    app.dependency_overrides[get_db] = lambda: db
    try:
        yield db
    finally:
        app.dependency_overrides.clear()
        db.close()
        engine.dispose()


def test_admin_farmer_list_detail_filters_404_and_admin_guard(isolated_profile_database):
    admin_headers = {"Authorization": f"Bearer {create_access_token(1, UserRole.ADMIN.value)}"}
    listed = client.get("/api/admin/farmers?district=Nashik", headers=admin_headers)
    assert listed.status_code == 200
    assert len(listed.json()) == 1
    assert listed.json()[0]["id"] == 301
    assert listed.json()[0]["full_name"] == "Ramesh Patil"

    detail = client.get("/api/admin/farmers/301", headers=admin_headers)
    assert detail.status_code == 200
    assert detail.json()["user_id"] == 10
    assert client.get("/api/admin/farmers/999", headers=admin_headers).status_code == 404
    farmer_headers = {"Authorization": f"Bearer {create_access_token(10, UserRole.FARMER.value)}"}
    assert client.get("/api/admin/farmers", headers=farmer_headers).status_code == 403
    assert client.get("/api/admin/farmers/301", headers=farmer_headers).status_code == 403


def test_buyer_verification_submission_and_admin_decisions(isolated_profile_database):
    buyer_headers = {"Authorization": f"Bearer {create_access_token(20, UserRole.BUYER.value)}"}
    payload = {
        "license_number": "APMC-NSK-501",
        "business_name": "Suresh Agro Wholesale",
        "business_type": "WHOLESALER",
        "market_address": "Lasalgaon APMC, shop 5",
        "documents_url": "doc-ref-501",
        "verification_notes": "License documents submitted",
    }
    submitted = client.post("/api/buyer/verification", headers=buyer_headers, json=payload)
    assert submitted.status_code == 200
    assert submitted.json()["verification_status"] == "PENDING"
    assert isolated_profile_database.get(BuyerProfile, 501).documents_url == "doc-ref-501"
    assert isolated_profile_database.get(BuyerProfile, 501).business_name == "Suresh Agro Wholesale"

    admin_headers = {"Authorization": f"Bearer {create_access_token(1, UserRole.ADMIN.value)}"}
    assert client.get("/api/admin/buyers?status=PENDING", headers=admin_headers).json()[0]["id"] == 501
    assert client.get("/api/admin/buyers/pending", headers=admin_headers).status_code == 200
    approved = client.put("/api/admin/buyers/501/approve", headers=admin_headers, json={"notes": "Verified"})
    assert approved.status_code == 200
    assert approved.json()["verification_status"] == "VERIFIED"
    rejected = client.put("/api/admin/buyers/501/reject", headers=admin_headers, json={"notes": "Resubmission required"})
    assert rejected.status_code == 200
    assert rejected.json()["verification_status"] == "REJECTED"
    suspended = client.put("/api/admin/buyers/501/suspend", headers=admin_headers, json={"notes": "Compliance hold"})
    assert suspended.status_code == 200
    assert suspended.json()["verification_status"] == "SUSPENDED"
    assert suspended.json()["verification_notes"] == "Compliance hold"
    assert isolated_profile_database.get(User, 20).is_active is False
    assert client.get("/api/buyer/profile", headers=buyer_headers).status_code == 401

    reapproved = client.put("/api/admin/buyers/501/approve", headers=admin_headers, json={"notes": "Hold cleared"})
    assert reapproved.status_code == 200
    assert isolated_profile_database.get(User, 20).is_active is True
    assert client.get("/api/buyer/profile", headers=buyer_headers).status_code == 200

    no_profile_headers = {"Authorization": f"Bearer {create_access_token(21, UserRole.BUYER.value)}"}
    missing = client.post("/api/buyer/verification", headers=no_profile_headers, json=payload)
    assert missing.status_code == 404


@pytest.mark.parametrize(
    ("method", "path", "user_id", "role", "payload", "expected_detail"),
    [
        ("GET", "/api/admin/farmers", 1, UserRole.ADMIN, None, "Unable to retrieve farmer profiles."),
        ("GET", "/api/admin/farmers/301", 1, UserRole.ADMIN, None, "Unable to retrieve farmer profile."),
        ("GET", "/api/admin/buyers", 1, UserRole.ADMIN, None, "Unable to retrieve buyer profiles."),
        ("PUT", "/api/admin/buyers/501/approve", 1, UserRole.ADMIN, None, "Unable to update buyer verification status."),
        ("POST", "/api/buyer/verification", 20, UserRole.BUYER, {
            "license_number": "APMC-NSK-501", "business_name": "Suresh Agro",
            "market_address": "Lasalgaon APMC shop",
        }, "Unable to submit buyer verification."),
    ],
)
def test_profile_workflow_database_errors_are_generic(
    method, path, user_id, role, payload, expected_detail
):
    class FailingSession:
        def __init__(self):
            self.rollback_count = 0

        def get(self, model, requested_id):
            roles = {1: UserRole.ADMIN, 20: UserRole.BUYER}
            return SimpleNamespace(id=requested_id, role=roles[requested_id], is_active=True)

        def execute(self, statement):
            raise OperationalError("SELECT", {}, RuntimeError("private profile database detail"))

        def rollback(self):
            self.rollback_count += 1

    db = FailingSession()
    app.dependency_overrides.clear()
    app.dependency_overrides[get_db] = lambda: db
    token = create_access_token(user_id, role.value)
    try:
        response = client.request(
            method,
            path,
            headers={"Authorization": f"Bearer {token}"},
            json=payload,
        )
        assert response.status_code == 500
        assert response.json() == {"detail": expected_detail}
        assert "private profile database detail" not in response.text
        assert db.rollback_count >= 1
    finally:
        app.dependency_overrides.clear()
