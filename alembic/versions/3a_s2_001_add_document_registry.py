"""add the Pack 3 document registry

Revision ID: 3a_s2_001
Revises: 3a_s1_001
Create Date: 2026-07-28
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "3a_s2_001"
down_revision: str | None = "3a_s1_001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _create_table(table_name: str, *args, **kwargs):
    """Resume safely after non-transactional MySQL DDL is interrupted."""
    if table_name in sa.inspect(op.get_bind()).get_table_names():
        return None
    return op.create_table(table_name, *args, **kwargs)


def _create_index(
    index_name: str,
    table_name: str,
    columns,
    **kwargs,
) -> None:
    """Create an index only when an earlier partial attempt did not."""
    existing = {
        item["name"]
        for item in sa.inspect(op.get_bind()).get_indexes(table_name)
    }
    if index_name not in existing:
        op.create_index(
            index_name,
            table_name,
            columns,
            **kwargs,
        )


def upgrade() -> None:
    _create_table(
        "documents",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("uuid", sa.String(length=36), nullable=False),
        sa.Column("slug", sa.String(length=255), nullable=False),
        sa.Column("source_id", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(length=500), nullable=False),
        sa.Column("subtitle", sa.String(length=500), nullable=True),
        sa.Column("abstract", sa.Text(), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("document_type", sa.String(length=50), nullable=False),
        sa.Column("language", sa.String(length=16), nullable=False),
        sa.Column("publication_date", sa.Date(), nullable=True),
        sa.Column("publication_year", sa.Integer(), nullable=True),
        sa.Column("author_override", sa.String(length=255), nullable=True),
        sa.Column("publisher_override", sa.String(length=255), nullable=True),
        sa.Column("status", sa.String(length=50), nullable=False),
        sa.Column(
            "active",
            sa.Boolean(),
            nullable=False,
            server_default=sa.true(),
        ),
        sa.Column(
            "archived",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "NOT (active = 1 AND archived = 1)",
            name="ck_documents_lifecycle",
        ),
        sa.CheckConstraint(
            "publication_year IS NULL OR "
            "(publication_year >= 1000 AND publication_year <= 9999)",
            name="ck_documents_publication_year",
        ),
        sa.ForeignKeyConstraint(
            ["source_id"],
            ["sources.id"],
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    _create_index(
        "ix_documents_author_override",
        "documents",
        ["author_override"],
        unique=False,
    )
    _create_index(
        "ix_documents_document_type",
        "documents",
        ["document_type"],
        unique=False,
    )
    _create_index(
        "ix_documents_language",
        "documents",
        ["language"],
        unique=False,
    )
    _create_index(
        "ix_documents_publication_date",
        "documents",
        ["publication_date"],
        unique=False,
    )
    _create_index(
        "ix_documents_publication_year",
        "documents",
        ["publication_year"],
        unique=False,
    )
    _create_index(
        "ix_documents_slug",
        "documents",
        ["slug"],
        unique=True,
    )
    _create_index(
        "ix_documents_source_id",
        "documents",
        ["source_id"],
        unique=False,
    )
    _create_index(
        "ix_documents_status",
        "documents",
        ["status"],
        unique=False,
    )
    _create_index(
        "ix_documents_title",
        "documents",
        ["title"],
        unique=False,
    )
    _create_index(
        "ix_documents_uuid",
        "documents",
        ["uuid"],
        unique=True,
    )

    _create_table(
        "document_versions",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("document_id", sa.Integer(), nullable=False),
        sa.Column("version", sa.String(length=100), nullable=False),
        sa.Column("checksum", sa.String(length=128), nullable=False),
        sa.Column("change_summary", sa.Text(), nullable=True),
        sa.Column("release_date", sa.Date(), nullable=True),
        sa.Column("is_current", sa.Boolean(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "is_current IS NULL OR is_current = 1",
            name="ck_document_versions_current",
        ),
        sa.ForeignKeyConstraint(
            ["document_id"],
            ["documents.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "document_id",
            "is_current",
            name="uq_document_current_version",
        ),
        sa.UniqueConstraint(
            "document_id",
            "version",
            name="uq_document_version",
        ),
        sa.UniqueConstraint(
            "document_id",
            "checksum",
            name="uq_document_version_checksum",
        ),
    )
    _create_index(
        "ix_document_versions_document_id",
        "document_versions",
        ["document_id"],
        unique=False,
    )

    _create_table(
        "document_files",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("document_version_id", sa.Integer(), nullable=False),
        sa.Column("original_filename", sa.String(length=1024), nullable=False),
        sa.Column("storage_key", sa.String(length=2048), nullable=True),
        sa.Column("mime_type", sa.String(length=255), nullable=False),
        sa.Column("extension", sa.String(length=32), nullable=False),
        sa.Column("size_bytes", sa.Integer(), nullable=False),
        sa.Column("page_count", sa.Integer(), nullable=True),
        sa.Column("sha256", sa.String(length=64), nullable=False),
        sa.Column("processing_status", sa.String(length=50), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "page_count IS NULL OR page_count > 0",
            name="ck_document_files_page_count",
        ),
        sa.CheckConstraint(
            "size_bytes >= 0",
            name="ck_document_files_size_bytes",
        ),
        sa.ForeignKeyConstraint(
            ["document_version_id"],
            ["document_versions.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    _create_index(
        "ix_document_files_document_version_id",
        "document_files",
        ["document_version_id"],
        unique=False,
    )
    _create_index(
        "ix_document_files_processing_status",
        "document_files",
        ["processing_status"],
        unique=False,
    )
    _create_index(
        "ix_document_files_sha256",
        "document_files",
        ["sha256"],
        unique=False,
    )
    _create_table(
        "document_identifiers",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("document_id", sa.Integer(), nullable=False),
        sa.Column("identifier_type", sa.String(length=100), nullable=False),
        sa.Column("identifier_value", sa.String(length=500), nullable=False),
        sa.ForeignKeyConstraint(
            ["document_id"],
            ["documents.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "identifier_type",
            "identifier_value",
            name="uq_document_identifier",
        ),
    )
    _create_index(
        "ix_document_identifiers_document_id",
        "document_identifiers",
        ["document_id"],
        unique=False,
    )
    _create_index(
        "ix_document_identifiers_identifier_type",
        "document_identifiers",
        ["identifier_type"],
        unique=False,
    )
    _create_index(
        "ix_document_identifiers_identifier_value",
        "document_identifiers",
        ["identifier_value"],
        unique=False,
    )

    _create_table(
        "document_relationships",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("source_document_id", sa.Integer(), nullable=False),
        sa.Column("target_document_id", sa.Integer(), nullable=False),
        sa.Column("relationship_type", sa.String(length=50), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "source_document_id <> target_document_id",
            name="ck_document_relationship_distinct",
        ),
        sa.ForeignKeyConstraint(
            ["source_document_id"],
            ["documents.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["target_document_id"],
            ["documents.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "source_document_id",
            "target_document_id",
            "relationship_type",
            name="uq_document_relationship",
        ),
    )
    _create_index(
        "ix_document_relationships_relationship_type",
        "document_relationships",
        ["relationship_type"],
        unique=False,
    )
    _create_index(
        "ix_document_relationships_source_document_id",
        "document_relationships",
        ["source_document_id"],
        unique=False,
    )
    _create_index(
        "ix_document_relationships_target_document_id",
        "document_relationships",
        ["target_document_id"],
        unique=False,
    )

    _create_table(
        "document_tags",
        sa.Column("document_id", sa.Integer(), nullable=False),
        sa.Column("tag_id", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(
            ["document_id"],
            ["documents.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["tag_id"],
            ["tags.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("document_id", "tag_id"),
    )

    _create_table(
        "import_batches",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("batch_uuid", sa.String(length=36), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("status", sa.String(length=50), nullable=False),
        sa.Column("created_by", sa.String(length=255), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "completed_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    _create_index(
        "ix_import_batches_batch_uuid",
        "import_batches",
        ["batch_uuid"],
        unique=True,
    )
    _create_index(
        "ix_import_batches_created_by",
        "import_batches",
        ["created_by"],
        unique=False,
    )
    _create_index(
        "ix_import_batches_status",
        "import_batches",
        ["status"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_table("import_batches")
    op.drop_table("document_tags")
    op.drop_table("document_relationships")
    op.drop_table("document_identifiers")
    op.drop_table("document_files")
    op.drop_table("document_versions")
    op.drop_table("documents")
