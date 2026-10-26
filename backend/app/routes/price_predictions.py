from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.database.connection import get_db
from app.ml.price_forecast import InsufficientPriceHistory, forecast_modal_price
from app.models.entities import Crop, Market, MarketPrice
from app.schemas.price_prediction import PricePredictionResponse

router = APIRouter(prefix="/price-predictions", tags=["Price Predictions"])


@router.get("", response_model=PricePredictionResponse, summary="Forecast a mandi modal price")
def predict_market_price(
    crop_id: int = Query(..., ge=1),
    market_id: int = Query(..., ge=1),
    horizon_days: int = Query(7, ge=1, le=30),
    variety: str | None = Query(None, min_length=1, max_length=100),
    grade: str | None = Query(None, min_length=1, max_length=100),
    db: Session = Depends(get_db),
):
    """Use a chronological linear trend trained only on stored historical records."""
    try:
        if db.get(Crop, crop_id) is None:
            raise HTTPException(status_code=404, detail="Crop not found.")
        if db.get(Market, market_id) is None:
            raise HTTPException(status_code=404, detail="Market not found.")
        rows = db.scalars(
            select(MarketPrice)
            .where(MarketPrice.crop_id == crop_id, MarketPrice.market_id == market_id)
            .order_by(MarketPrice.price_date.asc(), MarketPrice.id.asc())
        ).all()
        if variety is not None:
            rows = [row for row in rows if row.variety == variety]
        if grade is not None:
            rows = [row for row in rows if row.grade == grade]
        if not rows:
            raise HTTPException(status_code=422, detail="Insufficient historical price data for this crop and market.")
        if variety is None and len({row.variety for row in rows}) > 1:
            raise HTTPException(status_code=422, detail="Multiple varieties exist; select a variety to forecast.")
        if grade is None and len({row.grade for row in rows}) > 1:
            raise HTTPException(status_code=422, detail="Multiple grades exist; select a grade to forecast.")
        units = {row.price_unit.strip().casefold() for row in rows}
        if len(units) != 1:
            raise HTTPException(status_code=422, detail="Historical prices use inconsistent units.")
        forecast = forecast_modal_price(
            [(row.price_date, float(row.modal_price)) for row in rows], horizon_days
        )
        return PricePredictionResponse(
            crop_id=crop_id,
            market_id=market_id,
            variety=rows[0].variety,
            grade=rows[0].grade,
            horizon_days=horizon_days,
            predicted_modal_price=forecast.predicted_price,
            price_unit=rows[0].price_unit,
            model="chronological_linear_trend",
            as_of=forecast.as_of,
            training_observations=forecast.training_observations,
            evaluation_observations=forecast.evaluation_observations,
            evaluation_mae=forecast.mae,
            evaluation_mape_percent=forecast.mape_percent,
        )
    except HTTPException:
        raise
    except InsufficientPriceHistory as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    except ValueError as error:
        raise HTTPException(status_code=422, detail="Historical price series is invalid or ambiguous.") from error
    except SQLAlchemyError as error:
        db.rollback()
        raise HTTPException(status_code=500, detail="Unable to calculate a market price prediction.") from error
