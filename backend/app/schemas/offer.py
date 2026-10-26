from datetime import date, datetime
from enum import Enum
from typing import List, Optional
from pydantic import BaseModel, ConfigDict, Field


class OfferStatus(str, Enum):
    ACTIVE = "ACTIVE"
    WITHDRAWN = "WITHDRAWN"
    EXPIRED = "EXPIRED"
    ACCEPTED = "ACCEPTED"


class BuyerOfferCreate(BaseModel):
    lot_id: int = Field(..., ge=1, description="Farmer lot identifier being bid upon")
    offered_price_per_unit: float = Field(..., gt=0.0, description="Purchase bid price per unit")
    price_unit: str = Field(default="INR/quintal", description="Price unit (e.g. INR/quintal, INR/kg)")
    quantity_requested: float = Field(..., gt=0.0, description="Quantity buyer seeks to purchase")
    quantity_unit: str = Field(default="quintal", description="Unit of requested quantity")
    pickup_included: bool = Field(default=False, description="True if buyer arranges transport from farmgate")
    delivery_location: str = Field(..., min_length=2, max_length=200, description="Mandi premise or warehouse destination")
    valid_until: Optional[date] = Field(None, description="Expiry date of the offer")
    terms_and_notes: Optional[str] = Field(None, max_length=500, description="Payment terms or quality clauses")


class BuyerOfferUpdate(BaseModel):
    offered_price_per_unit: Optional[float] = Field(None, gt=0.0)
    quantity_requested: Optional[float] = Field(None, gt=0.0)
    pickup_included: Optional[bool] = None
    delivery_location: Optional[str] = Field(None, min_length=2, max_length=200)
    valid_until: Optional[date] = None
    terms_and_notes: Optional[str] = Field(None, max_length=500)


class BuyerOfferResponse(BaseModel):
    id: int
    buyer_id: int
    buyer_name: str
    lot_id: int
    crop_name: str
    offered_price_per_unit: float
    price_unit: str
    quantity_requested: float
    quantity_unit: str
    total_offer_value: float
    pickup_included: bool
    delivery_location: str
    status: OfferStatus
    valid_until: Optional[date] = None
    terms_and_notes: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


class BuyerOfferListResponse(BaseModel):
    total: int = Field(..., ge=0)
    items: List[BuyerOfferResponse]
    skip: int = Field(..., ge=0)
    limit: int = Field(..., ge=1)
