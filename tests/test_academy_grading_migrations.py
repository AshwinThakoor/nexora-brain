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
PARENT_REVISION = "2d_s2_001"
GRADING_REVISION = "2d_s3_001"
LATEST_REVISION = "3a_s6_001"
GRADING_TABLES = {
    "manual_grades",
    "assessment_reviews",
    "grading_audit_events",
}


def migration_config(database_url: str) -> Config:
    config = Config(str(PROJECT_ROOT / "alembic.ini"))
    config.set_main_option("script_location", str(PROJECT_ROOT / "alembic"))
    config.set_main_option("sqlalchemy.url", database_url)
    return config


def test_grading_migration_downgrade_reupgrade_preserves_learner(
    tmp_path: Path,
) -> None:
    path = tmp_path / "grading-migration.sqlite"
    url = f"sqlite:///{path.resolve().as_posix()}"
    config = migration_config(url)
    command.upgrade(config, PARENT_REVISION)

    engine = create_engine(url)
    metadata = MetaData()
    learners = Table("learners", metadata, autoload_with=engine)
    timestamp = datetime.now(timezone.utc)
    with engine.begin() as connection:
        learner_id = connection.execute(
            learners.insert().values(
                external_user_id="preserved-learner",
                email="preserved@example.com",
                display_name="Preserved Learner",
                status="active",
                created_at=timestamp,
                updated_at=timestamp,
            )
        ).inserted_primary_key[0]
    engine.dispose()

    command.upgrade(config, "head")
    upgraded = create_engine(url)
    inspector = inspect(upgraded)
    assert GRADING_TABLES <= set(inspector.get_table_names())
    assert {
        "current_manual_grade_id",
        "grading_status",
        "graded_at",
    } <= {
        column["name"]
        for column in inspector.get_columns("assessment_answers")
    }
    assert {
        "automatic_score_percent",
        "automatic_points_earned",
        "grading_status",
        "reviewed_at",
        "final_score_percent",
        "final_passed",
    } <= {
        column["name"]
        for column in inspector.get_columns("assessment_attempts")
    }
    with upgraded.connect() as connection:
        assert (
            MigrationContext.configure(connection).get_current_revision()
            == LATEST_REVISION
        )
    upgraded.dispose()
    command.check(config)

    command.downgrade(config, PARENT_REVISION)
    downgraded = create_engine(url)
    assert GRADING_TABLES.isdisjoint(
        inspect(downgraded).get_table_names()
    )
    downgraded_metadata = MetaData()
    downgraded_learners = Table(
        "learners", downgraded_metadata, autoload_with=downgraded
    )
    with downgraded.connect() as connection:
        assert connection.scalar(
            select(downgraded_learners.c.external_user_id).where(
                downgraded_learners.c.id == learner_id
            )
        ) == "preserved-learner"
    downgraded.dispose()

    command.upgrade(config, "head")
    final_engine = create_engine(url)
    with final_engine.connect() as connection:
        assert (
            MigrationContext.configure(connection).get_current_revision()
            == LATEST_REVISION
        )
    final_engine.dispose()


def test_grading_models_compile_to_mysql_compatible_ddl() -> None:
    dialect = mysql.dialect()
    for table_name in GRADING_TABLES:
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
