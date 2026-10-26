from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Path, Query, status
from sqlalchemy.exc import SQLAlchemyError
from app.core.dependencies import AuthenticatedUser, require_admin
from sqlalchemy.orm import Session
from app.database.connection import get_db
from app.schemas.crop import CropCategory, CropCreate, CropListResponse, CropResponse
from app.services.auth_service import DatabaseSchemaPendingError
from app.services.price_service import CropNameConflictError, CropRepository, get_crop_repo

router = APIRouter(prefix="/crops", tags=["Crops"])


@router.post(
    "",
    response_model=CropResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a crop catalog entry (admin only)",
)
def create_crop(
    crop_in: CropCreate,
    current_admin: AuthenticatedUser = Depends(require_admin),
    db: Session = Depends(get_db),
    crop_repo: CropRepository = Depends(get_crop_repo),
):
    """Adds a crop to the catalog. Only authenticated administrators may create crops."""
    try:
        return crop_repo.create(db, crop_in)
    except CropNameConflictError as error:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A crop with this name already exists.",
        ) from error
    except SQLAlchemyError as error:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Unable to create crop.",
        ) from error


@router.get(
    "",
    response_model=CropListResponse,
    status_code=status.HTTP_200_OK,
    summary="List agricultural crops catalog",
)
def list_crops(
    search: Optional[str] = Query(None, min_length=1, max_length=100, description="Search by crop name"),
    category: Optional[CropCategory] = Query(None, description="Filter by crop category"),
    skip: int = Query(0, ge=0, description="Pagination offset"),
    limit: int = Query(50, ge=1, le=100, description="Items per page"),
    db: Session = Depends(get_db),
    crop_repo: CropRepository = Depends(get_crop_repo),
):
    """
    Retrieves a paginated list of agricultural crops.
    Supports substring name search and category filtering.
    """
    try:
        items, total = crop_repo.list_crops(
            db, search=search, category=category, skip=skip, limit=limit
        )
        return CropListResponse(total=total, items=items, skip=skip, limit=limit)
    except DatabaseSchemaPendingError as e:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Database crop table schema is pending approval by Ankita: {str(e)}",
        )


@router.get(
    "/{crop_id}",
    response_model=CropResponse,
    status_code=status.HTTP_200_OK,
    summary="Get crop details by ID",
)
def get_crop_by_id(
    crop_id: int = Path(..., ge=1, description="Unique crop identifier"),
    db: Session = Depends(get_db),
    crop_repo: CropRepository = Depends(get_crop_repo),
):
    """
    Retrieves a single crop specification by ID.
    Returns 404 if crop ID does not exist.
    """
    try:
        crop = crop_repo.get_by_id(db, crop_id=crop_id)
        if not crop:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Crop with ID {crop_id} not found.",
            )
        return crop
    except DatabaseSchemaPendingError as e:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Database crop table schema is pending approval by Ankita: {str(e)}",
        )
    except SQLAlchemyError as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Unable to retrieve crop.",
        ) from e
