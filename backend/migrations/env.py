from logging.config import fileConfig

from alembic import context
from sqlalchemy import create_engine, pool

from app.core.config import settings
from app.database.base import Base
import app.models  # noqa: F401  Register all ORM tables on Base.metadata.


config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Keep credentials in the existing environment-backed settings. Doubling percent
# signs prevents ConfigParser interpolation from altering percent-encoded URLs.
config.set_main_option(
    "sqlalchemy.url", settings.SQLALCHEMY_DATABASE_URI.replace("%", "%%")
)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """Render migration SQL without creating an engine or opening a connection."""
    context.configure(
        url=settings.SQLALCHEMY_DATABASE_URI,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
        compare_server_default=True,
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations using the project's environment-configured database URL."""
    connectable = create_engine(
        settings.SQLALCHEMY_DATABASE_URI,
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
            compare_server_default=True,
        )

        with context.begin_transaction():
            context.run_migrations()

    connectable.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
