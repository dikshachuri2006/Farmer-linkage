"""One-time interactive password reset for the specified test farmer account."""

import getpass
import re
import sys

from sqlalchemy import create_engine, select, update
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.security import get_password_hash
from app.models.entities import User


USER_ID = 16
USER_EMAIL = "farmer.test.20261024@example.com"


def main() -> int:
    # The engine reads the project's environment-based settings. Never echo its URL.
    engine = create_engine(settings.SQLALCHEMY_DATABASE_URI, echo=False)
    session: Session | None = None

    try:
        session = Session(engine)
        matched_id = session.scalar(
            select(User.id).where(User.id == USER_ID, User.email == USER_EMAIL)
        )
        if matched_id is None:
            print("No change made: the user ID and email did not match.")
            return 1

        password = getpass.getpass("New password: ")
        confirmation = getpass.getpass("Confirm new password: ")

        # Match the public registration password policy and bcrypt's byte limit.
        if password != confirmation:
            print("No change made: passwords did not match.")
            return 1
        if (
            len(password) < 8
            or not re.search(r"[A-Za-z]", password)
            or not re.search(r"\d", password)
        ):
            print("No change made: use at least 8 characters, including a letter and a digit.")
            return 1
        if len(password.encode("utf-8")) > 72:
            print("No change made: the password must be at most 72 UTF-8 bytes.")
            return 1

        password_hash = get_password_hash(password)
        result = session.execute(
            update(User)
            .where(User.id == USER_ID, User.email == USER_EMAIL)
            .values(hashed_password=password_hash)
            .execution_options(synchronize_session=False)
        )
        if result.rowcount != 1:
            session.rollback()
            print("No change made: the account identity no longer matched.")
            return 1

        session.commit()
        print(f"Password updated for verified user ID {USER_ID}.")
        return 0
    except Exception:
        if session is not None:
            session.rollback()
        # Keep database errors, connection details, password, and hash out of output.
        print("Reset failed. The transaction was rolled back; no sensitive details were displayed.")
        return 1
    finally:
        if session is not None:
            session.close()
        engine.dispose()


if __name__ == "__main__":
    sys.exit(main())
