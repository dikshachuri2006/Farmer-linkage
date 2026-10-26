"""Provision one administrator from a trusted local operator session.

Run from the backend directory with ``python .\\provision_admin.py``.
This is deliberately a local command, not an HTTP endpoint.
"""

from __future__ import annotations

import getpass
import sys
from typing import Optional

from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.security import UserRole, get_password_hash
from app.models.entities import User
from app.schemas.auth import UserRegisterRequest


class AdminProvisioningError(RuntimeError):
    """A safe-to-display provisioning error without database details."""


def _safe_validation_message(error: ValidationError) -> str:
    """Summarize invalid fields without including submitted values."""
    reasons = {
        "email": "must be a valid email address",
        "full_name": "must contain 2 to 150 non-blank characters",
        "phone_number": "must be a valid 10-digit Indian mobile number starting with 6-9",
        "password": "must be 8 to 72 characters, include a letter and digit, and be at most 72 UTF-8 bytes",
        "role": "is not accepted by this provisioning command",
    }
    problems = []
    for item in error.errors(include_input=False, include_url=False):
        location = item.get("loc", ())
        field = location[0] if location and location[0] in reasons else None
        if field is None:
            problems.append("account details contain invalid or unsupported input")
        else:
            problems.append(f"{field}: {reasons[field]}")
    detail = "; ".join(dict.fromkeys(problems)) or "account details are invalid"
    return f"Invalid account details: {detail}. No account was created."


def _has_explicit_database_configuration(fields_set: set[str]) -> bool:
    """Reject the application's development-only connection defaults."""
    if "DATABASE_URL" in fields_set:
        return True
    required = {
        "POSTGRES_SERVER",
        "POSTGRES_PORT",
        "POSTGRES_USER",
        "POSTGRES_PASSWORD",
        "POSTGRES_DB",
    }
    return required.issubset(fields_set)


def _duplicate_field(error: IntegrityError) -> Optional[str]:
    diagnostic = getattr(error.orig, "diag", None)
    constraint_name = getattr(diagnostic, "constraint_name", None)
    if constraint_name == "users_email_key" or "UNIQUE constraint failed: users.email" in str(error.orig):
        return "email"
    if constraint_name == "users_phone_number_key" or "UNIQUE constraint failed: users.phone_number" in str(error.orig):
        return "phone"
    return None


def provision_admin(
    db: Session,
    *,
    email: str,
    full_name: str,
    phone_number: str,
    password: str,
) -> User:
    """Create a new ADMIN user, refusing any existing email or phone identity."""
    try:
        # Reuse the public registration field validation without accepting its role
        # value for creation. The inserted role below is always the existing ADMIN enum.
        validated = UserRegisterRequest(
            email=email.strip(),
            full_name=full_name.strip(),
            phone_number=phone_number,
            password=password,
            role=UserRole.FARMER,
        )
        if len(password.encode("utf-8")) > 72:
            raise AdminProvisioningError(
                "Invalid password: must be at most 72 UTF-8 bytes. No account was created."
            )

        if db.scalar(select(User.id).where(User.email == str(validated.email))) is not None:
            raise AdminProvisioningError("An account with this email already exists; no changes were made.")
        if db.scalar(select(User.id).where(User.phone_number == validated.phone_number)) is not None:
            raise AdminProvisioningError("An account with this phone already exists; no changes were made.")

        user = User(
            email=str(validated.email),
            full_name=validated.full_name,
            phone_number=validated.phone_number,
            hashed_password=get_password_hash(password),
            role=UserRole.ADMIN,
            is_active=True,
        )
        db.add(user)
        db.flush()
        db.refresh(user)
        db.commit()
        return user
    except IntegrityError as error:
        db.rollback()
        field = _duplicate_field(error)
        if field == "email":
            raise AdminProvisioningError("An account with this email already exists; no changes were made.") from error
        if field == "phone":
            raise AdminProvisioningError("An account with this phone already exists; no changes were made.") from error
        raise AdminProvisioningError("Provisioning failed; no account was created.") from error
    except ValidationError as error:
        db.rollback()
        raise AdminProvisioningError(_safe_validation_message(error)) from None
    except Exception:
        db.rollback()
        raise


def main() -> int:
    print("Create a separate administrator account. No existing account will be changed.")
    email = input("Administrator email: ").strip()
    full_name = input("Administrator full name: ").strip()
    phone_number = input("Administrator phone number: ").strip()
    password = getpass.getpass("Administrator password: ")
    confirmation = getpass.getpass("Confirm password: ")

    if password != confirmation:
        print("Passwords did not match; no account was created.", file=sys.stderr)
        return 1

    session: Optional[Session] = None
    try:
        from app.core.config import settings

        if not _has_explicit_database_configuration(settings.model_fields_set):
            print(
                "Database configuration is missing. Set DATABASE_URL or all POSTGRES_* settings in backend/.env.",
                file=sys.stderr,
            )
            return 1

        # Import the project's configured session factory only after checking that
        # configuration came from the environment or .env, not application defaults.
        from app.database.connection import SessionLocal

        session = SessionLocal()
        user = provision_admin(
            session,
            email=email,
            full_name=full_name,
            phone_number=phone_number,
            password=password,
        )
        print(f"Administrator account created for {user.email} (user ID {user.id}).")
        return 0
    except AdminProvisioningError as error:
        print(str(error), file=sys.stderr)
        return 1
    except ValueError:
        print("Provisioning failed; no account was created. Database details were not displayed.", file=sys.stderr)
        return 1
    except Exception:
        # Never display exception text: driver messages can contain connection details.
        print("Provisioning failed; no account was created. Database details were not displayed.", file=sys.stderr)
        return 1
    finally:
        password = ""
        confirmation = ""
        if session is not None:
            session.close()


if __name__ == "__main__":
    raise SystemExit(main())
