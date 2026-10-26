"""Focused endpoint tests for Module 8 using test-only repository doubles."""

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.core.security import UserRole, create_access_token
from app.database.base import Base
from app.database.connection import get_db
from app.models.entities import User
from app.main import app as production_app
from app.routes.admin import router as admin_router
from app.routes.complaints import router as complaints_router
from app.routes.notifications import router as notifications_router
from app.routes.transactions import router as transactions_router
from app.schemas.complaint import ComplaintIssueType, ComplaintStatus
from app.schemas.notification import NotificationType
from app.schemas.selling_request import SellingRequestStatus
from app.schemas.transaction import PaymentStatus, TransactionStatus
from app.services.complaint_service import get_complaint_repo
from app.services.notification_service import get_notification_repo
from app.services.trade_service import get_selling_request_repo
from app.services.transaction_service import get_transaction_repo


@dataclass
class SellingRequestFixture:
    id: int = 1
    farmer_id: int = 10
    farmer_name: str = "Test Farmer"
    buyer_id: int = 20
    buyer_name: str = "Test Buyer"
    status: SellingRequestStatus = SellingRequestStatus.ACCEPTED


@dataclass
class TransactionFixture:
    id: int = 1
    transaction_id: str = "TEST-TXN-001"
    selling_request_id: int = 1
    request_code: str = "TEST-REQ-001"
    farmer_id: int = 10
    farmer_name: str = "Test Farmer"
    buyer_id: int = 20
    buyer_name: str = "Test Buyer"
    crop_id: int = 3
    crop_name: str = "Test Wheat"
    quantity: float = 5
    quantity_unit: str = "quintal"
    agreed_price: float = 100
    price_unit: str = "INR/quintal"
    gross_amount: float = 500
    transport_cost: float = 10
    other_charges: float = 5
    net_amount: float = 485
    payment_status: PaymentStatus = PaymentStatus.PENDING
    transaction_status: TransactionStatus = TransactionStatus.CONFIRMED
    payment_method: str = "ESCROW"
    notes: Optional[str] = None
    created_at: datetime = datetime(2026, 1, 1, tzinfo=timezone.utc)
    updated_at: datetime = datetime(2026, 1, 1, tzinfo=timezone.utc)


@dataclass
class ComplaintFixture:
    id: int = 1
    ticket_number: str = "TEST-CMP-001"
    complainant_user_id: int = 10
    complainant_name: str = "Test Farmer"
    complainant_role: str = "FARMER"
    transaction_id: Optional[int] = 1
    transaction_code: Optional[str] = "TEST-TXN-001"
    against_user_id: Optional[int] = 20
    against_user_name: Optional[str] = "Test Buyer"
    issue_type: ComplaintIssueType = ComplaintIssueType.PAYMENT_ISSUE
    title: str = "Test payment dispute"
    description: str = "Test-only complaint fixture description."
    status: ComplaintStatus = ComplaintStatus.OPEN
    admin_notes: Optional[str] = None
    resolution_summary: Optional[str] = None
    created_at: datetime = datetime(2026, 1, 1, tzinfo=timezone.utc)
    resolved_at: Optional[datetime] = None


@dataclass
class NotificationFixture:
    id: int = 1
    user_id: int = 10
    notification_type: NotificationType = NotificationType.GENERAL
    title: str = "Test notification"
    message: str = "Test-only notification fixture."
    is_read: bool = False
    reference_id: Optional[str] = None
    created_at: datetime = datetime(2026, 1, 1, tzinfo=timezone.utc)


class SellingRequests:
    def __init__(self):
        self.items = {1: SellingRequestFixture()}

    def get_request_by_id(self, db, request_id):
        return self.items.get(request_id)


class Transactions:
    def __init__(self):
        self.items = {}

    def get_by_selling_request_id(self, db, request_id):
        return next((t for t in self.items.values() if t.selling_request_id == request_id), None)

    def create_transaction(self, db, selling_request, payment_method="ESCROW", notes=None):
        txn = TransactionFixture(
            id=len(self.items) + 1,
            selling_request_id=selling_request.id,
            payment_method=payment_method,
            notes=notes,
        )
        self.items[txn.id] = txn
        return txn

    def get_transaction_by_id(self, db, transaction_id):
        return self.items.get(transaction_id)

    def list_user_transactions(self, db, user_id, role, skip=0, limit=50):
        records = [t for t in self.items.values() if user_id in (t.farmer_id, t.buyer_id)]
        return records[skip:skip + limit], len(records)

    def update_transaction_status(self, db, transaction_id, update_in):
        txn = self.items[transaction_id]
        if update_in.transaction_status is not None:
            txn.transaction_status = update_in.transaction_status
        if update_in.payment_status is not None:
            txn.payment_status = update_in.payment_status
        return txn


class Complaints:
    def __init__(self):
        self.items = {}

    def create_complaint(self, db, complainant_id, complainant_name, complainant_role,
                         complaint_in, transaction_code=None, against_user_name=None):
        complaint = ComplaintFixture(
            id=len(self.items) + 1,
            complainant_user_id=complainant_id,
            complainant_name=complainant_name,
            complainant_role=complainant_role,
            transaction_id=complaint_in.transaction_id,
            transaction_code=transaction_code,
            against_user_id=complaint_in.against_user_id,
            against_user_name=against_user_name,
            issue_type=complaint_in.issue_type,
            title=complaint_in.title,
            description=complaint_in.description,
        )
        self.items[complaint.id] = complaint
        return complaint

    def get_complaint_by_id(self, db, complaint_id):
        return self.items.get(complaint_id)

    def update_complaint_admin(self, db, complaint_id, update_in):
        complaint = self.items.get(complaint_id)
        if not complaint:
            return None
        if update_in.status is not None:
            complaint.status = update_in.status
        if update_in.admin_notes is not None:
            complaint.admin_notes = update_in.admin_notes
        if update_in.resolution_summary is not None:
            complaint.resolution_summary = update_in.resolution_summary
        return complaint


class Notifications:
    def __init__(self):
        self.items = {1: NotificationFixture()}

    def list_user_notifications(self, db, user_id, unread_only=False, skip=0, limit=50):
        own = [n for n in self.items.values() if n.user_id == user_id]
        unread = sum(not n.is_read for n in own)
        filtered = [n for n in own if not unread_only or not n.is_read]
        return filtered[skip:skip + limit], len(filtered), unread

    def mark_as_read(self, db, notification_id, user_id):
        notification = self.items.get(notification_id)
        if notification is None or notification.user_id != user_id:
            return None
        notification.is_read = True
        return notification

    def mark_all_as_read(self, db, user_id):
        count = 0
        for notification in self.items.values():
            if notification.user_id == user_id and not notification.is_read:
                notification.is_read = True
                count += 1
        return count


@pytest.fixture
def module8_client():
    app = FastAPI()
    app.include_router(transactions_router, prefix="/api")
    app.include_router(complaints_router, prefix="/api")
    app.include_router(notifications_router, prefix="/api")
    app.include_router(admin_router, prefix="/api")
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine, tables=[User.__table__])
    db = Session(engine, expire_on_commit=False)
    db.add_all([
        User(id=1, email="admin@test.invalid", phone_number="9000000001", hashed_password="x", full_name="Admin", role=UserRole.ADMIN),
        User(id=10, email="farmer@test.invalid", phone_number="9000000010", hashed_password="x", full_name="Farmer", role=UserRole.FARMER),
        User(id=20, email="buyer@test.invalid", phone_number="9000000020", hashed_password="x", full_name="Buyer", role=UserRole.BUYER),
        User(id=99, email="buyer99@test.invalid", phone_number="9000000099", hashed_password="x", full_name="Buyer 99", role=UserRole.BUYER),
    ])
    db.commit()
    requests, transactions, complaints, notifications = SellingRequests(), Transactions(), Complaints(), Notifications()
    app.dependency_overrides[get_selling_request_repo] = lambda: requests
    app.dependency_overrides[get_transaction_repo] = lambda: transactions
    app.dependency_overrides[get_complaint_repo] = lambda: complaints
    app.dependency_overrides[get_notification_repo] = lambda: notifications
    app.dependency_overrides[get_db] = lambda: db
    with TestClient(app) as client:
        yield client, requests, transactions, complaints, notifications
    app.dependency_overrides.clear()
    db.close()
    engine.dispose()


def auth(role, user_id):
    return {"Authorization": f"Bearer {create_access_token(user_id, role.value)}"}


def test_transaction_created_from_accepted_request_and_duplicate_rejected(module8_client):
    client, _, _, _, _ = module8_client
    response = client.post("/api/transactions", headers=auth(UserRole.FARMER, 10),
                           json={"selling_request_id": 1, "payment_method": "UPI", "notes": "test"})
    assert response.status_code == 201
    assert response.json()["transaction_status"] == "CONFIRMED"
    assert response.json()["payment_status"] == "PENDING"
    assert response.json()["payment_method"] == "UPI"
    duplicate = client.post("/api/transactions", headers=auth(UserRole.BUYER, 20),
                            json={"selling_request_id": 1})
    assert duplicate.status_code == 409


@pytest.mark.parametrize("request_status,expected", [(SellingRequestStatus.PENDING, 400),
                                                        (SellingRequestStatus.REJECTED, 400)])
def test_transaction_rejects_unaccepted_selling_request(module8_client, request_status, expected):
    client, requests, _, _, _ = module8_client
    requests.items[1].status = request_status
    response = client.post("/api/transactions", headers=auth(UserRole.FARMER, 10),
                           json={"selling_request_id": 1})
    assert response.status_code == expected


def test_transaction_rejects_missing_request_and_nonparticipant_but_allows_admin(module8_client):
    client, _, _, _, _ = module8_client
    missing = client.post("/api/transactions", headers=auth(UserRole.FARMER, 10),
                          json={"selling_request_id": 999})
    assert missing.status_code == 404
    denied = client.post("/api/transactions", headers=auth(UserRole.BUYER, 99),
                         json={"selling_request_id": 1})
    assert denied.status_code == 403
    allowed = client.post("/api/transactions", headers=auth(UserRole.ADMIN, 1),
                          json={"selling_request_id": 1})
    assert allowed.status_code == 201


def test_transaction_receipt_is_private_to_participants_or_admin(module8_client):
    client, _, transactions, _, _ = module8_client
    transactions.items[1] = TransactionFixture()
    assert client.get("/api/transactions/1", headers=auth(UserRole.BUYER, 20)).status_code == 200
    assert client.get("/api/transactions/1", headers=auth(UserRole.BUYER, 99)).status_code == 403
    assert client.get("/api/transactions/1", headers=auth(UserRole.ADMIN, 1)).status_code == 200


def test_complaint_creation_and_transaction_participant_privacy(module8_client):
    client, _, transactions, complaints, _ = module8_client
    transactions.items[1] = TransactionFixture()
    payload = {"transaction_id": 1, "issue_type": "PAYMENT_ISSUE", "title": "Payment not received",
               "description": "Test-only details for a disputed payment."}
    created = client.post("/api/complaints", headers=auth(UserRole.FARMER, 10), json=payload)
    assert created.status_code == 201
    assert created.json()["against_user_id"] == 20
    assert created.json()["transaction_code"] == "TEST-TXN-001"
    assert complaints.items[1].status == ComplaintStatus.OPEN
    denied = client.post("/api/complaints", headers=auth(UserRole.BUYER, 99), json=payload)
    assert denied.status_code == 403


def test_complaint_details_are_private_and_admin_review_requires_admin(module8_client):
    client, _, _, complaints, _ = module8_client
    complaints.items[1] = ComplaintFixture()
    assert client.get("/api/complaints/1", headers=auth(UserRole.BUYER, 20)).status_code == 200
    assert client.get("/api/complaints/1", headers=auth(UserRole.BUYER, 99)).status_code == 403
    body = {"status": "UNDER_REVIEW", "admin_notes": "Test review", "resolution_summary": "Being reviewed"}
    denied = client.put("/api/admin/complaints/1/status", headers=auth(UserRole.FARMER, 10), json=body)
    assert denied.status_code == 403
    reviewed = client.put("/api/admin/complaints/1/status", headers=auth(UserRole.ADMIN, 1), json=body)
    assert reviewed.status_code == 200
    assert reviewed.json()["status"] == "UNDER_REVIEW"
    assert reviewed.json()["admin_notes"] == "Test review"


def test_notifications_list_and_read_are_scoped_to_authenticated_user(module8_client):
    client, _, _, _, notifications = module8_client
    notifications.items[2] = NotificationFixture(id=2, user_id=20, title="Buyer test notification")
    listing = client.get("/api/notifications", headers=auth(UserRole.FARMER, 10))
    assert listing.status_code == 200
    assert listing.json()["total"] == 1
    assert listing.json()["items"][0]["user_id"] == 10
    assert client.put("/api/notifications/2/read", headers=auth(UserRole.FARMER, 10)).status_code == 404
    read = client.put("/api/notifications/1/read", headers=auth(UserRole.FARMER, 10))
    assert read.status_code == 200
    assert read.json()["is_read"] is True


def test_module8_routers_are_mounted():
    paths = set(production_app.openapi()["paths"])
    assert "/api/transactions" in paths
    assert "/api/transactions/{transaction_id}" in paths
    assert "/api/complaints" in paths
    assert "/api/notifications" in paths

