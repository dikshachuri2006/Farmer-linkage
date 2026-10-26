from datetime import date, datetime, timezone, timedelta
from io import StringIO
from typing import List, Optional, Tuple
from fastapi.testclient import TestClient
import pytest
from pydantic import ValidationError
from sqlalchemy import create_engine, event, select, func
from sqlalchemy.exc import OperationalError, SQLAlchemyError
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool
from app.database.base import Base
from app.database.connection import get_db
from app.core.security import UserRole, create_access_token
from app.main import app
from app.models.entities import Crop, Market, MarketPrice, User
from app.schemas.crop import CropCategory, CropResponse
from app.schemas.market import MarketResponse
from app.schemas.price import PriceRecordResponse
from app.services.price_service import (
    get_crop_repo,
    get_market_repo,
    get_price_repo,
)
from app.services.price_importer import PriceImportError, import_market_prices_csv
from app.ml.price_forecast import InsufficientPriceHistory, forecast_modal_price

client = TestClient(app)


@pytest.fixture
def isolated_crop_database():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine, tables=[Crop.__table__, User.__table__])

    # SQLite does not generate values for the model's PostgreSQL BigInteger Identity.
    # Emulate only that database-generated value in this isolated test database.
    @event.listens_for(Crop, "before_insert")
    def assign_sqlite_test_identity(mapper, connection, target):
        if target.id is None:
            target.id = connection.scalar(select(func.coalesce(func.max(Crop.id), 0) + 1))

    db = Session(engine, expire_on_commit=False)
    db.add_all([
        User(id=1, email="admin@test.invalid", phone_number="9000000001", hashed_password="x", full_name="Admin", role=UserRole.ADMIN),
        User(id=2, email="farmer@test.invalid", phone_number="9000000002", hashed_password="x", full_name="Farmer", role=UserRole.FARMER),
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
        event.remove(Crop, "before_insert", assign_sqlite_test_identity)


@pytest.fixture
def isolated_market_database():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine, tables=[Market.__table__])
    db = Session(engine, expire_on_commit=False)
    app.dependency_overrides.clear()
    app.dependency_overrides[get_db] = lambda: db
    try:
        yield db
    finally:
        app.dependency_overrides.clear()
        db.close()
        engine.dispose()


@pytest.fixture
def isolated_price_database():
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(engine, tables=[Crop.__table__, Market.__table__, MarketPrice.__table__])

    @event.listens_for(MarketPrice, "before_insert")
    def assign_sqlite_test_identity(mapper, connection, target):
        if target.id is None:
            target.id = connection.scalar(select(func.coalesce(func.max(MarketPrice.id), 0) + 1))

    db = Session(engine, expire_on_commit=False)
    db.add_all([
        Crop(id=1, name="Onion", category=CropCategory.VEGETABLE, standard_unit="quintal"),
        Crop(id=2, name="Wheat", category=CropCategory.CEREAL, standard_unit="quintal"),
        Market(id=10, name="Lasalgaon", state="Maharashtra", district="Nashik"),
        Market(id=11, name="Niphad", state="Maharashtra", district="Nashik"),
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
        event.remove(MarketPrice, "before_insert", assign_sqlite_test_identity)


def _seed_crop_catalog(db):
    db.add_all(
        [
            Crop(id=1, name="Onion", category=CropCategory.VEGETABLE, standard_unit="kg", description="Red Onion"),
            Crop(id=2, name="Wheat", category=CropCategory.CEREAL, standard_unit="quintal", description="Lokwan"),
            Crop(id=3, name="Tomato", category=CropCategory.VEGETABLE, standard_unit="kg", description="Hybrid"),
            Crop(id=4, name="Soybean", category=CropCategory.OILSEED, standard_unit="quintal", description="Yellow"),
        ]
    )
    db.commit()


def _auth_headers(role: UserRole = UserRole.ADMIN):
    user_id = 1 if role == UserRole.ADMIN else 2
    token = create_access_token(subject=user_id, role=role.value)
    return {"Authorization": f"Bearer {token}"}


# ==============================================================================
# Isolated Synthetic Fixtures and Mock Repositories (Unit Tests Only)
# Note: These are synthetic test fixtures and NOT actual dataset records from Diya.
# ==============================================================================

class SyntheticMockCropRepo:
    def __init__(self):
        self.crops = [
            CropResponse(id=1, name="Onion", category=CropCategory.VEGETABLE, standard_unit="kg", description="Red Onion, Grade A"),
            CropResponse(id=2, name="Wheat", category=CropCategory.CEREAL, standard_unit="quintal", description="Lokwan Wheat"),
            CropResponse(id=3, name="Tomato", category=CropCategory.VEGETABLE, standard_unit="kg", description="Hybrid Tomato"),
            CropResponse(id=4, name="Soybean", category=CropCategory.OILSEED, standard_unit="quintal", description="Yellow Soybean"),
        ]

    def get_by_id(self, db, crop_id: int) -> Optional[CropResponse]:
        for c in self.crops:
            if c.id == crop_id:
                return c
        return None

    def list_crops(
        self, db, search: Optional[str] = None, category: Optional[CropCategory] = None, skip: int = 0, limit: int = 50
    ) -> Tuple[List[CropResponse], int]:
        res = list(self.crops)
        if search:
            res = [c for c in res if search.lower() in c.name.lower()]
        if category:
            res = [c for c in res if c.category == category]
        return res[skip : skip + limit], len(res)


class SyntheticMockMarketRepo:
    def __init__(self):
        self.markets = [
            MarketResponse(id=10, name="Lasalgaon APMC", state="Maharashtra", district="Nashik", market_code="MH-NSK-01", latitude=20.14, longitude=74.22),
            MarketResponse(id=11, name="Pimpalgaon APMC", state="Maharashtra", district="Nashik", market_code="MH-NSK-02", latitude=20.17, longitude=73.98),
            MarketResponse(id=12, name="Pune APMC (Gultekdi)", state="Maharashtra", district="Pune", market_code="MH-PUN-01", latitude=18.49, longitude=73.86),
        ]

    def get_by_id(self, db, market_id: int) -> Optional[MarketResponse]:
        for m in self.markets:
            if m.id == market_id:
                return m
        return None

    def list_markets(
        self, db, search: Optional[str] = None, state: Optional[str] = None, district: Optional[str] = None, skip: int = 0, limit: int = 50
    ) -> Tuple[List[MarketResponse], int]:
        res = list(self.markets)
        if search:
            res = [m for m in res if search.lower() in m.name.lower()]
        if state:
            res = [m for m in res if state.lower() in m.state.lower()]
        if district:
            res = [m for m in res if district.lower() in m.district.lower()]
        return res[skip : skip + limit], len(res)


class SyntheticMockPriceRepo:
    def __init__(self):
        self.prices = [
            PriceRecordResponse(
                id=101,
                crop_id=1,
                crop_name="Onion",
                market_id=10,
                market_name="Lasalgaon APMC",
                state="Maharashtra",
                district="Nashik",
                price_date=date(2026, 10, 15),
                min_price=2200.0,
                max_price=3100.0,
                modal_price=2850.0,
                arrival_quantity=1450.0,
                price_unit="INR/Quintal",
                arrival_unit="Tonnes",
                source="Synthetic Test Fixture (Diya Dataset Pending)",
            ),
            PriceRecordResponse(
                id=102,
                crop_id=1,
                crop_name="Onion",
                market_id=10,
                market_name="Lasalgaon APMC",
                state="Maharashtra",
                district="Nashik",
                price_date=date(2026, 10, 14),
                min_price=2150.0,
                max_price=3050.0,
                modal_price=2800.0,
                arrival_quantity=1320.0,
                price_unit="INR/Quintal",
                arrival_unit="Tonnes",
                source="Synthetic Test Fixture (Diya Dataset Pending)",
            ),
            PriceRecordResponse(
                id=103,
                crop_id=2,
                crop_name="Wheat",
                market_id=12,
                market_name="Pune APMC",
                state="Maharashtra",
                district="Pune",
                price_date=date(2026, 10, 15),
                min_price=2400.0,
                max_price=2800.0,
                modal_price=2650.0,
                arrival_quantity=850.0,
                price_unit="INR/Quintal",
                arrival_unit="Tonnes",
                source="Synthetic Test Fixture (Diya Dataset Pending)",
            ),
        ]

    def get_by_id(self, db, price_id: int) -> Optional[PriceRecordResponse]:
        for p in self.prices:
            if p.id == price_id:
                return p
        return None

    def list_prices(
        self, db, crop_id=None, market_id=None, start_date=None, end_date=None,
        variety=None, grade=None, sort_by="price_date", sort_order="desc", skip=0, limit=50
    ) -> Tuple[List[PriceRecordResponse], int]:
        res = list(self.prices)
        if crop_id:
            res = [p for p in res if p.crop_id == crop_id]
        if market_id:
            res = [p for p in res if p.market_id == market_id]
        if start_date:
            res = [p for p in res if p.price_date >= start_date]
        if end_date:
            res = [p for p in res if p.price_date <= end_date]
        if variety is not None:
            res = [p for p in res if p.variety == variety]
        if grade is not None:
            res = [p for p in res if p.grade == grade]

        reverse = (sort_order.lower() == "desc")
        res.sort(key=lambda x: getattr(x, sort_by, x.price_date), reverse=reverse)
        return res[skip : skip + limit], len(res)

    def get_latest_price(self, db, crop_id: int, market_id: Optional[int] = None, variety=None, grade=None) -> Optional[PriceRecordResponse]:
        matches = [p for p in self.prices if p.crop_id == crop_id]
        if market_id:
            matches = [p for p in matches if p.market_id == market_id]
        if variety is not None:
            matches = [p for p in matches if p.variety == variety]
        if grade is not None:
            matches = [p for p in matches if p.grade == grade]
        if not matches:
            return None
        matches.sort(key=lambda x: x.price_date, reverse=True)
        return matches[0]


# ==============================================================================
# Crop Tests
# ==============================================================================

def test_create_crop_as_admin_persists_and_returns_crop(isolated_crop_database):
    response = client.post(
        "/api/crops",
        headers=_auth_headers(),
        json={
            "name": "Millet",
            "category": "CEREAL",
            "standard_unit": "quintal",
            "description": "Pearl millet",
        },
    )

    assert response.status_code == 201
    data = response.json()
    assert data["id"] > 0
    assert data["name"] == "Millet"
    assert data["category"] == "CEREAL"
    assert data["standard_unit"] == "quintal"
    assert data["description"] == "Pearl millet"
    assert data["created_at"] is not None
    persisted = isolated_crop_database.get(Crop, data["id"])
    assert persisted is not None
    assert persisted.name == "Millet"


def test_create_crop_requires_admin_authentication(isolated_crop_database):
    payload = {"name": "Millet"}
    assert client.post("/api/crops", json=payload).status_code == 401
    assert client.post(
        "/api/crops", headers=_auth_headers(UserRole.FARMER), json=payload
    ).status_code == 403


@pytest.mark.parametrize(
    "payload",
    [
        {"name": "   "},
        {"name": "x" * 101},
        {"name": "Millet", "category": "UNKNOWN"},
        {"name": "Millet", "standard_unit": " "},
        {"name": "Millet", "standard_unit": "u" * 21},
        {"name": "Millet", "id": 45},
    ],
)
def test_create_crop_rejects_invalid_input(isolated_crop_database, payload):
    response = client.post("/api/crops", headers=_auth_headers(), json=payload)
    assert response.status_code == 422


def test_create_crop_duplicate_name_returns_conflict(isolated_crop_database):
    _seed_crop_catalog(isolated_crop_database)
    response = client.post(
        "/api/crops", headers=_auth_headers(), json={"name": "Onion"}
    )
    assert response.status_code == 409
    assert response.json()["detail"] == "A crop with this name already exists."


def test_create_crop_database_error_rolls_back_and_hides_details():
    class FailingCropSession:
        def __init__(self):
            self.rollback_count = 0

        def scalar(self, statement):
            raise OperationalError("SELECT", {}, RuntimeError("database unavailable"))

        def get(self, model, user_id):
            if model is User:
                return type("TestUser", (), {"role": UserRole.ADMIN, "is_active": True})()
            return None

        def rollback(self):
            self.rollback_count += 1

    db_session = FailingCropSession()
    app.dependency_overrides.clear()
    app.dependency_overrides[get_db] = lambda: db_session
    error_client = TestClient(app, raise_server_exceptions=False)
    try:
        response = error_client.post(
            "/api/crops", headers=_auth_headers(), json={"name": "Millet"}
        )
        assert response.status_code == 500
        assert response.json()["detail"] == "Unable to create crop."
        assert "database unavailable" not in response.text
        assert db_session.rollback_count >= 1
    finally:
        app.dependency_overrides.clear()

def test_list_crops_default_repository_returns_empty_catalog(isolated_crop_database):
    res = client.get("/api/crops")
    assert res.status_code == 200
    assert res.json() == {"total": 0, "items": [], "skip": 0, "limit": 50}


def test_list_crops_default_repository_returns_database_rows(isolated_crop_database):
    _seed_crop_catalog(isolated_crop_database)
    res = client.get("/api/crops")
    assert res.status_code == 200
    data = res.json()
    assert data["total"] == 4
    assert [crop["id"] for crop in data["items"]] == [1, 2, 3, 4]
    assert data["items"][0]["name"] == "Onion"
    assert data["items"][0]["category"] == "VEGETABLE"


def test_list_crops_default_repository_search_and_category_filters(isolated_crop_database):
    _seed_crop_catalog(isolated_crop_database)
    search_response = client.get("/api/crops?search=oni")
    assert search_response.status_code == 200
    assert search_response.json()["total"] == 1
    assert [crop["name"] for crop in search_response.json()["items"]] == ["Onion"]

    category_response = client.get("/api/crops?category=VEGETABLE")
    assert category_response.status_code == 200
    assert category_response.json()["total"] == 2
    assert [crop["name"] for crop in category_response.json()["items"]] == ["Onion", "Tomato"]


def test_list_crops_default_repository_preserves_pagination(isolated_crop_database):
    _seed_crop_catalog(isolated_crop_database)
    res = client.get("/api/crops?skip=1&limit=2")
    assert res.status_code == 200
    assert res.json()["total"] == 4
    assert [crop["id"] for crop in res.json()["items"]] == [2, 3]
    assert res.json()["skip"] == 1
    assert res.json()["limit"] == 2


def test_list_crops_database_error_returns_generic_500_and_rolls_back():
    class FailingCropSession:
        def __init__(self):
            self.rollback_count = 0

        def scalar(self, statement):
            raise OperationalError("SELECT", {}, RuntimeError("database unavailable"))

        def rollback(self):
            self.rollback_count += 1

    db_session = FailingCropSession()
    app.dependency_overrides.clear()
    app.dependency_overrides[get_db] = lambda: db_session
    error_client = TestClient(app, raise_server_exceptions=False)
    try:
        res = error_client.get("/api/crops")
        assert res.status_code == 500
        assert res.text == "Internal Server Error"
        assert db_session.rollback_count == 1
    finally:
        app.dependency_overrides.clear()


def test_list_crops_with_mock_repo():
    mock_crop_repo = SyntheticMockCropRepo()
    app.dependency_overrides[get_crop_repo] = lambda: mock_crop_repo

    try:
        res = client.get("/api/crops")
        assert res.status_code == 200
        data = res.json()
        assert data["total"] == 4
        assert len(data["items"]) == 4
        assert data["items"][0]["name"] == "Onion"
        assert data["items"][0]["category"] == "VEGETABLE"
    finally:
        app.dependency_overrides.clear()


def test_list_crops_search_and_category_filter():
    mock_crop_repo = SyntheticMockCropRepo()
    app.dependency_overrides[get_crop_repo] = lambda: mock_crop_repo

    try:
        # Search by substring
        res = client.get("/api/crops?search=oni")
        assert res.status_code == 200
        assert res.json()["total"] == 1
        assert res.json()["items"][0]["name"] == "Onion"

        # Filter by category
        cat_res = client.get("/api/crops?category=CEREAL")
        assert cat_res.status_code == 200
        assert cat_res.json()["total"] == 1
        assert cat_res.json()["items"][0]["name"] == "Wheat"
    finally:
        app.dependency_overrides.clear()


def test_get_crop_by_id_success_and_not_found():
    mock_crop_repo = SyntheticMockCropRepo()
    app.dependency_overrides[get_crop_repo] = lambda: mock_crop_repo

    try:
        # Success
        res1 = client.get("/api/crops/1")
        assert res1.status_code == 200
        assert res1.json()["name"] == "Onion"

        # Not Found (404)
        res2 = client.get("/api/crops/999")
        assert res2.status_code == 404
        assert "not found" in res2.json()["detail"]

        # Invalid ID parameter (422)
        res3 = client.get("/api/crops/0")
        assert res3.status_code == 422
    finally:
        app.dependency_overrides.clear()


def test_list_crops_invalid_pagination():
    res = client.get("/api/crops?skip=-1")
    assert res.status_code == 422

    res2 = client.get("/api/crops?limit=0")
    assert res2.status_code == 422


# ==============================================================================
# Market Tests
# ==============================================================================

def test_list_markets_default_repository_returns_empty_catalog(isolated_market_database):
    app.dependency_overrides.clear()
    app.dependency_overrides[get_db] = lambda: isolated_market_database
    res = client.get("/api/markets")
    assert res.status_code == 200
    assert res.json() == {"total": 0, "items": [], "skip": 0, "limit": 50}
    app.dependency_overrides.clear()


def test_list_markets_default_repository_filters_and_paginates(isolated_market_database):
    isolated_market_database.add_all(
        [
            Market(id=10, name="Lasalgaon APMC", state="Maharashtra", district="Nashik", market_code="MH-NSK-01"),
            Market(id=11, name="Pimpalgaon APMC", state="Maharashtra", district="Nashik", market_code="MH-NSK-02"),
            Market(id=12, name="Pune APMC", state="Maharashtra", district="Pune", market_code="MH-PUN-01"),
        ]
    )
    isolated_market_database.commit()

    response = client.get("/api/markets?search=lasal&state=Maharashtra&district=Nashik")
    assert response.status_code == 200
    assert response.json()["total"] == 1
    assert response.json()["items"][0]["name"] == "Lasalgaon APMC"

    page = client.get("/api/markets?skip=1&limit=1")
    assert page.status_code == 200
    assert page.json()["total"] == 3
    assert page.json()["items"][0]["id"] == 11


def test_get_market_by_id_default_repository_returns_record_and_404(isolated_market_database):
    isolated_market_database.add(
        Market(id=10, name="Lasalgaon APMC", state="Maharashtra", district="Nashik", market_code="MH-NSK-01")
    )
    isolated_market_database.commit()

    found = client.get("/api/markets/10")
    assert found.status_code == 200
    assert found.json()["market_code"] == "MH-NSK-01"
    assert client.get("/api/markets/999").status_code == 404


def test_get_crop_by_id_default_repository_returns_record_and_404(isolated_crop_database):
    _seed_crop_catalog(isolated_crop_database)
    found = client.get("/api/crops/1")
    assert found.status_code == 200
    assert found.json()["name"] == "Onion"
    assert client.get("/api/crops/999").status_code == 404


@pytest.mark.parametrize(
    "path,expected_detail",
    [
        ("/api/markets", "Unable to retrieve markets."),
        ("/api/markets/1", "Unable to retrieve market."),
        ("/api/crops/1", "Unable to retrieve crop."),
    ],
)
def test_catalog_read_database_errors_return_generic_500(path, expected_detail):
    class FailingReadSession:
        def __init__(self):
            self.rollback_count = 0

        def scalar(self, statement):
            raise OperationalError("SELECT", {}, RuntimeError("database secret detail"))

        def get(self, model, record_id):
            raise OperationalError("SELECT", {}, RuntimeError("database secret detail"))

        def rollback(self):
            self.rollback_count += 1

    db_session = FailingReadSession()
    app.dependency_overrides.clear()
    app.dependency_overrides[get_db] = lambda: db_session
    error_client = TestClient(app, raise_server_exceptions=False)
    try:
        response = error_client.get(path)
        assert response.status_code == 500
        assert response.json() == {"detail": expected_detail}
        assert "database secret detail" not in response.text
        assert db_session.rollback_count >= 1
    finally:
        app.dependency_overrides.clear()


def test_list_markets_with_mock_repo():
    mock_market_repo = SyntheticMockMarketRepo()
    app.dependency_overrides[get_market_repo] = lambda: mock_market_repo

    try:
        res = client.get("/api/markets")
        assert res.status_code == 200
        data = res.json()
        assert data["total"] == 3
        assert data["items"][0]["name"] == "Lasalgaon APMC"

        # Filter by state and district
        filt_res = client.get("/api/markets?state=Maharashtra&district=Nashik")
        assert filt_res.status_code == 200
        assert filt_res.json()["total"] == 2
    finally:
        app.dependency_overrides.clear()


def test_get_market_by_id_success_and_not_found():
    mock_market_repo = SyntheticMockMarketRepo()
    app.dependency_overrides[get_market_repo] = lambda: mock_market_repo

    try:
        # Success
        res1 = client.get("/api/markets/10")
        assert res1.status_code == 200
        assert res1.json()["name"] == "Lasalgaon APMC"
        assert res1.json()["latitude"] == 20.14

        # Not Found (404)
        res2 = client.get("/api/markets/999")
        assert res2.status_code == 404

        # Invalid ID parameter (422)
        res3 = client.get("/api/markets/abc")
        assert res3.status_code == 422
    finally:
        app.dependency_overrides.clear()


# ==============================================================================
# Market Price Tests
# ==============================================================================

def test_database_price_reads_and_empty_list(isolated_price_database):
    db = isolated_price_database
    empty = client.get("/api/market-prices")
    assert empty.status_code == 200
    assert empty.json() == {"total": 0, "items": [], "skip": 0, "limit": 50}

    db.add_all([
        MarketPrice(id=1, crop_id=1, market_id=10, price_date=date(2026, 1, 1), min_price=10, max_price=20, modal_price=15, price_unit="INR/Quintal", source="test"),
        MarketPrice(id=2, crop_id=1, market_id=10, price_date=date(2026, 1, 2), min_price=11, max_price=21, modal_price=16, price_unit="INR/Quintal", source="test"),
    ])
    db.commit()
    page = client.get("/api/market-prices?skip=1&limit=1&sort_by=price_date&sort_order=asc")
    assert page.status_code == 200
    assert page.json()["total"] == 2
    assert [item["id"] for item in page.json()["items"]] == [2]
    assert page.json()["items"][0]["crop_name"] == "Onion"
    latest = client.get("/api/market-prices/latest?crop_id=1&market_id=10")
    assert latest.status_code == 200
    assert latest.json()["id"] == 2
    assert client.get("/api/market-prices/1").json()["market_name"] == "Lasalgaon"
    assert client.get("/api/market-prices/999").status_code == 404


def test_market_price_database_errors_are_generic(isolated_price_database):
    class BrokenRepository:
        def list_prices(self, *args, **kwargs):
            raise SQLAlchemyError("sensitive database detail")

    app.dependency_overrides[get_price_repo] = lambda: BrokenRepository()
    response = client.get("/api/market-prices")
    assert response.status_code == 500
    assert response.json()["detail"] == "Unable to retrieve market prices."
    assert "sensitive database detail" not in response.text


def test_price_csv_import_is_idempotent_and_resolves_catalog(isolated_price_database):
    csv_data = StringIO(
        "Commodity,Market,State,District,Arrival_Date,Min_Price,Max_Price,Modal_Price,Price_Unit\n"
        "Onion,Lasalgaon,Maharashtra,Nashik,01/01/2026,100,150,125,INR/Quintal\n"
        "Onion,Lasalgaon,Maharashtra,Nashik,01/01/2026,100,150,125,INR/Quintal\n"
        "Onion,Lasalgaon,Maharashtra,Nashik,2026-01-02,110,160,130,INR/Quintal\n"
    )
    summary = import_market_prices_csv(isolated_price_database, csv_data, source="Verified official CSV")
    assert (summary.rows_read, summary.rows_inserted, summary.duplicates_skipped) == (3, 2, 1)
    again = import_market_prices_csv(
        isolated_price_database,
        StringIO("crop,market,state,district,date,min_price,max_price,modal_price,price_unit\nOnion,Lasalgaon,Maharashtra,Nashik,2026-01-01,100,150,125,INR/Quintal\n"),
        source="Verified official CSV",
    )
    assert (again.rows_inserted, again.duplicates_skipped) == (0, 1)


@pytest.mark.parametrize("csv_data", [
    "crop,market,date,min_price,max_price,modal_price\nOnion,Lasalgaon,2026-01-01,1,2,1\n",
    "crop,market,state,district,date,min_price,max_price,modal_price,price_unit\nOnion,Lasalgaon,Maharashtra,Nashik,2026-01-01,nope,2,1,INR/kg\n",
    "crop,market,state,district,date,min_price,max_price,modal_price,price_unit\nUnknown,Lasalgaon,Maharashtra,Nashik,2026-01-01,1,2,1,INR/kg\n",
    "crop,market,state,district,date,min_price,max_price,modal_price,price_unit\nOnion,Lasalgaon,Maharashtra,Nashik,2026-01-01,1,2,1,Rupees\n",
])
def test_price_csv_import_rejects_invalid_files_atomically(isolated_price_database, csv_data):
    with pytest.raises(PriceImportError):
        import_market_prices_csv(isolated_price_database, StringIO(csv_data), source="test")
    assert isolated_price_database.scalar(select(func.count(MarketPrice.id))) == 0


def test_price_csv_import_rejects_conflicting_duplicate_day(isolated_price_database):
    csv_data = StringIO(
        "crop,market,state,district,date,min_price,max_price,modal_price,price_unit\n"
        "Onion,Lasalgaon,Maharashtra,Nashik,2026-01-01,1,2,1.5,INR/kg\n"
        "Onion,Lasalgaon,Maharashtra,Nashik,2026-01-01,1,3,2,INR/kg\n"
    )
    with pytest.raises(PriceImportError, match="conflicting"):
        import_market_prices_csv(isolated_price_database, csv_data, source="test")
    assert isolated_price_database.scalar(select(func.count(MarketPrice.id))) == 0


def test_price_csv_import_uses_optional_row_source(isolated_price_database):
    data = StringIO(
        "crop,market,state,district,date,min_price,max_price,modal_price,price_unit,source\n"
        "Onion,Lasalgaon,Maharashtra,Nashik,2026-01-01,1,2,1.5,INR/kg,AGMARKNET daily report\n"
    )
    import_market_prices_csv(isolated_price_database, data, source="fallback label")
    stored = isolated_price_database.scalar(select(MarketPrice))
    assert stored.source == "AGMARKNET daily report"


def test_price_import_preserves_crop_market_and_variety_dimensions(isolated_price_database):
    data = StringIO(
        "report_date,state_name,district_name,market_center,commodity_name,variety,grade,"
        "arrival_quantity,arrival_units,min_price,max_price,modal_price,price_unit\n"
        "2026-01-01,Maharashtra,Nashik,Lasalgaon,Onion,Red,Local,10,Metric Tonnes,10,20,15,Rs./Quintal\n"
        "2026-01-01,Maharashtra,Nashik,Lasalgaon,Onion,Other,Local,11,Metric Tonnes,10,20,15,Rs./Quintal\n"
        "2026-01-01,Maharashtra,Nashik,Niphad,Wheat,FAQ,Local,12,Metric Tonnes,100,200,150,Rs./Quintal\n"
    )
    summary = import_market_prices_csv(
        isolated_price_database, data, source="supplied source file", commit=False
    )
    assert summary.rows_inserted == 3
    records = isolated_price_database.scalars(select(MarketPrice).order_by(MarketPrice.id)).all()
    assert {(r.crop_id, r.market_id, r.variety, r.grade) for r in records} == {
        (1, 10, "Red", "Local"), (1, 10, "Other", "Local"), (2, 11, "FAQ", "Local"),
    }
    assert {r.price_unit for r in records} == {"INR/Quintal"}
    isolated_price_database.rollback()


def test_price_forecast_requires_sufficient_real_history(isolated_price_database):
    response = client.get("/api/price-predictions?crop_id=1&market_id=10&horizon_days=7")
    assert response.status_code == 422
    with pytest.raises(InsufficientPriceHistory):
        forecast_modal_price([(date(2026, 1, 1), 100.0)], horizon_days=7)
    assert client.get("/api/price-predictions?crop_id=999&market_id=10").status_code == 404
    assert client.get("/api/price-predictions?crop_id=1&market_id=10&horizon_days=31").status_code == 422


def test_price_forecast_requires_explicit_variety_for_mixed_series(isolated_price_database):
    db = isolated_price_database
    db.add_all([
        MarketPrice(id=1, crop_id=1, market_id=10, price_date=date(2026, 1, 1), min_price=10, max_price=20, modal_price=15, variety="Red", grade="Local", price_unit="INR/Quintal", source="test"),
        MarketPrice(id=2, crop_id=1, market_id=10, price_date=date(2026, 1, 1), min_price=10, max_price=20, modal_price=15, variety="Other", grade="Local", price_unit="INR/Quintal", source="test"),
    ])
    db.commit()
    ambiguous = client.get("/api/price-predictions?crop_id=1&market_id=10")
    assert ambiguous.status_code == 422
    assert "select a variety" in ambiguous.json()["detail"]
    selected = client.get("/api/price-predictions?crop_id=1&market_id=10&variety=Red")
    assert selected.status_code == 422
    assert "observations spanning" in selected.json()["detail"]


def test_list_prices_with_mock_repo():
    mock_price_repo = SyntheticMockPriceRepo()
    app.dependency_overrides[get_price_repo] = lambda: mock_price_repo

    try:
        res = client.get("/api/market-prices")
        assert res.status_code == 200
        data = res.json()
        assert data["total"] == 3
        # Explicit unit check
        assert data["items"][0]["price_unit"] == "INR/Quintal"
        assert data["items"][0]["modal_price"] == 2850.0

        # Filter by crop_id & market_id
        filt_res = client.get("/api/market-prices?crop_id=1&market_id=10")
        assert filt_res.status_code == 200
        assert filt_res.json()["total"] == 2

        # Filter by date range
        date_res = client.get("/api/market-prices?start_date=2026-10-15&end_date=2026-10-15")
        assert date_res.status_code == 200
        assert date_res.json()["total"] == 2
    finally:
        app.dependency_overrides.clear()


def test_list_prices_invalid_date_range_returns_400():
    mock_price_repo = SyntheticMockPriceRepo()
    app.dependency_overrides[get_price_repo] = lambda: mock_price_repo

    try:
        res = client.get("/api/market-prices?start_date=2026-10-20&end_date=2026-10-10")
        assert res.status_code == 400
        assert "start_date cannot be greater than end_date" in res.json()["detail"]
    finally:
        app.dependency_overrides.clear()


def test_list_prices_invalid_sort_parameters_returns_400():
    mock_price_repo = SyntheticMockPriceRepo()
    app.dependency_overrides[get_price_repo] = lambda: mock_price_repo

    try:
        # Invalid sort_by field
        res1 = client.get("/api/market-prices?sort_by=illegal_column")
        assert res1.status_code == 400
        assert "Invalid sort_by field" in res1.json()["detail"]

        # Invalid sort_order
        res2 = client.get("/api/market-prices?sort_order=diagonal")
        assert res2.status_code == 400
        assert "sort_order must be either 'asc' or 'desc'" in res2.json()["detail"]
    finally:
        app.dependency_overrides.clear()


def test_get_latest_price_success_and_not_found():
    mock_price_repo = SyntheticMockPriceRepo()
    app.dependency_overrides[get_price_repo] = lambda: mock_price_repo

    try:
        # Latest price for Onion (crop_id=1)
        res = client.get("/api/market-prices/latest?crop_id=1")
        assert res.status_code == 200
        assert res.json()["price_date"] == "2026-10-15"
        assert res.json()["modal_price"] == 2850.0

        # Latest price for non-existent crop
        res2 = client.get("/api/market-prices/latest?crop_id=999")
        assert res2.status_code == 404
    finally:
        app.dependency_overrides.clear()


def test_get_price_record_by_id():
    mock_price_repo = SyntheticMockPriceRepo()
    app.dependency_overrides[get_price_repo] = lambda: mock_price_repo

    try:
        res = client.get("/api/market-prices/101")
        assert res.status_code == 200
        assert res.json()["modal_price"] == 2850.0

        res2 = client.get("/api/market-prices/999")
        assert res2.status_code == 404
    finally:
        app.dependency_overrides.clear()


def test_price_bounds_validation_schema():
    """Verify that PriceRecordResponse forbids max_price < min_price."""
    with pytest.raises(ValidationError):
        PriceRecordResponse(
            id=1,
            crop_id=1,
            market_id=10,
            price_date=date(2026, 10, 15),
            min_price=3000.0,
            max_price=2000.0,  # Max is less than min!
            modal_price=2500.0,
            price_unit="INR/Quintal",
        )
