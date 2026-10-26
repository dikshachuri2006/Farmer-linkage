from datetime import datetime, timezone
from typing import Any, List, Optional, Protocol, Tuple
from uuid import uuid4
from sqlalchemy import desc, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, aliased
from app.core.security import UserRole
from app.models.entities import Crop, FarmerLot, SellingRequest, Transaction, User
from app.schemas.farmer_lot import LotStatus
from app.schemas.selling_request import SellingRequestStatus
from app.schemas.transaction import (
    PaymentStatus,
    TransactionStatus,
    TransactionStatusUpdate,
)


class TransactionWorkflowError(Exception):
    """Business rule or state transition violation during transaction management."""
    pass


class TransactionRepository(Protocol):
    """
    Repository interface for Digital Transaction persistence.
    Maps to Ankita's proposed `transactions` table upon schema approval.
    """
    def create_transaction(
        self,
        db: Session,
        selling_request: Any,
        payment_method: Optional[str] = "ESCROW",
        notes: Optional[str] = None,
    ) -> Any: ...

    def get_transaction_by_id(self, db: Session, transaction_id: int) -> Optional[Any]: ...

    def get_by_reference(self, db: Session, reference_code: str) -> Optional[Any]: ...

    def get_by_selling_request_id(self, db: Session, selling_request_id: int) -> Optional[Any]: ...

    def list_user_transactions(
        self, db: Session, user_id: int, role: str, skip: int = 0, limit: int = 50
    ) -> Tuple[List[Any], int]: ...

    def list_all_transactions(
        self,
        db: Session,
        trans_status: Optional[TransactionStatus] = None,
        pay_status: Optional[PaymentStatus] = None,
        skip: int = 0,
        limit: int = 50,
    ) -> Tuple[List[Any], int]: ...

    def update_transaction_status(
        self,
        db: Session,
        transaction_id: int,
        update_in: TransactionStatusUpdate,
    ) -> Any: ...


class DefaultPostgresTransactionRepository:
    """
    PostgreSQL repository for transaction receipts and status updates.
    """
    def create_transaction(
        self,
        db: Session,
        selling_request: Any,
        payment_method: Optional[str] = "ESCROW",
        notes: Optional[str] = None,
    ) -> Any:
        try:
            request_id = selling_request.get("id") if isinstance(selling_request, dict) else selling_request.id
            request = db.scalar(
                select(SellingRequest).where(SellingRequest.id == request_id).with_for_update()
            )
            if request is None:
                raise TransactionWorkflowError("Selling request not found.")
            if request.status != SellingRequestStatus.ACCEPTED:
                raise TransactionWorkflowError("Only accepted selling requests can be transacted.")
            if db.scalar(
                select(Transaction.id).where(Transaction.selling_request_id == request.id)
            ) is not None:
                raise TransactionWorkflowError("A digital transaction already exists for this selling request.")

            lot = db.scalar(
                select(FarmerLot)
                .where(FarmerLot.id == request.lot_id, FarmerLot.farmer_id == request.farmer_id)
                .with_for_update()
            )
            if lot is None or lot.status.value != "COMMITTED":
                raise TransactionWorkflowError("The accepted selling request has no committed farmer lot.")
            crop = db.get(Crop, lot.crop_id)
            farmer = db.get(User, request.farmer_id)
            buyer = db.get(User, request.buyer_id)
            if crop is None or farmer is None or buyer is None:
                raise TransactionWorkflowError("The accepted selling request has incomplete trade references.")

            transaction = Transaction(
                transaction_id=f"TXN-{datetime.now(timezone.utc):%Y%m%d}-{uuid4().hex[:12].upper()}",
                selling_request_id=request.id,
                farmer_id=request.farmer_id,
                buyer_id=request.buyer_id,
                crop_id=lot.crop_id,
                quantity=request.quantity,
                quantity_unit=request.quantity_unit,
                agreed_price=request.proposed_price,
                price_unit=request.price_unit,
                gross_amount=request.estimated_gross_amount,
                transport_cost=request.estimated_transport_cost,
                other_charges=request.estimated_other_charges,
                net_amount=request.estimated_net_realization,
                payment_status=PaymentStatus.PENDING,
                transaction_status=TransactionStatus.CONFIRMED,
                payment_method=payment_method,
                notes=notes,
            )
            db.add(transaction)
            db.flush()
            response = self._transaction_response(db, transaction.id)
            db.commit()
            return response
        except IntegrityError as error:
            db.rollback()
            constraint = getattr(getattr(error.orig, "diag", None), "constraint_name", None)
            sqlite_duplicate = "UNIQUE constraint failed: transactions.selling_request_id" in str(error.orig)
            if constraint == "uq_transactions_selling_request_id" or sqlite_duplicate:
                raise TransactionWorkflowError(
                    "A digital transaction already exists for this selling request."
                ) from error
            raise
        except Exception:
            db.rollback()
            raise

    def get_transaction_by_id(self, db: Session, transaction_id: int) -> Optional[Any]:
        try:
            return self._transaction_response(db, transaction_id)
        except Exception:
            db.rollback()
            raise

    def get_by_reference(self, db: Session, reference_code: str) -> Optional[Any]:
        try:
            row = db.execute(self._transaction_query().where(Transaction.transaction_id == reference_code)).one_or_none()
            return self._response_data(row) if row is not None else None
        except Exception:
            db.rollback()
            raise

    def get_by_selling_request_id(self, db: Session, selling_request_id: int) -> Optional[Any]:
        try:
            row = db.execute(
                self._transaction_query().where(Transaction.selling_request_id == selling_request_id)
            ).one_or_none()
            return self._response_data(row) if row is not None else None
        except Exception:
            db.rollback()
            raise

    def list_user_transactions(
        self, db: Session, user_id: int, role: str, skip: int = 0, limit: int = 50
    ) -> Tuple[List[Any], int]:
        try:
            if role == UserRole.FARMER.value:
                participant_filter = Transaction.farmer_id == user_id
            elif role == UserRole.BUYER.value:
                participant_filter = Transaction.buyer_id == user_id
            else:
                return [], 0
            total = db.scalar(select(func.count(Transaction.id)).where(participant_filter)) or 0
            rows = db.execute(
                self._transaction_query()
                .where(participant_filter)
                .order_by(desc(Transaction.created_at), desc(Transaction.id))
                .offset(skip)
                .limit(limit)
            ).all()
            return [self._response_data(row) for row in rows], total
        except Exception:
            db.rollback()
            raise

    def list_all_transactions(
        self,
        db: Session,
        trans_status: Optional[TransactionStatus] = None,
        pay_status: Optional[PaymentStatus] = None,
        skip: int = 0,
        limit: int = 50,
    ) -> Tuple[List[Any], int]:
        try:
            filters = []
            if trans_status is not None:
                filters.append(Transaction.transaction_status == trans_status)
            if pay_status is not None:
                filters.append(Transaction.payment_status == pay_status)
            total = db.scalar(select(func.count(Transaction.id)).where(*filters)) or 0
            rows = db.execute(
                self._transaction_query()
                .where(*filters)
                .order_by(desc(Transaction.created_at), desc(Transaction.id))
                .offset(skip)
                .limit(limit)
            ).all()
            return [self._response_data(row) for row in rows], total
        except Exception:
            db.rollback()
            raise

    def update_transaction_status(
        self,
        db: Session,
        transaction_id: int,
        update_in: TransactionStatusUpdate,
    ) -> Any:
        try:
            transaction = db.scalar(
                select(Transaction).where(Transaction.id == transaction_id).with_for_update()
            )
            if transaction is None:
                raise TransactionWorkflowError("Transaction not found.")

            current_status = transaction.transaction_status
            target_status = update_in.transaction_status

            if target_status is not None and target_status != current_status:
                if current_status == TransactionStatus.COMPLETED:
                    raise TransactionWorkflowError("Completed transactions cannot transition to another status.")
                if current_status == TransactionStatus.CANCELLED:
                    raise TransactionWorkflowError("Cancelled transactions cannot transition to another status.")
                transaction.transaction_status = target_status

            if update_in.payment_status is not None:
                transaction.payment_status = update_in.payment_status
            if update_in.notes is not None:
                transaction.notes = update_in.notes

            # Maintain synchronization between transaction status, selling request, and lot availability
            selling_req = db.get(SellingRequest, transaction.selling_request_id)
            if selling_req is not None:
                lot = db.get(FarmerLot, selling_req.lot_id) if selling_req.lot_id else None
                if target_status == TransactionStatus.COMPLETED:
                    selling_req.status = SellingRequestStatus.COMPLETED
                    if lot is not None:
                        lot.status = LotStatus.SOLD
                elif target_status == TransactionStatus.CANCELLED:
                    selling_req.status = SellingRequestStatus.CANCELLED
                    if lot is not None and lot.status == LotStatus.COMMITTED:
                        lot.status = LotStatus.AVAILABLE

            db.flush()
            response = self._transaction_response(db, transaction.id)
            db.commit()
            return response
        except Exception:
            db.rollback()
            raise

    @staticmethod
    def _transaction_query():
        farmer = aliased(User)
        buyer = aliased(User)
        return (
            select(Transaction, SellingRequest.request_code, farmer.full_name, buyer.full_name, Crop.name)
            .join(SellingRequest, Transaction.selling_request_id == SellingRequest.id)
            .join(farmer, Transaction.farmer_id == farmer.id)
            .join(buyer, Transaction.buyer_id == buyer.id)
            .join(Crop, Transaction.crop_id == Crop.id)
        )

    @classmethod
    def _transaction_response(cls, db: Session, transaction_id: int) -> Optional[Any]:
        row = db.execute(cls._transaction_query().where(Transaction.id == transaction_id)).one_or_none()
        return cls._response_data(row) if row is not None else None

    @staticmethod
    def _response_data(row: tuple) -> dict:
        transaction, request_code, farmer_name, buyer_name, crop_name = row
        data = {column.key: getattr(transaction, column.key) for column in Transaction.__table__.columns}
        data.update(
            request_code=request_code,
            farmer_name=farmer_name,
            buyer_name=buyer_name,
            crop_name=crop_name,
        )
        return data


_default_transaction_repo = DefaultPostgresTransactionRepository()


def get_transaction_repo() -> TransactionRepository:
    """FastAPI dependency injection for TransactionRepository."""
    return _default_transaction_repo
