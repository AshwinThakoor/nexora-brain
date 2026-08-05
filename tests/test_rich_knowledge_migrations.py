from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from alembic import command
from alembic.config import Config
from alembic.runtime.migration import MigrationContext
from sqlalchemy import MetaData, Table, create_engine, inspect, select


PROJECT_ROOT = Path(__file__).resolve().parents[1]
PREVIOUS_HEAD = "2b_s2_001"
RICH_HEAD = "2c_s1_001"
RICH_TABLES = {
    "asset_classes",
    "case_studies",
    "claim_conflicts",
    "concept_aliases",
    "economic_event_types",
    "faqs",
    "formulas",
    "indicators",
    "instruments",
    "knowledge_articles",
    "knowledge_reviews",
    "knowledge_revisions",
    "knowledge_sections",
    "patterns",
    "source_assessments",
    "strategies",
}


def migration_config(database_url: str) -> Config:
    config = Config(str(PROJECT_ROOT / "alembic.ini"))
    config.set_main_option("script_location", str(PROJECT_ROOT / "alembic"))
    config.set_main_option("sqlalchemy.url", database_url)
    return config


def test_upgrade_from_pack_2b_preserves_data_and_downgrades(
    tmp_path: Path,
) -> None:
    database_path = tmp_path / "pack-2c-migration.sqlite"
    database_url = f"sqlite:///{database_path.resolve().as_posix()}"
    config = migration_config(database_url)

    command.upgrade(config, PREVIOUS_HEAD)
    engine = create_engine(database_url)
    old_metadata = MetaData()
    concepts = Table("concepts", old_metadata, autoload_with=engine)
    claims = Table("claims", old_metadata, autoload_with=engine)
    timestamp = datetime.now(timezone.utc)
    with engine.begin() as connection:
        concept_id = connection.execute(
            concepts.insert().values(
                title="Preserved Concept",
                slug="preserved-concept",
                difficulty="beginner",
                status="draft",
                version=1,
                created_at=timestamp,
                updated_at=timestamp,
            )
        ).inserted_primary_key[0]
        claim_id = connection.execute(
            claims.insert().values(
                concept_id=concept_id,
                statement="This Pack 2B claim must survive.",
                claim_type="general",
                status="draft",
                created_at=timestamp,
                updated_at=timestamp,
            )
        ).inserted_primary_key[0]
    engine.dispose()

    command.upgrade(config, RICH_HEAD)
    upgraded_engine = create_engine(database_url)
    upgraded_tables = set(inspect(upgraded_engine).get_table_names())
    assert RICH_TABLES <= upgraded_tables
    assert {
        "lifecycle_status",
        "confidence_method",
        "confidence_reason",
        "last_reviewed_at",
    } <= {column["name"] for column in inspect(upgraded_engine).get_columns("claims")}
    upgraded_metadata = MetaData()
    upgraded_claims = Table(
        "claims",
        upgraded_metadata,
        autoload_with=upgraded_engine,
    )
    with upgraded_engine.connect() as connection:
        preserved = connection.execute(
            select(
                upgraded_claims.c.statement,
                upgraded_claims.c.lifecycle_status,
            ).where(upgraded_claims.c.id == claim_id)
        ).one()
        context = MigrationContext.configure(connection)
        assert context.get_current_revision() == RICH_HEAD
    assert preserved.statement == "This Pack 2B claim must survive."
    assert preserved.lifecycle_status == "draft"
    upgraded_engine.dispose()

    command.downgrade(config, PREVIOUS_HEAD)
    downgraded_engine = create_engine(database_url)
    assert RICH_TABLES.isdisjoint(inspect(downgraded_engine).get_table_names())
    assert "lifecycle_status" not in {
        column["name"] for column in inspect(downgraded_engine).get_columns("claims")
    }
    downgraded_metadata = MetaData()
    downgraded_claims = Table(
        "claims",
        downgraded_metadata,
        autoload_with=downgraded_engine,
    )
    with downgraded_engine.connect() as connection:
        assert connection.scalar(
            select(downgraded_claims.c.statement).where(
                downgraded_claims.c.id == claim_id
            )
        ) == "This Pack 2B claim must survive."
    downgraded_engine.dispose()

    command.upgrade(config, RICH_HEAD)
    final_engine = create_engine(database_url)
    with final_engine.connect() as connection:
        context = MigrationContext.configure(connection)
        assert context.get_current_revision() == RICH_HEAD
    final_engine.dispose()
