from decimal import Decimal
from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field, field_validator


class SupportedQuantityUnit(str, Enum):
    KG = "kg"
    QUINTAL = "quintal"
    TONNE = "tonne"


class SupportedPriceUnit(str, Enum):
    INR_PER_KG = "INR/kg"
    INR_PER_QUINTAL = "INR/quintal"
    INR_PER_TONNE = "INR/tonne"


class MarketOptionInput(BaseModel):
    market_name: str = Field(..., min_length=2, max_length=150, description="Name of candidate Mandi or Buyer")
    market_id: Optional[int] = Field(None, ge=1, description="Database Market or Buyer ID if linked")
    offered_price: Optional[float] = Field(None, ge=0.0, description="Price per unit offered or prevailing")
    price_unit: Optional[SupportedPriceUnit] = Field(
        default=SupportedPriceUnit.INR_PER_QUINTAL,
        description="Explicit unit of the offered price (INR/kg, INR/quintal, INR/tonne)",
    )
    market_latitude: Optional[float] = Field(None, ge=-90.0, le=90.0)
    market_longitude: Optional[float] = Field(None, ge=-180.0, le=180.0)
    distance_km: Optional[float] = Field(None, ge=0.0, description="Direct road distance in km if known")
    supplied_transport_cost: Optional[float] = Field(None, ge=0.0, description="Direct transport quotation if available")
    transport_rate_per_km_per_kg: Optional[float] = Field(None, ge=0.0, description="Transport rate override")
    market_cess_rate_percent: Optional[float] = Field(None, ge=0.0, le=50.0, description="APMC mandi cess/tax percentage")
    fixed_market_charges: Optional[float] = Field(None, ge=0.0, description="Fixed mandi unloading/weighment fee in INR")
    other_deductions: Optional[float] = Field(None, ge=0.0, description="Packaging/other deductions in INR")


class PriceComparisonRequest(BaseModel):
    crop_name: str = Field(..., min_length=2, max_length=100, description="Target crop commodity")
    sale_quantity: float = Field(..., gt=0.0, description="Quantity to sell (must be strictly positive)")
    quantity_unit: SupportedQuantityUnit = Field(default=SupportedQuantityUnit.QUINTAL)
    farmer_location: Optional[str] = Field(None, description="Farmer village or taluka name")
    farmer_latitude: Optional[float] = Field(None, ge=-90.0, le=90.0)
    farmer_longitude: Optional[float] = Field(None, ge=-180.0, le=180.0)
    candidate_options: List[MarketOptionInput] = Field(
        ...,
        min_length=1,
        description="List of candidate markets or buyer quotes to compare",
    )


class AutoPriceDiscoveryRequest(BaseModel):
    crop_id: int = Field(..., ge=1, description="Database crop identifier")
    sale_quantity: float = Field(..., gt=0.0, description="Quantity to sell")
    quantity_unit: SupportedQuantityUnit = Field(default=SupportedQuantityUnit.QUINTAL)
    farmer_location: Optional[str] = Field(None, description="Farmer village or taluka name")
    farmer_state: Optional[str] = Field(None, description="Farmer state (e.g. Maharashtra)")
    farmer_district: Optional[str] = Field(None, description="Farmer district (e.g. Nashik)")
    farmer_latitude: Optional[float] = Field(None, ge=-90.0, le=90.0)
    farmer_longitude: Optional[float] = Field(None, ge=-180.0, le=180.0)
    max_markets: int = Field(default=10, ge=1, le=50)


class MarketRealizationOption(BaseModel):
    rank: Optional[int] = None
    market_name: str
    market_id: Optional[int] = None
    source_price: Optional[float] = None
    source_price_unit: Optional[str] = None
    normalized_price_per_kg: Optional[float] = None
    gross_sale_value: Optional[float] = None
    transport_cost: Optional[float] = None
    transport_data_source: str
    market_cess_charges: Optional[float] = None
    fixed_market_charges: Optional[float] = None
    other_charges: Optional[float] = None
    total_deductions: Optional[float] = None
    estimated_net_realization: Optional[float] = None
    estimated_net_per_original_unit: Optional[float] = None
    estimated_net_per_kg: Optional[float] = None
    is_complete: bool
    missing_data: List[str]
    notes: str

    model_config = ConfigDict(from_attributes=True)


class PriceComparisonResponse(BaseModel):
    crop_name: str
    sale_quantity: float
    quantity_unit: str
    normalized_quantity_kg: float
    total_options_evaluated: int
    is_comparison_complete: bool
    ranking_is_valid: bool
    ranked_options: List[MarketRealizationOption]
    best_net_realization_option: Optional[MarketRealizationOption] = None
    general_disclaimers: List[str]
