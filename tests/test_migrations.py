from __future__ import annotations

from pathlib import Path

from alembic import command
from alembic.autogenerate import compare_metadata
from alembic.config import Config
from alembic.runtime.migration import MigrationContext
from alembic.script import ScriptDirectory
from sqlalchemy import create_engine, inspect

from nexora_knowledge import models  # noqa: F401
from nexora_knowledge.database import Base


PROJECT_ROOT = Path(__file__).resolve().parents[1]
EXPECTED_TABLES = {
    "assessment_answers",
    "assessment_attempts",
    "assessment_options",
    "assessment_questions",
    "assessment_reviews",
    "assessments",
    "asset_classes",
    "case_studies",
    "categories",
    "claim_conflicts",
    "claims",
    "chunk_relationships",
    "chunk_sets",
    "chunk_source_spans",
    "chunking_artifacts",
    "chunking_executions",
    "concept_aliases",
    "concept_relationships",
    "concept_tags",
    "concepts",
    "courses",
    "course_enrollments",
    "curriculum_path_enrollments",
    "curriculum_path_lessons",
    "curriculum_paths",
    "degrees",
    "document_files",
    "document_identifiers",
    "document_relationships",
    "document_tags",
    "document_versions",
    "documents",
    "economic_event_types",
    "evidence",
    "faqs",
    "file_hashes",
    "formulas",
    "grading_audit_events",
    "indicators",
    "instruments",
    "import_batches",
    "ingestion_attempts",
    "ingestion_audit_events",
    "ingestion_jobs",
    "knowledge_articles",
    "knowledge_chunks",
    "knowledge_documents",
    "knowledge_reviews",
    "knowledge_revisions",
    "knowledge_sections",
    "learners",
    "learning_objectives",
    "lesson_prerequisites",
    "lesson_completions",
    "lesson_progress",
    "lessons",
    "modules",
    "manual_grades",
    "patterns",
    "parse_artifacts",
    "parse_executions",
    "parse_results",
    "processing_nodes",
    "job_reservations",
    "source_assessments",
    "source_aliases",
    "source_licenses",
    "source_organizations",
    "source_tags",
    "source_versions",
    "storage_providers",
    "stored_files",
    "schools",
    "sources",
    "strategies",
    "tags",
    "upload_sessions",
}
LATEST_REVISION = "3a_s6_001"


def alembic_config(database_url: str) -> Config:
    config = Config(str(PROJECT_ROOT / "alembic.ini"))
    config.set_main_option("script_location", str(PROJECT_ROOT / "alembic"))
    config.set_main_option("sqlalchemy.url", database_url)
    return config


def sqlite_url(database_path: Path) -> str:
    return f"sqlite:///{database_path.resolve().as_posix()}"


def test_alembic_configuration_and_head_load() -> None:
    config = alembic_config("sqlite:///:memory:")
    scripts = ScriptDirectory.from_config(config)

    assert Path(config.config_file_name) == PROJECT_ROOT / "alembic.ini"
    assert scripts.get_current_head() == LATEST_REVISION
    assert scripts.get_heads() == [LATEST_REVISION]


def test_migration_upgrade_downgrade_and_schema_sync(tmp_path: Path) -> None:
    database_path = tmp_path / "migration-cycle.sqlite"
    database_url = sqlite_url(database_path)
    config = alembic_config(database_url)
    engine = create_engine(database_url)

    assert set(Base.metadata.tables) == EXPECTED_TABLES

    command.upgrade(config, "head")
    assert EXPECTED_TABLES <= set(inspect(engine).get_table_names())

    with engine.connect() as connection:
        migration_context = MigrationContext.configure(connection)
        assert migration_context.get_current_revision() == LATEST_REVISION
        differences = compare_metadata(migration_context, Base.metadata)
    assert differences == []

    engine.dispose()
    command.downgrade(config, "base")

    downgraded_engine = create_engine(database_url)
    assert EXPECTED_TABLES.isdisjoint(inspect(downgraded_engine).get_table_names())
    downgraded_engine.dispose()

    command.upgrade(config, "head")
    upgraded_engine = create_engine(database_url)
    assert EXPECTED_TABLES <= set(inspect(upgraded_engine).get_table_names())
    with upgraded_engine.connect() as connection:
        migration_context = MigrationContext.configure(connection)
        assert migration_context.get_current_revision() == LATEST_REVISION
    upgraded_engine.dispose()
