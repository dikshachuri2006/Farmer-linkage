from datetime import date, datetime, timezone
from decimal import Decimal
from fastapi.testclient import TestClient
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.core.security import UserRole, create_access_token
from app.database.base import Base
from app.database.connection import get_db
from app.main import app
from app.models.entities import Crop, FarmerLot, User
from app.schemas.crop import CropCategory
from app.schemas.farmer_lot import LotQualityGrade, LotStatus

client = TestClient(app)


def _token_headers(user_id: int, role: UserRole):
    token = create_access_token(subject=user_id, role=role.value)
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def marketplace_test_db():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(
        engine,
        tables=[User.__table__, Crop.__table__, FarmerLot.__table__],
    )
    db = Session(engine, expire_on_commit=False)

    # Seed Users
    users = [
        User(
            id=10,
            email="ramesh.farmer@example.test",
            phone_number="9876543210",
            hashed_password="hashed_pw_ramesh",
            full_name="Ramesh Patil",
            role=UserRole.FARMER,
            is_active=True,
        ),
        User(
            id=20,
            email="suresh.farmer@example.test",
            phone_number="9876543220",
            hashed_password="hashed_pw_suresh",
            full_name="Suresh Deshmukh",
            role=UserRole.FARMER,
            is_active=True,
        ),
        User(
            id=30,
            email="vijay.buyer@example.test",
            phone_number="9876543230",
            hashed_password="hashed_pw_vijay",
            full_name="Vijay Traders",
            role=UserRole.BUYER,
            is_active=True,
        ),
        User(
            id=1,
            email="admin@example.test",
            phone_number="9876543201",
            hashed_password="hashed_pw_admin",
            full_name="Admin Officer",
            role=UserRole.ADMIN,
            is_active=True,
        ),
    ]
    db.add_all(users)

    # Seed Crops
    crops = [
        Crop(id=1, name="Onion", category=CropCategory.VEGETABLE, standard_unit="quintal"),
        Crop(id=2, name="Wheat", category=CropCategory.CEREAL, standard_unit="quintal"),
        Crop(id=3, name="Soybean", category=CropCategory.OILSEED, standard_unit="quintal"),
    ]
    db.add_all(crops)

    # Seed Farmer Lots: 4 AVAILABLE, 1 COMMITTED, 1 SOLD, 1 WITHDRAWN
    lots = [
        # Available lots
        FarmerLot(
            id=101,
            farmer_id=10,
            crop_id=1,
            quantity=Decimal("100.000"),
            unit="quintal",
            quality_grade=LotQualityGrade.GRADE_A,
            expected_price_per_unit=Decimal("2500.00"),
            price_unit="INR/quintal",
            harvest_date=date(2026, 10, 15),
            location_state="Maharashtra",
            location_district="Nashik",
            location_pincode="422001",
            status=LotStatus.AVAILABLE,
        ),
        FarmerLot(
            id=102,
            farmer_id=10,
            crop_id=2,
            quantity=Decimal("50.000"),
            unit="quintal",
            quality_grade=LotQualityGrade.GRADE_B,
            expected_price_per_unit=Decimal("3200.00"),
            price_unit="INR/quintal",
            harvest_date=date(2026, 10, 10),
            location_state="Maharashtra",
            location_district="Pune",
            location_pincode="411001",
            status=LotStatus.AVAILABLE,
        ),
        FarmerLot(
            id=103,
            farmer_id=20,
            crop_id=1,
            quantity=Decimal("200.000"),
            unit="quintal",
            quality_grade=LotQualityGrade.FAIR_AVERAGE,
            expected_price_per_unit=Decimal("1800.00"),
            price_unit="INR/quintal",
            harvest_date=date(2026, 10, 18),
            location_state="Madhya Pradesh",
            location_district="Indore",
            location_pincode="452001",
            status=LotStatus.AVAILABLE,
        ),
        FarmerLot(
            id=104,
            farmer_id=20,
            crop_id=3,
            quantity=Decimal("80.000"),
            unit="quintal",
            quality_grade=LotQualityGrade.GRADE_A,
            expected_price_per_unit=Decimal("4500.00"),
            price_unit="INR/quintal",
            harvest_date=date(2026, 10, 20),
            location_state="Maharashtra",
            location_district="Nagpur",
            location_pincode="440001",
            status=LotStatus.AVAILABLE,
        ),
        # Unavailable lots that MUST be excluded from marketplace listings
        FarmerLot(
            id=105,
            farmer_id=10,
            crop_id=1,
            quantity=Decimal("30.000"),
            unit="quintal",
            quality_grade=LotQualityGrade.GRADE_A,
            expected_price_per_unit=Decimal("2400.00"),
            price_unit="INR/quintal",
            harvest_date=date(2026, 10, 12),
            location_state="Maharashtra",
            location_district="Nashik",
            location_pincode="422001",
            status=LotStatus.COMMITTED,
        ),
        FarmerLot(
            id=106,
            farmer_id=20,
            crop_id=2,
            quantity=Decimal("40.000"),
            unit="quintal",
            quality_grade=LotQualityGrade.GRADE_B,
            expected_price_per_unit=Decimal("3100.00"),
            price_unit="INR/quintal",
            harvest_date=date(2026, 10, 14),
            location_state="Maharashtra",
            location_district="Pune",
            location_pincode="411001",
            status=LotStatus.SOLD,
        ),
        FarmerLot(
            id=107,
            farmer_id=10,
            crop_id=3,
            quantity=Decimal("60.000"),
            unit="quintal",
            quality_grade=LotQualityGrade.GRADE_C,
            expected_price_per_unit=Decimal("4000.00"),
            price_unit="INR/quintal",
            harvest_date=date(2026, 10, 16),
            location_state="Maharashtra",
            location_district="Nagpur",
            location_pincode="440001",
            status=LotStatus.WITHDRAWN,
        ),
    ]
    db.add_all(lots)
    db.commit()

    app.dependency_overrides[get_db] = lambda: db
    try:
        yield db
    finally:
        app.dependency_overrides.clear()
        db.close()
        engine.dispose()


# ==============================================================================
# 1. A Buyer can browse available listings
# ==============================================================================
def test_buyer_can_browse_available_listings(marketplace_test_db):
    headers = _token_headers(user_id=30, role=UserRole.BUYER)
    response = client.get("/api/marketplace/lots", headers=headers)
    assert response.status_code == 200
    data = response.json()

    assert data["total"] == 4
    assert len(data["items"]) == 4
    assert data["skip"] == 0
    assert data["limit"] == 50

    returned_ids = [item["id"] for item in data["items"]]
    assert set(returned_ids) == {101, 102, 103, 104}

    # Verify lot detail structure
    first_lot = next(item for item in data["items"] if item["id"] == 101)
    assert first_lot["crop_name"] == "Onion"
    assert first_lot["farmer_name"] == "Ramesh Patil"
    assert first_lot["quantity"] == 100.0
    assert first_lot["unit"] == "quintal"
    assert first_lot["quality_grade"] == "GRADE_A"
    assert first_lot["expected_price_per_unit"] == 2500.0
    assert first_lot["price_unit"] == "INR/quintal"
    assert first_lot["location_state"] == "Maharashtra"
    assert first_lot["location_district"] == "Nashik"
    assert first_lot["status"] == "AVAILABLE"


# ==============================================================================
# 2. Unavailable lots (COMMITTED, SOLD, WITHDRAWN) are excluded
# ==============================================================================
def test_unavailable_lots_excluded(marketplace_test_db):
    headers = _token_headers(user_id=30, role=UserRole.BUYER)
    response = client.get("/api/marketplace/lots", headers=headers)
    assert response.status_code == 200
    data = response.json()

    lot_ids = [item["id"] for item in data["items"]]
    assert 105 not in lot_ids  # COMMITTED must be excluded
    assert 106 not in lot_ids  # SOLD must be excluded
    assert 107 not in lot_ids  # WITHDRAWN must be excluded

    # All returned lots must strictly be AVAILABLE
    for item in data["items"]:
        assert item["status"] == "AVAILABLE"


# ==============================================================================
# 3. Filtering by crop, location, grade, and price works where supported
# ==============================================================================
def test_filtering_by_crop_id(marketplace_test_db):
    headers = _token_headers(user_id=30, role=UserRole.BUYER)

    # Filter by Crop 1 (Onion) -> Lots 101 and 103
    res1 = client.get("/api/marketplace/lots?crop_id=1", headers=headers)
    assert res1.status_code == 200
    data1 = res1.json()
    assert data1["total"] == 2
    assert set(item["id"] for item in data1["items"]) == {101, 103}
    assert all(item["crop_id"] == 1 for item in data1["items"])

    # Filter by Crop 3 (Soybean) -> Lot 104
    res3 = client.get("/api/marketplace/lots?crop_id=3", headers=headers)
    assert res3.status_code == 200
    data3 = res3.json()
    assert data3["total"] == 1
    assert data3["items"][0]["id"] == 104


def test_filtering_by_location_state_and_district(marketplace_test_db):
    headers = _token_headers(user_id=30, role=UserRole.BUYER)

    # Filter by state = Maharashtra (case-insensitive) -> Lots 101, 102, 104
    res_state = client.get("/api/marketplace/lots?state=maharashtra", headers=headers)
    assert res_state.status_code == 200
    data_state = res_state.json()
    assert data_state["total"] == 3
    assert set(item["id"] for item in data_state["items"]) == {101, 102, 104}

    # Filter by state = Madhya Pradesh -> Lot 103
    res_mp = client.get("/api/marketplace/lots?state=Madhya Pradesh", headers=headers)
    assert res_mp.status_code == 200
    data_mp = res_mp.json()
    assert data_mp["total"] == 1
    assert data_mp["items"][0]["id"] == 103

    # Filter by district = Pune (case-insensitive) -> Lot 102
    res_dist = client.get("/api/marketplace/lots?district=pune", headers=headers)
    assert res_dist.status_code == 200
    data_dist = res_dist.json()
    assert data_dist["total"] == 1
    assert data_dist["items"][0]["id"] == 102


def test_filtering_by_grade(marketplace_test_db):
    headers = _token_headers(user_id=30, role=UserRole.BUYER)

    # Filter by grade = GRADE_A -> Lots 101 and 104
    res_a = client.get("/api/marketplace/lots?grade=GRADE_A", headers=headers)
    assert res_a.status_code == 200
    data_a = res_a.json()
    assert data_a["total"] == 2
    assert set(item["id"] for item in data_a["items"]) == {101, 104}

    # Filter by grade = FAIR_AVERAGE -> Lot 103
    res_faq = client.get("/api/marketplace/lots?grade=FAIR_AVERAGE", headers=headers)
    assert res_faq.status_code == 200
    data_faq = res_faq.json()
    assert data_faq["total"] == 1
    assert data_faq["items"][0]["id"] == 103


def test_filtering_by_price_range(marketplace_test_db):
    headers = _token_headers(user_id=30, role=UserRole.BUYER)

    # min_price = 3000 -> Lots 102 (3200) and 104 (4500)
    res_min = client.get("/api/marketplace/lots?min_price=3000", headers=headers)
    assert res_min.status_code == 200
    data_min = res_min.json()
    assert data_min["total"] == 2
    assert set(item["id"] for item in data_min["items"]) == {102, 104}

    # max_price = 2600 -> Lots 101 (2500) and 103 (1800)
    res_max = client.get("/api/marketplace/lots?max_price=2600", headers=headers)
    assert res_max.status_code == 200
    data_max = res_max.json()
    assert data_max["total"] == 2
    assert set(item["id"] for item in data_max["items"]) == {101, 103}

    # Range: 2000 to 3500 -> Lots 101 (2500) and 102 (3200)
    res_range = client.get("/api/marketplace/lots?min_price=2000&max_price=3500", headers=headers)
    assert res_range.status_code == 200
    data_range = res_range.json()
    assert data_range["total"] == 2
    assert set(item["id"] for item in data_range["items"]) == {101, 102}


# ==============================================================================
# 4. Pagination works correctly
# ==============================================================================
def test_pagination_works_correctly(marketplace_test_db):
    headers = _token_headers(user_id=30, role=UserRole.BUYER)

    # First page: skip=0, limit=2
    res_p1 = client.get("/api/marketplace/lots?skip=0&limit=2", headers=headers)
    assert res_p1.status_code == 200
    data_p1 = res_p1.json()
    assert data_p1["total"] == 4
    assert len(data_p1["items"]) == 2
    assert data_p1["skip"] == 0
    assert data_p1["limit"] == 2

    # Second page: skip=2, limit=2
    res_p2 = client.get("/api/marketplace/lots?skip=2&limit=2", headers=headers)
    assert res_p2.status_code == 200
    data_p2 = res_p2.json()
    assert data_p2["total"] == 4
    assert len(data_p2["items"]) == 2
    assert data_p2["skip"] == 2
    assert data_p2["limit"] == 2

    # Page 1 and Page 2 items must be disjoint
    ids_p1 = {item["id"] for item in data_p1["items"]}
    ids_p2 = {item["id"] for item in data_p2["items"]}
    assert ids_p1.isdisjoint(ids_p2)
    assert ids_p1 | ids_p2 == {101, 102, 103, 104}

    # Out of range: skip=10, limit=10
    res_empty = client.get("/api/marketplace/lots?skip=10&limit=10", headers=headers)
    assert res_empty.status_code == 200
    data_empty = res_empty.json()
    assert data_empty["total"] == 4
    assert data_empty["items"] == []


# ==============================================================================
# 5. Unauthenticated requests follow the project's authentication rules
# ==============================================================================
def test_unauthenticated_requests_rejected(marketplace_test_db):
    # No Authorization header
    res_no_auth = client.get("/api/marketplace/lots")
    assert res_no_auth.status_code == 401

    # Invalid / malformed bearer token
    res_bad_token = client.get(
        "/api/marketplace/lots",
        headers={"Authorization": "Bearer invalid.token.payload"},
    )
    assert res_bad_token.status_code == 401


# ==============================================================================
# 6. Invalid query parameters return appropriate errors
# ==============================================================================
def test_invalid_query_parameters(marketplace_test_db):
    headers = _token_headers(user_id=30, role=UserRole.BUYER)

    # min_price > max_price -> 400 Bad Request
    res_inverted = client.get(
        "/api/marketplace/lots?min_price=3000&max_price=2000", headers=headers
    )
    assert res_inverted.status_code == 400
    assert "min_price cannot be greater than max_price" in res_inverted.json()["detail"]

    # Negative min_price -> 422 Unprocessable Entity
    res_neg_price = client.get("/api/marketplace/lots?min_price=-5", headers=headers)
    assert res_neg_price.status_code == 422

    # Invalid crop_id (<= 0) -> 422 Unprocessable Entity
    res_invalid_crop = client.get("/api/marketplace/lots?crop_id=0", headers=headers)
    assert res_invalid_crop.status_code == 422

    # Invalid quality grade -> 422 Unprocessable Entity
    res_invalid_grade = client.get("/api/marketplace/lots?grade=SUPER_EXTRA", headers=headers)
    assert res_invalid_grade.status_code == 422

    # Invalid limit (0 or > 100) -> 422 Unprocessable Entity
    res_zero_limit = client.get("/api/marketplace/lots?limit=0", headers=headers)
    assert res_zero_limit.status_code == 422

    res_excess_limit = client.get("/api/marketplace/lots?limit=101", headers=headers)
    assert res_excess_limit.status_code == 422


# ==============================================================================
# 7. One farmer cannot see another farmer's private information through the response
# ==============================================================================
def test_farmer_cannot_see_another_farmer_private_information(marketplace_test_db):
    # Farmer 10 authenticates and browses marketplace listings
    headers = _token_headers(user_id=10, role=UserRole.FARMER)
    response = client.get("/api/marketplace/lots", headers=headers)
    assert response.status_code == 200
    data = response.json()

    assert data["total"] == 4

    # Private fields that must NEVER appear in the response items
    forbidden_private_fields = {
        "email",
        "phone_number",
        "phone",
        "hashed_password",
        "location_pincode",
        "pincode",
        "land_area_acres",
        "village",
        "taluka",
        "latitude",
        "longitude",
    }

    for item in data["items"]:
        # Verify no item dictionary contains forbidden private fields
        for field in forbidden_private_fields:
            assert field not in item, f"Private field '{field}' leaked in marketplace response"

        # Allowed public fields
        assert "id" in item
        assert "crop_id" in item
        assert "crop_name" in item
        assert "quantity" in item
        assert "unit" in item
        assert "quality_grade" in item
        assert "expected_price_per_unit" in item
        assert "price_unit" in item
        assert "location_state" in item
        assert "location_district" in item
        assert "status" in item
