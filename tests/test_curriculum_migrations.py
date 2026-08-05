from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from alembic import command
from alembic.config import Config
from alembic.runtime.migration import MigrationContext
from sqlalchemy import MetaData, Table, create_engine, inspect, select


PROJECT_ROOT = Path(__file__).resolve().parents[1]
PREVIOUS_HEAD = "2c_s1_001"
CURRICULUM_HEAD = "2d_s1_001"
LATEST_HEAD = "3a_s6_001"
CURRICULUM_TABLES = {
    "schools",
    "degrees",
    "courses",
    "modules",
    "lessons",
    "learning_objectives",
    "lesson_prerequisites",
    "curriculum_paths",
    "curriculum_path_lessons",
}


def migration_config(database_url: str) -> Config:
    config = Config(str(PROJECT_ROOT / "alembic.ini"))
    config.set_main_option("script_location", str(PROJECT_ROOT / "alembic"))
    config.set_main_option("sqlalchemy.url", database_url)
    return config


def test_curriculum_migration_upgrade_and_downgrade_preserves_pack_2c(
    tmp_path: Path,
) -> None:
    database_path = tmp_path / "pack-2d-migration.sqlite"
    database_url = f"sqlite:///{database_path.resolve().as_posix()}"
    config = migration_config(database_url)

    command.upgrade(config, PREVIOUS_HEAD)
    engine = create_engine(database_url)
    metadata = MetaData()
    articles = Table(
        "knowledge_articles",
        metadata,
        autoload_with=engine,
    )
    timestamp = datetime.now(timezone.utc)
    with engine.begin() as connection:
        article_id = connection.execute(
            articles.insert().values(
                title="Preserved Article",
                slug="preserved-article",
                difficulty_level="beginner",
                language="en",
                lifecycle_status="draft",
                review_status="pending",
                version=1,
                created_at=timestamp,
                updated_at=timestamp,
            )
        ).inserted_primary_key[0]
    engine.dispose()

    command.upgrade(config, CURRICULUM_HEAD)
    upgraded_engine = create_engine(database_url)
    inspector = inspect(upgraded_engine)
    assert CURRICULUM_TABLES <= set(inspector.get_table_names())
    assert {
        index["name"] for index in inspector.get_indexes("lessons")
    } >= {
        "ix_lessons_module_id",
        "ix_lessons_knowledge_article_id",
        "ix_lessons_concept_id",
        "ix_lessons_slug",
    }
    assert {
        constraint["name"]
        for constraint in inspector.get_unique_constraints(
            "lesson_prerequisites"
        )
    } >= {"uq_lesson_prerequisite_pair"}
    with upgraded_engine.connect() as connection:
        context = MigrationContext.configure(connection)
        assert context.get_current_revision() == CURRICULUM_HEAD
    upgraded_engine.dispose()

    command.downgrade(config, PREVIOUS_HEAD)
    downgraded_engine = create_engine(database_url)
    assert CURRICULUM_TABLES.isdisjoint(
        inspect(downgraded_engine).get_table_names()
    )
    downgraded_metadata = MetaData()
    downgraded_articles = Table(
        "knowledge_articles",
        downgraded_metadata,
        autoload_with=downgraded_engine,
    )
    with downgraded_engine.connect() as connection:
        assert connection.scalar(
            select(downgraded_articles.c.title).where(
                downgraded_articles.c.id == article_id
            )
        ) == "Preserved Article"
    downgraded_engine.dispose()

    command.upgrade(config, "head")
    final_engine = create_engine(database_url)
    with final_engine.connect() as connection:
        context = MigrationContext.configure(connection)
        assert context.get_current_revision() == LATEST_HEAD
    final_engine.dispose()
