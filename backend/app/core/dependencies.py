from typing import Callable, List, Optional
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
import jwt
from pydantic import BaseModel
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session
from app.core.config import settings
from app.core.security import UserRole, decode_access_token
from app.database.connection import get_db
from app.services.auth_service import UserRepository, get_user_repository

# OAuth2 scheme pointing to the form-encoded token endpoint used by Swagger UI.
oauth2_scheme = OAuth2PasswordBearer(
    tokenUrl=f"{settings.API_V1_STR}/auth/token",
    auto_error=True,
)


class AuthenticatedUser(BaseModel):
    id: int
    role: UserRole
    raw_payload: dict


def get_current_user_claims(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
    user_repo: UserRepository = Depends(get_user_repository),
) -> AuthenticatedUser:
    """
    Decodes the JWT token from the Authorization header and validates claims.
    Raises 401 Unauthorized if token is expired, invalid, or malformed.
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials or token expired.",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = decode_access_token(token)
    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has expired. Please log in again.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except jwt.InvalidTokenError:
        raise credentials_exception

    subject: Optional[str] = payload.get("sub")
    role_str: Optional[str] = payload.get("role")
    try:
        user_id = int(subject) if subject is not None else None
        token_role = UserRole(role_str) if role_str is not None else None
    except (ValueError, TypeError):
        raise credentials_exception
    if user_id is None or token_role is None:
        raise credentials_exception

    try:
        user = user_repo.get_by_id(db, user_id)
    except SQLAlchemyError as error:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Authentication service temporarily unavailable.",
        ) from error

    if user is None or not user.is_active:
        raise credentials_exception
    try:
        current_role = UserRole(user.role)
    except (ValueError, TypeError):
        raise credentials_exception
    if token_role != current_role:
        raise credentials_exception

    return AuthenticatedUser(id=user_id, role=current_role, raw_payload=payload)


def require_role(allowed_roles: List[UserRole]) -> Callable:
    """
    Factory dependency to enforce role-based access control (RBAC).
    Rejects any user whose role is not within the allowed_roles list with 403 Forbidden.
    """

    def role_checker(
        current_user: AuthenticatedUser = Depends(get_current_user_claims),
    ) -> AuthenticatedUser:
        if current_user.role not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Access forbidden: requires one of {[r.value for r in allowed_roles]} role.",
            )
        return current_user

    return role_checker


# Convenient role-specific dependencies
require_farmer = require_role([UserRole.FARMER])
require_buyer = require_role([UserRole.BUYER])
require_admin = require_role([UserRole.ADMIN])
require_farmer_or_admin = require_role([UserRole.FARMER, UserRole.ADMIN])
require_buyer_or_admin = require_role([UserRole.BUYER, UserRole.ADMIN])
