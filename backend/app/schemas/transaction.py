from datetime import datetime
from enum import Enum
from typing import List, Optional
from pydantic import BaseModel, ConfigDict, Field


class PaymentStatus(str, Enum):
    PENDING = "PENDING"
    PAYMENT_INITIATED = "PAYMENT_INITIATED"
    ESCROW_HELD = "ESCROW_HELD"
    PAID = "PAID"
    FAILED = "FAILED"
    REFUNDED = "REFUNDED"
    DISPUTED = "DISPUTED"


class TransactionStatus(str, Enum):
    CONFIRMED = "CONFIRMED"
    IN_TRANSIT = "IN_TRANSIT"
    DELIVERED = "DELIVERED"
    COMPLETED = "COMPLETED"
    CANCELLED = "CANCELLED"


class TransactionCreate(BaseModel):
    selling_request_id: int = Field(..., ge=1, description="ID of the accepted selling request")
    payment_method: Optional[str] = Field("ESCROW", description="Payment method: ESCROW, BANK_TRANSFER, UPI, CASH_AT_MANDI")
    notes: Optional[str] = Field(None, max_length=500, description="Optional trade confirmation notes")


class TransactionStatusUpdate(BaseModel):
    transaction_status: Optional[TransactionStatus] = Field(None, description="New shipment/fulfillment status")
    payment_status: Optional[PaymentStatus] = Field(None, description="New settlement/payment status")
    notes: Optional[str] = Field(None, max_length=500, description="Status update justification notes")


class TransactionResponse(BaseModel):
    id: int
    transaction_id: str = Field(..., description="Unique human-readable transaction receipt code")
    selling_request_id: int
    request_code: str
    farmer_id: int
    farmer_name: str
    buyer_id: int
    buyer_name: str
    crop_id: int
    crop_name: str
    quantity: float
    quantity_unit: str
    agreed_price: float
    price_unit: str
    gross_amount: float
    transport_cost: float
    other_charges: float
    net_amount: float
    payment_status: PaymentStatus
    transaction_status: TransactionStatus
    payment_method: Optional[str] = None
    notes: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


class TransactionListResponse(BaseModel):
    total: int = Field(..., ge=0)
    items: List[TransactionResponse]
    skip: int = Field(..., ge=0)
    limit: int = Field(..., ge=1)
