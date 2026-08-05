"""add the Pack 3 ingestion orchestration engine

Revision ID: 3a_s3_001
Revises: 3a_s2_001
Create Date: 2026-07-28
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "3a_s3_001"
down_revision: str | None = "3a_s2_001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "ingestion_jobs",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("uuid", sa.String(length=36), nullable=False),
        sa.Column("document_id", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=50), nullable=False),
        sa.Column("priority", sa.Integer(), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "priority >= 0",
            name="ck_ingestion_jobs_priority",
        ),
        sa.ForeignKeyConstraint(
            ["document_id"],
            ["documents.id"],
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_ingestion_jobs_document_id",
        "ingestion_jobs",
        ["document_id"],
        unique=False,
    )
    op.create_index(
        "ix_ingestion_jobs_priority",
        "ingestion_jobs",
        ["priority"],
        unique=False,
    )
    op.create_index(
        "ix_ingestion_jobs_status",
        "ingestion_jobs",
        ["status"],
        unique=False,
    )
    op.create_index(
        "ix_ingestion_jobs_uuid",
        "ingestion_jobs",
        ["uuid"],
        unique=True,
    )

    op.create_table(
        "processing_nodes",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("node_name", sa.String(length=255), nullable=False),
        sa.Column("node_version", sa.String(length=100), nullable=False),
        sa.Column("hostname", sa.String(length=255), nullable=False),
        sa.Column(
            "last_heartbeat",
            sa.DateTime(timezone=True),
            nullable=False,
        ),
        sa.Column("active", sa.Boolean(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_processing_nodes_active",
        "processing_nodes",
        ["active"],
        unique=False,
    )
    op.create_index(
        "ix_processing_nodes_last_heartbeat",
        "processing_nodes",
        ["last_heartbeat"],
        unique=False,
    )
    op.create_index(
        "ix_processing_nodes_node_name",
        "processing_nodes",
        ["node_name"],
        unique=True,
    )

    op.create_table(
        "ingestion_attempts",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("job_id", sa.Integer(), nullable=False),
        sa.Column("attempt_number", sa.Integer(), nullable=False),
        sa.Column(
            "started_at",
            sa.DateTime(timezone=True),
            nullable=False,
        ),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("status", sa.String(length=50), nullable=False),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("duration_ms", sa.Integer(), nullable=True),
        sa.CheckConstraint(
            "attempt_number > 0",
            name="ck_ingestion_attempts_number",
        ),
        sa.CheckConstraint(
            "duration_ms IS NULL OR duration_ms >= 0",
            name="ck_ingestion_attempts_duration",
        ),
        sa.ForeignKeyConstraint(
            ["job_id"],
            ["ingestion_jobs.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "job_id",
            "attempt_number",
            name="uq_ingestion_attempt_number",
        ),
    )
    op.create_index(
        "ix_ingestion_attempts_job_id",
        "ingestion_attempts",
        ["job_id"],
        unique=False,
    )
    op.create_index(
        "ix_ingestion_attempts_status",
        "ingestion_attempts",
        ["status"],
        unique=False,
    )

    op.create_table(
        "ingestion_audit_events",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("job_id", sa.Integer(), nullable=False),
        sa.Column("event_type", sa.String(length=50), nullable=False),
        sa.Column("previous_status", sa.String(length=50), nullable=True),
        sa.Column("new_status", sa.String(length=50), nullable=False),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["job_id"],
            ["ingestion_jobs.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_ingestion_audit_events_event_type",
        "ingestion_audit_events",
        ["event_type"],
        unique=False,
    )
    op.create_index(
        "ix_ingestion_audit_events_job_id",
        "ingestion_audit_events",
        ["job_id"],
        unique=False,
    )

    op.create_table(
        "job_reservations",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("job_id", sa.Integer(), nullable=False),
        sa.Column("node_id", sa.Integer(), nullable=False),
        sa.Column(
            "reserved_at",
            sa.DateTime(timezone=True),
            nullable=False,
        ),
        sa.Column(
            "expires_at",
            sa.DateTime(timezone=True),
            nullable=False,
        ),
        sa.Column("released_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("active_slot", sa.Boolean(), nullable=True),
        sa.CheckConstraint(
            "expires_at > reserved_at",
            name="ck_job_reservations_expiry",
        ),
        sa.CheckConstraint(
            "(released_at IS NULL AND active_slot = 1) OR "
            "(released_at IS NOT NULL AND active_slot IS NULL)",
            name="ck_job_reservations_active",
        ),
        sa.ForeignKeyConstraint(
            ["job_id"],
            ["ingestion_jobs.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["node_id"],
            ["processing_nodes.id"],
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "job_id",
            "active_slot",
            name="uq_job_active_reservation",
        ),
    )
    op.create_index(
        "ix_job_reservations_expires_at",
        "job_reservations",
        ["expires_at"],
        unique=False,
    )
    op.create_index(
        "ix_job_reservations_job_id",
        "job_reservations",
        ["job_id"],
        unique=False,
    )
    op.create_index(
        "ix_job_reservations_node_id",
        "job_reservations",
        ["node_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_table("job_reservations")
    op.drop_table("ingestion_audit_events")
    op.drop_table("ingestion_attempts")
    op.drop_table("processing_nodes")
    op.drop_table("ingestion_jobs")
