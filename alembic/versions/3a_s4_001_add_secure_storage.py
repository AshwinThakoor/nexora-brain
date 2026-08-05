"""add the Pack 3 secure upload and storage abstraction

Revision ID: 3a_s4_001
Revises: 3a_s3_001
Create Date: 2026-07-28
"""

from collections.abc import Sequence
from datetime import datetime, timezone

from alembic import op
import sqlalchemy as sa


revision: str = "3a_s4_001"
down_revision: str | None = "3a_s3_001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "storage_providers",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("provider_type", sa.String(length=50), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_storage_providers_active",
        "storage_providers",
        ["active"],
        unique=False,
    )
    op.create_index(
        "ix_storage_providers_name",
        "storage_providers",
        ["name"],
        unique=True,
    )
    op.create_index(
        "ix_storage_providers_provider_type",
        "storage_providers",
        ["provider_type"],
        unique=True,
    )
    providers = sa.table(
        "storage_providers",
        sa.column("name", sa.String()),
        sa.column("provider_type", sa.String()),
        sa.column("active", sa.Boolean()),
        sa.column("created_at", sa.DateTime(timezone=True)),
    )
    created_at = datetime.now(timezone.utc)
    op.bulk_insert(
        providers,
        [
            {
                "name": "local",
                "provider_type": "local",
                "active": True,
                "created_at": created_at,
            },
            {
                "name": "null",
                "provider_type": "null",
                "active": True,
                "created_at": created_at,
            },
        ],
    )

    op.create_table(
        "upload_sessions",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("uuid", sa.String(length=36), nullable=False),
        sa.Column("status", sa.String(length=50), nullable=False),
        sa.Column("created_by", sa.String(length=255), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("cancelled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "expires_at > created_at",
            name="ck_upload_sessions_expiry",
        ),
        sa.CheckConstraint(
            "NOT (completed_at IS NOT NULL AND cancelled_at IS NOT NULL)",
            name="ck_upload_sessions_terminal_state",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_upload_sessions_created_by",
        "upload_sessions",
        ["created_by"],
        unique=False,
    )
    op.create_index(
        "ix_upload_sessions_expires_at",
        "upload_sessions",
        ["expires_at"],
        unique=False,
    )
    op.create_index(
        "ix_upload_sessions_status",
        "upload_sessions",
        ["status"],
        unique=False,
    )
    op.create_index(
        "ix_upload_sessions_uuid",
        "upload_sessions",
        ["uuid"],
        unique=True,
    )

    op.create_table(
        "stored_files",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("uuid", sa.String(length=36), nullable=False),
        sa.Column("upload_session_id", sa.Integer(), nullable=False),
        sa.Column("document_version_id", sa.Integer(), nullable=False),
        sa.Column(
            "original_filename",
            sa.String(length=1024),
            nullable=False,
        ),
        sa.Column(
            "normalized_filename",
            sa.String(length=255),
            nullable=False,
        ),
        sa.Column(
            "storage_provider",
            sa.String(length=50),
            nullable=False,
        ),
        sa.Column("storage_path", sa.String(length=1024), nullable=False),
        sa.Column("mime_type", sa.String(length=255), nullable=False),
        sa.Column("extension", sa.String(length=32), nullable=False),
        sa.Column("size_bytes", sa.Integer(), nullable=False),
        sa.Column("sha256", sa.String(length=64), nullable=False),
        sa.Column("sha1", sa.String(length=40), nullable=True),
        sa.Column("md5", sa.String(length=32), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "size_bytes > 0",
            name="ck_stored_files_size",
        ),
        sa.ForeignKeyConstraint(
            ["document_version_id"],
            ["document_versions.id"],
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["upload_session_id"],
            ["upload_sessions.id"],
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_stored_files_document_version_id",
        "stored_files",
        ["document_version_id"],
        unique=False,
    )
    op.create_index(
        "ix_stored_files_sha256",
        "stored_files",
        ["sha256"],
        unique=True,
    )
    op.create_index(
        "ix_stored_files_storage_provider",
        "stored_files",
        ["storage_provider"],
        unique=False,
    )
    op.create_index(
        "ix_stored_files_upload_session_id",
        "stored_files",
        ["upload_session_id"],
        unique=True,
    )
    op.create_index(
        "ix_stored_files_uuid",
        "stored_files",
        ["uuid"],
        unique=True,
    )

    op.create_table(
        "file_hashes",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("stored_file_id", sa.Integer(), nullable=False),
        sa.Column("algorithm", sa.String(length=20), nullable=False),
        sa.Column("value", sa.String(length=128), nullable=False),
        sa.ForeignKeyConstraint(
            ["stored_file_id"],
            ["stored_files.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "stored_file_id",
            "algorithm",
            name="uq_file_hash_algorithm",
        ),
    )
    op.create_index(
        "ix_file_hashes_algorithm",
        "file_hashes",
        ["algorithm"],
        unique=False,
    )
    op.create_index(
        "ix_file_hashes_stored_file_id",
        "file_hashes",
        ["stored_file_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_table("file_hashes")
    op.drop_table("stored_files")
    op.drop_table("upload_sessions")
    op.drop_table("storage_providers")
