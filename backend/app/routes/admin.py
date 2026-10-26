from decimal import Decimal
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Path, Query, status
from sqlalchemy import func, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session
from app.core.dependencies import AuthenticatedUser, require_admin
from app.core.security import UserRole
from app.database.connection import get_db
from app.models.entities import BuyerProfile, Complaint, FarmerLot, Transaction, User
from app.schemas.admin import AdminStatsResponse
from app.schemas.buyer import (
    AdminBuyerActionRequest,
    BuyerProfileResponse,
    BuyerVerificationStatus,
)
from app.schemas.complaint import (
    ComplaintIssueType,
    ComplaintListResponse,
    ComplaintResponse,
    ComplaintStatus,
    ComplaintUpdateAdmin,
)
from app.schemas.farmer import FarmerProfileResponse
from app.schemas.farmer_lot import LotStatus
from app.schemas.notification import NotificationType
from app.schemas.transaction import (
    PaymentStatus,
    TransactionListResponse,
    TransactionResponse,
    TransactionStatus,
)
from app.services.auth_service import DatabaseSchemaPendingError
from app.services.complaint_service import (
    ComplaintRepository,
    ComplaintWorkflowError,
    get_complaint_repo,
)
from app.services.notification_service import (
    NotificationRepository,
    dispatch_in_app_notification,
    get_notification_repo,
)
from app.services.profile_service import (
    BuyerProfileRepository,
    FarmerProfileRepository,
    get_buyer_profile_repo,
    get_farmer_profile_repo,
)
from app.services.transaction_service import (
    TransactionRepository,
    get_transaction_repo,
)

router = APIRouter(prefix="/admin", tags=["Admin Management"])


def _record_value(record, field: str, default=None):
    if isinstance(record, dict):
        return record.get(field, default)
    return getattr(record, field, default)


@router.get(
    "/stats",
    response_model=AdminStatsResponse,
    status_code=status.HTTP_200_OK,
    summary="Get platform aggregated metrics and KPIs",
)
def get_admin_dashboard_stats(
    current_admin: AuthenticatedUser = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """
    Returns platform-wide KPIs for the system administrator dashboard:
    - Total registered farmers and buyers
    - Pending KYC verification reviews
    - Active produce listings available on the marketplace
    - Total transaction volume in quintals (standardized unit conversion)
    - Total GMV (Gross Merchandise Value in INR)
    - Total and open dispute tickets
    """
    try:
        total_farmers = db.scalar(
            select(func.count(User.id)).where(User.role == UserRole.FARMER, User.is_active == True)
        ) or 0
        total_buyers = db.scalar(
            select(func.count(User.id)).where(User.role == UserRole.BUYER, User.is_active == True)
        ) or 0
        pending_kyc = db.scalar(
            select(func.count(BuyerProfile.id)).where(BuyerProfile.verification_status == BuyerVerificationStatus.PENDING)
        ) or 0

        active_listings = db.scalar(
            select(func.count(FarmerLot.id)).where(FarmerLot.status == LotStatus.AVAILABLE)
        ) or 0

        total_transactions = db.scalar(select(func.count(Transaction.id))) or 0
        completed_txns = db.scalars(
            select(Transaction).where(Transaction.transaction_status == TransactionStatus.COMPLETED)
        ).all()
        completed_count = len(completed_txns)

        unit_to_quintals = {
            "quintal": Decimal("1.0"),
            "quintals": Decimal("1.0"),
            "qtl": Decimal("1.0"),
            "tonne": Decimal("10.0"),
            "tonnes": Decimal("10.0"),
            "metric tonne": Decimal("10.0"),
            "kg": Decimal("0.01"),
            "kgs": Decimal("0.01"),
            "kilogram": Decimal("0.01"),
            "kilograms": Decimal("0.01"),
        }

        total_volume_quintals = Decimal("0.0")
        total_gmv = Decimal("0.0")
        for txn in completed_txns:
            unit_norm = txn.quantity_unit.strip().lower() if txn.quantity_unit else "quintal"
            factor = unit_to_quintals.get(unit_norm, Decimal("1.0"))
            total_volume_quintals += Decimal(str(txn.quantity)) * factor
            total_gmv += Decimal(str(txn.gross_amount))

        total_complaints = db.scalar(select(func.count(Complaint.id))) or 0
        open_complaints = db.scalar(
            select(func.count(Complaint.id)).where(Complaint.status == ComplaintStatus.OPEN)
        ) or 0

        return AdminStatsResponse(
            total_farmers=total_farmers,
            total_buyers=total_buyers,
            pending_kyc_buyers=pending_kyc,
            active_listings=active_listings,
            total_transactions=total_transactions,
            completed_transactions=completed_count,
            total_traded_volume_quintals=float(round(total_volume_quintals, 2)),
            total_gmv_inr=float(round(total_gmv, 2)),
            total_complaints=total_complaints,
            open_complaints=open_complaints,
        )
    except DatabaseSchemaPendingError as e:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Database schema pending: {str(e)}",
        )
    except SQLAlchemyError as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Unable to calculate admin platform statistics.",
        ) from e


@router.get(
    "/farmers",
    response_model=List[FarmerProfileResponse],
    status_code=status.HTTP_200_OK,
    summary="List all registered farmers",
)
def list_farmers_admin(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    state: Optional[str] = None,
    district: Optional[str] = None,
    current_admin: AuthenticatedUser = Depends(require_admin),
    db: Session = Depends(get_db),
    farmer_repo: FarmerProfileRepository = Depends(get_farmer_profile_repo),
):
    """Admin-only view to browse registered farmer profiles."""
    try:
        return farmer_repo.list_farmers(db, skip=skip, limit=limit, state=state, district=district)
    except DatabaseSchemaPendingError as e:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Database profile schema pending approval by Ankita: {str(e)}",
        )
    except SQLAlchemyError as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Unable to retrieve farmer profiles.",
        ) from e


@router.get(
    "/farmers/{farmer_id}",
    response_model=FarmerProfileResponse,
    status_code=status.HTTP_200_OK,
    summary="Retrieve a farmer profile by ID",
)
def get_farmer_admin(
    farmer_id: int = Path(..., ge=1, description="Farmer profile ID"),
    current_admin: AuthenticatedUser = Depends(require_admin),
    db: Session = Depends(get_db),
    farmer_repo: FarmerProfileRepository = Depends(get_farmer_profile_repo),
):
    """Admin-only retrieval of a farmer profile by profile ID."""
    try:
        farmer = farmer_repo.get_by_id(db, farmer_id)
        if farmer is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Farmer profile not found.")
        return farmer
    except DatabaseSchemaPendingError as e:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Database profile schema pending approval by Ankita: {str(e)}",
        ) from e
    except SQLAlchemyError as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Unable to retrieve farmer profile.",
        ) from e


@router.get(
    "/buyers",
    response_model=List[BuyerProfileResponse],
    status_code=status.HTTP_200_OK,
    summary="List all registered buyers",
)
def list_buyers_admin(
    status_filter: Optional[BuyerVerificationStatus] = Query(None, alias="status"),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    current_admin: AuthenticatedUser = Depends(require_admin),
    db: Session = Depends(get_db),
    buyer_repo: BuyerProfileRepository = Depends(get_buyer_profile_repo),
):
    """Admin-only view to browse buyers with optional verification status filter."""
    try:
        return buyer_repo.list_buyers(db, status=status_filter, skip=skip, limit=limit)
    except DatabaseSchemaPendingError as e:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Database profile schema pending approval by Ankita: {str(e)}",
        )
    except SQLAlchemyError as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Unable to retrieve buyer profiles.",
        ) from e


@router.get(
    "/buyers/pending",
    response_model=List[BuyerProfileResponse],
    status_code=status.HTTP_200_OK,
    summary="List buyers pending verification review",
)
def list_pending_buyers_admin(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    current_admin: AuthenticatedUser = Depends(require_admin),
    db: Session = Depends(get_db),
    buyer_repo: BuyerProfileRepository = Depends(get_buyer_profile_repo),
):
    """Admin-only view to list all buyers currently in PENDING verification status."""
    try:
        return buyer_repo.list_buyers(db, status=BuyerVerificationStatus.PENDING, skip=skip, limit=limit)
    except DatabaseSchemaPendingError as e:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Database profile schema pending approval by Ankita: {str(e)}",
        )
    except SQLAlchemyError as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Unable to retrieve pending buyer profiles.",
        ) from e


@router.put(
    "/buyers/{buyer_id}/approve",
    response_model=BuyerProfileResponse,
    status_code=status.HTTP_200_OK,
    summary="Approve and verify a buyer account",
)
def approve_buyer_admin(
    buyer_id: int,
    action_in: Optional[AdminBuyerActionRequest] = None,
    current_admin: AuthenticatedUser = Depends(require_admin),
    db: Session = Depends(get_db),
    buyer_repo: BuyerProfileRepository = Depends(get_buyer_profile_repo),
):
    """Admin-only action to approve and verify a buyer."""
    try:
        notes = action_in.notes if action_in else "Approved by Admin"
        updated = buyer_repo.update_verification_status(
            db, profile_id=buyer_id, new_status=BuyerVerificationStatus.VERIFIED, notes=notes
        )
        if not updated:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Buyer profile not found.")
        return updated
    except DatabaseSchemaPendingError as e:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Database profile schema pending approval by Ankita: {str(e)}",
        )
    except SQLAlchemyError as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Unable to update buyer verification status.",
        ) from e


@router.put(
    "/buyers/{buyer_id}/reject",
    response_model=BuyerProfileResponse,
    status_code=status.HTTP_200_OK,
    summary="Reject buyer verification application",
)
def reject_buyer_admin(
    buyer_id: int,
    action_in: Optional[AdminBuyerActionRequest] = None,
    current_admin: AuthenticatedUser = Depends(require_admin),
    db: Session = Depends(get_db),
    buyer_repo: BuyerProfileRepository = Depends(get_buyer_profile_repo),
):
    """Admin-only action to reject a buyer's verification application."""
    try:
        notes = action_in.notes if action_in else "Verification rejected"
        updated = buyer_repo.update_verification_status(
            db, profile_id=buyer_id, new_status=BuyerVerificationStatus.REJECTED, notes=notes
        )
        if not updated:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Buyer profile not found.")
        return updated
    except DatabaseSchemaPendingError as e:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Database profile schema pending approval by Ankita: {str(e)}",
        )
    except SQLAlchemyError as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Unable to update buyer verification status.",
        ) from e


@router.put(
    "/buyers/{buyer_id}/suspend",
    response_model=BuyerProfileResponse,
    status_code=status.HTTP_200_OK,
    summary="Suspend a buyer account",
)
def suspend_buyer_admin(
    buyer_id: int,
    action_in: Optional[AdminBuyerActionRequest] = None,
    current_admin: AuthenticatedUser = Depends(require_admin),
    db: Session = Depends(get_db),
    buyer_repo: BuyerProfileRepository = Depends(get_buyer_profile_repo),
):
    """Admin-only action to suspend a buyer account."""
    try:
        notes = action_in.notes if action_in else "Suspended by Admin"
        updated = buyer_repo.update_verification_status(
            db, profile_id=buyer_id, new_status=BuyerVerificationStatus.SUSPENDED, notes=notes
        )
        if not updated:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Buyer profile not found.")
        return updated
    except DatabaseSchemaPendingError as e:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Database profile schema pending approval by Ankita: {str(e)}",
        )
    except SQLAlchemyError as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Unable to update buyer verification status.",
        ) from e


# ==============================================================================
# Admin Digital Transactions Endpoints
# ==============================================================================

@router.get(
    "/transactions",
    response_model=TransactionListResponse,
    status_code=status.HTTP_200_OK,
    summary="List all digital trade transactions across platform",
)
def list_transactions_admin(
    trans_status: Optional[TransactionStatus] = Query(None, description="Filter by fulfillment status"),
    pay_status: Optional[PaymentStatus] = Query(None, description="Filter by settlement status"),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    current_admin: AuthenticatedUser = Depends(require_admin),
    db: Session = Depends(get_db),
    trans_repo: TransactionRepository = Depends(get_transaction_repo),
):
    """Admin-only view to monitor platform trade execution and settlements."""
    try:
        items, total = trans_repo.list_all_transactions(
            db, trans_status=trans_status, pay_status=pay_status, skip=skip, limit=limit
        )
        return TransactionListResponse(total=total, items=items, skip=skip, limit=limit)
    except DatabaseSchemaPendingError as e:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Database transactions schema pending approval by Ankita: {str(e)}",
        )


# ==============================================================================
# Admin Complaints & Grievance Resolution Endpoints
# ==============================================================================

@router.get(
    "/complaints",
    response_model=ComplaintListResponse,
    status_code=status.HTTP_200_OK,
    summary="List all dispute tickets across platform",
)
def list_complaints_admin(
    status_filter: Optional[ComplaintStatus] = Query(None, alias="status"),
    issue_type: Optional[ComplaintIssueType] = Query(None, alias="issue_type"),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    current_admin: AuthenticatedUser = Depends(require_admin),
    db: Session = Depends(get_db),
    complaint_repo: ComplaintRepository = Depends(get_complaint_repo),
):
    """Admin-only view to browse, filter, and inspect submitted disputes."""
    try:
        items, total = complaint_repo.list_all_complaints(
            db, status=status_filter, issue_type=issue_type, skip=skip, limit=limit
        )
        return ComplaintListResponse(total=total, items=items, skip=skip, limit=limit)
    except DatabaseSchemaPendingError as e:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Database complaints schema pending approval by Ankita: {str(e)}",
        )


@router.put(
    "/complaints/{complaint_id}/status",
    response_model=ComplaintResponse,
    status_code=status.HTTP_200_OK,
    summary="Update dispute status and record resolution findings",
)
def update_complaint_status_admin(
    update_in: ComplaintUpdateAdmin,
    complaint_id: int = Path(..., ge=1, description="Complaint ticket ID"),
    current_admin: AuthenticatedUser = Depends(require_admin),
    db: Session = Depends(get_db),
    complaint_repo: ComplaintRepository = Depends(get_complaint_repo),
    notif_repo: NotificationRepository = Depends(get_notification_repo),
):
    """
    Administrative workflow to investigate, update, and resolve dispute tickets.
    Records administrative findings and sends in-app notifications to the complainant.
    """
    try:
        updated_complaint = complaint_repo.update_complaint_admin(db, complaint_id, update_in)
        if not updated_complaint:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Complaint with ID {complaint_id} not found.",
            )

        # Dispatch notification to complainant
        complainant_id = _record_value(updated_complaint, "complainant_user_id")
        if complainant_id:
            status_value = _record_value(updated_complaint, "status")
            status_val = status_value.value if hasattr(status_value, "value") else str(status_value)
            ticket_number = _record_value(updated_complaint, "ticket_number")
            resolution_summary = _record_value(updated_complaint, "resolution_summary")
            dispatch_in_app_notification(
                db=db,
                notification_repo=notif_repo,
                user_id=complainant_id,
                notification_type=NotificationType.COMPLAINT_UPDATE,
                title=f"Dispute Ticket Status: {status_val}",
                message=f"Your dispute {ticket_number} is now {status_val}. Notes: {resolution_summary or 'Reviewed by Admin'}",
                reference_id=ticket_number,
            )

        return updated_complaint

    except HTTPException:
        raise
    except DatabaseSchemaPendingError as e:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Database complaints schema pending approval by Ankita: {str(e)}",
        )
    except ComplaintWorkflowError as e:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(e),
        )

