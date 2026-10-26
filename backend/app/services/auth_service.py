from typing import Any, Optional, Protocol
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from app.core.security import verify_password
from app.models.entities import User
from app.schemas.auth import UserRegisterRequest, normalize_phone_number


class DatabaseSchemaPendingError(RuntimeError):
    """Raised by repositories whose persistence schema remains deferred."""
    pass


class DuplicateUserError(ValueError):
    """A database uniqueness constraint rejected a duplicate user identity."""

    def __init__(self, field: str):
        self.field = field
        super().__init__(f"A user with this {field} already exists.")


class InvalidCredentialsError(ValueError):
    """Raised when an identifier or password does not match a user."""


class InactiveUserError(ValueError):
    """Raised when valid credentials belong to a disabled account."""


def _duplicate_user_field(error: IntegrityError) -> Optional[str]:
    """Return the user field for known unique constraints, if this is a duplicate."""
    original = error.orig
    diagnostic = getattr(original, "diag", None)
    constraint_name = getattr(diagnostic, "constraint_name", None)
    if constraint_name == "users_email_key":
        return "email"
    if constraint_name == "users_phone_number_key":
        return "phone"
    return None


class UserRepository(Protocol):
    """Repository interface for persistent user data operations."""
    def get_by_id(self, db: Session, user_id: int) -> Optional[Any]:
        ...

    def get_by_email(self, db: Session, email: str) -> Optional[Any]:
        ...

    def get_by_phone(self, db: Session, phone_number: str) -> Optional[Any]:
        ...

    def create_user(
        self, db: Session, user_in: UserRegisterRequest, password_hash: str
    ) -> Any:
        ...


class DefaultPostgresUserRepository:
    """SQLAlchemy repository for the migrated ``users`` table."""
    def get_by_id(self, db: Session, user_id: int) -> Optional[Any]:
        return db.get(User, user_id)

    def get_by_email(self, db: Session, email: str) -> Optional[Any]:
        return db.scalar(select(User).where(User.email == str(email)))

    def get_by_phone(self, db: Session, phone_number: str) -> Optional[Any]:
        return db.scalar(select(User).where(User.phone_number == phone_number))

    def create_user(
        self, db: Session, user_in: UserRegisterRequest, password_hash: str
    ) -> Any:
        user = User(
            email=str(user_in.email),
            phone_number=user_in.phone_number,
            hashed_password=password_hash,
            full_name=user_in.full_name,
            role=user_in.role,
            is_active=True,
        )
        try:
            db.add(user)
            db.flush()
            db.refresh(user)
            db.commit()
            return user
        except IntegrityError as error:
            db.rollback()
            field = _duplicate_user_field(error)
            if field is not None:
                raise DuplicateUserError(field) from error
            raise
        except Exception:
            db.rollback()
            raise


def authenticate_user(
    db: Session,
    user_repo: UserRepository,
    identifier: str,
    password: str,
) -> Any:
    """Authenticate an email or phone identifier using the repository's user record."""
    normalized_identifier = identifier.strip()
    if "@" in normalized_identifier:
        user = user_repo.get_by_email(db, normalized_identifier)
    else:
        try:
            phone = normalize_phone_number(normalized_identifier)
            user = user_repo.get_by_phone(db, phone)
        except ValueError:
            user = None

    if user is None or not verify_password(password, user.hashed_password):
        raise InvalidCredentialsError("Invalid email/phone or password.")
    if not getattr(user, "is_active", True):
        raise InactiveUserError("Account is inactive or suspended. Please contact support.")
    return user


# Global default repository instance
_default_user_repo = DefaultPostgresUserRepository()


def get_user_repository() -> UserRepository:
    """FastAPI dependency for injecting the user repository."""
    return _default_user_repo
