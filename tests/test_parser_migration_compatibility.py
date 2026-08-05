from __future__ import annotations

from pathlib import Path

from alembic import command
from alembic.autogenerate import compare_metadata
from alembic.config import Config
from alembic.runtime.migration import MigrationContext
from alembic.script import ScriptDirectory
from sqlalchemy import create_engine
from sqlalchemy.dialects import mysql, sqlite
from sqlalchemy.schema import CreateTable

from nexora_knowledge.database import Base
from nexora_knowledge.models.canonical_document import CanonicalDocument


PROJECT_ROOT = Path(__file__).resolve().parents[1]
CURRENT_HEAD = "3a_s6_001"


def _config(database_url: str) -> Config:
    config = Config(str(PROJECT_ROOT / "alembic.ini"))
    config.set_main_option(
        "script_location",
        str(PROJECT_ROOT / "alembic"),
    )
    config.set_main_option("sqlalchemy.url", database_url)
    return config


def test_parser_framework_and_results_share_current_migration(
    tmp_path: Path,
) -> None:
    database_path = tmp_path / "parser-compatibility.sqlite"
    database_url = f"sqlite:///{database_path.resolve().as_posix()}"
    config = _config(database_url)
    scripts = ScriptDirectory.from_config(config)

    assert scripts.get_current_head() == CURRENT_HEAD
    assert "parse_results" in Base.metadata.tables
    assert not hasattr(CanonicalDocument, "__table__")

    command.upgrade(config, "head")
    engine = create_engine(database_url)
    with engine.connect() as connection:
        context = MigrationContext.configure(connection)
        assert context.get_current_revision() == CURRENT_HEAD
        assert compare_metadata(context, Base.metadata) == []
    engine.dispose()
    command.check(config)


def test_existing_metadata_remains_sqlite_and_mysql_compilable() -> None:
    for dialect in (sqlite.dialect(), mysql.dialect()):
        for table in Base.metadata.sorted_tables:
            ddl = str(CreateTable(table).compile(dialect=dialect))
            assert "CREATE TABLE" in ddl
