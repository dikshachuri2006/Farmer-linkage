from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from types import SimpleNamespace
from typing import Dict, List, Optional, Tuple
from fastapi.testclient import TestClient
import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool
from app.core.security import UserRole, create_access_token
from app.database.base import Base
from app.database.connection import get_db
from app.main import app
from app.schemas.buyer import (
    BuyerBusinessType,
    BuyerProfileResponse,
    BuyerVerificationStatus,
)
from app.schemas.farmer_lot import (
    FarmerLotCreate,
    FarmerLotResponse,
    FarmerLotUpdate,
    LotQualityGrade,
    LotStatus,
)
from app.schemas.crop import CropCategory
from app.models.entities import Complaint as ComplaintModel
from app.models.entities import BuyerOffer as BuyerOfferModel
from app.models.entities import BuyerProfile as BuyerProfileModel
from app.models.entities import Crop, FarmerLot, Notification as NotificationModel
from app.models.entities import SellingRequest as SellingRequestModel, Transaction as TransactionModel, User
from app.schemas.notification import NotificationCreate, NotificationType
from app.schemas.offer import (
    BuyerOfferCreate,
    BuyerOfferResponse,
    BuyerOfferUpdate,
    OfferStatus,
)
from app.schemas.selling_request import (
    RequestActionType,
    SellingRequestActionRequest,
    SellingRequestCreate,
    SellingRequestResponse,
    SellingRequestStatus,
)
from app.schemas.transaction import PaymentStatus, TransactionStatus
from app.services.profile_service import get_buyer_profile_repo
from app.services.trade_service import (
    DefaultBuyerOfferRepository,
    TradeWorkflowError,
    get_buyer_offer_repo,
    get_farmer_lot_repo,
    get_selling_request_repo,
)
from app.services.transaction_service import DefaultPostgresTransactionRepository
from app.services.complaint_service import DefaultPostgresComplaintRepository
from app.services.notification_service import (
    DefaultPostgresNotificationRepository,
    NotificationRecipientNotFoundError,
)

client = TestClient(app)


class IdentityOnlySession:
    def get(self, model, user_id):
        roles = {
            1: UserRole.ADMIN, 10: UserRole.FARMER, 20: UserRole.BUYER,
            30: UserRole.BUYER, 31: UserRole.FARMER, 77: UserRole.BUYER,
            88: UserRole.FARMER, 99: UserRole.FARMER,
        }
        role = roles.get(user_id)
        return SimpleNamespace(id=user_id, role=role, is_active=True) if role else None


@pytest.fixture(autouse=True)
def isolated_identity_session():
    app.dependency_overrides[get_db] = lambda: IdentityOnlySession()
    try:
        yield
    finally:
        app.dependency_overrides.clear()


def _farmer_headers(user_id: int = 10, role: UserRole = UserRole.FARMER):
    if role == UserRole.BUYER and user_id == 10:
        user_id = 30
    token = create_access_token(subject=user_id, role=role.value)
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def isolated_lot_database():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(
        engine,
        tables=[
            User.__table__, Crop.__table__, FarmerLot.__table__,
            BuyerProfileModel.__table__, BuyerOfferModel.__table__, SellingRequestModel.__table__,
            TransactionModel.__table__, ComplaintModel.__table__, NotificationModel.__table__,
        ],
    )
    db = Session(engine, expire_on_commit=False)
    sqlite_ids = {
        BuyerOfferModel: 1000, SellingRequestModel: 2000,
        TransactionModel: 3000, ComplaintModel: 4000, NotificationModel: 5000,
    }

    def assign_sqlite_identity(session, flush_context, instances):
        for instance in session.new:
            if isinstance(instance, FarmerLot) and instance.id is None:
                instance.id = 202
            elif type(instance) in sqlite_ids and instance.id is None:
                instance.id = sqlite_ids[type(instance)]
                sqlite_ids[type(instance)] += 1

    event.listen(db, "before_flush", assign_sqlite_identity)
    db.add_all(
        [
            User(
                id=10,
                email="farmer10@example.test",
                phone_number="9876543210",
                hashed_password="test-hash",
                full_name="Farmer Ten",
                role=UserRole.FARMER,
            ),
            User(
                id=20,
                email="farmer20@example.test",
                phone_number="9876543211",
                hashed_password="test-hash",
                full_name="Farmer Twenty",
                role=UserRole.FARMER,
            ),
            User(
                id=30,
                email="buyer30@example.test",
                phone_number="9876543212",
                hashed_password="test-hash",
                full_name="Buyer Thirty",
                role=UserRole.BUYER,
            ),
            User(id=1, email="admin1@example.test", phone_number="9876543201", hashed_password="test-hash", full_name="Admin One", role=UserRole.ADMIN),
            User(id=31, email="farmer31@example.test", phone_number="9876543231", hashed_password="test-hash", full_name="Farmer Thirty One", role=UserRole.FARMER),
            User(id=77, email="buyer77@example.test", phone_number="9876543277", hashed_password="test-hash", full_name="Buyer Seventy Seven", role=UserRole.BUYER),
            User(id=88, email="farmer88@example.test", phone_number="9876543288", hashed_password="test-hash", full_name="Farmer Eighty Eight", role=UserRole.FARMER),
            User(id=99, email="farmer99@example.test", phone_number="9876543299", hashed_password="test-hash", full_name="Farmer Ninety Nine", role=UserRole.FARMER),
            Crop(
                id=1,
                name="Onion",
                category=CropCategory.VEGETABLE,
                standard_unit="quintal",
            ),
        ]
    )
    db.add(
        BuyerProfileModel(
            id=30,
            user_id=30,
            business_name="Buyer Thirty Trading",
            state="Maharashtra",
            district="Nashik",
            market_address="Nashik Market",
            verification_status=BuyerVerificationStatus.VERIFIED,
        )
    )
    base_time = datetime(2026, 1, 1, tzinfo=timezone.utc)
    for lot_id, owner_id, days in [(101, 10, 0), (102, 10, 1), (103, 10, 2), (201, 20, 3)]:
        created_at = base_time + timedelta(days=days)
        db.add(
            FarmerLot(
                id=lot_id,
                farmer_id=owner_id,
                crop_id=1,
                quantity=Decimal("10.000"),
                unit="quintal",
                quality_grade=LotQualityGrade.GRADE_A,
                expected_price_per_unit=Decimal("2500.00"),
                price_unit="INR/quintal",
                location_state="Maharashtra",
                location_district="Nashik",
                status=LotStatus.AVAILABLE,
                created_at=created_at,
                updated_at=created_at,
            )
        )
    db.commit()

    app.dependency_overrides.clear()
    app.dependency_overrides[get_db] = lambda: db
    try:
        yield db
    finally:
        app.dependency_overrides.clear()
        db.close()
        engine.dispose()


# ==============================================================================
# Isolated In-Memory Fixtures for Unit Testing
# (Used strictly for testing endpoint behavior without hitting a live database)
# ==============================================================================

class IsolatedMockLotRepo:
    def __init__(self):
        self.lots: Dict[int, FarmerLotResponse] = {}
        self.next_id = 1

    def create_lot(self, db, farmer_id: int, farmer_name: str, lot_in: FarmerLotCreate) -> FarmerLotResponse:
        lot = FarmerLotResponse(
            id=self.next_id,
            farmer_id=farmer_id,
            farmer_name=farmer_name,
            crop_id=lot_in.crop_id,
            crop_name=lot_in.crop_name,
            quantity=lot_in.quantity,
            unit=lot_in.unit,
            quality_grade=lot_in.quality_grade,
            expected_price_per_unit=lot_in.expected_price_per_unit,
            price_unit=lot_in.price_unit,
            harvest_date=lot_in.harvest_date,
            location_state=lot_in.location_state,
            location_district=lot_in.location_district,
            status=LotStatus.AVAILABLE,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )
        self.lots[self.next_id] = lot
        self.next_id += 1
        return lot

    def get_lot_by_id(self, db, lot_id: int, farmer_id: Optional[int] = None) -> Optional[FarmerLotResponse]:
        lot = self.lots.get(lot_id)
        if farmer_id is not None and (lot is None or lot.farmer_id != farmer_id):
            return None
        return lot

    def list_farmer_lots(self, db, farmer_id: int, skip: int = 0, limit: int = 50) -> Tuple[List[FarmerLotResponse], int]:
        matches = [l for l in self.lots.values() if l.farmer_id == farmer_id]
        return matches[skip : skip + limit], len(matches)

    def update_lot(self, db, lot_id: int, farmer_id: int, lot_update: FarmerLotUpdate) -> Optional[FarmerLotResponse]:
        lot = self.lots.get(lot_id)
        if not lot or lot.farmer_id != farmer_id:
            return None
        if lot_update.quantity is not None:
            lot.quantity = lot_update.quantity
        if lot_update.expected_price_per_unit is not None:
            lot.expected_price_per_unit = lot_update.expected_price_per_unit
        if lot_update.quality_grade is not None:
            lot.quality_grade = lot_update.quality_grade
        if lot_update.location_district is not None:
            lot.location_district = lot_update.location_district
        if lot_update.status is not None:
            lot.status = lot_update.status
        lot.updated_at = datetime.now(timezone.utc)
        return lot

    def withdraw_lot(self, db, lot_id: int, farmer_id: int) -> Optional[FarmerLotResponse]:
        lot = self.lots.get(lot_id)
        if not lot or lot.farmer_id != farmer_id:
            return None
        lot.status = LotStatus.WITHDRAWN
        lot.updated_at = datetime.now(timezone.utc)
        return lot


class IsolatedMockOfferRepo:
    def __init__(self):
        self.offers: Dict[int, BuyerOfferResponse] = {}
        self.next_id = 1

    def create_offer(self, db, buyer_id: int, buyer_name: str, lot: FarmerLotResponse, offer_in: BuyerOfferCreate) -> BuyerOfferResponse:
        total_val = round(offer_in.offered_price_per_unit * offer_in.quantity_requested, 2)
        offer = BuyerOfferResponse(
            id=self.next_id,
            buyer_id=buyer_id,
            buyer_name=buyer_name,
            lot_id=lot.id,
            crop_name=lot.crop_name,
            offered_price_per_unit=offer_in.offered_price_per_unit,
            price_unit=offer_in.price_unit,
            quantity_requested=offer_in.quantity_requested,
            quantity_unit=offer_in.quantity_unit,
            total_offer_value=total_val,
            pickup_included=offer_in.pickup_included,
            delivery_location=offer_in.delivery_location,
            status=OfferStatus.ACTIVE,
            valid_until=offer_in.valid_until,
            terms_and_notes=offer_in.terms_and_notes,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )
        self.offers[self.next_id] = offer
        self.next_id += 1
        return offer

    def get_offer_by_id(self, db, offer_id: int) -> Optional[BuyerOfferResponse]:
        return self.offers.get(offer_id)

    def list_buyer_offers(self, db, buyer_id: int, skip: int = 0, limit: int = 50) -> Tuple[List[BuyerOfferResponse], int]:
        matches = [o for o in self.offers.values() if o.buyer_id == buyer_id]
        return matches[skip : skip + limit], len(matches)

    def list_offers_for_lot(self, db, lot_id: int, farmer_id: int) -> List[BuyerOfferResponse]:
        return [o for o in self.offers.values() if o.lot_id == lot_id and o.status == OfferStatus.ACTIVE]

    def withdraw_offer(self, db, offer_id: int, buyer_id: int) -> Optional[BuyerOfferResponse]:
        offer = self.offers.get(offer_id)
        if not offer or offer.buyer_id != buyer_id:
            return None
        offer.status = OfferStatus.WITHDRAWN
        offer.updated_at = datetime.now(timezone.utc)
        return offer


class IsolatedMockSellingRequestRepo:
    def __init__(self, lot_repo: IsolatedMockLotRepo):
        self.requests: Dict[int, SellingRequestResponse] = {}
        self.lot_repo = lot_repo
        self.next_id = 1

    def create_request(self, db, farmer_id: int, farmer_name: str, buyer_id: int, buyer_name: str, lot: FarmerLotResponse, req_in: SellingRequestCreate) -> SellingRequestResponse:
        gross = round(req_in.proposed_price * req_in.quantity, 2)
        trans = round(req_in.estimated_transport_cost or 0.0, 2)
        other = round(req_in.estimated_other_charges or 0.0, 2)
        net = round(gross - trans - other, 2)

        req = SellingRequestResponse(
            id=self.next_id,
            request_code=f"REQ-2026-{self.next_id:04d}",
            farmer_id=farmer_id,
            farmer_name=farmer_name,
            buyer_id=buyer_id,
            buyer_name=buyer_name,
            lot_id=lot.id,
            crop_name=lot.crop_name,
            quantity=req_in.quantity,
            quantity_unit=req_in.quantity_unit,
            proposed_price=req_in.proposed_price,
            price_unit=req_in.price_unit,
            estimated_gross_amount=gross,
            estimated_transport_cost=trans,
            estimated_other_charges=other,
            estimated_net_realization=net,
            status=SellingRequestStatus.PENDING,
            rejection_reason=None,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )
        self.requests[self.next_id] = req
        self.next_id += 1
        return req

    def get_request_by_id(
        self, db, request_id: int, farmer_id: Optional[int] = None, buyer_id: Optional[int] = None
    ) -> Optional[SellingRequestResponse]:
        request = self.requests.get(request_id)
        if farmer_id is not None and (request is None or request.farmer_id != farmer_id):
            return None
        if buyer_id is not None and (request is None or request.buyer_id != buyer_id):
            return None
        return request

    def list_farmer_requests(self, db, farmer_id: int, skip: int = 0, limit: int = 50) -> Tuple[List[SellingRequestResponse], int]:
        matches = [r for r in self.requests.values() if r.farmer_id == farmer_id]
        return matches[skip : skip + limit], len(matches)

    def list_buyer_requests(self, db, buyer_id: int, skip: int = 0, limit: int = 50) -> Tuple[List[SellingRequestResponse], int]:
        matches = [r for r in self.requests.values() if r.buyer_id == buyer_id]
        return matches[skip : skip + limit], len(matches)

    def execute_action(self, db, request_id: int, actor_id: int, actor_role: str, action_in: SellingRequestActionRequest) -> SellingRequestResponse:
        req = self.requests.get(request_id)
        if not req:
            raise TradeWorkflowError("Selling request not found.")

        # State machine transition guard: terminal states cannot be changed
        if req.status in [SellingRequestStatus.ACCEPTED, SellingRequestStatus.REJECTED, SellingRequestStatus.CANCELLED, SellingRequestStatus.COMPLETED]:
            raise TradeWorkflowError(f"Request is in terminal state '{req.status.value}' and cannot undergo further actions.")

        if action_in.action == RequestActionType.ACCEPT:
            # Check lot is not committed
            lot = self.lot_repo.get_lot_by_id(db, req.lot_id)
            if not lot or lot.status != LotStatus.AVAILABLE:
                raise TradeWorkflowError("Underlying farmer lot is no longer available.")
            req.status = SellingRequestStatus.ACCEPTED
            lot.status = LotStatus.COMMITTED
            lot.updated_at = datetime.now(timezone.utc)

        elif action_in.action == RequestActionType.REJECT:
            req.status = SellingRequestStatus.REJECTED
            req.rejection_reason = action_in.reason_or_notes or "Rejected by counterparty."

        elif action_in.action == RequestActionType.COUNTER:
            req.status = SellingRequestStatus.COUNTERED
            if action_in.counter_price is not None:
                req.proposed_price = action_in.counter_price
            if action_in.counter_quantity is not None:
                req.quantity = action_in.counter_quantity
            gross = round(req.proposed_price * req.quantity, 2)
            req.estimated_gross_amount = gross
            req.estimated_net_realization = round(gross - req.estimated_transport_cost - req.estimated_other_charges, 2)

        elif action_in.action == RequestActionType.CANCEL:
            req.status = SellingRequestStatus.CANCELLED
            req.rejection_reason = action_in.reason_or_notes or "Cancelled by creator."

        req.updated_at = datetime.now(timezone.utc)
        return req


class IsolatedMockBuyerProfileRepo:
    def __init__(self):
        self.profiles = {}

    def get_by_user_id(self, db, user_id: int):
        return self.profiles.get(user_id)


# ==============================================================================
# 1. Farmer Lot Tests
# ==============================================================================

def _valid_farmer_lot_payload(**overrides):
    payload = {
        "crop_id": 1,
        "crop_name": "Onion",
        "quantity": 100.0,
        "unit": "quintal",
        "quality_grade": "GRADE_A",
        "expected_price_per_unit": 2800.0,
        "price_unit": "INR/quintal",
        "location_state": "Maharashtra",
        "location_district": "Nashik",
        "location_pincode": "422209",
    }
    payload.update(overrides)
    return payload


def test_farmer_default_lot_detail_update_withdraw_and_owner_scope(isolated_lot_database):
    headers = _farmer_headers()
    detail = client.get("/api/farmer/lots/101", headers=headers)
    assert detail.status_code == 200
    assert detail.json()["farmer_id"] == 10
    assert detail.json()["crop_name"] == "Onion"

    other_owner = client.get("/api/farmer/lots/201", headers=headers)
    assert other_owner.status_code == 404
    assert client.get("/api/farmer/lots/999", headers=headers).status_code == 404

    invalid_update = client.put(
        "/api/farmer/lots/101", headers=headers, json={"quantity": 0}
    )
    assert invalid_update.status_code == 422

    updated = client.put(
        "/api/farmer/lots/101", headers=headers, json={"quantity": 8.5}
    )
    assert updated.status_code == 200
    assert updated.json()["quantity"] == 8.5

    forbidden_transition = client.put(
        "/api/farmer/lots/101", headers=headers, json={"status": "SOLD"}
    )
    assert forbidden_transition.status_code == 409
    assert isolated_lot_database.get(FarmerLot, 101).status == LotStatus.AVAILABLE

    withdrawn = client.delete("/api/farmer/lots/101", headers=headers)
    assert withdrawn.status_code == 200
    assert withdrawn.json()["status"] == "WITHDRAWN"
    assert isolated_lot_database.get(FarmerLot, 101) is not None


def test_farmer_offers_only_sees_active_unexpired_offers_for_owned_lot(isolated_lot_database):
    isolated_lot_database.add_all(
        [
            BuyerOfferModel(
                id=501, buyer_id=30, lot_id=101, offered_price_per_unit=Decimal("2600"),
                quantity_requested=Decimal("5"), delivery_location="Nashik", status=OfferStatus.ACTIVE,
                valid_until=date.today() + timedelta(days=1),
            ),
            BuyerOfferModel(
                id=502, buyer_id=30, lot_id=101, offered_price_per_unit=Decimal("2500"),
                quantity_requested=Decimal("5"), delivery_location="Nashik", status=OfferStatus.WITHDRAWN,
            ),
            BuyerOfferModel(
                id=503, buyer_id=30, lot_id=201, offered_price_per_unit=Decimal("2700"),
                quantity_requested=Decimal("5"), delivery_location="Nashik", status=OfferStatus.ACTIVE,
            ),
        ]
    )
    isolated_lot_database.commit()

    response = client.get("/api/farmer/lots/101/offers", headers=_farmer_headers())
    assert response.status_code == 200
    assert len(response.json()) == 1
    assert response.json()[0]["id"] == 501
    assert response.json()[0]["buyer_name"] == "Buyer Thirty Trading"
    assert response.json()[0]["total_offer_value"] == 13000.0
    assert client.get("/api/farmer/lots/201/offers", headers=_farmer_headers()).status_code == 404


def test_farmer_selling_request_create_list_pagination_and_buyer_validation(isolated_lot_database):
    headers = _farmer_headers()
    payload = {
        "lot_id": 101,
        "buyer_id": 30,
        "proposed_price": 2450,
        "quantity": 4,
        "estimated_transport_cost": 100,
        "estimated_other_charges": 25,
    }
    created = client.post("/api/farmer/selling-requests", headers=headers, json=payload)
    assert created.status_code == 201
    data = created.json()
    assert data["farmer_id"] == 10 and data["buyer_id"] == 30
    assert data["farmer_name"] == "Farmer Ten"
    assert data["buyer_name"] == "Buyer Thirty"
    assert data["crop_name"] == "Onion"
    assert data["estimated_gross_amount"] == 9800.0
    assert data["estimated_net_realization"] == 9675.0
    assert isolated_lot_database.get(SellingRequestModel, data["id"]) is not None
    second = client.post("/api/farmer/selling-requests", headers=headers, json=payload)
    assert second.status_code == 201
    listing = client.get("/api/farmer/selling-requests?skip=1&limit=1", headers=headers)
    assert listing.status_code == 200
    assert listing.json()["total"] == 2
    assert len(listing.json()["items"]) == 1
    assert listing.json()["skip"] == 1
    other_farmer_listing = client.get(
        "/api/farmer/selling-requests", headers=_farmer_headers(user_id=20)
    )
    assert other_farmer_listing.status_code == 200
    assert other_farmer_listing.json()["total"] == 0

    unknown_buyer = {**payload, "buyer_id": 999}
    assert client.post("/api/farmer/selling-requests", headers=headers, json=unknown_buyer).status_code == 404
    other_lot = {**payload, "lot_id": 201}
    assert client.post("/api/farmer/selling-requests", headers=headers, json=other_lot).status_code == 404
    too_much = {**payload, "quantity": 11}
    assert client.post("/api/farmer/selling-requests", headers=headers, json=too_much).status_code == 400


def test_selling_request_rejects_price_and_quantity_unit_mismatch(isolated_lot_database):
    response = client.post("/api/farmer/selling-requests", headers=_farmer_headers(10), json={
        "lot_id": 101,
        "buyer_id": 30,
        "proposed_price": 2500,
        "price_unit": "INR/quintal",
        "quantity": 2,
        "quantity_unit": "kg",
    })
    assert response.status_code == 409
    assert isolated_lot_database.query(SellingRequestModel).count() == 0


def test_farmer_selling_request_action_transitions_and_validation(isolated_lot_database):
    headers = _farmer_headers()
    created = client.post(
        "/api/farmer/selling-requests",
        headers=headers,
        json={"lot_id": 101, "buyer_id": 30, "proposed_price": 2450, "quantity": 4},
    )
    request_id = created.json()["id"]

    invalid_action = client.post(
        f"/api/farmer/selling-requests/{request_id}/action",
        headers=headers,
        json={"action": "BOGUS"},
    )
    assert invalid_action.status_code == 422
    missing_counter = client.post(
        f"/api/farmer/selling-requests/{request_id}/action",
        headers=headers,
        json={"action": "COUNTER"},
    )
    assert missing_counter.status_code == 409

    countered = client.post(
        f"/api/farmer/selling-requests/{request_id}/action",
        headers=headers,
        json={"action": "COUNTER", "counter_price": 2500, "counter_quantity": 3},
    )
    assert countered.status_code == 200
    assert countered.json()["status"] == "COUNTERED"
    assert countered.json()["estimated_gross_amount"] == 7500.0

    accepted = client.post(
        f"/api/farmer/selling-requests/{request_id}/action",
        headers=headers,
        json={"action": "ACCEPT"},
    )
    assert accepted.status_code == 200
    assert accepted.json()["status"] == "ACCEPTED"
    assert isolated_lot_database.get(FarmerLot, 101).status == LotStatus.COMMITTED
    repeated = client.post(
        f"/api/farmer/selling-requests/{request_id}/action",
        headers=headers,
        json={"action": "CANCEL"},
    )
    assert repeated.status_code == 409
    assert client.post(
        "/api/farmer/selling-requests/9999/action",
        headers=headers,
        json={"action": "CANCEL"},
    ).status_code == 404
    assert client.post(
        f"/api/farmer/selling-requests/{request_id}/action",
        headers=_farmer_headers(user_id=20),
        json={"action": "CANCEL"},
    ).status_code == 404


def test_farmer_selling_request_action_rolls_back_multirow_failure(isolated_lot_database):
    headers = _farmer_headers()
    created = client.post(
        "/api/farmer/selling-requests",
        headers=headers,
        json={"lot_id": 101, "buyer_id": 30, "proposed_price": 2450, "quantity": 4},
    )
    request_id = created.json()["id"]

    def fail_before_flush(session, flush_context, instances):
        raise RuntimeError("simulated database failure")

    event.listen(isolated_lot_database, "before_flush", fail_before_flush)
    error_client = TestClient(app, raise_server_exceptions=False)
    try:
        response = error_client.post(
            f"/api/farmer/selling-requests/{request_id}/action",
            headers=headers,
            json={"action": "COUNTER", "counter_price": 2500},
        )
        assert response.status_code == 500
        persisted = isolated_lot_database.get(SellingRequestModel, request_id)
        lot = isolated_lot_database.get(FarmerLot, 101)
        assert persisted.status == SellingRequestStatus.PENDING
        assert persisted.proposed_price == Decimal("2450.00")
        assert lot.status == LotStatus.AVAILABLE
    finally:
        event.remove(isolated_lot_database, "before_flush", fail_before_flush)


def test_farmer_can_reject_a_countered_request_and_cancel_an_open_request(isolated_lot_database):
    headers = _farmer_headers()
    for lot_id in (101, 102):
        created = client.post(
            "/api/farmer/selling-requests",
            headers=headers,
            json={"lot_id": lot_id, "buyer_id": 30, "proposed_price": 2450, "quantity": 2},
        )
        assert created.status_code == 201
        request_id = created.json()["id"]
        if lot_id == 101:
            counter = client.post(
                f"/api/farmer/selling-requests/{request_id}/action",
                headers=headers,
                json={"action": "COUNTER", "counter_price": 2500},
            )
            assert counter.status_code == 200
            action = "REJECT"
        else:
            action = "CANCEL"
        result = client.post(
            f"/api/farmer/selling-requests/{request_id}/action",
            headers=headers,
            json={"action": action, "reason_or_notes": "Terms not accepted"},
        )
        assert result.status_code == 200
        assert result.json()["status"] == ("REJECTED" if action == "REJECT" else "CANCELLED")
    assert isolated_lot_database.get(FarmerLot, 101).status == LotStatus.AVAILABLE
    assert isolated_lot_database.get(FarmerLot, 102).status == LotStatus.AVAILABLE


def test_buyer_acceptance_of_default_repository_request_commits_lot_atomically(isolated_lot_database):
    created = client.post(
        "/api/farmer/selling-requests",
        headers=_farmer_headers(),
        json={"lot_id": 101, "buyer_id": 30, "proposed_price": 2450, "quantity": 4},
    )
    request_id = created.json()["id"]
    buyer_headers = _farmer_headers(user_id=30, role=UserRole.BUYER)
    accepted = client.post(
        f"/api/buyer/requests/{request_id}/accept", headers=buyer_headers
    )
    assert accepted.status_code == 200
    assert accepted.json()["status"] == "ACCEPTED"
    assert isolated_lot_database.get(SellingRequestModel, request_id).status == SellingRequestStatus.ACCEPTED
    assert isolated_lot_database.get(FarmerLot, 101).status == LotStatus.COMMITTED


def test_farmer_lot_detail_requires_auth_and_returns_generic_database_error():
    assert client.get("/api/farmer/lots/1").status_code == 401
    assert client.get(
        "/api/farmer/lots/1", headers=_farmer_headers(role=UserRole.BUYER)
    ).status_code == 403

    class FailingLotSession:
        def __init__(self):
            self.rollback_count = 0

        def scalar(self, statement):
            raise OperationalError("SELECT", {}, RuntimeError("database unavailable"))

        def get(self, model, user_id):
            return SimpleNamespace(id=user_id, role=UserRole.FARMER, is_active=True)

        def rollback(self):
            self.rollback_count += 1

    session = FailingLotSession()
    app.dependency_overrides.clear()
    app.dependency_overrides[get_db] = lambda: session
    error_client = TestClient(app, raise_server_exceptions=False)
    try:
        response = error_client.get("/api/farmer/lots/1", headers=_farmer_headers())
        assert response.status_code == 500
        assert response.text == "Internal Server Error"
        assert session.rollback_count == 1
    finally:
        app.dependency_overrides.clear()


@pytest.mark.parametrize(
    ("method", "path", "payload"),
    [
        ("GET", "/api/farmer/profile", None),
        ("PUT", "/api/farmer/profile", {"state": "Maharashtra", "district": "Nashik", "pincode": "422209"}),
        ("POST", "/api/farmer/lots", _valid_farmer_lot_payload()),
        ("GET", "/api/farmer/lots", None),
        ("GET", "/api/farmer/lots/101", None),
        ("PUT", "/api/farmer/lots/101", {"quantity": 5}),
        ("DELETE", "/api/farmer/lots/101", None),
        ("GET", "/api/farmer/lots/101/offers", None),
        ("POST", "/api/farmer/selling-requests", {"lot_id": 101, "buyer_id": 30, "proposed_price": 2500, "quantity": 2}),
        ("GET", "/api/farmer/selling-requests", None),
        ("POST", "/api/farmer/selling-requests/1/action", {"action": "CANCEL"}),
    ],
)
def test_all_farmer_endpoints_reject_missing_and_wrong_role_auth(method, path, payload):
    app.dependency_overrides.clear()
    app.dependency_overrides[get_db] = lambda: IdentityOnlySession()
    try:
        missing = client.request(method, path, json=payload)
        assert missing.status_code == 401, path
        wrong_role = client.request(
            method, path, headers=_farmer_headers(role=UserRole.BUYER), json=payload
        )
        assert wrong_role.status_code == 403, path
    finally:
        app.dependency_overrides.clear()


def test_farmer_lot_default_repository_creates_authenticated_farmer_lot(isolated_lot_database):
    farmer_token = create_access_token(
        subject=10,
        role=UserRole.FARMER.value,
        extra_claims={"full_name": "Farmer Ten"},
    )
    res = client.post(
        "/api/farmer/lots",
        headers={"Authorization": f"Bearer {farmer_token}"},
        json=_valid_farmer_lot_payload(farmer_id=20),
    )
    assert res.status_code == 201
    created = res.json()
    assert created["id"] == 202
    assert created["farmer_id"] == 10
    assert created["farmer_name"] == "Farmer Ten"
    assert created["crop_id"] == 1
    assert created["crop_name"] == "Onion"
    persisted = isolated_lot_database.get(FarmerLot, 202)
    assert persisted is not None
    assert persisted.farmer_id == 10
    assert persisted.crop_id == 1


def test_farmer_lot_creation_rejects_nonpositive_crop_id(isolated_lot_database):
    farmer_token = create_access_token(subject=10, role=UserRole.FARMER.value)
    res = client.post(
        "/api/farmer/lots",
        headers={"Authorization": f"Bearer {farmer_token}"},
        json=_valid_farmer_lot_payload(crop_id=0),
    )
    assert res.status_code == 422
    assert isolated_lot_database.get(FarmerLot, 202) is None


def test_farmer_lot_creation_returns_404_for_unknown_crop(isolated_lot_database):
    farmer_token = create_access_token(subject=10, role=UserRole.FARMER.value)
    before = isolated_lot_database.query(FarmerLot).count()
    res = client.post(
        "/api/farmer/lots",
        headers={"Authorization": f"Bearer {farmer_token}"},
        json=_valid_farmer_lot_payload(crop_id=999),
    )
    assert res.status_code == 404
    assert res.json()["detail"] == "Crop not found."
    assert isolated_lot_database.query(FarmerLot).count() == before


def test_farmer_lot_creation_preserves_request_validation(isolated_lot_database):
    farmer_token = create_access_token(subject=10, role=UserRole.FARMER.value)
    res = client.post(
        "/api/farmer/lots",
        headers={"Authorization": f"Bearer {farmer_token}"},
        json=_valid_farmer_lot_payload(quantity=0),
    )
    assert res.status_code == 422
    assert isolated_lot_database.get(FarmerLot, 202) is None


def test_farmer_lot_creation_database_failure_rolls_back():
    class FailingLotSession:
        def __init__(self):
            self.rollback_count = 0

        def get(self, model, key):
            if model is User:
                return SimpleNamespace(id=key, role=UserRole.FARMER, is_active=True)
            raise OperationalError("SELECT", {}, RuntimeError("database unavailable"))

        def scalar(self, statement):
            raise OperationalError("SELECT", {}, RuntimeError("database unavailable"))

        def rollback(self):
            self.rollback_count += 1

    db_session = FailingLotSession()
    app.dependency_overrides.clear()
    app.dependency_overrides[get_db] = lambda: db_session
    farmer_token = create_access_token(subject=10, role=UserRole.FARMER.value)
    error_client = TestClient(app, raise_server_exceptions=False)
    try:
        res = error_client.post(
            "/api/farmer/lots",
            headers={"Authorization": f"Bearer {farmer_token}"},
            json=_valid_farmer_lot_payload(),
        )
        assert res.status_code == 500
        assert res.text == "Internal Server Error"
        assert db_session.rollback_count == 1
    finally:
        app.dependency_overrides.clear()


def test_farmer_lots_default_repository_lists_owned_lots(isolated_lot_database):
    farmer_token = create_access_token(subject=10, role=UserRole.FARMER.value)
    res = client.get("/api/farmer/lots", headers={"Authorization": f"Bearer {farmer_token}"})
    assert res.status_code == 200
    data = res.json()
    assert data["total"] == 3
    assert [item["id"] for item in data["items"]] == [103, 102, 101]
    assert all(item["farmer_id"] == 10 for item in data["items"])
    assert data["items"][0]["crop_name"] == "Onion"
    assert data["items"][0]["farmer_name"] == "Farmer Ten"


def test_farmer_lots_default_repository_returns_empty_list(isolated_lot_database):
    farmer_token = create_access_token(subject=31, role=UserRole.FARMER.value)
    res = client.get("/api/farmer/lots", headers={"Authorization": f"Bearer {farmer_token}"})
    assert res.status_code == 200
    assert res.json() == {"total": 0, "items": [], "skip": 0, "limit": 50}


def test_farmer_lots_default_repository_preserves_pagination(isolated_lot_database):
    farmer_token = create_access_token(subject=10, role=UserRole.FARMER.value)
    res = client.get(
        "/api/farmer/lots?skip=1&limit=1",
        headers={"Authorization": f"Bearer {farmer_token}"},
    )
    assert res.status_code == 200
    assert res.json()["total"] == 3
    assert [item["id"] for item in res.json()["items"]] == [102]
    assert res.json()["skip"] == 1
    assert res.json()["limit"] == 1


def test_farmer_lots_default_repository_isolates_each_farmer(isolated_lot_database):
    farmer_token = create_access_token(subject=20, role=UserRole.FARMER.value)
    res = client.get("/api/farmer/lots", headers={"Authorization": f"Bearer {farmer_token}"})
    assert res.status_code == 200
    assert res.json()["total"] == 1
    assert [item["id"] for item in res.json()["items"]] == [201]
    assert res.json()["items"][0]["farmer_id"] == 20


def test_farmer_lots_database_error_returns_generic_500_and_rolls_back():
    class FailingLotSession:
        def __init__(self):
            self.rollback_count = 0

        def scalar(self, statement):
            raise OperationalError("SELECT", {}, RuntimeError("database unavailable"))

        def get(self, model, user_id):
            return SimpleNamespace(id=user_id, role=UserRole.FARMER, is_active=True)

        def rollback(self):
            self.rollback_count += 1

    db_session = FailingLotSession()
    app.dependency_overrides.clear()
    app.dependency_overrides[get_db] = lambda: db_session
    farmer_token = create_access_token(subject=10, role=UserRole.FARMER.value)
    error_client = TestClient(app, raise_server_exceptions=False)
    try:
        res = error_client.get("/api/farmer/lots", headers={"Authorization": f"Bearer {farmer_token}"})
        assert res.status_code == 500
        assert res.text == "Internal Server Error"
        assert db_session.rollback_count == 1
    finally:
        app.dependency_overrides.clear()


def test_farmer_lot_creation_and_listing():
    lot_repo = IsolatedMockLotRepo()
    app.dependency_overrides[get_farmer_lot_repo] = lambda: lot_repo
    farmer_token = create_access_token(subject=10, role=UserRole.FARMER.value, extra_claims={"full_name": "Ramesh Patil"})

    try:
        # Create lot
        create_res = client.post(
            "/api/farmer/lots",
            headers={"Authorization": f"Bearer {farmer_token}"},
            json={
                "crop_id": 1,
                "crop_name": "Onion",
                "quantity": 100.0,
                "unit": "quintal",
                "quality_grade": "GRADE_A",
                "expected_price_per_unit": 2800.0,
                "price_unit": "INR/quintal",
                "location_state": "Maharashtra",
                "location_district": "Nashik",
            },
        )
        assert create_res.status_code == 201
        lot_data = create_res.json()
        assert lot_data["id"] == 1
        assert lot_data["farmer_id"] == 10
        assert lot_data["status"] == "AVAILABLE"

        # List farmer lots
        list_res = client.get("/api/farmer/lots", headers={"Authorization": f"Bearer {farmer_token}"})
        assert list_res.status_code == 200
        assert list_res.json()["total"] == 1
        assert list_res.json()["items"][0]["crop_name"] == "Onion"

        # Another farmer cannot access Ramesh's lot (404)
        other_farmer_token = create_access_token(subject=99, role=UserRole.FARMER.value)
        other_res = client.get("/api/farmer/lots/1", headers={"Authorization": f"Bearer {other_farmer_token}"})
        assert other_res.status_code == 404

        # Update lot
        upd_res = client.put(
            "/api/farmer/lots/1",
            headers={"Authorization": f"Bearer {farmer_token}"},
            json={"expected_price_per_unit": 2900.0},
        )
        assert upd_res.status_code == 200
        assert upd_res.json()["expected_price_per_unit"] == 2900.0

        # Withdraw lot
        del_res = client.delete("/api/farmer/lots/1", headers={"Authorization": f"Bearer {farmer_token}"})
        assert del_res.status_code == 200
        assert del_res.json()["status"] == "WITHDRAWN"

    finally:
        app.dependency_overrides.clear()


def test_farmer_lot_unauthorized_modification():
    lot_repo = IsolatedMockLotRepo()
    lot_in = FarmerLotCreate(
        crop_id=1, crop_name="Onion", quantity=50.0, unit="quintal",
        quality_grade=LotQualityGrade.GRADE_A, expected_price_per_unit=2500.0,
        location_state="Maharashtra", location_district="Nashik"
    )
    lot_repo.create_lot(None, 10, "Ramesh", lot_in)
    app.dependency_overrides[get_farmer_lot_repo] = lambda: lot_repo

    other_farmer_token = create_access_token(subject=88, role=UserRole.FARMER.value)

    try:
        # Other farmer cannot update Lot 1
        put_res = client.put(
            "/api/farmer/lots/1",
            headers={"Authorization": f"Bearer {other_farmer_token}"},
            json={"expected_price_per_unit": 3500.0},
        )
        assert put_res.status_code == 404

        # Other farmer cannot delete/withdraw Lot 1
        del_res = client.delete(
            "/api/farmer/lots/1",
            headers={"Authorization": f"Bearer {other_farmer_token}"},
        )
        assert del_res.status_code == 404
    finally:
        app.dependency_overrides.clear()


# ==============================================================================
# 2. Buyer Offer Tests (Verification Guard & Quantities)
# ==============================================================================

def test_database_backed_buyer_offer_empty_create_retrieve_and_ownership(isolated_lot_database):
    buyer_headers = {
        "Authorization": f"Bearer {create_access_token(subject=30, role=UserRole.BUYER.value)}"
    }
    other_buyer_headers = {
        "Authorization": f"Bearer {create_access_token(subject=77, role=UserRole.BUYER.value)}"
    }
    empty = client.get("/api/buyer/offers", headers=buyer_headers)
    assert empty.status_code == 200
    assert empty.json()["total"] == 0
    assert empty.json()["items"] == []

    invalid_lot = client.post("/api/buyer/offers", headers=buyer_headers, json={
        "lot_id": 99999, "offered_price_per_unit": 2700,
        "quantity_requested": 2, "delivery_location": "Nashik Market",
    })
    assert invalid_lot.status_code == 404

    created = client.post("/api/buyer/offers", headers=buyer_headers, json={
        "lot_id": 101, "offered_price_per_unit": 2700,
        "quantity_requested": 2, "delivery_location": "Nashik Market",
    })
    assert created.status_code == 201
    offer = created.json()
    offer_id = offer["id"]
    assert offer["buyer_id"] == 30
    assert offer["buyer_name"] == "Buyer Thirty Trading"
    assert offer["crop_name"] == "Onion"
    assert offer["total_offer_value"] == 5400.0

    listed = client.get("/api/buyer/offers", headers=buyer_headers)
    assert listed.status_code == 200
    assert listed.json()["total"] == 1
    assert listed.json()["items"][0]["id"] == offer_id
    retrieved = client.get(f"/api/buyer/offers/{offer_id}", headers=buyer_headers)
    assert retrieved.status_code == 200
    assert retrieved.json()["id"] == offer_id

    assert client.get(f"/api/buyer/offers/{offer_id}", headers=other_buyer_headers).status_code == 404
    assert client.delete(f"/api/buyer/offers/{offer_id}", headers=other_buyer_headers).status_code == 404
    assert isolated_lot_database.get(BuyerOfferModel, offer_id).status == OfferStatus.ACTIVE
    withdrawn = client.delete(f"/api/buyer/offers/{offer_id}", headers=buyer_headers)
    assert withdrawn.status_code == 200
    assert withdrawn.json()["status"] == "WITHDRAWN"


def test_farmer_accepts_owned_offer_and_creates_transaction_ready_request(isolated_lot_database):
    buyer_headers = {
        "Authorization": f"Bearer {create_access_token(subject=30, role=UserRole.BUYER.value)}"
    }
    farmer_headers = _farmer_headers(10)
    other_farmer_headers = _farmer_headers(20)
    created = client.post("/api/buyer/offers", headers=buyer_headers, json={
        "lot_id": 101,
        "offered_price_per_unit": 2700,
        "quantity_requested": 2,
        "delivery_location": "Nashik Market",
    })
    assert created.status_code == 201
    offer_id = created.json()["id"]

    forbidden_owner = client.post(f"/api/farmer/offers/{offer_id}/accept", headers=other_farmer_headers)
    assert forbidden_owner.status_code == 404
    accepted = client.post(f"/api/farmer/offers/{offer_id}/accept", headers=farmer_headers)
    assert accepted.status_code == 200
    body = accepted.json()
    assert body["offer"]["status"] == "ACCEPTED"
    assert body["selling_request"]["status"] == "ACCEPTED"
    assert body["selling_request"]["buyer_offer_id"] == offer_id
    assert isolated_lot_database.get(FarmerLot, 101).status == LotStatus.COMMITTED

    duplicate = client.post(f"/api/farmer/offers/{offer_id}/accept", headers=farmer_headers)
    assert duplicate.status_code == 409
    assert isolated_lot_database.query(SellingRequestModel).filter_by(buyer_offer_id=offer_id).count() == 1


def test_offer_acceptance_rejects_unverified_buyer_and_rolls_back(isolated_lot_database):
    buyer_headers = {
        "Authorization": f"Bearer {create_access_token(subject=77, role=UserRole.BUYER.value)}"
    }
    farmer_headers = _farmer_headers(10)
    isolated_lot_database.add(BuyerProfileModel(
        id=77, user_id=77, business_name="Verified Buyer", state="Maharashtra",
        district="Nashik", market_address="Nashik", verification_status=BuyerVerificationStatus.VERIFIED,
    ))
    isolated_lot_database.commit()
    created = client.post("/api/buyer/offers", headers=buyer_headers, json={
        "lot_id": 101, "offered_price_per_unit": 2700, "quantity_requested": 2,
        "delivery_location": "Nashik Market",
    })
    assert created.status_code == 201
    offer_id = created.json()["id"]
    isolated_lot_database.get(BuyerProfileModel, 77).verification_status = BuyerVerificationStatus.PENDING
    isolated_lot_database.commit()

    rejected = client.post(f"/api/farmer/offers/{offer_id}/accept", headers=farmer_headers)
    assert rejected.status_code == 409
    assert isolated_lot_database.get(BuyerOfferModel, offer_id).status == OfferStatus.ACTIVE
    assert isolated_lot_database.get(FarmerLot, 101).status == LotStatus.AVAILABLE
    assert isolated_lot_database.query(SellingRequestModel).count() == 0


def _seed_accepted_transaction_request(db, request_id=2001, request_status=SellingRequestStatus.ACCEPTED):
    db.get(FarmerLot, 101).status = LotStatus.COMMITTED
    db.add(SellingRequestModel(
        id=request_id,
        request_code=f"REQ-TEST-{request_id}",
        farmer_id=10,
        buyer_id=30,
        lot_id=101,
        quantity=Decimal("4.000"),
        quantity_unit="quintal",
        proposed_price=Decimal("2450.00"),
        price_unit="INR/quintal",
        estimated_gross_amount=Decimal("9800.00"),
        estimated_transport_cost=Decimal("100.00"),
        estimated_other_charges=Decimal("25.00"),
        estimated_net_realization=Decimal("9675.00"),
        status=request_status,
    ))
    db.commit()


def test_database_backed_transaction_lifecycle_and_participant_access(isolated_lot_database):
    _seed_accepted_transaction_request(isolated_lot_database)
    farmer_headers = _farmer_headers()
    buyer_headers = {
        "Authorization": f"Bearer {create_access_token(subject=30, role=UserRole.BUYER.value)}"
    }
    outsider_headers = {
        "Authorization": f"Bearer {create_access_token(subject=77, role=UserRole.BUYER.value)}"
    }

    created = client.post("/api/transactions", headers=farmer_headers, json={
        "selling_request_id": 2001, "payment_method": "UPI", "notes": "Agreed at mandi",
    })
    assert created.status_code == 201
    receipt = created.json()
    assert receipt["transaction_id"].startswith("TXN-")
    assert receipt["request_code"] == "REQ-TEST-2001"
    assert receipt["farmer_name"] == "Farmer Ten"
    assert receipt["buyer_name"] == "Buyer Thirty"
    assert receipt["crop_name"] == "Onion"
    assert receipt["gross_amount"] == 9800.0
    assert receipt["net_amount"] == 9675.0
    assert receipt["transaction_status"] == "CONFIRMED"
    assert receipt["payment_status"] == "PENDING"
    assert receipt["payment_method"] == "UPI"

    transaction_id = receipt["id"]
    repository = DefaultPostgresTransactionRepository()
    assert repository.get_by_reference(isolated_lot_database, receipt["transaction_id"])["id"] == transaction_id
    assert repository.get_by_selling_request_id(isolated_lot_database, 2001)["id"] == transaction_id
    assert client.post("/api/transactions", headers=buyer_headers, json={
        "selling_request_id": 2001,
    }).status_code == 409
    assert client.get(f"/api/transactions/{transaction_id}", headers=buyer_headers).status_code == 200
    assert client.get(f"/api/transactions/{transaction_id}", headers=outsider_headers).status_code == 403

    farmer_list = client.get("/api/transactions", headers=farmer_headers)
    buyer_list = client.get("/api/transactions", headers=buyer_headers)
    assert farmer_list.status_code == buyer_list.status_code == 200
    assert farmer_list.json()["total"] == buyer_list.json()["total"] == 1
    admin_headers = {
        "Authorization": f"Bearer {create_access_token(subject=1, role=UserRole.ADMIN.value)}"
    }
    admin_list = client.get("/api/admin/transactions", headers=admin_headers)
    assert admin_list.status_code == 200
    assert admin_list.json()["total"] == 1

    assert client.put(f"/api/transactions/{transaction_id}/status", headers=outsider_headers,
                      json={"transaction_status": "DELIVERED"}).status_code == 403
    farmer_payment = client.put(f"/api/transactions/{transaction_id}/status", headers=farmer_headers,
                                json={"payment_status": "PAID"})
    assert farmer_payment.status_code == 403

    in_transit = client.put(f"/api/transactions/{transaction_id}/status", headers=farmer_headers,
                            json={"transaction_status": "IN_TRANSIT"})
    assert in_transit.status_code == 200
    assert in_transit.json()["transaction_status"] == "IN_TRANSIT"
    buyer_update = client.put(f"/api/transactions/{transaction_id}/status", headers=buyer_headers,
                              json={"transaction_status": "DELIVERED", "payment_status": "PAYMENT_INITIATED",
                                    "notes": "Delivery received"})
    assert buyer_update.status_code == 200
    assert buyer_update.json()["transaction_status"] == "DELIVERED"
    assert buyer_update.json()["payment_status"] == "PAYMENT_INITIATED"
    assert buyer_update.json()["notes"] == "Delivery received"


def test_transaction_creation_rejects_unaccepted_request(isolated_lot_database):
    _seed_accepted_transaction_request(
        isolated_lot_database, request_id=2002, request_status=SellingRequestStatus.PENDING
    )
    response = client.post("/api/transactions", headers=_farmer_headers(), json={
        "selling_request_id": 2002,
    })
    assert response.status_code == 400
    assert isolated_lot_database.query(TransactionModel).count() == 0


def test_transaction_repository_database_error_rolls_back():
    class FailingSession:
        def __init__(self):
            self.rollback_count = 0

        def execute(self, statement):
            raise OperationalError("SELECT", {}, RuntimeError("database unavailable"))

        def rollback(self):
            self.rollback_count += 1

    session = FailingSession()
    with pytest.raises(OperationalError):
        DefaultPostgresTransactionRepository().get_transaction_by_id(session, 1)
    assert session.rollback_count == 1


def test_database_backed_complaint_create_retrieve_list_and_admin_resolution(isolated_lot_database):
    _seed_accepted_transaction_request(isolated_lot_database, request_id=2011)
    transaction = client.post("/api/transactions", headers=_farmer_headers(), json={
        "selling_request_id": 2011,
    })
    assert transaction.status_code == 201
    transaction_id = transaction.json()["id"]

    farmer_headers = _farmer_headers()
    buyer_headers = {
        "Authorization": f"Bearer {create_access_token(subject=30, role=UserRole.BUYER.value)}"
    }
    outsider_headers = {
        "Authorization": f"Bearer {create_access_token(subject=77, role=UserRole.BUYER.value)}"
    }
    payload = {
        "transaction_id": transaction_id,
        "issue_type": "PAYMENT_ISSUE",
        "title": "Payment not received",
        "description": "The agreed payment has not reached my account.",
    }
    created = client.post("/api/complaints", headers=farmer_headers, json=payload)
    assert created.status_code == 201
    complaint = created.json()
    assert complaint["ticket_number"].startswith("CMP-")
    assert complaint["complainant_user_id"] == 10
    assert complaint["complainant_name"] == "Farmer Ten"
    assert complaint["complainant_role"] == "FARMER"
    assert complaint["transaction_code"] == transaction.json()["transaction_id"]
    assert complaint["against_user_id"] == 30
    assert complaint["against_user_name"] == "Buyer Thirty"
    assert complaint["status"] == "OPEN"

    complaint_id = complaint["id"]
    listing = client.get("/api/complaints", headers=farmer_headers)
    assert listing.status_code == 200
    assert listing.json()["total"] == 1
    assert listing.json()["items"][0]["id"] == complaint_id
    assert client.get("/api/complaints", headers=buyer_headers).json()["total"] == 0
    assert client.get(f"/api/complaints/{complaint_id}", headers=buyer_headers).status_code == 200
    assert client.get(f"/api/complaints/{complaint_id}", headers=outsider_headers).status_code == 403

    admin_headers = {
        "Authorization": f"Bearer {create_access_token(subject=1, role=UserRole.ADMIN.value)}"
    }
    assert client.put(f"/api/admin/complaints/{complaint_id}/status", headers=farmer_headers,
                      json={"status": "RESOLVED"}).status_code == 403
    resolved = client.put(f"/api/admin/complaints/{complaint_id}/status", headers=admin_headers, json={
        "status": "RESOLVED", "admin_notes": "Verified settlement records",
        "resolution_summary": "Payment confirmed by the bank.",
    })
    assert resolved.status_code == 200
    assert resolved.json()["status"] == "RESOLVED"
    assert resolved.json()["admin_notes"] == "Verified settlement records"
    assert resolved.json()["resolution_summary"] == "Payment confirmed by the bank."
    assert resolved.json()["resolved_at"] is not None

    admin_list = client.get("/api/admin/complaints?status=RESOLVED&issue_type=PAYMENT_ISSUE",
                            headers=admin_headers)
    assert admin_list.status_code == 200
    assert admin_list.json()["total"] == 1
    assert admin_list.json()["items"][0]["id"] == complaint_id

    repository = DefaultPostgresComplaintRepository()
    assert repository.get_by_ticket_number(isolated_lot_database, complaint["ticket_number"])["id"] == complaint_id


def test_complaint_creation_rejects_missing_transaction_and_respondent(isolated_lot_database):
    headers = _farmer_headers()
    base_payload = {
        "issue_type": "OTHER",
        "title": "General complaint",
        "description": "This complaint has a sufficiently long description.",
    }
    missing_transaction = client.post("/api/complaints", headers=headers, json={
        **base_payload, "transaction_id": 99999,
    })
    assert missing_transaction.status_code == 404

    missing_user = client.post("/api/complaints", headers=headers, json={
        **base_payload, "against_user_id": 99999,
    })
    assert missing_user.status_code == 404
    assert isolated_lot_database.query(ComplaintModel).count() == 0


def test_complaint_repository_database_error_rolls_back():
    from app.schemas.complaint import ComplaintCreate, ComplaintIssueType

    class FailingSession:
        def __init__(self):
            self.rollback_count = 0

        def get(self, model, entity_id):
            raise OperationalError("SELECT", {}, RuntimeError("database unavailable"))

        def rollback(self):
            self.rollback_count += 1

    session = FailingSession()
    with pytest.raises(OperationalError):
        DefaultPostgresComplaintRepository().create_complaint(
            session, 10, "Farmer Ten", "FARMER",
            ComplaintCreate(issue_type=ComplaintIssueType.OTHER, title="Complaint title",
                            description="Description with enough detail."),
        )
    assert session.rollback_count == 1


def test_complaint_database_error_returns_generic_500():
    class FailingSession:
        def __init__(self):
            self.rollback_count = 0

        def scalar(self, statement):
            raise OperationalError("SELECT", {}, RuntimeError("sensitive database detail"))

        def get(self, model, user_id):
            return SimpleNamespace(id=user_id, role=UserRole.FARMER, is_active=True)

        def rollback(self):
            self.rollback_count += 1

    session = FailingSession()
    app.dependency_overrides.clear()
    app.dependency_overrides[get_db] = lambda: session
    error_client = TestClient(app, raise_server_exceptions=False)
    try:
        response = error_client.get("/api/complaints", headers=_farmer_headers())
        assert response.status_code == 500
        assert response.text == "Internal Server Error"
        assert "sensitive database detail" not in response.text
        assert session.rollback_count == 1
    finally:
        app.dependency_overrides.clear()


def test_database_backed_notifications_create_list_unread_and_mark_read(isolated_lot_database):
    repo = DefaultPostgresNotificationRepository()
    farmer_notice = repo.create_notification(isolated_lot_database, NotificationCreate(
        user_id=10, notification_type=NotificationType.NEW_REQUEST,
        title="New selling request", message="A buyer sent you a request.", reference_id="REQ-NEW-1",
    ))
    second_farmer_notice = repo.create_notification(isolated_lot_database, NotificationCreate(
        user_id=10, notification_type=NotificationType.GENERAL,
        title="Profile updated", message="Your profile was updated.",
    ))
    buyer_notice = repo.create_notification(isolated_lot_database, NotificationCreate(
        user_id=30, notification_type=NotificationType.GENERAL,
        title="Buyer notice", message="This belongs to the buyer.",
    ))
    assert farmer_notice.id != second_farmer_notice.id

    farmer_headers = _farmer_headers()
    buyer_headers = {
        "Authorization": f"Bearer {create_access_token(subject=30, role=UserRole.BUYER.value)}"
    }
    assert client.get("/api/notifications").status_code == 401

    unread = client.get("/api/notifications?unread_only=true", headers=farmer_headers)
    assert unread.status_code == 200
    assert unread.json()["total"] == 2
    assert unread.json()["unread_count"] == 2
    assert {item["id"] for item in unread.json()["items"]} == {
        farmer_notice.id, second_farmer_notice.id,
    }

    wrong_owner = client.put(f"/api/notifications/{buyer_notice.id}/read", headers=farmer_headers)
    assert wrong_owner.status_code == 404
    assert isolated_lot_database.get(NotificationModel, buyer_notice.id).is_read is False

    marked = client.put(f"/api/notifications/{farmer_notice.id}/read", headers=farmer_headers)
    assert marked.status_code == 200
    assert marked.json()["is_read"] is True
    all_notices = client.get("/api/notifications", headers=farmer_headers)
    assert all_notices.json()["total"] == 2
    assert all_notices.json()["unread_count"] == 1
    unread = client.get("/api/notifications?unread_only=true", headers=farmer_headers)
    assert unread.json()["total"] == unread.json()["unread_count"] == 1

    mark_all = client.put("/api/notifications/mark-all-read", headers=farmer_headers)
    assert mark_all.status_code == 200
    assert mark_all.json()["marked_count"] == 1
    repeated = client.put("/api/notifications/mark-all-read", headers=farmer_headers)
    assert repeated.json()["marked_count"] == 0
    assert client.get("/api/notifications?unread_only=true", headers=farmer_headers).json()["total"] == 0
    assert isolated_lot_database.get(NotificationModel, buyer_notice.id).is_read is False
    assert client.get("/api/notifications", headers=buyer_headers).json()["items"][0]["id"] == buyer_notice.id


def test_notification_creation_rejects_unknown_recipient(isolated_lot_database):
    with pytest.raises(NotificationRecipientNotFoundError):
        DefaultPostgresNotificationRepository().create_notification(
            isolated_lot_database,
            NotificationCreate(
                user_id=99999, notification_type=NotificationType.GENERAL,
                title="Invalid recipient", message="This user does not exist.",
            ),
        )
    assert isolated_lot_database.query(NotificationModel).count() == 0


def test_notification_repository_database_error_rolls_back():
    class FailingSession:
        def __init__(self):
            self.rollback_count = 0

        def scalar(self, statement):
            raise OperationalError("SELECT", {}, RuntimeError("database unavailable"))

        def rollback(self):
            self.rollback_count += 1

    session = FailingSession()
    with pytest.raises(OperationalError):
        DefaultPostgresNotificationRepository().list_user_notifications(session, 10)
    assert session.rollback_count == 1


def test_notification_database_error_returns_generic_500():
    class FailingSession:
        def __init__(self):
            self.rollback_count = 0

        def scalar(self, statement):
            raise OperationalError("SELECT", {}, RuntimeError("sensitive database detail"))

        def get(self, model, user_id):
            return SimpleNamespace(id=user_id, role=UserRole.FARMER, is_active=True)

        def rollback(self):
            self.rollback_count += 1

    session = FailingSession()
    app.dependency_overrides.clear()
    app.dependency_overrides[get_db] = lambda: session
    error_client = TestClient(app, raise_server_exceptions=False)
    try:
        response = error_client.get("/api/notifications", headers=_farmer_headers())
        assert response.status_code == 500
        assert response.text == "Internal Server Error"
        assert "sensitive database detail" not in response.text
        assert session.rollback_count == 1
    finally:
        app.dependency_overrides.clear()


def test_buyer_offer_repository_database_error_rolls_back():
    class FailingSession:
        def __init__(self):
            self.rollback_count = 0

        def scalar(self, statement):
            raise OperationalError("SELECT", {}, RuntimeError("database unavailable"))

        def rollback(self):
            self.rollback_count += 1

    session = FailingSession()
    with pytest.raises(OperationalError):
        DefaultBuyerOfferRepository().list_buyer_offers(session, 30)
    assert session.rollback_count == 1


def test_buyer_offer_blocked_if_unverified():
    lot_repo = IsolatedMockLotRepo()
    offer_repo = IsolatedMockOfferRepo()
    buyer_profile_repo = IsolatedMockBuyerProfileRepo()

    # Seed an available lot
    lot_in = FarmerLotCreate(
        crop_id=1, crop_name="Onion", quantity=50.0, unit="quintal",
        quality_grade=LotQualityGrade.GRADE_A, expected_price_per_unit=2500.0,
        location_state="Maharashtra", location_district="Nashik"
    )
    lot_repo.create_lot(None, 10, "Ramesh", lot_in)

    # Buyer profile with PENDING verification
    buyer_profile = BuyerProfileResponse(
        id=1, user_id=20, full_name="Trader Suresh", email="suresh@trader.in",
        phone_number="9876543211", business_name="Suresh Agro", business_type=BuyerBusinessType.TRADER,
        state="Maharashtra", district="Nashik", market_address="Shop 10",
        verification_status=BuyerVerificationStatus.PENDING
    )
    buyer_profile_repo.profiles[20] = buyer_profile

    app.dependency_overrides[get_farmer_lot_repo] = lambda: lot_repo
    app.dependency_overrides[get_buyer_offer_repo] = lambda: offer_repo
    app.dependency_overrides[get_buyer_profile_repo] = lambda: buyer_profile_repo

    buyer_token = create_access_token(subject=20, role=UserRole.BUYER.value)

    try:
        # Attempt to create offer while PENDING -> 403 Forbidden
        res = client.post(
            "/api/buyer/offers",
            headers={"Authorization": f"Bearer {buyer_token}"},
            json={
                "lot_id": 1,
                "offered_price_per_unit": 2700.0,
                "quantity_requested": 20.0,
                "delivery_location": "Lasalgaon Mandi",
            },
        )
        assert res.status_code == 403
        assert "Only approved and verified buyers" in res.json()["detail"]

        # Now approve buyer -> VERIFIED
        buyer_profile.verification_status = BuyerVerificationStatus.VERIFIED

        # Offer quantity exceeding lot stock (50 quintals available, requested 80) -> 400 Bad Request
        res_exceed = client.post(
            "/api/buyer/offers",
            headers={"Authorization": f"Bearer {buyer_token}"},
            json={
                "lot_id": 1,
                "offered_price_per_unit": 2700.0,
                "quantity_requested": 80.0,
                "delivery_location": "Lasalgaon Mandi",
            },
        )
        assert res_exceed.status_code == 400
        assert "exceeds available lot stock" in res_exceed.json()["detail"]

        # Valid offer -> 201 Created
        res_valid = client.post(
            "/api/buyer/offers",
            headers={"Authorization": f"Bearer {buyer_token}"},
            json={
                "lot_id": 1,
                "offered_price_per_unit": 2700.0,
                "quantity_requested": 30.0,
                "delivery_location": "Lasalgaon Mandi",
            },
        )
        assert res_valid.status_code == 201
        assert res_valid.json()["total_offer_value"] == 81000.0

        # Withdraw offer
        res_del = client.delete("/api/buyer/offers/1", headers={"Authorization": f"Bearer {buyer_token}"})
        assert res_del.status_code == 200
        assert res_del.json()["status"] == "WITHDRAWN"

    finally:
        app.dependency_overrides.clear()


def test_buyer_unauthorized_offer_access():
    offer_repo = IsolatedMockOfferRepo()
    offer = BuyerOfferResponse(
        id=1, buyer_id=20, buyer_name="Buyer 20", lot_id=1, crop_name="Wheat",
        offered_price_per_unit=2500.0, price_unit="INR/quintal", quantity_requested=30.0,
        quantity_unit="quintal", total_offer_value=75000.0, pickup_included=False,
        delivery_location="Mandi", status=OfferStatus.ACTIVE
    )
    offer_repo.offers[1] = offer
    app.dependency_overrides[get_buyer_offer_repo] = lambda: offer_repo

    other_buyer_token = create_access_token(subject=77, role=UserRole.BUYER.value)

    try:
        # Other buyer cannot view Offer 1
        get_res = client.get("/api/buyer/offers/1", headers={"Authorization": f"Bearer {other_buyer_token}"})
        assert get_res.status_code == 404

        # Other buyer cannot withdraw Offer 1
        del_res = client.delete("/api/buyer/offers/1", headers={"Authorization": f"Bearer {other_buyer_token}"})
        assert del_res.status_code == 404
    finally:
        app.dependency_overrides.clear()


# ==============================================================================
# 3. Selling Request Negotiation & State Machine Tests
# ==============================================================================

def test_selling_request_negotiation_workflow():
    lot_repo = IsolatedMockLotRepo()
    req_repo = IsolatedMockSellingRequestRepo(lot_repo)

    lot_in = FarmerLotCreate(
        crop_id=1, crop_name="Wheat", quantity=40.0, unit="quintal",
        quality_grade=LotQualityGrade.GRADE_A, expected_price_per_unit=2400.0,
        location_state="Maharashtra", location_district="Nashik"
    )
    lot = lot_repo.create_lot(None, 10, "Ramesh Patil", lot_in)

    app.dependency_overrides[get_farmer_lot_repo] = lambda: lot_repo
    app.dependency_overrides[get_selling_request_repo] = lambda: req_repo

    farmer_token = create_access_token(subject=10, role=UserRole.FARMER.value)
    buyer_token = create_access_token(subject=20, role=UserRole.BUYER.value)

    try:
        # 1. Farmer initiates selling request to Buyer 20
        res_create = client.post(
            "/api/farmer/selling-requests",
            headers={"Authorization": f"Bearer {farmer_token}"},
            json={
                "lot_id": 1,
                "buyer_id": 20,
                "proposed_price": 2450.0,
                "quantity": 40.0,
                "estimated_transport_cost": 1500.0,
                "estimated_other_charges": 500.0,
            },
        )
        assert res_create.status_code == 201
        req_data = res_create.json()
        assert req_data["status"] == "PENDING"
        assert req_data["estimated_gross_amount"] == 98000.0
        assert req_data["estimated_net_realization"] == 96000.0

        # 2. Buyer views requests targeting them
        b_list = client.get("/api/buyer/requests", headers={"Authorization": f"Bearer {buyer_token}"})
        assert b_list.status_code == 200
        assert b_list.json()["total"] == 1

        # 3. Buyer accepts request -> ACCEPTED, underlying lot marked COMMITTED
        accept_res = client.post("/api/buyer/requests/1/accept", headers={"Authorization": f"Bearer {buyer_token}"})
        assert accept_res.status_code == 200
        assert accept_res.json()["status"] == "ACCEPTED"
        assert lot.status == LotStatus.COMMITTED

        # 4. Duplicate acceptance attempt -> 409 Conflict
        dup_res = client.post("/api/buyer/requests/1/accept", headers={"Authorization": f"Bearer {buyer_token}"})
        assert dup_res.status_code == 409
        assert "terminal state" in dup_res.json()["detail"]

        # 5. Cannot initiate new request on already committed lot -> 409 Conflict
        res_locked = client.post(
            "/api/farmer/selling-requests",
            headers={"Authorization": f"Bearer {farmer_token}"},
            json={
                "lot_id": 1,
                "buyer_id": 25,
                "proposed_price": 2450.0,
                "quantity": 40.0,
            },
        )
        assert res_locked.status_code == 409
        assert "unavailable, committed, or sold lot" in res_locked.json()["detail"]

    finally:
        app.dependency_overrides.clear()


def test_selling_request_rejection():
    lot_repo = IsolatedMockLotRepo()
    req_repo = IsolatedMockSellingRequestRepo(lot_repo)

    lot_in = FarmerLotCreate(
        crop_id=2, crop_name="Tomato", quantity=50.0, unit="quintal",
        quality_grade=LotQualityGrade.GRADE_B, expected_price_per_unit=1500.0,
        location_state="Maharashtra", location_district="Nashik"
    )
    lot_repo.create_lot(None, 10, "Ramesh Patil", lot_in)

    app.dependency_overrides[get_farmer_lot_repo] = lambda: lot_repo
    app.dependency_overrides[get_selling_request_repo] = lambda: req_repo

    farmer_token = create_access_token(subject=10, role=UserRole.FARMER.value)
    buyer_token = create_access_token(subject=20, role=UserRole.BUYER.value)

    try:
        # Create request
        client.post(
            "/api/farmer/selling-requests",
            headers={"Authorization": f"Bearer {farmer_token}"},
            json={"lot_id": 1, "buyer_id": 20, "proposed_price": 1600.0, "quantity": 50.0},
        )

        # Buyer rejects request with reason
        rej_res = client.post(
            "/api/buyer/requests/1/reject?notes=Price+too+high+for+grade+B",
            headers={"Authorization": f"Bearer {buyer_token}"},
        )
        assert rej_res.status_code == 200
        assert rej_res.json()["status"] == "REJECTED"
        assert "Price too high" in rej_res.json()["rejection_reason"]

    finally:
        app.dependency_overrides.clear()


def test_conflicting_selling_requests_on_same_lot():
    """
    Scenario: Farmer has 1 lot of 50 quintals.
    Farmer sends Request 1 to Buyer 20, and Request 2 to Buyer 30 while lot is AVAILABLE.
    Buyer 20 accepts Request 1 first -> transitions to ACCEPTED, lot marked COMMITTED.
    Buyer 30 subsequently attempts to accept Request 2 -> fails with 409 Conflict.
    """
    lot_repo = IsolatedMockLotRepo()
    req_repo = IsolatedMockSellingRequestRepo(lot_repo)

    lot_in = FarmerLotCreate(
        crop_id=3, crop_name="Soybean", quantity=50.0, unit="quintal",
        quality_grade=LotQualityGrade.GRADE_A, expected_price_per_unit=4200.0,
        location_state="Maharashtra", location_district="Nashik"
    )
    lot = lot_repo.create_lot(None, 10, "Ramesh Patil", lot_in)

    app.dependency_overrides[get_farmer_lot_repo] = lambda: lot_repo
    app.dependency_overrides[get_selling_request_repo] = lambda: req_repo

    farmer_token = create_access_token(subject=10, role=UserRole.FARMER.value)
    buyer20_token = create_access_token(subject=20, role=UserRole.BUYER.value)
    buyer30_token = create_access_token(subject=30, role=UserRole.BUYER.value)

    try:
        # Create Request 1 to Buyer 20
        res1 = client.post(
            "/api/farmer/selling-requests",
            headers={"Authorization": f"Bearer {farmer_token}"},
            json={"lot_id": 1, "buyer_id": 20, "proposed_price": 4200.0, "quantity": 50.0},
        )
        assert res1.status_code == 201

        # Create Request 2 to Buyer 30
        res2 = client.post(
            "/api/farmer/selling-requests",
            headers={"Authorization": f"Bearer {farmer_token}"},
            json={"lot_id": 1, "buyer_id": 30, "proposed_price": 4250.0, "quantity": 50.0},
        )
        assert res2.status_code == 201

        # Buyer 20 accepts Request 1 -> SUCCESS
        accept_res1 = client.post("/api/buyer/requests/1/accept", headers={"Authorization": f"Bearer {buyer20_token}"})
        assert accept_res1.status_code == 200
        assert accept_res1.json()["status"] == "ACCEPTED"
        assert lot.status == LotStatus.COMMITTED

        # Buyer 30 attempts to accept Request 2 on the now COMMITTED lot -> 409 Conflict
        accept_res2 = client.post("/api/buyer/requests/2/accept", headers={"Authorization": f"Bearer {buyer30_token}"})
        assert accept_res2.status_code == 409
        assert "no longer available" in accept_res2.json()["detail"]

    finally:
        app.dependency_overrides.clear()


def test_counteroffer_negotiation_action():
    """
    Scenario: Farmer proposes ₹2000/quintal.
    Farmer executes COUNTER action proposing ₹2100/quintal with 35 quintals.
    Request status becomes COUNTERED and amounts recalculate.
    """
    lot_repo = IsolatedMockLotRepo()
    req_repo = IsolatedMockSellingRequestRepo(lot_repo)

    lot_in = FarmerLotCreate(
        crop_id=1, crop_name="Onion", quantity=50.0, unit="quintal",
        quality_grade=LotQualityGrade.GRADE_A, expected_price_per_unit=2000.0,
        location_state="Maharashtra", location_district="Nashik"
    )
    lot_repo.create_lot(None, 10, "Ramesh Patil", lot_in)

    app.dependency_overrides[get_farmer_lot_repo] = lambda: lot_repo
    app.dependency_overrides[get_selling_request_repo] = lambda: req_repo

    farmer_token = create_access_token(subject=10, role=UserRole.FARMER.value)

    try:
        # Create initial request
        client.post(
            "/api/farmer/selling-requests",
            headers={"Authorization": f"Bearer {farmer_token}"},
            json={"lot_id": 1, "buyer_id": 20, "proposed_price": 2000.0, "quantity": 50.0},
        )

        # Farmer counters with ₹2100 and 35 quintals
        counter_res = client.post(
            "/api/farmer/selling-requests/1/action",
            headers={"Authorization": f"Bearer {farmer_token}"},
            json={
                "action": "COUNTER",
                "counter_price": 2100.0,
                "counter_quantity": 35.0,
                "reason_or_notes": "Revised minimum quote for immediate pickup",
            },
        )
        assert counter_res.status_code == 200
        data = counter_res.json()
        assert data["status"] == "COUNTERED"
        assert data["proposed_price"] == 2100.0
        assert data["quantity"] == 35.0
        assert data["estimated_gross_amount"] == 73500.0

    finally:
        app.dependency_overrides.clear()
