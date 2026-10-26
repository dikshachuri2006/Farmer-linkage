from datetime import datetime
from enum import Enum
from typing import List, Optional
from pydantic import BaseModel, ConfigDict, Field
from app.schemas.offer import BuyerOfferResponse


class SellingRequestStatus(str, Enum):
    PENDING = "PENDING"
    COUNTERED = "COUNTERED"
    ACCEPTED = "ACCEPTED"
    REJECTED = "REJECTED"
    CANCELLED = "CANCELLED"
    EXPIRED = "EXPIRED"
    COMPLETED = "COMPLETED"


class RequestActionType(str, Enum):
    ACCEPT = "ACCEPT"
    REJECT = "REJECT"
    COUNTER = "COUNTER"
    CANCEL = "CANCEL"


class SellingRequestCreate(BaseModel):
    lot_id: int = Field(..., ge=1, description="Farmer lot identifier")
    buyer_id: int = Field(..., ge=1, description="Target buyer user ID (users.id)")
    proposed_price: float = Field(..., gt=0.0, description="Proposed price per unit")
    price_unit: str = Field(default="INR/quintal", description="Price unit")
    quantity: float = Field(..., gt=0.0, description="Quantity for negotiation")
    quantity_unit: str = Field(default="quintal", description="Quantity unit")
    estimated_transport_cost: Optional[float] = Field(0.0, ge=0.0, description="Estimated transport cost")
    estimated_other_charges: Optional[float] = Field(0.0, ge=0.0, description="Estimated mandi/other fees")
    message: Optional[str] = Field(None, max_length=500, description="Initial negotiation note")


class SellingRequestActionRequest(BaseModel):
    action: RequestActionType = Field(..., description="Action to execute: ACCEPT, REJECT, COUNTER, CANCEL")
    counter_price: Optional[float] = Field(None, gt=0.0, description="New proposed price if countering")
    counter_quantity: Optional[float] = Field(None, gt=0.0, description="New proposed quantity if countering")
    reason_or_notes: Optional[str] = Field(None, max_length=500, description="Rejection reason or counter terms")


class SellingRequestResponse(BaseModel):
    id: int
    request_code: str
    farmer_id: int
    farmer_name: str
    buyer_id: int
    buyer_name: str
    lot_id: int
    buyer_offer_id: Optional[int] = None
    crop_name: str
    quantity: float
    quantity_unit: str
    proposed_price: float
    price_unit: str
    estimated_gross_amount: float
    estimated_transport_cost: float
    estimated_other_charges: float
    estimated_net_realization: float
    status: SellingRequestStatus
    rejection_reason: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


class SellingRequestListResponse(BaseModel):
    total: int = Field(..., ge=0)
    items: List[SellingRequestResponse]
    skip: int = Field(..., ge=0)
    limit: int = Field(..., ge=1)


class OfferAcceptanceResponse(BaseModel):
    offer: BuyerOfferResponse
    selling_request: SellingRequestResponse
