from datetime import date
from typing import Any, List, Optional, Protocol, Tuple
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from app.models.entities import Crop, Market, MarketPrice
from app.schemas.crop import CropCategory
from app.services.auth_service import DatabaseSchemaPendingError


class CropNameConflictError(ValueError):
    """Raised when a crop with the same unique name already exists."""


class MarketConflictError(ValueError):
    """Raised when an APMC market conflict occurs."""


class CropRepository(Protocol):
    """Repository contract for Crop master data."""
    def create(self, db: Session, crop_in: Any) -> Any:
        ...

    def get_by_id(self, db: Session, crop_id: int) -> Optional[Any]:
        ...

    def list_crops(
        self,
        db: Session,
        search: Optional[str] = None,
        category: Optional[CropCategory] = None,
        skip: int = 0,
        limit: int = 50,
    ) -> Tuple[List[Any], int]:
        ...


class MarketRepository(Protocol):
    """Repository contract for APMC Market master data."""
    def create(self, db: Session, market_in: Any) -> Any:
        ...

    def get_by_id(self, db: Session, market_id: int) -> Optional[Any]:
        ...

    def list_markets(
        self,
        db: Session,
        search: Optional[str] = None,
        state: Optional[str] = None,
        district: Optional[str] = None,
        skip: int = 0,
        limit: int = 50,
    ) -> Tuple[List[Any], int]:
        ...


class MarketPriceRepository(Protocol):
    """Repository contract for historical and daily mandi arrival price records."""
    def get_by_id(self, db: Session, price_id: int) -> Optional[Any]:
        ...

    def list_prices(
        self,
        db: Session,
        crop_id: Optional[int] = None,
        market_id: Optional[int] = None,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
        variety: Optional[str] = None,
        grade: Optional[str] = None,
        sort_by: str = "price_date",
        sort_order: str = "desc",
        skip: int = 0,
        limit: int = 50,
    ) -> Tuple[List[Any], int]:
        ...

    def get_latest_price(
        self, db: Session, crop_id: int, market_id: Optional[int] = None,
        variety: Optional[str] = None, grade: Optional[str] = None,
    ) -> Optional[Any]:
        ...


class DefaultCropRepository:
    def create(self, db: Session, crop_in: Any) -> Any:
        try:
            existing = db.scalar(select(Crop.id).where(Crop.name == crop_in.name))
            if existing is not None:
                raise CropNameConflictError("A crop with this name already exists.")

            crop = Crop(**crop_in.model_dump())
            db.add(crop)
            db.flush()
            db.refresh(crop)
            db.commit()
            return crop
        except IntegrityError as error:
            db.rollback()
            constraint_name = getattr(getattr(error.orig, "diag", None), "constraint_name", None)
            sqlite_name_conflict = "UNIQUE constraint failed: crops.name" in str(error.orig)
            if constraint_name in {"crops_name_key", "uq_crops_name"} or sqlite_name_conflict:
                raise CropNameConflictError("A crop with this name already exists.") from error
            raise
        except Exception:
            db.rollback()
            raise

    def get_by_id(self, db: Session, crop_id: int) -> Optional[Any]:
        try:
            return db.get(Crop, crop_id)
        except Exception:
            db.rollback()
            raise

    def list_crops(
        self,
        db: Session,
        search: Optional[str] = None,
        category: Optional[CropCategory] = None,
        skip: int = 0,
        limit: int = 50,
    ) -> Tuple[List[Any], int]:
        try:
            filters = []
            if search:
                filters.append(Crop.name.ilike(f"%{search}%"))
            if category is not None:
                filters.append(Crop.category == category)

            total = db.scalar(
                select(func.count(Crop.id)).where(*filters)
            ) or 0
            items = db.scalars(
                select(Crop)
                .where(*filters)
                .order_by(Crop.id.asc())
                .offset(skip)
                .limit(limit)
            ).all()
            return items, total
        except Exception:
            db.rollback()
            raise


class DefaultMarketRepository:
    def create(self, db: Session, market_in: Any) -> Any:
        try:
            market = Market(
                name=market_in.name.strip(),
                state=market_in.state.strip(),
                district=market_in.district.strip(),
                market_code=market_in.market_code.strip() if market_in.market_code else None,
                latitude=market_in.latitude,
                longitude=market_in.longitude,
            )
            db.add(market)
            db.commit()
            db.refresh(market)
            return market
        except IntegrityError:
            db.rollback()
            raise MarketConflictError("Market with these details already exists.")
        except Exception:
            db.rollback()
            raise

    def get_by_id(self, db: Session, market_id: int) -> Optional[Any]:
        try:
            return db.get(Market, market_id)
        except Exception:
            db.rollback()
            raise

    def list_markets(
        self,
        db: Session,
        search: Optional[str] = None,
        state: Optional[str] = None,
        district: Optional[str] = None,
        skip: int = 0,
        limit: int = 50,
    ) -> Tuple[List[Any], int]:
        try:
            filters = []
            if search:
                filters.append(Market.name.ilike(f"%{search}%"))
            if state:
                filters.append(Market.state.ilike(f"%{state}%"))
            if district:
                filters.append(Market.district.ilike(f"%{district}%"))

            total = db.scalar(select(func.count(Market.id)).where(*filters)) or 0
            items = db.scalars(
                select(Market)
                .where(*filters)
                .order_by(Market.id.asc())
                .offset(skip)
                .limit(limit)
            ).all()
            return items, total
        except Exception:
            db.rollback()
            raise


class DefaultMarketPriceRepository:
    def get_by_id(self, db: Session, price_id: int) -> Optional[Any]:
        try:
            row = db.execute(
                select(MarketPrice, Crop.name, Market.name, Market.state, Market.district)
                .join(Crop, Crop.id == MarketPrice.crop_id)
                .join(Market, Market.id == MarketPrice.market_id)
                .where(MarketPrice.id == price_id)
            ).first()
            return _price_response_row(row)
        except Exception:
            db.rollback()
            raise

    def list_prices(
        self,
        db: Session,
        crop_id: Optional[int] = None,
        market_id: Optional[int] = None,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
        variety: Optional[str] = None,
        grade: Optional[str] = None,
        sort_by: str = "price_date",
        sort_order: str = "desc",
        skip: int = 0,
        limit: int = 50,
    ) -> Tuple[List[Any], int]:
        try:
            filters = []
            if crop_id is not None:
                filters.append(MarketPrice.crop_id == crop_id)
            if market_id is not None:
                filters.append(MarketPrice.market_id == market_id)
            if start_date is not None:
                filters.append(MarketPrice.price_date >= start_date)
            if end_date is not None:
                filters.append(MarketPrice.price_date <= end_date)
            if variety is not None:
                filters.append(MarketPrice.variety == variety)
            if grade is not None:
                filters.append(MarketPrice.grade == grade)

            total = db.scalar(select(func.count(MarketPrice.id)).where(*filters)) or 0
            sort_column = getattr(MarketPrice, sort_by)
            sort_expression = sort_column.asc() if sort_order == "asc" else sort_column.desc()
            rows = db.execute(
                select(MarketPrice, Crop.name, Market.name, Market.state, Market.district)
                .join(Crop, Crop.id == MarketPrice.crop_id)
                .join(Market, Market.id == MarketPrice.market_id)
                .where(*filters)
                .order_by(sort_expression, MarketPrice.id.desc())
                .offset(skip)
                .limit(limit)
            ).all()
            return [_price_response_row(row) for row in rows], total
        except Exception:
            db.rollback()
            raise

    def get_latest_price(
        self, db: Session, crop_id: int, market_id: Optional[int] = None,
        variety: Optional[str] = None, grade: Optional[str] = None,
    ) -> Optional[Any]:
        try:
            filters = [MarketPrice.crop_id == crop_id]
            if market_id is not None:
                filters.append(MarketPrice.market_id == market_id)
            if variety is not None:
                filters.append(MarketPrice.variety == variety)
            if grade is not None:
                filters.append(MarketPrice.grade == grade)
            row = db.execute(
                select(MarketPrice, Crop.name, Market.name, Market.state, Market.district)
                .join(Crop, Crop.id == MarketPrice.crop_id)
                .join(Market, Market.id == MarketPrice.market_id)
                .where(*filters)
                .order_by(MarketPrice.price_date.desc(), MarketPrice.id.desc())
                .limit(1)
            ).first()
            return _price_response_row(row)
        except Exception:
            db.rollback()
            raise


def _price_response_row(row: Any) -> Optional[dict[str, Any]]:
    if row is None:
        return None
    price, crop_name, market_name, state, district = row
    return {
        "id": price.id,
        "crop_id": price.crop_id,
        "crop_name": crop_name,
        "market_id": price.market_id,
        "market_name": market_name,
        "state": state,
        "district": district,
        "price_date": price.price_date,
        "min_price": price.min_price,
        "max_price": price.max_price,
        "modal_price": price.modal_price,
        "variety": price.variety,
        "grade": price.grade,
        "arrival_quantity": price.arrival_quantity,
        "price_unit": price.price_unit,
        "arrival_unit": price.arrival_unit,
        "source": price.source,
    }


_default_crop_repo = DefaultCropRepository()
_default_market_repo = DefaultMarketRepository()
_default_price_repo = DefaultMarketPriceRepository()


def get_crop_repo() -> CropRepository:
    return _default_crop_repo


def get_market_repo() -> MarketRepository:
    return _default_market_repo


def get_price_repo() -> MarketPriceRepository:
    return _default_price_repo
