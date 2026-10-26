from datetime import date
from pydantic import BaseModel, Field


class PricePredictionResponse(BaseModel):
    crop_id: int
    market_id: int
    variety: str | None = None
    grade: str | None = None
    horizon_days: int = Field(ge=1, le=30)
    predicted_modal_price: float = Field(ge=0)
    price_unit: str
    model: str
    as_of: date
    training_observations: int
    evaluation_observations: int
    evaluation_mae: float = Field(ge=0)
    evaluation_mape_percent: float | None = Field(default=None, ge=0)
