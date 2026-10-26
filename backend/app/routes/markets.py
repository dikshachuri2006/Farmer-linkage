from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Path, Query, status
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session
from app.core.dependencies import AuthenticatedUser, require_admin
from app.database.connection import get_db
from app.schemas.market import MarketCreate, MarketListResponse, MarketResponse
from app.services.price_service import MarketConflictError, MarketRepository, get_market_repo

router = APIRouter(prefix="/markets", tags=["Markets"])


@router.post(
    "",
    response_model=MarketResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create an APMC market (admin only)",
)
def create_market(
    market_in: MarketCreate,
    current_admin: AuthenticatedUser = Depends(require_admin),
    db: Session = Depends(get_db),
    market_repo: MarketRepository = Depends(get_market_repo),
):
    """Adds an APMC mandi to the directory. Only authenticated administrators may create markets."""
    try:
        return market_repo.create(db, market_in)
    except MarketConflictError as error:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(error),
        ) from error
    except SQLAlchemyError as error:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Unable to create market.",
        ) from error


@router.get(
    "",
    response_model=MarketListResponse,
    status_code=status.HTTP_200_OK,
    summary="List APMC Mandis and trade markets",
)
def list_markets(
    search: Optional[str] = Query(None, min_length=1, max_length=100, description="Search by mandi name"),
    state: Optional[str] = Query(None, min_length=2, max_length=100, description="Filter by state (e.g. Maharashtra)"),
    district: Optional[str] = Query(None, min_length=2, max_length=100, description="Filter by district (e.g. Nashik)"),
    skip: int = Query(0, ge=0, description="Pagination offset"),
    limit: int = Query(50, ge=1, le=100, description="Items per page"),
    db: Session = Depends(get_db),
    market_repo: MarketRepository = Depends(get_market_repo),
):
    """
    Retrieves a paginated list of agricultural APMC markets.
    Supports filtering by operating state and district.
    """
    try:
        items, total = market_repo.list_markets(
            db, search=search, state=state, district=district, skip=skip, limit=limit
        )
        return MarketListResponse(total=total, items=items, skip=skip, limit=limit)
    except SQLAlchemyError as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Unable to retrieve markets.",
        ) from e


@router.get(
    "/{market_id}",
    response_model=MarketResponse,
    status_code=status.HTTP_200_OK,
    summary="Get APMC Mandi details by ID",
)
def get_market_by_id(
    market_id: int = Path(..., ge=1, description="Unique market identifier"),
    db: Session = Depends(get_db),
    market_repo: MarketRepository = Depends(get_market_repo),
):
    """
    Retrieves market specification and location coordinates by ID.
    Returns 404 if market does not exist.
    """
    try:
        market = market_repo.get_by_id(db, market_id=market_id)
        if not market:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Market with ID {market_id} not found.",
            )
        return market
    except SQLAlchemyError as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Unable to retrieve market.",
        ) from e
