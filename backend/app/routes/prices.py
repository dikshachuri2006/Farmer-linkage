from datetime import date
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Path, Query, status
from sqlalchemy.orm import Session
from app.database.connection import get_db
from app.schemas.price import PriceRecordListResponse, PriceRecordResponse
from app.services.price_service import MarketPriceRepository, get_price_repo

router = APIRouter(prefix="/market-prices", tags=["Market Prices"])


@router.get(
    "",
    response_model=PriceRecordListResponse,
    status_code=status.HTTP_200_OK,
    summary="Retrieve agricultural market price records",
)
def list_market_prices(
    crop_id: Optional[int] = Query(None, ge=1, description="Filter by crop ID"),
    market_id: Optional[int] = Query(None, ge=1, description="Filter by market ID"),
    start_date: Optional[date] = Query(None, description="Start date (YYYY-MM-DD)"),
    end_date: Optional[date] = Query(None, description="End date (YYYY-MM-DD)"),
    variety: Optional[str] = Query(None, min_length=1, max_length=100),
    grade: Optional[str] = Query(None, min_length=1, max_length=100),
    sort_by: str = Query("price_date", description="Field to sort by"),
    sort_order: str = Query("desc", description="Sort direction (asc or desc)"),
    skip: int = Query(0, ge=0, description="Pagination offset"),
    limit: int = Query(50, ge=1, le=100, description="Items per page"),
    db: Session = Depends(get_db),
    price_repo: MarketPriceRepository = Depends(get_price_repo),
):
    """
    Retrieves historical and prevailing mandi price records.
    Supports filtering by commodity, mandi market, and trading date range.
    """
    # Validate date range
    if start_date and end_date and start_date > end_date:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="start_date cannot be greater than end_date.",
        )

    # Validate sorting fields
    allowed_sort_fields = {"price_date", "modal_price", "min_price", "max_price", "arrival_quantity"}
    if sort_by not in allowed_sort_fields:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid sort_by field '{sort_by}'. Allowed fields: {sorted(allowed_sort_fields)}",
        )

    if sort_order.lower() not in {"asc", "desc"}:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="sort_order must be either 'asc' or 'desc'.",
        )

    try:
        items, total = price_repo.list_prices(
            db,
            crop_id=crop_id,
            market_id=market_id,
            start_date=start_date,
            end_date=end_date,
            variety=variety,
            grade=grade,
            sort_by=sort_by,
            sort_order=sort_order.lower(),
            skip=skip,
            limit=limit,
        )
        return PriceRecordListResponse(total=total, items=items, skip=skip, limit=limit)

    except Exception as e:
        if isinstance(e, HTTPException):
            raise
        raise HTTPException(status_code=500, detail="Unable to retrieve market prices.") from e


@router.get(
    "/latest",
    response_model=PriceRecordResponse,
    status_code=status.HTTP_200_OK,
    summary="Get latest prevailing market price for a crop",
)
def get_latest_market_price(
    crop_id: int = Query(..., ge=1, description="Crop ID"),
    market_id: Optional[int] = Query(None, ge=1, description="Optional specific Mandi ID"),
    variety: Optional[str] = Query(None, min_length=1, max_length=100),
    grade: Optional[str] = Query(None, min_length=1, max_length=100),
    db: Session = Depends(get_db),
    price_repo: MarketPriceRepository = Depends(get_price_repo),
):
    """
    Returns the most recent daily price record for the specified crop.
    """
    try:
        latest = price_repo.get_latest_price(
            db, crop_id=crop_id, market_id=market_id, variety=variety, grade=grade
        )
        if not latest:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"No price records found for crop ID {crop_id}.",
            )
        return latest
    except Exception as e:
        if isinstance(e, HTTPException):
            raise
        raise HTTPException(status_code=500, detail="Unable to retrieve the latest market price.") from e


@router.get(
    "/{price_id}",
    response_model=PriceRecordResponse,
    status_code=status.HTTP_200_OK,
    summary="Get price record by ID",
)
def get_price_record_by_id(
    price_id: int = Path(..., ge=1, description="Price record ID"),
    db: Session = Depends(get_db),
    price_repo: MarketPriceRepository = Depends(get_price_repo),
):
    """
    Retrieves a single price arrival record by ID.
    """
    try:
        record = price_repo.get_by_id(db, price_id=price_id)
        if not record:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Price record with ID {price_id} not found.",
            )
        return record
    except Exception as e:
        if isinstance(e, HTTPException):
            raise
        raise HTTPException(status_code=500, detail="Unable to retrieve the market price record.") from e
