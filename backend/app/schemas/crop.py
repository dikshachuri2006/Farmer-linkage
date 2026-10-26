import enum
from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, ConfigDict, Field, field_validator


class CropCategory(str, enum.Enum):
    CEREAL = "CEREAL"
    PULSE = "PULSE"
    VEGETABLE = "VEGETABLE"
    FRUIT = "FRUIT"
    OILSEED = "OILSEED"
    SPICE = "SPICE"
    OTHER = "OTHER"


class CropCreate(BaseModel):
    """Fields accepted when an administrator adds a crop to the catalog."""

    name: str = Field(..., min_length=1, max_length=100)
    category: CropCategory = CropCategory.OTHER
    standard_unit: str = Field(default="kg", min_length=1, max_length=20)
    description: Optional[str] = None

    model_config = ConfigDict(extra="forbid")

    @field_validator("name", "standard_unit")
    @classmethod
    def require_non_whitespace_value(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("must contain a non-whitespace character")
        return value


class CropResponse(BaseModel):
    id: int
    name: str = Field(..., description="Crop name (e.g. Onion, Wheat, Tomato)")
    category: CropCategory = Field(default=CropCategory.OTHER)
    standard_unit: str = Field(default="kg", description="Normalized trade unit (e.g. kg, quintal)")
    description: Optional[str] = None
    created_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


class CropListResponse(BaseModel):
    total: int = Field(..., ge=0)
    items: List[CropResponse]
    skip: int = Field(..., ge=0)
    limit: int = Field(..., ge=1)
