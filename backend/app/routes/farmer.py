from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Path, Query, status
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session
from app.core.dependencies import AuthenticatedUser, require_farmer
from app.database.connection import get_db
from app.schemas.farmer import FarmerProfileResponse, FarmerProfileUpdate
from app.schemas.farmer_lot import (
    FarmerLotCreate,
    FarmerLotListResponse,
    FarmerLotResponse,
    FarmerLotUpdate,
    LotStatus,
)
from app.schemas.notification import NotificationType
from app.schemas.offer import BuyerOfferResponse
from app.schemas.selling_request import (
    OfferAcceptanceResponse,
    SellingRequestActionRequest,
    SellingRequestCreate,
    SellingRequestListResponse,
    SellingRequestResponse,
)
from app.services.notification_service import (
    NotificationRepository,
    dispatch_in_app_notification,
    get_notification_repo,
)
from app.services.profile_service import (
    FarmerProfileCreationDataError,
    FarmerProfileRepository,
    get_farmer_profile_repo,
)
from app.services.trade_service import (
    BuyerNotFoundError,
    BuyerOfferRepository,
    CropNotFoundError,
    FarmerLotRepository,
    SellingRequestRepository,
    TradeWorkflowError,
    get_buyer_offer_repo,
    get_farmer_lot_repo,
    get_selling_request_repo,
)

router = APIRouter(prefix="/farmer", tags=["Farmer"])


def _value(record, field: str, default=None):
    """Read a projected repository mapping or an ORM-style object uniformly."""
    if isinstance(record, dict):
        return record.get(field, default)
    return getattr(record, field, default)


# ==============================================================================
# Farmer Profile Endpoints (Preserved from Module 4)
# ==============================================================================

@router.get(
    "/profile",
    response_model=FarmerProfileResponse,
    status_code=status.HTTP_200_OK,
    summary="Get authenticated farmer profile",
)
def get_farmer_profile(
    current_user: AuthenticatedUser = Depends(require_farmer),
    db: Session = Depends(get_db),
    farmer_repo: FarmerProfileRepository = Depends(get_farmer_profile_repo),
):
    profile = farmer_repo.get_by_user_id(db, current_user.id)
    if not profile:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Farmer profile not found. Please initialize your profile.",
        )
    return profile


@router.put(
    "/profile",
    response_model=FarmerProfileResponse,
    status_code=status.HTTP_200_OK,
    summary="Update authenticated farmer profile",
)
def update_farmer_profile(
    profile_update: FarmerProfileUpdate,
    current_user: AuthenticatedUser = Depends(require_farmer),
    db: Session = Depends(get_db),
    farmer_repo: FarmerProfileRepository = Depends(get_farmer_profile_repo),
):
    try:
        updated = farmer_repo.save_or_update(db, current_user.id, profile_update)
    except FarmerProfileCreationDataError as error:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="state, district, and a six-digit pincode are required to create a farmer profile.",
        ) from error
    if updated is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Farmer profile not found. Please initialize your profile.",
        )
    return updated


# ==============================================================================
# Farmer Crop Lots Endpoints
# ==============================================================================

@router.post(
    "/lots",
    response_model=FarmerLotResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new harvest crop lot for sale",
)
def create_farmer_lot(
    lot_in: FarmerLotCreate,
    current_user: AuthenticatedUser = Depends(require_farmer),
    db: Session = Depends(get_db),
    lot_repo: FarmerLotRepository = Depends(get_farmer_lot_repo),
):
    try:
        farmer_name = current_user.raw_payload.get("full_name", f"Farmer #{current_user.id}")
        created_lot = lot_repo.create_lot(db, current_user.id, farmer_name, lot_in)
        return created_lot
    except CropNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Crop not found.",
        ) from e
    except TradeWorkflowError as e:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(e),
        ) from e


@router.get(
    "/lots",
    response_model=FarmerLotListResponse,
    status_code=status.HTTP_200_OK,
    summary="List authenticated farmer's crop lots",
)
def list_farmer_lots(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    current_user: AuthenticatedUser = Depends(require_farmer),
    db: Session = Depends(get_db),
    lot_repo: FarmerLotRepository = Depends(get_farmer_lot_repo),
):
    items, total = lot_repo.list_farmer_lots(db, current_user.id, skip=skip, limit=limit)
    return FarmerLotListResponse(total=total, items=items, skip=skip, limit=limit)


@router.get(
    "/lots/{lot_id}",
    response_model=FarmerLotResponse,
    status_code=status.HTTP_200_OK,
    summary="Retrieve farmer lot by ID",
)
def get_farmer_lot_by_id(
    lot_id: int = Path(..., ge=1),
    current_user: AuthenticatedUser = Depends(require_farmer),
    db: Session = Depends(get_db),
    lot_repo: FarmerLotRepository = Depends(get_farmer_lot_repo),
):
    lot = lot_repo.get_lot_by_id(db, lot_id, farmer_id=current_user.id)
    if not lot:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Lot with ID {lot_id} not found in your inventory.",
        )
    return lot


@router.put(
    "/lots/{lot_id}",
    response_model=FarmerLotResponse,
    status_code=status.HTTP_200_OK,
    summary="Update farmer lot",
)
def update_farmer_lot(
    lot_update: FarmerLotUpdate,
    lot_id: int = Path(..., ge=1),
    current_user: AuthenticatedUser = Depends(require_farmer),
    db: Session = Depends(get_db),
    lot_repo: FarmerLotRepository = Depends(get_farmer_lot_repo),
):
    try:
        lot = lot_repo.get_lot_by_id(db, lot_id, farmer_id=current_user.id)
        if not lot:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Lot with ID {lot_id} not found in your inventory.",
            )
        if _value(lot, "status") in [LotStatus.COMMITTED, LotStatus.SOLD]:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Cannot update a lot that is already committed or sold in a transaction.",
            )
        if lot_update.status in [LotStatus.COMMITTED, LotStatus.SOLD]:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Lot status is managed by the selling workflow.",
            )
        updated = lot_repo.update_lot(db, lot_id, current_user.id, lot_update)
        if updated is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Lot not found in your inventory.")
        return updated
    except TradeWorkflowError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e)) from e


@router.delete(
    "/lots/{lot_id}",
    response_model=FarmerLotResponse,
    status_code=status.HTTP_200_OK,
    summary="Withdraw/deactivate a crop lot",
)
def withdraw_farmer_lot(
    lot_id: int = Path(..., ge=1),
    current_user: AuthenticatedUser = Depends(require_farmer),
    db: Session = Depends(get_db),
    lot_repo: FarmerLotRepository = Depends(get_farmer_lot_repo),
):
    try:
        lot = lot_repo.get_lot_by_id(db, lot_id, farmer_id=current_user.id)
        if not lot:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Lot with ID {lot_id} not found in your inventory.",
            )
        if _value(lot, "status") in [LotStatus.COMMITTED, LotStatus.SOLD]:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Cannot withdraw a lot that is already committed or sold in a transaction.",
            )
        withdrawn = lot_repo.withdraw_lot(db, lot_id, current_user.id)
        if withdrawn is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Lot not found in your inventory.")
        return withdrawn
    except TradeWorkflowError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e)) from e


@router.get(
    "/lots/{lot_id}/offers",
    response_model=List[BuyerOfferResponse],
    status_code=status.HTTP_200_OK,
    summary="View buyer offers received on farmer lot",
)
def get_offers_on_farmer_lot(
    lot_id: int = Path(..., ge=1),
    current_user: AuthenticatedUser = Depends(require_farmer),
    db: Session = Depends(get_db),
    lot_repo: FarmerLotRepository = Depends(get_farmer_lot_repo),
    offer_repo: BuyerOfferRepository = Depends(get_buyer_offer_repo),
):
    lot = lot_repo.get_lot_by_id(db, lot_id, farmer_id=current_user.id)
    if not lot:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Lot with ID {lot_id} not found in your inventory.",
        )
    return offer_repo.list_offers_for_lot(db, lot_id, current_user.id)


@router.post(
    "/offers/{offer_id}/accept",
    response_model=OfferAcceptanceResponse,
    status_code=status.HTTP_200_OK,
    summary="Accept a buyer offer on an owned farmer lot",
)
def accept_buyer_offer(
    offer_id: int = Path(..., ge=1),
    current_user: AuthenticatedUser = Depends(require_farmer),
    db: Session = Depends(get_db),
    offer_repo: BuyerOfferRepository = Depends(get_buyer_offer_repo),
    notification_repo: NotificationRepository = Depends(get_notification_repo),
):
    try:
        result = offer_repo.accept_offer(db, offer_id, current_user.id)
    except TradeWorkflowError as error:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(error)) from error
    except SQLAlchemyError as error:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Offer acceptance is temporarily unavailable.",
        ) from error
    if result is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Buyer offer not found on your inventory.")

    buyer_id = result.get("offer", {}).get("buyer_id")
    request_code = result.get("selling_request", {}).get("request_code", "")
    if buyer_id:
        dispatch_in_app_notification(
            db,
            notification_repo,
            user_id=buyer_id,
            notification_type=NotificationType.REQUEST_ACCEPTED,
            title="Offer Accepted by Farmer",
            message=f"Your offer #{offer_id} was accepted. A transaction request {request_code} has been created.",
            reference_id=str(offer_id),
        )

    return result


@router.post(
    "/offers/{offer_id}/reject",
    response_model=BuyerOfferResponse,
    status_code=status.HTTP_200_OK,
    summary="Decline a buyer offer on an owned farmer lot",
)
def reject_buyer_offer(
    offer_id: int = Path(..., ge=1),
    reason: Optional[str] = Query(None, max_length=200, description="Reason for declining offer"),
    current_user: AuthenticatedUser = Depends(require_farmer),
    db: Session = Depends(get_db),
    offer_repo: BuyerOfferRepository = Depends(get_buyer_offer_repo),
    notification_repo: NotificationRepository = Depends(get_notification_repo),
):
    try:
        result = offer_repo.reject_offer(db, offer_id, current_user.id, reason=reason)
    except TradeWorkflowError as error:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(error)) from error
    except SQLAlchemyError as error:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Offer rejection is temporarily unavailable.",
        ) from error
    if result is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Buyer offer not found on your inventory.")

    buyer_id = result.get("buyer_id")
    if buyer_id:
        dispatch_in_app_notification(
            db,
            notification_repo,
            user_id=buyer_id,
            notification_type=NotificationType.REQUEST_REJECTED,
            title="Offer Declined",
            message=f"Your offer #{offer_id} was declined by the farmer." + (f" Reason: {reason}" if reason else ""),
            reference_id=str(offer_id),
        )

    return result


# ==============================================================================
# Farmer Selling Requests & Negotiation Endpoints
# ==============================================================================

@router.post(
    "/selling-requests",
    response_model=SellingRequestResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Initiate a selling request addressed to a buyer user ID",
)
def create_selling_request(
    req_in: SellingRequestCreate,
    current_user: AuthenticatedUser = Depends(require_farmer),
    db: Session = Depends(get_db),
    lot_repo: FarmerLotRepository = Depends(get_farmer_lot_repo),
    request_repo: SellingRequestRepository = Depends(get_selling_request_repo),
):
    try:
        lot = lot_repo.get_lot_by_id(db, req_in.lot_id, farmer_id=current_user.id)
        if not lot:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Lot not found in your inventory.",
            )
        if _value(lot, "status") != LotStatus.AVAILABLE:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Cannot initiate request on an unavailable, committed, or sold lot.",
            )
        if req_in.quantity > _value(lot, "quantity", 0.0):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Requested quantity ({req_in.quantity}) exceeds available lot stock ({_value(lot, 'quantity', 0.0)}).",
            )
        farmer_name = current_user.raw_payload.get("full_name", f"Farmer #{current_user.id}")
        created_req = request_repo.create_request(
            db,
            farmer_id=current_user.id,
            farmer_name=farmer_name,
            buyer_id=req_in.buyer_id,
            buyer_name=f"Buyer #{req_in.buyer_id}",
            lot=lot,
            req_in=req_in,
        )
        return created_req
    except BuyerNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Buyer not found.") from e
    except TradeWorkflowError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e)) from e


@router.get(
    "/selling-requests",
    response_model=SellingRequestListResponse,
    status_code=status.HTTP_200_OK,
    summary="List farmer selling requests",
)
def list_farmer_selling_requests(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    current_user: AuthenticatedUser = Depends(require_farmer),
    db: Session = Depends(get_db),
    request_repo: SellingRequestRepository = Depends(get_selling_request_repo),
):
    items, total = request_repo.list_farmer_requests(db, current_user.id, skip=skip, limit=limit)
    return SellingRequestListResponse(total=total, items=items, skip=skip, limit=limit)


@router.post(
    "/selling-requests/{request_id}/action",
    response_model=SellingRequestResponse,
    status_code=status.HTTP_200_OK,
    summary="Execute negotiation action (ACCEPT, REJECT, COUNTER, CANCEL)",
)
def execute_farmer_request_action(
    action_in: SellingRequestActionRequest,
    request_id: int = Path(..., ge=1),
    current_user: AuthenticatedUser = Depends(require_farmer),
    db: Session = Depends(get_db),
    request_repo: SellingRequestRepository = Depends(get_selling_request_repo),
):
    try:
        req = request_repo.get_request_by_id(db, request_id, farmer_id=current_user.id)
        if not req:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Selling request not found.",
            )
        updated = request_repo.execute_action(
            db, request_id, current_user.id, "FARMER", action_in
        )
        return updated
    except TradeWorkflowError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e)) from e
