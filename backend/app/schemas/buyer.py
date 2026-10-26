import enum
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, ConfigDict, Field


class BuyerBusinessType(str, enum.Enum):
    TRADER = "TRADER"
    WHOLESALER = "WHOLESALER"
    PROCESSOR = "PROCESSOR"
    EXPORTER = "EXPORTER"
    RETAILER = "RETAILER"


class BuyerVerificationStatus(str, enum.Enum):
    PENDING = "PENDING"
    VERIFIED = "VERIFIED"
    REJECTED = "REJECTED"
    SUSPENDED = "SUSPENDED"


class BuyerProfileCreate(BaseModel):
    business_name: str = Field(..., min_length=2, max_length=200, description="Business or trade entity name")
    business_type: BuyerBusinessType = Field(default=BuyerBusinessType.TRADER)
    license_number: Optional[str] = Field(None, max_length=100, description="APMC / GSTIN / FSSAI license")
    state: str = Field(..., min_length=2, max_length=100)
    district: str = Field(..., min_length=2, max_length=100)
    market_address: str = Field(..., min_length=5, description="Full operating premises / mandi address")
    latitude: Optional[float] = Field(None, ge=-90.0, le=90.0)
    longitude: Optional[float] = Field(None, ge=-180.0, le=180.0)


class BuyerProfileUpdate(BaseModel):
    business_name: Optional[str] = Field(None, min_length=2, max_length=200)
    business_type: Optional[BuyerBusinessType] = None
    license_number: Optional[str] = Field(None, max_length=100)
    state: Optional[str] = Field(None, min_length=2, max_length=100)
    district: Optional[str] = Field(None, min_length=2, max_length=100)
    market_address: Optional[str] = Field(None, min_length=5)
    latitude: Optional[float] = Field(None, ge=-90.0, le=90.0)
    longitude: Optional[float] = Field(None, ge=-180.0, le=180.0)


class BuyerVerificationRequest(BaseModel):
    license_number: str = Field(..., min_length=3, max_length=100, description="APMC / GST / Trade License Number")
    business_name: str = Field(..., min_length=2, max_length=200)
    business_type: BuyerBusinessType = Field(default=BuyerBusinessType.TRADER)
    market_address: str = Field(..., min_length=5)
    documents_url: Optional[str] = Field(None, description="Document verification URL or reference ID")
    verification_notes: Optional[str] = Field(None, description="Applicant remarks or clarification notes")


class AdminBuyerActionRequest(BaseModel):
    notes: Optional[str] = Field(None, description="Official administrative notes or justification")


class BuyerProfileResponse(BaseModel):
    id: int
    user_id: int
    full_name: str
    email: str
    phone_number: str
    business_name: str
    business_type: BuyerBusinessType
    license_number: Optional[str] = None
    state: str
    district: str
    market_address: str
    verification_status: BuyerVerificationStatus
    verification_notes: Optional[str] = None
    rating: float = 5.0
    total_transactions: int = 0
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)
