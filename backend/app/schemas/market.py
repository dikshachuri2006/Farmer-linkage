from typing import List, Optional
from pydantic import BaseModel, ConfigDict, Field, field_validator


class MarketCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=150, description="APMC Mandi or Market Hub name")
    state: str = Field(..., min_length=1, max_length=100, description="Operating State (e.g. Maharashtra)")
    district: str = Field(..., min_length=1, max_length=100, description="Operating District (e.g. Nashik)")
    market_code: Optional[str] = Field(None, max_length=100, description="Official APMC or Agmarknet market code")
    latitude: Optional[float] = Field(None, ge=-90.0, le=90.0)
    longitude: Optional[float] = Field(None, ge=-180.0, le=180.0)

    model_config = ConfigDict(extra="forbid")

    @field_validator("name", "state", "district")
    @classmethod
    def require_non_whitespace_value(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("must contain a non-whitespace character")
        return value


class MarketResponse(BaseModel):
    id: int
    name: str = Field(..., description="APMC Mandi or Market Hub name")
    state: str = Field(..., description="Operating State (e.g. Maharashtra)")
    district: str = Field(..., description="Operating District (e.g. Nashik)")
    market_code: Optional[str] = Field(None, description="Official APMC or Agmarknet market code")
    latitude: Optional[float] = Field(None, ge=-90.0, le=90.0)
    longitude: Optional[float] = Field(None, ge=-180.0, le=180.0)

    model_config = ConfigDict(from_attributes=True)


class MarketListResponse(BaseModel):
    total: int = Field(..., ge=0)
    items: List[MarketResponse]
    skip: int = Field(..., ge=0)
    limit: int = Field(..., ge=1)
