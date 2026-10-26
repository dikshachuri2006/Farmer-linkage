import re
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator
from app.core.security import UserRole


def normalize_phone_number(v: str) -> str:
    """Normalize and validate a 10-digit Indian mobile number."""
    # Strip spaces and dashes
    cleaned = re.sub(r"[\s\-]", "", v)
    if cleaned.startswith("+91"):
        cleaned = cleaned[3:]
    elif cleaned.startswith("0") and len(cleaned) == 11:
        cleaned = cleaned[1:]
    if not re.fullmatch(r"[6-9]\d{9}", cleaned):
        raise ValueError("Phone number must be a valid 10-digit Indian mobile number starting with 6-9.")
    return cleaned


normalize_phone = normalize_phone_number


class UserRegisterRequest(BaseModel):
    full_name: str = Field(..., min_length=2, max_length=150, description="User's full name")
    email: EmailStr = Field(..., description="Valid unique email address")
    phone_number: str = Field(
        ...,
        description="10-digit Indian mobile number (e.g. 9876543210)",
    )
    password: str = Field(
        ...,
        min_length=8,
        max_length=72,
        description="Secure password (at least 8 characters, containing letter and digit)",
    )
    role: UserRole = Field(
        default=UserRole.FARMER,
        description="Role: FARMER or BUYER (ADMIN cannot be registered publicly)",
    )

    @field_validator("phone_number")
    @classmethod
    def validate_phone(cls, v: str) -> str:
        return normalize_phone_number(v)

    @field_validator("password")
    @classmethod
    def validate_password_strength(cls, v: str) -> str:
        if not re.search(r"[A-Za-z]", v):
            raise ValueError("Password must contain at least one letter.")
        if not re.search(r"\d", v):
            raise ValueError("Password must contain at least one digit.")
        return v

    @field_validator("role")
    @classmethod
    def validate_public_role(cls, v: UserRole) -> UserRole:
        if v == UserRole.ADMIN:
            raise ValueError("Administrator accounts cannot be created via public registration.")
        return v


class UserLoginRequest(BaseModel):
    username_or_email: str = Field(
        ...,
        description="Registered email address or 10-digit phone number",
    )
    password: str = Field(
        ...,
        min_length=1,
        description="Account password",
    )


class UserResponse(BaseModel):
    id: int
    full_name: str
    email: str
    phone_number: str
    role: UserRole
    is_active: bool
    created_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in_minutes: int
    user: UserResponse


class OAuth2TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class UserMeResponse(UserResponse):
    pass
