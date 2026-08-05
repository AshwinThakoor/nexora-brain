from __future__ import annotations

from alembic.runtime.migration import MigrationContext
from sqlalchemy import text
from sqlalchemy.engine import Engine

from .database import Base, engine


def check_database_connection(database_engine: Engine | None = None) -> bool:
    """Verify that the configured database accepts a simple connection."""
    target_engine = database_engine or engine
    with target_engine.connect() as connection:
        connection.execute(text("SELECT 1"))
    return True


def get_database_revision(database_engine: Engine | None = None) -> str | None:
    """Return the applied Alembic revision, or None for an unmigrated database."""
    target_engine = database_engine or engine
    with target_engine.connect() as connection:
        context = MigrationContext.configure(connection)
        return context.get_current_revision()


def initialize_development_database(
    database_engine: Engine | None = None,
) -> None:
    """Create the current schema for explicit local/test compatibility only.

    Alembic is the official schema-management mechanism. Production and shared
    environments should run ``python -m alembic upgrade head`` instead.
    """
    from . import models  # noqa: F401

    target_engine = database_engine or engine
    Base.metadata.create_all(bind=target_engine)
