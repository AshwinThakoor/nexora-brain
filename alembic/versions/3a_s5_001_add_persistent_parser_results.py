"""add persistent canonical parser results

Revision ID: 3a_s5_001
Revises: 3a_s4_001
Create Date: 2026-07-28
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql


revision: str = "3a_s5_001"
down_revision: str | None = "3a_s4_001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "parse_results",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("uuid", sa.String(length=36), nullable=False),
        sa.Column("stored_file_id", sa.Integer(), nullable=False),
        sa.Column("document_version_id", sa.Integer(), nullable=False),
        sa.Column("ingestion_job_id", sa.Integer(), nullable=True),
        sa.Column("parser_name", sa.String(length=100), nullable=False),
        sa.Column("parser_version", sa.String(length=64), nullable=False),
        sa.Column("input_sha256", sa.String(length=64), nullable=False),
        sa.Column(
            "canonical_schema_version",
            sa.String(length=32),
            nullable=False,
        ),
        sa.Column("status", sa.String(length=50), nullable=False),
        sa.Column("content_hash", sa.String(length=64), nullable=True),
        sa.Column(
            "canonical_json",
            sa.Text().with_variant(mysql.LONGTEXT(), "mysql"),
            nullable=True,
        ),
        sa.Column("statistics_json", sa.JSON(), nullable=True),
        sa.Column("metadata_json", sa.JSON(), nullable=True),
        sa.Column(
            "started_at",
            sa.DateTime(timezone=True),
            nullable=False,
        ),
        sa.Column(
            "completed_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["document_version_id"],
            ["document_versions.id"],
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["ingestion_job_id"],
            ["ingestion_jobs.id"],
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["stored_file_id"],
            ["stored_files.id"],
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "stored_file_id",
            "input_sha256",
            "parser_name",
            "parser_version",
            name="uq_parse_result_identity",
        ),
    )
    op.create_index(
        "ix_parse_results_content_hash",
        "parse_results",
        ["content_hash"],
        unique=False,
    )
    op.create_index(
        "ix_parse_results_document_version_id",
        "parse_results",
        ["document_version_id"],
        unique=False,
    )
    op.create_index(
        "ix_parse_results_file_status",
        "parse_results",
        ["stored_file_id", "status"],
        unique=False,
    )
    op.create_index(
        "ix_parse_results_ingestion_job_id",
        "parse_results",
        ["ingestion_job_id"],
        unique=False,
    )
    op.create_index(
        "ix_parse_results_input_sha256",
        "parse_results",
        ["input_sha256"],
        unique=False,
    )
    op.create_index(
        "ix_parse_results_parser_name",
        "parse_results",
        ["parser_name"],
        unique=False,
    )
    op.create_index(
        "ix_parse_results_parser_version",
        "parse_results",
        ["parser_version"],
        unique=False,
    )
    op.create_index(
        "ix_parse_results_status",
        "parse_results",
        ["status"],
        unique=False,
    )
    op.create_index(
        "ix_parse_results_stored_file_id",
        "parse_results",
        ["stored_file_id"],
        unique=False,
    )
    op.create_index(
        "ix_parse_results_uuid",
        "parse_results",
        ["uuid"],
        unique=True,
    )
    op.create_index(
        "ix_parse_results_version_status",
        "parse_results",
        ["document_version_id", "status"],
        unique=False,
    )

    op.create_table(
        "parse_executions",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("parse_result_id", sa.Integer(), nullable=False),
        sa.Column("attempt_number", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=50), nullable=False),
        sa.Column(
            "started_at",
            sa.DateTime(timezone=True),
            nullable=False,
        ),
        sa.Column(
            "finished_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
        sa.Column("duration_ms", sa.Integer(), nullable=True),
        sa.Column("error_code", sa.String(length=100), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("parser_name", sa.String(length=100), nullable=False),
        sa.Column("parser_version", sa.String(length=64), nullable=False),
        sa.Column("node_name", sa.String(length=255), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
        ),
        sa.CheckConstraint(
            "attempt_number > 0",
            name="ck_parse_executions_attempt_number",
        ),
        sa.CheckConstraint(
            "duration_ms IS NULL OR duration_ms >= 0",
            name="ck_parse_executions_duration",
        ),
        sa.ForeignKeyConstraint(
            ["parse_result_id"],
            ["parse_results.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "parse_result_id",
            "attempt_number",
            name="uq_parse_execution_attempt",
        ),
    )
    op.create_index(
        "ix_parse_executions_error_code",
        "parse_executions",
        ["error_code"],
        unique=False,
    )
    op.create_index(
        "ix_parse_executions_parse_result_id",
        "parse_executions",
        ["parse_result_id"],
        unique=False,
    )
    op.create_index(
        "ix_parse_executions_status",
        "parse_executions",
        ["status"],
        unique=False,
    )

    op.create_table(
        "parse_artifacts",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("parse_result_id", sa.Integer(), nullable=False),
        sa.Column("artifact_type", sa.String(length=50), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("mime_type", sa.String(length=255), nullable=True),
        sa.Column("content_json", sa.JSON(), nullable=True),
        sa.Column("content_text", sa.Text(), nullable=True),
        sa.Column("checksum", sa.String(length=64), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["parse_result_id"],
            ["parse_results.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_parse_artifacts_artifact_type",
        "parse_artifacts",
        ["artifact_type"],
        unique=False,
    )
    op.create_index(
        "ix_parse_artifacts_checksum",
        "parse_artifacts",
        ["checksum"],
        unique=False,
    )
    op.create_index(
        "ix_parse_artifacts_parse_result_id",
        "parse_artifacts",
        ["parse_result_id"],
        unique=False,
    )
    op.create_index(
        "ix_parse_artifacts_result_type",
        "parse_artifacts",
        ["parse_result_id", "artifact_type"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_table("parse_artifacts")
    op.drop_table("parse_executions")
    op.drop_table("parse_results")
