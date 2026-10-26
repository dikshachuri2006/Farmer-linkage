from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from app.core.config import settings
from app.core.dependencies import AuthenticatedUser, get_current_user_claims
from app.core.security import UserRole, create_access_token, get_password_hash
from app.database.connection import get_db
from app.schemas.auth import (
    OAuth2TokenResponse,
    TokenResponse,
    UserLoginRequest,
    UserMeResponse,
    UserRegisterRequest,
    UserResponse,
)
from app.services.auth_service import (
    DatabaseSchemaPendingError,
    DuplicateUserError,
    InactiveUserError,
    InvalidCredentialsError,
    UserRepository,
    authenticate_user,
    get_user_repository,
)

router = APIRouter(prefix="/auth", tags=["Authentication"])


def _authenticate_and_issue_token(
    identifier: str,
    password: str,
    db: Session,
    user_repo: UserRepository,
):
    try:
        user = authenticate_user(db, user_repo, identifier, password)
    except InvalidCredentialsError as error:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email/phone or password.",
            headers={"WWW-Authenticate": "Bearer"},
        ) from error
    except InactiveUserError as error:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(error),
        ) from error
    except DatabaseSchemaPendingError as error:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Database user table schema is pending approval by Ankita: {str(error)}",
        ) from error

    role = user.role.value if hasattr(user.role, "value") else str(user.role)
    access_token = create_access_token(
        subject=user.id,
        role=role,
        extra_claims={"email": user.email, "full_name": user.full_name},
    )
    return user, access_token, role


@router.post(
    "/register",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register a new Farmer or Buyer account",
)
def register_user(
    user_in: UserRegisterRequest,
    db: Session = Depends(get_db),
    user_repo: UserRepository = Depends(get_user_repository),
):
    """
    Registers a new Farmer or Buyer account.
    - Validates email and Indian 10-digit mobile number format.
    - Validates password strength (minimum 8 chars, letter + digit).
    - Prevents public registration of ADMIN role.
    - Hashes password using bcrypt. Never stores plain passwords.
    - Prevents duplicate registration.
    """
    if user_in.role == UserRole.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Administrator accounts cannot be registered publicly.",
        )

    try:
        # Check duplicate email
        existing_email = user_repo.get_by_email(db, user_in.email)
        if existing_email:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="An account with this email address already exists.",
            )

        # Check duplicate phone
        existing_phone = user_repo.get_by_phone(db, user_in.phone_number)
        if existing_phone:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="An account with this phone number already exists.",
            )

        # Hash password securely
        password_hash = get_password_hash(user_in.password)

        # Persist user record
        created_user = user_repo.create_user(db, user_in, password_hash)
        return created_user

    except DuplicateUserError as e:
        detail = (
            "An account with this email address already exists."
            if e.field == "email"
            else "An account with this phone number already exists."
        )
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=detail) from e
    except DatabaseSchemaPendingError as e:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Database user table schema is pending approval by Ankita: {str(e)}",
        )


@router.post(
    "/login",
    response_model=TokenResponse,
    status_code=status.HTTP_200_OK,
    summary="Authenticate user and issue JWT access token",
)
def login_user(
    credentials: UserLoginRequest,
    db: Session = Depends(get_db),
    user_repo: UserRepository = Depends(get_user_repository),
):
    """
    Authenticates a user by email or mobile number and password.
    Returns a signed JWT access token upon successful credentials verification.
    """
    user, access_token, role = _authenticate_and_issue_token(
        credentials.username_or_email,
        credentials.password,
        db,
        user_repo,
    )
    user_response = UserResponse(
        id=user.id,
        full_name=user.full_name,
        email=user.email,
        phone_number=user.phone_number,
        role=UserRole(role),
        is_active=getattr(user, "is_active", True),
        created_at=getattr(user, "created_at", None),
    )
    return TokenResponse(
        access_token=access_token,
        token_type="bearer",
        expires_in_minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES,
        user=user_response,
    )


@router.post(
    "/token",
    response_model=OAuth2TokenResponse,
    status_code=status.HTTP_200_OK,
    summary="Authenticate with OAuth2 password form and return an access token",
)
def oauth2_password_token(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db),
    user_repo: UserRepository = Depends(get_user_repository),
):
    """OAuth2-compatible form endpoint used by Swagger UI's Authorize dialog."""
    _, access_token, _ = _authenticate_and_issue_token(
        form_data.username,
        form_data.password,
        db,
        user_repo,
    )
    return OAuth2TokenResponse(access_token=access_token, token_type="bearer")


@router.get(
    "/me",
    response_model=UserMeResponse,
    status_code=status.HTTP_200_OK,
    summary="Get authenticated user profile",
)
def get_current_user_profile(
    current_claims: AuthenticatedUser = Depends(get_current_user_claims),
    db: Session = Depends(get_db),
    user_repo: UserRepository = Depends(get_user_repository),
):
    """
    Returns the profile of the currently authenticated user.
    Requires a valid Bearer JWT access token.
    """
    try:
        user = user_repo.get_by_id(db, current_claims.id)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User profile not found.",
            )
        user_role_str = user.role.value if hasattr(user.role, "value") else str(user.role)
        return UserMeResponse(
            id=user.id,
            full_name=user.full_name,
            email=user.email,
            phone_number=user.phone_number,
            role=UserRole(user_role_str),
            is_active=getattr(user, "is_active", True),
            created_at=getattr(user, "created_at", None),
        )
    except DatabaseSchemaPendingError:
        # Fall back gracefully to verified JWT claims when DB schema is awaiting Ankita's approval
        return UserMeResponse(
            id=current_claims.id,
            full_name=current_claims.raw_payload.get("full_name", "Verified User"),
            email=current_claims.raw_payload.get("email", "farmer@example.com"),
            phone_number=current_claims.raw_payload.get("phone", "9876543210"),
            role=current_claims.role,
            is_active=True,
            created_at=None,
        )
