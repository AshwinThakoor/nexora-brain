from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from alembic import command
from alembic.config import Config
from alembic.runtime.migration import MigrationContext
from sqlalchemy import MetaData, Table, create_engine, inspect
from sqlalchemy.dialects import mysql
from sqlalchemy.schema import CreateTable, UniqueConstraint
from sqlalchemy.sql.sqltypes import String

from nexora_knowledge.database import Base


PROJECT_ROOT = Path(__file__).resolve().parents[1]
PARENT_REVISION = "3a_s1_001"
DOCUMENT_REGISTRY_REVISION = "3a_s2_001"
LATEST_REVISION = "3a_s6_001"
DOCUMENT_REGISTRY_TABLES = {
    "document_files",
    "document_identifiers",
    "document_relationships",
    "document_tags",
    "document_versions",
    "documents",
    "import_batches",
}


def migration_config(database_url: str) -> Config:
    config = Config(str(PROJECT_ROOT / "alembic.ini"))
    config.set_main_option("script_location", str(PROJECT_ROOT / "alembic"))
    config.set_main_option("sqlalchemy.url", database_url)
    return config


def test_document_registry_migration_cycle(tmp_path: Path) -> None:
    path = tmp_path / "document-registry-migration.sqlite"
    url = f"sqlite:///{path.resolve().as_posix()}"
    config = migration_config(url)
    command.upgrade(config, PARENT_REVISION)

    engine = create_engine(url)
    metadata = MetaData()
    sources = Table("sources", metadata, autoload_with=engine)
    licenses = Table("source_licenses", metadata, autoload_with=engine)
    timestamp = datetime.now(timezone.utc)
    with engine.begin() as connection:
        license_id = connection.execute(
            licenses.insert().values(
                name="Migration Licence",
                slug="migration-licence",
                allows_ingestion=True,
                allows_distribution=False,
            )
        ).inserted_primary_key[0]
        connection.execute(
            sources.insert().values(
                uuid="67c734f6-665f-4913-ac7f-347c015c1f30",
                slug="migration-source",
                title="Migration Source",
                source_type="report",
                language="en",
                trust_level="official",
                license_id=license_id,
                active=True,
                archived=False,
                created_at=timestamp,
                updated_at=timestamp,
            )
        )
    engine.dispose()

    command.upgrade(config, "head")
    upgraded = create_engine(url)
    assert DOCUMENT_REGISTRY_TABLES <= set(
        inspect(upgraded).get_table_names()
    )
    with upgraded.connect() as connection:
        assert (
            MigrationContext.configure(connection).get_current_revision()
            == LATEST_REVISION
        )
    upgraded.dispose()
    command.check(config)

    command.downgrade(config, PARENT_REVISION)
    downgraded = create_engine(url)
    assert DOCUMENT_REGISTRY_TABLES.isdisjoint(
        inspect(downgraded).get_table_names()
    )
    downgraded.dispose()

    command.upgrade(config, "head")
    final_engine = create_engine(url)
    with final_engine.connect() as connection:
        assert (
            MigrationContext.configure(connection).get_current_revision()
            == LATEST_REVISION
        )
    final_engine.dispose()


def test_document_registry_models_compile_for_mysql() -> None:
    dialect = mysql.dialect()
    for table_name in DOCUMENT_REGISTRY_TABLES:
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
