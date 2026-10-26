import re
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, ConfigDict, Field, field_validator


class FarmerProfileCreate(BaseModel):
    state: str = Field(..., min_length=2, max_length=100, description="State of farming operations")
    district: str = Field(..., min_length=2, max_length=100, description="District")
    taluka: Optional[str] = Field(None, max_length=100, description="Sub-district / Taluka")
    village: Optional[str] = Field(None, max_length=100, description="Village or town name")
    pincode: str = Field(..., description="6-digit postal code")
    land_area_acres: Optional[float] = Field(None, ge=0, description="Total land area in acres")
    preferred_language: str = Field(default="en", max_length=10, description="Preferred language (en, hi, mr)")
    latitude: Optional[float] = Field(None, ge=-90.0, le=90.0, description="GPS Latitude")
    longitude: Optional[float] = Field(None, ge=-180.0, le=180.0, description="GPS Longitude")

    @field_validator("pincode")
    @classmethod
    def validate_pincode(cls, v: str) -> str:
        cleaned = v.strip()
        if not re.fullmatch(r"^\d{6}$", cleaned):
            raise ValueError("Pincode must be exactly 6 digits.")
        return cleaned


class FarmerProfileUpdate(BaseModel):
    state: Optional[str] = Field(None, min_length=2, max_length=100)
    district: Optional[str] = Field(None, min_length=2, max_length=100)
    taluka: Optional[str] = Field(None, max_length=100)
    village: Optional[str] = Field(None, max_length=100)
    pincode: Optional[str] = None
    land_area_acres: Optional[float] = Field(None, ge=0)
    preferred_language: Optional[str] = Field(None, max_length=10)
    latitude: Optional[float] = Field(None, ge=-90.0, le=90.0)
    longitude: Optional[float] = Field(None, ge=-180.0, le=180.0)

    @field_validator("pincode")
    @classmethod
    def validate_pincode(cls, v: Optional[str]) -> Optional[str]:
        if v is not None:
            cleaned = v.strip()
            if not re.fullmatch(r"^\d{6}$", cleaned):
                raise ValueError("Pincode must be exactly 6 digits.")
            return cleaned
        return v


class FarmerProfileResponse(BaseModel):
    id: int
    user_id: int
    full_name: str
    email: str
    phone_number: str
    state: str
    district: str
    taluka: Optional[str] = None
    village: Optional[str] = None
    pincode: str
    land_area_acres: Optional[float] = None
    preferred_language: str = "en"
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)
