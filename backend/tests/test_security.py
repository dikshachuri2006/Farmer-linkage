import time
from datetime import timedelta
import jwt
import pytest
from app.core.config import settings
from app.core.security import (
    UserRole,
    create_access_token,
    decode_access_token,
    get_password_hash,
    verify_password,
)


def test_password_hashing_and_verification():
    raw_password = "SecureFarmerPassword123!"
    hashed = get_password_hash(raw_password)

    # Hash must be non-empty and different from plain password
    assert hashed != raw_password
    assert hashed.startswith("$2b$")

    # Verification must succeed for correct password
    assert verify_password(raw_password, hashed) is True

    # Verification must fail for incorrect password
    assert verify_password("WrongPassword999", hashed) is False
    assert verify_password("", hashed) is False


def test_jwt_token_generation_and_decode():
    user_id = 42
    role = UserRole.FARMER

    token = create_access_token(
        subject=user_id,
        role=role.value,
        expires_delta=timedelta(minutes=30),
        extra_claims={"phone": "9876543210"},
    )

    assert isinstance(token, str)
    assert len(token) > 20

    payload = decode_access_token(token)
    assert payload["sub"] == str(user_id)
    assert payload["role"] == "FARMER"
    assert payload["phone"] == "9876543210"
    assert "exp" in payload


def test_jwt_expired_token():
    # Token with negative expiry
    token = create_access_token(
        subject=99,
        role=UserRole.BUYER.value,
        expires_delta=timedelta(seconds=-5),
    )

    with pytest.raises(jwt.ExpiredSignatureError):
        decode_access_token(token)


def test_jwt_tampered_token():
    token = create_access_token(subject=1, role=UserRole.ADMIN.value)
    tampered = token[:-4] + "abcd"

    with pytest.raises(jwt.InvalidTokenError):
        decode_access_token(tampered)
