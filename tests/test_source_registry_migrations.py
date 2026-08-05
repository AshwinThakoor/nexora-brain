from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from alembic import command
from alembic.config import Config
from alembic.runtime.migration import MigrationContext
from sqlalchemy import MetaData, Table, create_engine, inspect, select
from sqlalchemy.dialects import mysql
from sqlalchemy.schema import CreateTable

from nexora_knowledge.database import Base


PROJECT_ROOT = Path(__file__).resolve().parents[1]
PARENT_REVISION = "2d_s3_001"
SOURCE_REGISTRY_REVISION = "3a_s1_001"
LATEST_REVISION = "3a_s6_001"
SOURCE_REGISTRY_TABLES = {
    "source_aliases",
    "source_licenses",
    "source_organizations",
    "source_tags",
    "source_versions",
}


def migration_config(database_url: str) -> Config:
    config = Config(str(PROJECT_ROOT / "alembic.ini"))
    config.set_main_option("script_location", str(PROJECT_ROOT / "alembic"))
    config.set_main_option("sqlalchemy.url", database_url)
    return config


def test_source_registry_migration_cycle_preserves_legacy_sources(
    tmp_path: Path,
) -> None:
    path = tmp_path / "source-registry-migration.sqlite"
    url = f"sqlite:///{path.resolve().as_posix()}"
    config = migration_config(url)
    command.upgrade(config, PARENT_REVISION)

    engine = create_engine(url)
    metadata = MetaData()
    sources = Table("sources", metadata, autoload_with=engine)
    timestamp = datetime.now(timezone.utc)
    with engine.begin() as connection:
        source_id = connection.execute(
            sources.insert().values(
                title="Preserved Legacy Source",
                source_type="legacy_document",
                created_at=timestamp,
                updated_at=timestamp,
            )
        ).inserted_primary_key[0]
    engine.dispose()

    command.upgrade(config, "head")
    upgraded = create_engine(url)
    inspector = inspect(upgraded)
    assert SOURCE_REGISTRY_TABLES <= set(inspector.get_table_names())
    assert {
        "uuid",
        "slug",
        "subtitle",
        "description",
        "language",
        "trust_level",
        "publication_date",
        "isbn",
        "doi",
        "external_identifier",
        "organization_id",
        "license_id",
        "active",
        "archived",
    } <= {
        column["name"] for column in inspector.get_columns("sources")
    }
    upgraded_metadata = MetaData()
    upgraded_sources = Table(
        "sources",
        upgraded_metadata,
        autoload_with=upgraded,
    )
    with upgraded.connect() as connection:
        row = connection.execute(
            select(upgraded_sources).where(upgraded_sources.c.id == source_id)
        ).one()
        assert row.title == "Preserved Legacy Source"
        assert row.uuid
        assert row.slug == f"source-{source_id}"
        assert row.language == "en"
        assert row.trust_level == "medium"
        assert row.active is True
        assert row.archived is False
        assert (
            MigrationContext.configure(connection).get_current_revision()
            == LATEST_REVISION
        )
    upgraded.dispose()
    command.check(config)

    command.downgrade(config, PARENT_REVISION)
    downgraded = create_engine(url)
    assert SOURCE_REGISTRY_TABLES.isdisjoint(
        inspect(downgraded).get_table_names()
    )
    downgraded_metadata = MetaData()
    downgraded_sources = Table(
        "sources",
        downgraded_metadata,
        autoload_with=downgraded,
    )
    with downgraded.connect() as connection:
        assert connection.scalar(
            select(downgraded_sources.c.title).where(
                downgraded_sources.c.id == source_id
            )
        ) == "Preserved Legacy Source"
    downgraded.dispose()

    command.upgrade(config, "head")
    final_engine = create_engine(url)
    with final_engine.connect() as connection:
        assert (
            MigrationContext.configure(connection).get_current_revision()
            == LATEST_REVISION
        )
    final_engine.dispose()


def test_source_registry_models_compile_to_mysql_compatible_ddl() -> None:
    dialect = mysql.dialect()
    for table_name in {*SOURCE_REGISTRY_TABLES, "sources"}:
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
