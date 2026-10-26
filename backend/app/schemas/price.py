from datetime import date
from typing import List, Optional
from pydantic import BaseModel, ConfigDict, Field, field_validator


class PriceRecordResponse(BaseModel):
    id: int
    crop_id: int
    crop_name: Optional[str] = Field(None, description="Crop common name")
    market_id: int
    market_name: Optional[str] = Field(None, description="APMC Mandi name")
    state: Optional[str] = None
    district: Optional[str] = None
    price_date: date = Field(..., description="Date of price recording (YYYY-MM-DD)")
    min_price: float = Field(..., ge=0.0, description="Minimum price observed")
    max_price: float = Field(..., ge=0.0, description="Maximum price observed")
    modal_price: float = Field(..., ge=0.0, description="Modal / prevailing trading price")
    variety: Optional[str] = Field(None, description="Source variety; retained as a separate price series")
    grade: Optional[str] = Field(None, description="Source grade; retained as a separate price series")
    arrival_quantity: Optional[float] = Field(None, ge=0.0, description="Quantity arrived on date")
    price_unit: str = Field(
        default="INR/Quintal",
        description="Explicit source currency and unit (e.g. INR/Quintal or INR/kg). Must be kept explicit.",
    )
    arrival_unit: Optional[str] = Field(
        default="Tonnes",
        description="Unit of arrival volume (e.g. Tonnes, Quintals, Bags)",
    )
    source: str = Field(
        default="Agmarknet Dataset (Diya - Pending Delivery)",
        description="Dataset origin and verification source",
    )

    model_config = ConfigDict(from_attributes=True)

    @field_validator("max_price")
    @classmethod
    def validate_price_bounds(cls, v: float, info) -> float:
        min_p = info.data.get("min_price")
        if min_p is not None and v < min_p:
            raise ValueError(f"max_price ({v}) cannot be lower than min_price ({min_p})")
        return v


class PriceRecordListResponse(BaseModel):
    total: int = Field(..., ge=0)
    items: List[PriceRecordResponse]
    skip: int = Field(..., ge=0)
    limit: int = Field(..., ge=1)
