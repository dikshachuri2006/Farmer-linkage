from unittest.mock import MagicMock
import pytest
from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import DeclarativeBase, Session
from app.core.config import settings
from app.database.base import Base, TimestampMixin
from app.database.connection import (
    SessionLocal,
    create_db_engine,
    get_db,
    verify_database_connection,
)


def test_base_declarative_structure():
    """Verify Base is a valid SQLAlchemy 2.0 DeclarativeBase."""
    assert issubclass(Base, DeclarativeBase)
    assert hasattr(TimestampMixin, "created_at")
    assert hasattr(TimestampMixin, "updated_at")


def test_create_db_engine():
    """Verify database engine initialization with configured PostgreSQL settings."""
    engine = create_db_engine()
    assert isinstance(engine, Engine)
    # Validate driver is psycopg
    assert "psycopg" in str(engine.url.drivername)


def test_session_generator_lifecycle():
    """Verify get_db dependency yields a session and closes it cleanly."""
    session_gen = get_db()
    db_session = next(session_gen)
    assert isinstance(db_session, Session)
    
    # Finish the generator to trigger the finally: db.close() block
    with pytest.raises(StopIteration):
        next(session_gen)


def test_verify_database_connection_failure():
    """Verify connection probe returns False safely without raising when DB is offline."""
    # Dummy engine pointing to an unreachable port
    unreachable_engine = create_engine(
        "postgresql+psycopg://postgres:wrong_pwd@127.0.0.1:54999/nonexistent_db",
        connect_args={"connect_timeout": 1},
    )
    is_connected = verify_database_connection(unreachable_engine)
    assert is_connected is False


def test_verify_database_connection_success_with_engine():
    """Verify connection probe returns True when connection succeeds."""
    mock_engine = MagicMock(spec=Engine)
    mock_connection = MagicMock()
    mock_result = MagicMock()
    mock_result.scalar.return_value = 1
    mock_connection.execute.return_value = mock_result
    mock_engine.connect.return_value.__enter__.return_value = mock_connection

    is_connected = verify_database_connection(mock_engine)
    assert is_connected is True
