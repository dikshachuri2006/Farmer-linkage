import logging
from typing import Generator
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker
from app.core.config import settings

logger = logging.getLogger(__name__)


def create_db_engine(uri: str = settings.SQLALCHEMY_DATABASE_URI) -> Engine:
    """
    Creates a SQLAlchemy engine configured for PostgreSQL with connection pooling.
    pool_pre_ping=True ensures stale connections are recycled safely.
    """
    return create_engine(
        uri,
        pool_pre_ping=True,
        pool_size=10,
        max_overflow=20,
        echo=settings.DEBUG and settings.ENVIRONMENT == "development",
    )


# Default application engine
engine: Engine = create_db_engine()

# Default session factory
SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine,
)


def get_db() -> Generator[Session, None, None]:
    """
    FastAPI dependency that provides a transactional database session per request.
    Automatically closes session when the request finishes.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def verify_database_connection(target_engine: Engine = engine) -> bool:
    """
    Safely probes the database with 'SELECT 1'.
    Returns True if reachable, False otherwise without raising unhandled exceptions.
    """
    try:
        with target_engine.connect() as connection:
            result = connection.execute(text("SELECT 1"))
            return result.scalar() == 1
    except Exception as e:
        logger.warning("Database connection probe failed: %s", str(e))
        return False
