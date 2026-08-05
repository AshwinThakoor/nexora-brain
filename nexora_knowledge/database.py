from __future__ import annotations

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine, make_url
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from .config import get_database_url


class Base(DeclarativeBase):
    pass


def is_sqlite_database_url(database_url: str) -> bool:
    """Return whether a SQLAlchemy URL selects the SQLite dialect."""
    return make_url(database_url).get_backend_name() == "sqlite"


def create_database_engine(database_url: str | None = None) -> Engine:
    """Create an engine with dialect-appropriate connection options."""
    resolved_url = get_database_url(database_url)
    options: dict[str, object] = {"pool_pre_ping": True}
    if is_sqlite_database_url(resolved_url):
        options["connect_args"] = {"check_same_thread": False}
    return create_engine(resolved_url, **options)


engine = create_database_engine()
SessionLocal = sessionmaker(
    bind=engine,
    autoflush=False,
    autocommit=False,
    expire_on_commit=False,
)


def init_database() -> None:
    """Compatibility wrapper for explicit local-development initialization."""
    from .db_management import initialize_development_database

    initialize_development_database()
