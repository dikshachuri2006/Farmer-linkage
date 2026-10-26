from datetime import datetime
from enum import Enum
from typing import List, Optional
from pydantic import BaseModel, ConfigDict, Field


class ComplaintIssueType(str, Enum):
    PAYMENT_ISSUE = "PAYMENT_ISSUE"
    WRONG_QUANTITY = "WRONG_QUANTITY"
    BUYER_NO_SHOW = "BUYER_NO_SHOW"
    PRICE_DISPUTE = "PRICE_DISPUTE"
    FRAUD = "FRAUD"
    QUALITY_MISMATCH = "QUALITY_MISMATCH"
    TRANSPORT_DELAY = "TRANSPORT_DELAY"
    OTHER = "OTHER"


class ComplaintStatus(str, Enum):
    OPEN = "OPEN"
    UNDER_REVIEW = "UNDER_REVIEW"
    RESOLVED = "RESOLVED"
    DISMISSED = "DISMISSED"


class ComplaintCreate(BaseModel):
    transaction_id: Optional[int] = Field(None, ge=1, description="Associated transaction ID if dispute is trade-related")
    against_user_id: Optional[int] = Field(None, ge=1, description="Optional ID of respondent user")
    issue_type: ComplaintIssueType = Field(..., description="Categorized nature of grievance")
    title: str = Field(..., min_length=5, max_length=200, description="Short summary of the dispute")
    description: str = Field(..., min_length=10, max_length=2000, description="Detailed statement of facts")


class ComplaintUpdateAdmin(BaseModel):
    status: Optional[ComplaintStatus] = Field(None, description="Updated ticket status: UNDER_REVIEW, RESOLVED, DISMISSED")
    admin_notes: Optional[str] = Field(None, max_length=1000, description="Internal administrative investigation notes")
    resolution_summary: Optional[str] = Field(None, max_length=1000, description="Official resolution decision conveyed to parties")


class ComplaintResponse(BaseModel):
    id: int
    ticket_number: str = Field(..., description="Unique dispute ticket reference number")
    complainant_user_id: int
    complainant_name: str
    complainant_role: str
    transaction_id: Optional[int] = None
    transaction_code: Optional[str] = None
    against_user_id: Optional[int] = None
    against_user_name: Optional[str] = None
    issue_type: ComplaintIssueType
    title: str
    description: str
    status: ComplaintStatus
    admin_notes: Optional[str] = None
    resolution_summary: Optional[str] = None
    created_at: Optional[datetime] = None
    resolved_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


class ComplaintListResponse(BaseModel):
    total: int = Field(..., ge=0)
    items: List[ComplaintResponse]
    skip: int = Field(..., ge=0)
    limit: int = Field(..., ge=1)
