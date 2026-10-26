from datetime import datetime, timezone
from typing import Any, List, Optional, Protocol, Tuple
from uuid import uuid4
from sqlalchemy import desc, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, aliased
from app.core.security import UserRole
from app.models.entities import Complaint, Transaction, User
from app.schemas.complaint import (
    ComplaintCreate,
    ComplaintIssueType,
    ComplaintResponse,
    ComplaintStatus,
    ComplaintUpdateAdmin,
)


class ComplaintWorkflowError(Exception):
    """Business rule or state transition violation during dispute/complaint management."""
    pass


class ComplaintReferenceNotFoundError(ComplaintWorkflowError):
    """A complaint references a user or transaction that does not exist."""


class ComplaintRepository(Protocol):
    """
    Repository interface for Complaints and Disputes persistence.
    Persists complaints and dispute tickets.
    """
    def create_complaint(
        self,
        db: Session,
        complainant_id: int,
        complainant_name: str,
        complainant_role: str,
        complaint_in: ComplaintCreate,
        transaction_code: Optional[str] = None,
        against_user_name: Optional[str] = None,
    ) -> Any: ...

    def get_complaint_by_id(self, db: Session, complaint_id: int) -> Optional[Any]: ...

    def get_by_ticket_number(self, db: Session, ticket_number: str) -> Optional[Any]: ...

    def list_user_complaints(
        self, db: Session, user_id: int, skip: int = 0, limit: int = 50
    ) -> Tuple[List[Any], int]: ...

    def list_all_complaints(
        self,
        db: Session,
        status: Optional[ComplaintStatus] = None,
        issue_type: Optional[ComplaintIssueType] = None,
        skip: int = 0,
        limit: int = 50,
    ) -> Tuple[List[Any], int]: ...

    def update_complaint_admin(
        self,
        db: Session,
        complaint_id: int,
        update_in: ComplaintUpdateAdmin,
    ) -> Any: ...


class DefaultPostgresComplaintRepository:
    """PostgreSQL repository for complaint tickets and administrative review."""
    def create_complaint(
        self,
        db: Session,
        complainant_id: int,
        complainant_name: str,
        complainant_role: str,
        complaint_in: ComplaintCreate,
        transaction_code: Optional[str] = None,
        against_user_name: Optional[str] = None,
    ) -> Any:
        try:
            complainant = db.get(User, complainant_id)
            if complainant is None:
                raise ComplaintReferenceNotFoundError("Complainant user not found.")

            transaction = None
            if complaint_in.transaction_id is not None:
                transaction = db.get(Transaction, complaint_in.transaction_id)
                if transaction is None:
                    raise ComplaintReferenceNotFoundError("Transaction not found.")

            against_user_id = complaint_in.against_user_id
            if against_user_id is not None and db.get(User, against_user_id) is None:
                raise ComplaintReferenceNotFoundError("Respondent user not found.")

            complaint = Complaint(
                ticket_number=f"CMP-{datetime.now(timezone.utc):%Y%m%d}-{uuid4().hex[:12].upper()}",
                complainant_user_id=complainant_id,
                transaction_id=complaint_in.transaction_id,
                against_user_id=against_user_id,
                issue_type=complaint_in.issue_type,
                title=complaint_in.title,
                description=complaint_in.description,
                status=ComplaintStatus.OPEN,
            )
            db.add(complaint)
            db.flush()
            response = self._complaint_response(db, complaint.id)
            db.commit()
            return response
        except IntegrityError as error:
            db.rollback()
            constraint = getattr(getattr(error.orig, "diag", None), "constraint_name", None)
            sqlite_ticket_conflict = "UNIQUE constraint failed: complaints.ticket_number" in str(error.orig)
            if constraint in {"complaints_ticket_number_key", "uq_complaints_ticket_number"} or sqlite_ticket_conflict:
                raise ComplaintWorkflowError("Unable to allocate a unique complaint ticket number.") from error
            raise
        except Exception:
            db.rollback()
            raise

    def get_complaint_by_id(self, db: Session, complaint_id: int) -> Optional[Any]:
        try:
            return self._complaint_response(db, complaint_id)
        except Exception:
            db.rollback()
            raise

    def get_by_ticket_number(self, db: Session, ticket_number: str) -> Optional[Any]:
        try:
            row = db.execute(
                self._complaint_query().where(Complaint.ticket_number == ticket_number)
            ).one_or_none()
            return self._response_data(row) if row is not None else None
        except Exception:
            db.rollback()
            raise

    def list_user_complaints(
        self, db: Session, user_id: int, skip: int = 0, limit: int = 50
    ) -> Tuple[List[Any], int]:
        try:
            clause = Complaint.complainant_user_id == user_id
            total = db.scalar(select(func.count(Complaint.id)).where(clause)) or 0
            rows = db.execute(
                self._complaint_query()
                .where(clause)
                .order_by(desc(Complaint.created_at), desc(Complaint.id))
                .offset(skip)
                .limit(limit)
            ).all()
            return [self._response_data(row) for row in rows], total
        except Exception:
            db.rollback()
            raise

    def list_all_complaints(
        self,
        db: Session,
        status: Optional[ComplaintStatus] = None,
        issue_type: Optional[ComplaintIssueType] = None,
        skip: int = 0,
        limit: int = 50,
    ) -> Tuple[List[Any], int]:
        try:
            filters = []
            if status is not None:
                filters.append(Complaint.status == status)
            if issue_type is not None:
                filters.append(Complaint.issue_type == issue_type)
            total = db.scalar(select(func.count(Complaint.id)).where(*filters)) or 0
            rows = db.execute(
                self._complaint_query()
                .where(*filters)
                .order_by(desc(Complaint.created_at), desc(Complaint.id))
                .offset(skip)
                .limit(limit)
            ).all()
            return [self._response_data(row) for row in rows], total
        except Exception:
            db.rollback()
            raise

    def update_complaint_admin(
        self,
        db: Session,
        complaint_id: int,
        update_in: ComplaintUpdateAdmin,
    ) -> Any:
        try:
            complaint = db.scalar(
                select(Complaint).where(Complaint.id == complaint_id).with_for_update()
            )
            if complaint is None:
                return None
            if update_in.status is not None:
                complaint.status = update_in.status
                if update_in.status in (ComplaintStatus.RESOLVED, ComplaintStatus.DISMISSED):
                    complaint.resolved_at = datetime.now(timezone.utc)
                else:
                    complaint.resolved_at = None
            if update_in.admin_notes is not None:
                complaint.admin_notes = update_in.admin_notes
            if update_in.resolution_summary is not None:
                complaint.resolution_summary = update_in.resolution_summary
            db.flush()
            response = self._complaint_response(db, complaint.id)
            db.commit()
            return response
        except Exception:
            db.rollback()
            raise

    @staticmethod
    def _complaint_query():
        complainant = aliased(User)
        respondent = aliased(User)
        return (
            select(
                Complaint,
                complainant.full_name,
                complainant.role,
                respondent.full_name,
                Transaction.transaction_id,
            )
            .join(complainant, Complaint.complainant_user_id == complainant.id)
            .outerjoin(respondent, Complaint.against_user_id == respondent.id)
            .outerjoin(Transaction, Complaint.transaction_id == Transaction.id)
        )

    @classmethod
    def _complaint_response(cls, db: Session, complaint_id: int) -> Optional[Any]:
        row = db.execute(cls._complaint_query().where(Complaint.id == complaint_id)).one_or_none()
        return cls._response_data(row) if row is not None else None

    @staticmethod
    def _response_data(row: tuple) -> dict:
        complaint, complainant_name, complainant_role, against_user_name, transaction_code = row
        data = {column.key: getattr(complaint, column.key) for column in Complaint.__table__.columns}
        data.update(
            complainant_name=complainant_name,
            complainant_role=complainant_role.value if hasattr(complainant_role, "value") else complainant_role,
            against_user_name=against_user_name,
            transaction_code=transaction_code,
        )
        return data


_default_complaint_repo = DefaultPostgresComplaintRepository()


def get_complaint_repo() -> ComplaintRepository:
    """FastAPI dependency injection for ComplaintRepository."""
    return _default_complaint_repo
