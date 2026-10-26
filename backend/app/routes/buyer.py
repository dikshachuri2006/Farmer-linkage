from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Path, Query, status
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session
from app.core.dependencies import AuthenticatedUser, require_buyer
from app.database.connection import get_db
from app.schemas.buyer import (
    BuyerProfileResponse,
    BuyerProfileUpdate,
    BuyerVerificationRequest,
    BuyerVerificationStatus,
)
from app.schemas.farmer_lot import LotStatus
from app.schemas.offer import (
    BuyerOfferCreate,
    BuyerOfferListResponse,
    BuyerOfferResponse,
    BuyerOfferUpdate,
    OfferStatus,
)
from app.schemas.notification import NotificationType
from app.schemas.selling_request import (
    RequestActionType,
    SellingRequestActionRequest,
    SellingRequestListResponse,
    SellingRequestResponse,
)
from app.services.auth_service import DatabaseSchemaPendingError
from app.services.notification_service import (
    NotificationRepository,
    dispatch_in_app_notification,
    get_notification_repo,
)
from app.services.profile_service import (
    BuyerProfileCreationDataError,
    BuyerProfileRepository,
    get_buyer_profile_repo,
)
from app.services.trade_service import (
    BuyerOfferRepository,
    FarmerLotRepository,
    SellingRequestRepository,
    TradeWorkflowError,
    get_buyer_offer_repo,
    get_farmer_lot_repo,
    get_selling_request_repo,
)

router = APIRouter(prefix="/buyer", tags=["Buyer"])


def _entity_value(record, field: str, default=None):
    if isinstance(record, dict):
        return record.get(field, default)
    return getattr(record, field, default)


# ==============================================================================
# Buyer Profile & Verification Endpoints (Preserved from Module 4)
# ==============================================================================

@router.get(
    "/profile",
    response_model=BuyerProfileResponse,
    status_code=status.HTTP_200_OK,
    summary="Get authenticated buyer profile",
)
def get_buyer_profile(
    current_user: AuthenticatedUser = Depends(require_buyer),
    db: Session = Depends(get_db),
    buyer_repo: BuyerProfileRepository = Depends(get_buyer_profile_repo),
):
    try:
        profile = buyer_repo.get_by_user_id(db, current_user.id)
        if not profile:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Buyer profile not found. Please initialize your business profile.",
            )
        return profile
    except DatabaseSchemaPendingError as e:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Database profile schema pending approval by Ankita: {str(e)}",
        )


@router.put(
    "/profile",
    response_model=BuyerProfileResponse,
    status_code=status.HTTP_200_OK,
    summary="Update authenticated buyer profile",
)
def update_buyer_profile(
    profile_update: BuyerProfileUpdate,
    current_user: AuthenticatedUser = Depends(require_buyer),
    db: Session = Depends(get_db),
    buyer_repo: BuyerProfileRepository = Depends(get_buyer_profile_repo),
):
    try:
        updated = buyer_repo.save_or_update(db, current_user.id, profile_update)
        return updated
    except BuyerProfileCreationDataError as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="business_name, state, district, and market_address are required to create a buyer profile.",
        ) from e
    except DatabaseSchemaPendingError as e:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Database profile schema pending approval by Ankita: {str(e)}",
        )


@router.post(
    "/verification",
    response_model=BuyerProfileResponse,
    status_code=status.HTTP_200_OK,
    summary="Submit license/documents for verification",
)
def submit_buyer_verification(
    verification_req: BuyerVerificationRequest,
    current_user: AuthenticatedUser = Depends(require_buyer),
    db: Session = Depends(get_db),
    buyer_repo: BuyerProfileRepository = Depends(get_buyer_profile_repo),
):
    try:
        result = buyer_repo.submit_verification(db, current_user.id, verification_req)
        if result is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Buyer profile not found. Please create your business profile first.",
            )
        return result
    except DatabaseSchemaPendingError as e:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Database profile schema pending approval by Ankita: {str(e)}",
        )
    except SQLAlchemyError as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Unable to submit buyer verification.",
        ) from e


# ==============================================================================
# Buyer Offers Endpoints
# ==============================================================================

@router.post(
    "/offers",
    response_model=BuyerOfferResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Place purchase offer on a farmer lot",
)
def create_buyer_offer(
    offer_in: BuyerOfferCreate,
    current_user: AuthenticatedUser = Depends(require_buyer),
    db: Session = Depends(get_db),
    buyer_repo: BuyerProfileRepository = Depends(get_buyer_profile_repo),
    lot_repo: FarmerLotRepository = Depends(get_farmer_lot_repo),
    offer_repo: BuyerOfferRepository = Depends(get_buyer_offer_repo),
    notification_repo: NotificationRepository = Depends(get_notification_repo),
):
    try:
        # Check buyer verification status
        buyer_profile = buyer_repo.get_by_user_id(db, current_user.id)
        verification_status = _entity_value(buyer_profile, "verification_status")
        if not buyer_profile or verification_status != BuyerVerificationStatus.VERIFIED:
            status_str = verification_status or "UNVERIFIED"
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Only approved and verified buyers can place offers. Your status is: {status_str}.",
            )

        # Check lot exists and is available
        lot = lot_repo.get_lot_by_id(db, offer_in.lot_id)
        if not lot or _entity_value(lot, "status") != LotStatus.AVAILABLE:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Target farmer lot {offer_in.lot_id} is unavailable or does not exist.",
            )

        # Check quantity requested does not exceed available lot quantity
        lot_quantity = _entity_value(lot, "quantity", 0.0)
        if offer_in.quantity_requested > lot_quantity:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Requested quantity ({offer_in.quantity_requested}) exceeds available lot stock ({lot_quantity}).",
            )

        buyer_name = _entity_value(buyer_profile, "business_name", f"Buyer #{current_user.id}")
        created_offer = offer_repo.create_offer(
            db, buyer_id=current_user.id, buyer_name=buyer_name, lot=lot, offer_in=offer_in
        )

        farmer_id = _entity_value(lot, "farmer_id")
        if farmer_id:
            crop_name = _entity_value(created_offer, "crop_name", "produce")
            offer_id = _entity_value(created_offer, "id")
            dispatch_in_app_notification(
                db,
                notification_repo,
                user_id=farmer_id,
                notification_type=NotificationType.NEW_REQUEST,
                title="New Offer Received",
                message=f"{buyer_name} has placed an offer of ₹{offer_in.offered_price_per_unit}/{offer_in.price_unit} for {offer_in.quantity_requested} {offer_in.quantity_unit} of {crop_name}.",
                reference_id=str(offer_id) if offer_id else None,
            )

        return created_offer

    except DatabaseSchemaPendingError as e:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Database offers schema pending approval by Ankita: {str(e)}",
        )
    except TradeWorkflowError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e)) from e


@router.get(
    "/offers",
    response_model=BuyerOfferListResponse,
    status_code=status.HTTP_200_OK,
    summary="List offers made by authenticated buyer",
)
def list_buyer_offers(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    current_user: AuthenticatedUser = Depends(require_buyer),
    db: Session = Depends(get_db),
    offer_repo: BuyerOfferRepository = Depends(get_buyer_offer_repo),
):
    try:
        items, total = offer_repo.list_buyer_offers(db, current_user.id, skip=skip, limit=limit)
        return BuyerOfferListResponse(total=total, items=items, skip=skip, limit=limit)
    except DatabaseSchemaPendingError as e:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Database offers schema pending approval by Ankita: {str(e)}",
        )


@router.get(
    "/offers/{offer_id}",
    response_model=BuyerOfferResponse,
    status_code=status.HTTP_200_OK,
    summary="Retrieve buyer offer by ID",
)
def get_buyer_offer_by_id(
    offer_id: int = Path(..., ge=1),
    current_user: AuthenticatedUser = Depends(require_buyer),
    db: Session = Depends(get_db),
    offer_repo: BuyerOfferRepository = Depends(get_buyer_offer_repo),
):
    try:
        offer = offer_repo.get_offer_by_id(db, offer_id)
        if not offer or _entity_value(offer, "buyer_id") != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Offer with ID {offer_id} not found in your account.",
            )
        return offer
    except DatabaseSchemaPendingError as e:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Database offers schema pending approval by Ankita: {str(e)}",
        )


@router.delete(
    "/offers/{offer_id}",
    response_model=BuyerOfferResponse,
    status_code=status.HTTP_200_OK,
    summary="Withdraw/cancel a buyer offer",
)
def withdraw_buyer_offer(
    offer_id: int = Path(..., ge=1),
    current_user: AuthenticatedUser = Depends(require_buyer),
    db: Session = Depends(get_db),
    offer_repo: BuyerOfferRepository = Depends(get_buyer_offer_repo),
):
    try:
        offer = offer_repo.get_offer_by_id(db, offer_id)
        if not offer or _entity_value(offer, "buyer_id") != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Offer with ID {offer_id} not found in your account.",
            )
        if _entity_value(offer, "status") == OfferStatus.ACCEPTED:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Cannot withdraw an offer that has already been accepted into a trade agreement.",
            )
        withdrawn = offer_repo.withdraw_offer(db, offer_id, current_user.id)
        return withdrawn
    except DatabaseSchemaPendingError as e:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Database offers schema pending approval by Ankita: {str(e)}",
        )


# ==============================================================================
# Buyer Selling Requests & Negotiation Responses
# ==============================================================================

@router.get(
    "/requests",
    response_model=SellingRequestListResponse,
    status_code=status.HTTP_200_OK,
    summary="List selling requests received from farmers",
)
def list_buyer_selling_requests(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    current_user: AuthenticatedUser = Depends(require_buyer),
    db: Session = Depends(get_db),
    request_repo: SellingRequestRepository = Depends(get_selling_request_repo),
):
    try:
        items, total = request_repo.list_buyer_requests(db, current_user.id, skip=skip, limit=limit)
        return SellingRequestListResponse(total=total, items=items, skip=skip, limit=limit)
    except DatabaseSchemaPendingError as e:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Database requests schema pending approval by Ankita: {str(e)}",
        )


@router.get(
    "/requests/{request_id}",
    response_model=SellingRequestResponse,
    status_code=status.HTTP_200_OK,
    summary="Retrieve selling request details",
)
def get_buyer_selling_request_by_id(
    request_id: int = Path(..., ge=1),
    current_user: AuthenticatedUser = Depends(require_buyer),
    db: Session = Depends(get_db),
    request_repo: SellingRequestRepository = Depends(get_selling_request_repo),
):
    try:
        req = request_repo.get_request_by_id(db, request_id, buyer_id=current_user.id)
        if not req:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Selling request with ID {request_id} not found.",
            )
        return req
    except DatabaseSchemaPendingError as e:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Database requests schema pending approval by Ankita: {str(e)}",
        )


@router.post(
    "/requests/{request_id}/accept",
    response_model=SellingRequestResponse,
    status_code=status.HTTP_200_OK,
    summary="Accept farmer selling request",
)
def accept_buyer_selling_request(
    request_id: int = Path(..., ge=1),
    current_user: AuthenticatedUser = Depends(require_buyer),
    db: Session = Depends(get_db),
    request_repo: SellingRequestRepository = Depends(get_selling_request_repo),
):
    try:
        req = request_repo.get_request_by_id(db, request_id, buyer_id=current_user.id)
        if not req:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Selling request with ID {request_id} not found.",
            )
        action_in = SellingRequestActionRequest(action=RequestActionType.ACCEPT)
        updated = request_repo.execute_action(
            db, request_id, current_user.id, "BUYER", action_in
        )
        return updated
    except TradeWorkflowError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))
    except DatabaseSchemaPendingError as e:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Database requests schema pending approval by Ankita: {str(e)}",
        )


@router.post(
    "/requests/{request_id}/reject",
    response_model=SellingRequestResponse,
    status_code=status.HTTP_200_OK,
    summary="Reject farmer selling request",
)
def reject_buyer_selling_request(
    request_id: int = Path(..., ge=1),
    notes: Optional[str] = Query(None, description="Reason for rejection"),
    current_user: AuthenticatedUser = Depends(require_buyer),
    db: Session = Depends(get_db),
    request_repo: SellingRequestRepository = Depends(get_selling_request_repo),
):
    try:
        req = request_repo.get_request_by_id(db, request_id, buyer_id=current_user.id)
        if not req:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Selling request with ID {request_id} not found.",
            )
        action_in = SellingRequestActionRequest(
            action=RequestActionType.REJECT, reason_or_notes=notes or "Declined by buyer."
        )
        updated = request_repo.execute_action(
            db, request_id, current_user.id, "BUYER", action_in
        )
        return updated
    except TradeWorkflowError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))
    except DatabaseSchemaPendingError as e:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Database requests schema pending approval by Ankita: {str(e)}",
        )
