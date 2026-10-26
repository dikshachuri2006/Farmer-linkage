from pydantic import BaseModel, Field


class AdminStatsResponse(BaseModel):
    total_farmers: int = Field(..., ge=0, description="Total registered farmers")
    total_buyers: int = Field(..., ge=0, description="Total registered buyers")
    pending_kyc_buyers: int = Field(..., ge=0, description="Buyers pending KYC verification")
    active_listings: int = Field(..., ge=0, description="Active produce lots available for sale")
    total_transactions: int = Field(..., ge=0, description="Total transactions generated")
    completed_transactions: int = Field(..., ge=0, description="Completed transactions")
    total_traded_volume_quintals: float = Field(..., ge=0.0, description="Total volume traded in quintals")
    total_gmv_inr: float = Field(..., ge=0.0, description="Gross merchandise value in INR")
    total_complaints: int = Field(..., ge=0, description="Total dispute tickets lodged")
    open_complaints: int = Field(..., ge=0, description="Open disputes awaiting resolution")
