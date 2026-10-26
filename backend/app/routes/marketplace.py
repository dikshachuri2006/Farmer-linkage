from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.core.dependencies import AuthenticatedUser, get_current_user_claims
from app.database.connection import get_db
from app.schemas.farmer_lot import (
    FarmerLotListResponse,
    LotQualityGrade,
)
from app.services.trade_service import (
    FarmerLotRepository,
    get_farmer_lot_repo,
)

router = APIRouter(prefix="/marketplace", tags=["Marketplace"])


@router.get(
    "/lots",
    response_model=FarmerLotListResponse,
    status_code=status.HTTP_200_OK,
    summary="Discover available produce listings across mandis and farmgates",
)
def list_marketplace_lots(
    crop_id: Optional[int] = Query(None, ge=1, description="Filter by crop identifier"),
    state: Optional[str] = Query(None, min_length=1, max_length=100, description="Filter by location state"),
    district: Optional[str] = Query(None, min_length=1, max_length=100, description="Filter by location district"),
    grade: Optional[LotQualityGrade] = Query(None, description="Filter by lot quality grade"),
    min_price: Optional[float] = Query(None, ge=0.0, description="Minimum asking price per unit"),
    max_price: Optional[float] = Query(None, ge=0.0, description="Maximum asking price per unit"),
    skip: int = Query(0, ge=0, description="Pagination offset"),
    limit: int = Query(50, ge=1, le=100, description="Items per page"),
    current_user: AuthenticatedUser = Depends(get_current_user_claims),
    db: Session = Depends(get_db),
    lot_repo: FarmerLotRepository = Depends(get_farmer_lot_repo),
):
    """
    Marketplace Produce Discovery API for SIH26132.
    Allows authenticated buyers to discover available produce listings created by farmers.
    - Excludes committed, sold, or withdrawn lots (only AVAILABLE status).
    - Protects farmer privacy: does not expose contact details, coordinates, or farm profile.
    - Applies multi-criteria filtering and pagination directly in the database query.
    """
    if min_price is not None and max_price is not None and min_price > max_price:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="min_price cannot be greater than max_price.",
        )

    try:
        items, total = lot_repo.list_marketplace_lots(
            db=db,
            crop_id=crop_id,
            state=state.strip() if state else None,
            district=district.strip() if district else None,
            grade=grade,
            min_price=min_price,
            max_price=max_price,
            skip=skip,
            limit=limit,
        )
        return FarmerLotListResponse(total=total, items=items, skip=skip, limit=limit)
    except Exception as e:
        if isinstance(e, HTTPException):
            raise
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Unable to retrieve marketplace listings.",
        ) from e
