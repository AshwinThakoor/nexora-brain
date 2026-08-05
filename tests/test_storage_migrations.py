from __future__ import annotations

from pathlib import Path

from alembic import command
from alembic.config import Config
from alembic.runtime.migration import MigrationContext
from sqlalchemy import create_engine, inspect
from sqlalchemy.dialects import mysql
from sqlalchemy.schema import CreateTable, UniqueConstraint
from sqlalchemy.sql.sqltypes import String

from nexora_knowledge.database import Base


PROJECT_ROOT = Path(__file__).resolve().parents[1]
PARENT_REVISION = "3a_s3_001"
STORAGE_REVISION = "3a_s4_001"
LATEST_REVISION = "3a_s6_001"
STORAGE_TABLES = {
    "file_hashes",
    "storage_providers",
    "stored_files",
    "upload_sessions",
}


def migration_config(database_url: str) -> Config:
    config = Config(str(PROJECT_ROOT / "alembic.ini"))
    config.set_main_option("script_location", str(PROJECT_ROOT / "alembic"))
    config.set_main_option("sqlalchemy.url", database_url)
    return config


def test_storage_migration_upgrade_downgrade_cycle(tmp_path: Path) -> None:
    path = tmp_path / "secure-storage.sqlite"
    url = f"sqlite:///{path.resolve().as_posix()}"
    config = migration_config(url)
    command.upgrade(config, PARENT_REVISION)
    parent_engine = create_engine(url)
    assert STORAGE_TABLES.isdisjoint(
        inspect(parent_engine).get_table_names()
    )
    assert "document_versions" in inspect(parent_engine).get_table_names()
    parent_engine.dispose()

    command.upgrade(config, "head")
    upgraded = create_engine(url)
    assert STORAGE_TABLES <= set(inspect(upgraded).get_table_names())
    with upgraded.connect() as connection:
        assert (
            MigrationContext.configure(connection).get_current_revision()
            == LATEST_REVISION
        )
    upgraded.dispose()
    command.check(config)

    command.downgrade(config, PARENT_REVISION)
    downgraded = create_engine(url)
    assert STORAGE_TABLES.isdisjoint(
        inspect(downgraded).get_table_names()
    )
    assert "document_versions" in inspect(downgraded).get_table_names()
    downgraded.dispose()

    command.upgrade(config, "head")
    final_engine = create_engine(url)
    with final_engine.connect() as connection:
        assert (
            MigrationContext.configure(connection).get_current_revision()
            == LATEST_REVISION
        )
    final_engine.dispose()


def test_storage_models_compile_for_mysql_with_safe_keys() -> None:
    dialect = mysql.dialect()
    for table_name in STORAGE_TABLES:
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
        indexed_column_sets = [
            tuple(index.columns) for index in table.indexes
        ]
        indexed_column_sets.extend(
            tuple(constraint.columns)
            for constraint in table.constraints
            if isinstance(constraint, UniqueConstraint)
        )
        for columns in indexed_column_sets:
            utf8mb4_bytes = sum(
                column.type.length * 4
                for column in columns
                if isinstance(column.type, String)
            )
            assert utf8mb4_bytes <= 3072
