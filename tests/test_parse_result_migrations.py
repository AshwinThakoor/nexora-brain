from __future__ import annotations

from pathlib import Path

from alembic import command
from alembic.autogenerate import compare_metadata
from alembic.config import Config
from alembic.runtime.migration import MigrationContext
from sqlalchemy import create_engine, inspect
from sqlalchemy.dialects import mysql, sqlite
from sqlalchemy.schema import CreateTable, UniqueConstraint
from sqlalchemy.sql.sqltypes import String

from nexora_knowledge.database import Base


PROJECT_ROOT = Path(__file__).resolve().parents[1]
PARENT_REVISION = "3a_s4_001"
PARSE_REVISION = "3a_s6_001"
PARSE_TABLES = {
    "parse_artifacts",
    "parse_executions",
    "parse_results",
}


def _config(database_url: str) -> Config:
    config = Config(str(PROJECT_ROOT / "alembic.ini"))
    config.set_main_option("script_location", str(PROJECT_ROOT / "alembic"))
    config.set_main_option("sqlalchemy.url", database_url)
    return config


def test_parse_result_migration_upgrade_downgrade_reupgrade(
    tmp_path: Path,
) -> None:
    database = tmp_path / "parse-results.sqlite"
    url = f"sqlite:///{database.resolve().as_posix()}"
    config = _config(url)
    command.upgrade(config, PARENT_REVISION)
    engine = create_engine(url)
    assert PARSE_TABLES.isdisjoint(inspect(engine).get_table_names())
    engine.dispose()

    command.upgrade(config, "head")
    upgraded = create_engine(url)
    assert PARSE_TABLES <= set(inspect(upgraded).get_table_names())
    with upgraded.connect() as connection:
        context = MigrationContext.configure(connection)
        assert context.get_current_revision() == PARSE_REVISION
        assert compare_metadata(context, Base.metadata) == []
    upgraded.dispose()
    command.check(config)

    command.downgrade(config, PARENT_REVISION)
    downgraded = create_engine(url)
    assert PARSE_TABLES.isdisjoint(inspect(downgraded).get_table_names())
    assert "stored_files" in inspect(downgraded).get_table_names()
    downgraded.dispose()

    command.upgrade(config, "head")
    final = create_engine(url)
    with final.connect() as connection:
        assert (
            MigrationContext.configure(connection).get_current_revision()
            == PARSE_REVISION
        )
    final.dispose()


def test_parse_result_schema_compiles_for_sqlite_and_mysql() -> None:
    for dialect in (sqlite.dialect(), mysql.dialect()):
        for table_name in PARSE_TABLES:
            table = Base.metadata.tables[table_name]
            ddl = str(CreateTable(table).compile(dialect=dialect))
            assert "CREATE TABLE" in ddl
            assert all(
                len(identifier) <= dialect.max_identifier_length
                for identifier in [
                    table.name,
                    *(
                        constraint.name
                        for constraint in table.constraints
                        if constraint.name
                    ),
                    *(index.name for index in table.indexes if index.name),
                ]
            )
            indexed = [tuple(index.columns) for index in table.indexes]
            indexed.extend(
                tuple(constraint.columns)
                for constraint in table.constraints
                if isinstance(constraint, UniqueConstraint)
            )
            for columns in indexed:
                utf8mb4_bytes = sum(
                    column.type.length * 4
                    for column in columns
                    if isinstance(column.type, String)
                )
                assert utf8mb4_bytes <= 3072
