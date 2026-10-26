from datetime import date, datetime
from enum import Enum
from typing import List, Optional
from pydantic import BaseModel, ConfigDict, Field


class LotQualityGrade(str, Enum):
    GRADE_A = "GRADE_A"
    GRADE_B = "GRADE_B"
    GRADE_C = "GRADE_C"
    FAIR_AVERAGE = "FAIR_AVERAGE"


class LotStatus(str, Enum):
    AVAILABLE = "AVAILABLE"
    COMMITTED = "COMMITTED"
    SOLD = "SOLD"
    WITHDRAWN = "WITHDRAWN"


class FarmerLotCreate(BaseModel):
    crop_id: int = Field(..., ge=1, description="Database crop identifier")
    crop_name: str = Field(..., min_length=2, max_length=100, description="Common crop name")
    quantity: float = Field(..., gt=0.0, description="Available lot harvest quantity")
    unit: str = Field(default="quintal", description="Quantity unit (kg, quintal, tonne)")
    quality_grade: LotQualityGrade = Field(default=LotQualityGrade.GRADE_A)
    expected_price_per_unit: float = Field(..., gt=0.0, description="Farmer's target reserve price")
    price_unit: str = Field(default="INR/quintal", description="Price unit (e.g. INR/quintal, INR/kg)")
    harvest_date: Optional[date] = Field(None, description="Harvest completion date")
    location_state: str = Field(..., min_length=2, max_length=100)
    location_district: str = Field(..., min_length=2, max_length=100)
    location_pincode: Optional[str] = Field(None, max_length=10)


class FarmerLotUpdate(BaseModel):
    quantity: Optional[float] = Field(None, gt=0.0)
    quality_grade: Optional[LotQualityGrade] = None
    expected_price_per_unit: Optional[float] = Field(None, gt=0.0)
    price_unit: Optional[str] = None
    location_state: Optional[str] = Field(None, min_length=2, max_length=100)
    location_district: Optional[str] = Field(None, min_length=2, max_length=100)
    status: Optional[LotStatus] = None


class FarmerLotResponse(BaseModel):
    id: int
    farmer_id: int
    farmer_name: str
    crop_id: int
    crop_name: str
    quantity: float
    unit: str
    quality_grade: LotQualityGrade
    expected_price_per_unit: float
    price_unit: str
    harvest_date: Optional[date] = None
    location_state: str
    location_district: str
    status: LotStatus
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


class FarmerLotListResponse(BaseModel):
    total: int = Field(..., ge=0)
    items: List[FarmerLotResponse]
    skip: int = Field(..., ge=0)
    limit: int = Field(..., ge=1)
