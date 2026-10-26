from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Path, Query, status
from sqlalchemy.orm import Session
from app.core.dependencies import AuthenticatedUser, get_current_user_claims
from app.core.security import UserRole
from app.database.connection import get_db
from app.schemas.complaint import (
    ComplaintCreate,
    ComplaintListResponse,
    ComplaintResponse,
    ComplaintStatus,
)
from app.schemas.notification import NotificationType
from app.schemas.transaction import PaymentStatus, TransactionStatusUpdate
from app.services.auth_service import DatabaseSchemaPendingError
from app.services.complaint_service import (
    ComplaintRepository,
    ComplaintReferenceNotFoundError,
    ComplaintWorkflowError,
    get_complaint_repo,
)
from app.services.notification_service import (
    NotificationRepository,
    dispatch_in_app_notification,
    get_notification_repo,
)
from app.services.transaction_service import (
    TransactionRepository,
    get_transaction_repo,
)

router = APIRouter(prefix="/complaints", tags=["Complaints & Disputes"])


def _record_value(record, field: str, default=None):
    if isinstance(record, dict):
        return record.get(field, default)
    return getattr(record, field, default)


@router.post(
    "",
    response_model=ComplaintResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Lodge a dispute or complaint",
)
def create_complaint(
    complaint_in: ComplaintCreate,
    current_user: AuthenticatedUser = Depends(get_current_user_claims),
    db: Session = Depends(get_db),
    complaint_repo: ComplaintRepository = Depends(get_complaint_repo),
    trans_repo: TransactionRepository = Depends(get_transaction_repo),
    notif_repo: NotificationRepository = Depends(get_notification_repo),
):
    """
    Submits a new complaint or trade dispute ticket.
    - If linked to a transaction, verifies that the complainant was a direct participant (farmer or buyer).
    - Automatically sets the against_user_id to the trade counterparty if omitted.
    - Assigns an initial OPEN status and generates a unique ticket reference.
    """
    try:
        transaction_code = None
        against_user_id = complaint_in.against_user_id
        against_user_name = None

        if complaint_in.transaction_id:
            txn = trans_repo.get_transaction_by_id(db, complaint_in.transaction_id)
            if not txn:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Transaction with ID {complaint_in.transaction_id} not found.",
                )

            # Enforce participant verification
            farmer_id = _record_value(txn, "farmer_id")
            buyer_id = _record_value(txn, "buyer_id")
            if current_user.id not in (farmer_id, buyer_id) and current_user.role != UserRole.ADMIN:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="You can only file complaints for transactions you participated in.",
                )

            transaction_code = _record_value(txn, "transaction_id")
            # Default against_user to counterparty
            if not against_user_id:
                if current_user.id == farmer_id:
                    against_user_id = buyer_id
                    against_user_name = _record_value(txn, "buyer_name", f"Buyer #{buyer_id}")
                else:
                    against_user_id = farmer_id
                    against_user_name = _record_value(txn, "farmer_name", f"Farmer #{farmer_id}")

        complainant_name = current_user.raw_payload.get("full_name", f"User #{current_user.id}")
        complainant_role = current_user.role.value if hasattr(current_user.role, "value") else str(current_user.role)

        # Mutate against_user_id if defaulted
        complaint_data = complaint_in.model_copy(update={"against_user_id": against_user_id})

        created_complaint = complaint_repo.create_complaint(
            db=db,
            complainant_id=current_user.id,
            complainant_name=complainant_name,
            complainant_role=complainant_role,
            complaint_in=complaint_data,
            transaction_code=transaction_code,
            against_user_name=against_user_name,
        )

        # Freeze transaction payment status if dispute is transaction-linked
        if complaint_in.transaction_id:
            try:
                ticket_number = _record_value(created_complaint, "ticket_number")
                trans_repo.update_transaction_status(
                    db,
                    complaint_in.transaction_id,
                    TransactionStatusUpdate(
                        payment_status=PaymentStatus.DISPUTED,
                        notes=f"Settlement placed on dispute hold under ticket {ticket_number}."
                    ),
                )
            except Exception:
                pass

        # Notify against_user if trade-linked
        if against_user_id:
            ticket_number = _record_value(created_complaint, "ticket_number")
            complaint_title = _record_value(created_complaint, "title")
            dispatch_in_app_notification(
                db=db,
                notification_repo=notif_repo,
                user_id=against_user_id,
                notification_type=NotificationType.COMPLAINT_FILED,
                title="Dispute Ticket Filed",
                message=f"Dispute ticket {ticket_number} was filed regarding trade: '{complaint_title}'.",
                reference_id=ticket_number,
            )

        return created_complaint

    except HTTPException:
        raise
    except DatabaseSchemaPendingError as e:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Database complaints schema is pending approval by Ankita: {str(e)}",
        )
    except ComplaintReferenceNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e)) from e
    except ComplaintWorkflowError as e:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(e),
        )


@router.get(
    "",
    response_model=ComplaintListResponse,
    status_code=status.HTTP_200_OK,
    summary="List complaints filed by the authenticated user",
)
def list_my_complaints(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    current_user: AuthenticatedUser = Depends(get_current_user_claims),
    db: Session = Depends(get_db),
    complaint_repo: ComplaintRepository = Depends(get_complaint_repo),
):
    """
    Retrieves all dispute and grievance tickets submitted by the authenticated user.
    """
    try:
        items, total = complaint_repo.list_user_complaints(
            db, user_id=current_user.id, skip=skip, limit=limit
        )
        return ComplaintListResponse(total=total, items=items, skip=skip, limit=limit)
    except DatabaseSchemaPendingError as e:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Database complaints schema is pending approval by Ankita: {str(e)}",
        )


@router.get(
    "/{complaint_id}",
    response_model=ComplaintResponse,
    status_code=status.HTTP_200_OK,
    summary="Retrieve complaint ticket details",
)
def get_complaint_by_id(
    complaint_id: int = Path(..., ge=1, description="Complaint ID"),
    current_user: AuthenticatedUser = Depends(get_current_user_claims),
    db: Session = Depends(get_db),
    complaint_repo: ComplaintRepository = Depends(get_complaint_repo),
):
    """
    Retrieves detailed dispute status, investigation findings, and resolution notes.
    Enforces privacy: Only the complainant, respondent, or system administrators can view the ticket.
    """
    try:
        complaint = complaint_repo.get_complaint_by_id(db, complaint_id)
        if not complaint:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Complaint with ID {complaint_id} not found.",
            )

        # Authorization check
        complainant_id = _record_value(complaint, "complainant_user_id")
        against_id = _record_value(complaint, "against_user_id")
        is_party = current_user.id in (complainant_id, against_id)
        is_admin = current_user.role == UserRole.ADMIN

        if not is_party and not is_admin:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You are not authorized to access this complaint ticket.",
            )

        return complaint

    except HTTPException:
        raise
    except DatabaseSchemaPendingError as e:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Database complaints schema is pending approval by Ankita: {str(e)}",
        )
