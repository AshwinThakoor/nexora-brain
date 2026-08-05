from __future__ import annotations

from pathlib import Path

from alembic import command
from alembic.config import Config
from alembic.runtime.migration import MigrationContext
from sqlalchemy import create_engine, inspect
from sqlalchemy.dialects import mysql
from sqlalchemy.schema import CreateTable

from nexora_knowledge.database import Base


PROJECT_ROOT = Path(__file__).resolve().parents[1]
PARENT_REVISION = "2d_s1_001"
LEARNING_REVISION = "2d_s2_001"
LATEST_REVISION = "3a_s6_001"
LEARNING_TABLES = {
    "learners",
    "course_enrollments",
    "curriculum_path_enrollments",
    "lesson_progress",
    "lesson_completions",
    "assessments",
    "assessment_questions",
    "assessment_options",
    "assessment_attempts",
    "assessment_answers",
}


def migration_config(database_url: str) -> Config:
    config = Config(str(PROJECT_ROOT / "alembic.ini"))
    config.set_main_option("script_location", str(PROJECT_ROOT / "alembic"))
    config.set_main_option("sqlalchemy.url", database_url)
    return config


def test_learning_migration_downgrade_reupgrade_and_drift_check(
    tmp_path: Path,
) -> None:
    path = tmp_path / "learning-migration.sqlite"
    url = f"sqlite:///{path.resolve().as_posix()}"
    config = migration_config(url)

    command.upgrade(config, PARENT_REVISION)
    parent_engine = create_engine(url)
    assert LEARNING_TABLES.isdisjoint(
        inspect(parent_engine).get_table_names()
    )
    parent_engine.dispose()

    command.upgrade(config, "head")
    upgraded_engine = create_engine(url)
    inspector = inspect(upgraded_engine)
    assert LEARNING_TABLES <= set(inspector.get_table_names())
    assert {
        item["name"]
        for item in inspector.get_unique_constraints("course_enrollments")
    } >= {"uq_course_enrollment_learner_course"}
    assert {
        item["name"]
        for item in inspector.get_unique_constraints("assessment_answers")
    } >= {"uq_assessment_answer_attempt_question"}
    with upgraded_engine.connect() as connection:
        assert (
            MigrationContext.configure(connection).get_current_revision()
            == LATEST_REVISION
        )
    upgraded_engine.dispose()
    command.check(config)

    command.downgrade(config, PARENT_REVISION)
    downgraded_engine = create_engine(url)
    assert LEARNING_TABLES.isdisjoint(
        inspect(downgraded_engine).get_table_names()
    )
    downgraded_engine.dispose()

    command.upgrade(config, "head")
    final_engine = create_engine(url)
    with final_engine.connect() as connection:
        assert (
            MigrationContext.configure(connection).get_current_revision()
            == LATEST_REVISION
        )
    final_engine.dispose()


def test_learning_models_compile_to_mysql_compatible_ddl() -> None:
    dialect = mysql.dialect()
    for table_name in LEARNING_TABLES:
        table = Base.metadata.tables[table_name]
        ddl = str(CreateTable(table).compile(dialect=dialect))
        assert "CREATE TABLE" in ddl
        assert all(
            len(identifier) <= dialect.max_identifier_length
            for identifier in [
                table.name,
                *(constraint.name for constraint in table.constraints if constraint.name),
                *(index.name for index in table.indexes if index.name),
            ]
        )
