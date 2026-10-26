from datetime import datetime
from enum import Enum
from typing import List, Optional
from pydantic import BaseModel, ConfigDict, Field


class NotificationType(str, Enum):
    BUYER_VERIFICATION = "BUYER_VERIFICATION"
    NEW_REQUEST = "NEW_REQUEST"
    REQUEST_ACCEPTED = "REQUEST_ACCEPTED"
    REQUEST_REJECTED = "REQUEST_REJECTED"
    TRANSACTION_CREATED = "TRANSACTION_CREATED"
    TRANSACTION_STATUS = "TRANSACTION_STATUS"
    COMPLAINT_FILED = "COMPLAINT_FILED"
    COMPLAINT_UPDATE = "COMPLAINT_UPDATE"
    GENERAL = "GENERAL"


class NotificationCreate(BaseModel):
    user_id: int = Field(..., ge=1, description="Target recipient user ID")
    notification_type: NotificationType = Field(..., description="System event classification")
    title: str = Field(..., min_length=2, max_length=200, description="Short notification subject")
    message: str = Field(..., min_length=2, max_length=1000, description="Body content of notification")
    reference_id: Optional[str] = Field(None, max_length=60, description="Linked entity code (e.g. TXN-ID, REQ-ID)")


class NotificationResponse(BaseModel):
    id: int
    user_id: int
    notification_type: NotificationType
    title: str
    message: str
    is_read: bool
    reference_id: Optional[str] = None
    created_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


class NotificationListResponse(BaseModel):
    total: int = Field(..., ge=0)
    unread_count: int = Field(..., ge=0)
    items: List[NotificationResponse]
    skip: int = Field(..., ge=0)
    limit: int = Field(..., ge=1)
