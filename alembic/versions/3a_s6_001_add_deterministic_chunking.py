"""add deterministic chunking and provenance

Revision ID: 3a_s6_001
Revises: 3a_s5_001
Create Date: 2026-07-28
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql


revision: str = "3a_s6_001"
down_revision: str | None = "3a_s5_001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "chunk_sets",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("uuid", sa.String(length=36), nullable=False),
        sa.Column("parse_result_id", sa.Integer(), nullable=False),
        sa.Column("document_version_id", sa.Integer(), nullable=False),
        sa.Column("stored_file_id", sa.Integer(), nullable=False),
        sa.Column("strategy_name", sa.String(length=100), nullable=False),
        sa.Column("strategy_version", sa.String(length=64), nullable=False),
        sa.Column(
            "configuration_json",
            sa.Text().with_variant(mysql.LONGTEXT(), "mysql"),
            nullable=False,
        ),
        sa.Column("configuration_hash", sa.String(length=64), nullable=False),
        sa.Column(
            "canonical_content_hash",
            sa.String(length=64),
            nullable=False,
        ),
        sa.Column("status", sa.String(length=50), nullable=False),
        sa.Column("chunk_count", sa.Integer(), nullable=False),
        sa.Column("total_character_count", sa.Integer(), nullable=False),
        sa.Column("total_word_count", sa.Integer(), nullable=False),
        sa.Column("content_hash", sa.String(length=64), nullable=True),
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
            ["parse_result_id"],
            ["parse_results.id"],
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["stored_file_id"],
            ["stored_files.id"],
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "parse_result_id",
            "canonical_content_hash",
            "strategy_name",
            "strategy_version",
            "configuration_hash",
            name="uq_chunk_set_identity",
        ),
    )
    _indexes(
        "chunk_sets",
        {
            "ix_chunk_sets_canonical_content_hash": [
                "canonical_content_hash"
            ],
            "ix_chunk_sets_configuration_hash": ["configuration_hash"],
            "ix_chunk_sets_content_hash": ["content_hash"],
            "ix_chunk_sets_document_version_id": ["document_version_id"],
            "ix_chunk_sets_parse_result_id": ["parse_result_id"],
            "ix_chunk_sets_parse_status": ["parse_result_id", "status"],
            "ix_chunk_sets_status": ["status"],
            "ix_chunk_sets_stored_file_id": ["stored_file_id"],
            "ix_chunk_sets_strategy_name": ["strategy_name"],
            "ix_chunk_sets_strategy_version": ["strategy_version"],
            "ix_chunk_sets_uuid": ["uuid"],
            "ix_chunk_sets_version_status": [
                "document_version_id",
                "status",
            ],
        },
        unique={"ix_chunk_sets_uuid"},
    )

    with op.batch_alter_table("knowledge_chunks") as batch:
        batch.alter_column(
            "document_id",
            existing_type=sa.Integer(),
            nullable=True,
        )
        batch.add_column(sa.Column("uuid", sa.String(length=36)))
        batch.add_column(sa.Column("chunk_set_id", sa.Integer()))
        batch.add_column(sa.Column("ordinal", sa.Integer()))
        batch.add_column(sa.Column("stable_key", sa.String(length=64)))
        batch.add_column(sa.Column("content_type", sa.String(length=50)))
        batch.add_column(
            sa.Column(
                "text",
                sa.Text().with_variant(mysql.LONGTEXT(), "mysql"),
            )
        )
        batch.add_column(
            sa.Column(
                "normalized_text",
                sa.Text().with_variant(mysql.LONGTEXT(), "mysql"),
            )
        )
        batch.add_column(sa.Column("heading_context_json", sa.JSON()))
        batch.add_column(sa.Column("language", sa.String(length=64)))
        batch.add_column(sa.Column("character_count", sa.Integer()))
        batch.add_column(sa.Column("content_hash", sa.String(length=64)))
        batch.add_column(sa.Column("previous_chunk_id", sa.Integer()))
        batch.add_column(sa.Column("next_chunk_id", sa.Integer()))
        batch.create_foreign_key(
            "fk_knowledge_chunks_chunk_set_id",
            "chunk_sets",
            ["chunk_set_id"],
            ["id"],
            ondelete="CASCADE",
        )
        batch.create_foreign_key(
            "fk_knowledge_chunks_previous_chunk_id",
            "knowledge_chunks",
            ["previous_chunk_id"],
            ["id"],
            ondelete="SET NULL",
        )
        batch.create_foreign_key(
            "fk_knowledge_chunks_next_chunk_id",
            "knowledge_chunks",
            ["next_chunk_id"],
            ["id"],
            ondelete="SET NULL",
        )
        batch.create_unique_constraint(
            "uq_knowledge_chunk_ordinal",
            ["chunk_set_id", "ordinal"],
        )
        batch.create_unique_constraint(
            "uq_knowledge_chunk_stable_key",
            ["chunk_set_id", "stable_key"],
        )
        batch.create_check_constraint(
            "ck_knowledge_chunks_ordinal",
            "chunk_set_id IS NULL OR ordinal >= 0",
        )
    _indexes(
        "knowledge_chunks",
        {
            "ix_knowledge_chunks_chunk_set_id": ["chunk_set_id"],
            "ix_knowledge_chunks_content_hash": ["content_hash"],
            "ix_knowledge_chunks_content_type": ["content_type"],
            "ix_knowledge_chunks_language": ["language"],
            "ix_knowledge_chunks_next_chunk_id": ["next_chunk_id"],
            "ix_knowledge_chunks_previous_chunk_id": ["previous_chunk_id"],
            "ix_knowledge_chunks_set_type": [
                "chunk_set_id",
                "content_type",
            ],
            "ix_knowledge_chunks_stable_key": ["stable_key"],
            "ix_knowledge_chunks_uuid": ["uuid"],
        },
        unique={"ix_knowledge_chunks_uuid"},
    )

    op.create_table(
        "chunk_source_spans",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("knowledge_chunk_id", sa.Integer(), nullable=False),
        sa.Column("source_order", sa.Integer(), nullable=False),
        sa.Column(
            "canonical_block_type",
            sa.String(length=50),
            nullable=False,
        ),
        sa.Column("canonical_block_index", sa.Integer(), nullable=True),
        sa.Column("source_index", sa.Integer(), nullable=True),
        sa.Column("page_number", sa.Integer(), nullable=True),
        sa.Column("section_path_json", sa.JSON(), nullable=True),
        sa.Column("paragraph_index", sa.Integer(), nullable=True),
        sa.Column("table_index", sa.Integer(), nullable=True),
        sa.Column("table_row_start", sa.Integer(), nullable=True),
        sa.Column("table_row_end", sa.Integer(), nullable=True),
        sa.Column("character_start", sa.Integer(), nullable=True),
        sa.Column("character_end", sa.Integer(), nullable=True),
        sa.Column("source_locator", sa.String(length=1000), nullable=True),
        sa.Column("text_start_in_chunk", sa.Integer(), nullable=False),
        sa.Column("text_end_in_chunk", sa.Integer(), nullable=False),
        sa.Column("is_overlap", sa.Boolean(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
        ),
        sa.CheckConstraint(
            "table_row_start IS NULL OR table_row_end IS NULL OR "
            "table_row_end >= table_row_start",
            name="ck_chunk_source_spans_table_rows",
        ),
        sa.CheckConstraint(
            "text_start_in_chunk >= 0 AND "
            "text_end_in_chunk >= text_start_in_chunk",
            name="ck_chunk_source_spans_text_offsets",
        ),
        sa.ForeignKeyConstraint(
            ["knowledge_chunk_id"],
            ["knowledge_chunks.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "knowledge_chunk_id",
            "source_order",
            name="uq_chunk_source_span_order",
        ),
    )
    _indexes(
        "chunk_source_spans",
        {
            "ix_chunk_source_spans_canonical_block_type": [
                "canonical_block_type"
            ],
            "ix_chunk_source_spans_knowledge_chunk_id": [
                "knowledge_chunk_id"
            ],
            "ix_chunk_source_spans_page_number": ["page_number"],
            "ix_chunk_source_spans_source_index": ["source_index"],
        },
    )

    op.create_table(
        "chunk_relationships",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("chunk_set_id", sa.Integer(), nullable=False),
        sa.Column("source_chunk_id", sa.Integer(), nullable=False),
        sa.Column("target_chunk_id", sa.Integer(), nullable=False),
        sa.Column(
            "relationship_type",
            sa.String(length=50),
            nullable=False,
        ),
        sa.Column("metadata_json", sa.JSON(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
        ),
        sa.CheckConstraint(
            "source_chunk_id <> target_chunk_id",
            name="ck_chunk_relationship_not_self",
        ),
        sa.ForeignKeyConstraint(
            ["chunk_set_id"],
            ["chunk_sets.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["source_chunk_id"],
            ["knowledge_chunks.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["target_chunk_id"],
            ["knowledge_chunks.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "source_chunk_id",
            "target_chunk_id",
            "relationship_type",
            name="uq_chunk_relationship_tuple",
        ),
    )
    _indexes(
        "chunk_relationships",
        {
            "ix_chunk_relationships_chunk_set_id": ["chunk_set_id"],
            "ix_chunk_relationships_relationship_type": [
                "relationship_type"
            ],
            "ix_chunk_relationships_set_type": [
                "chunk_set_id",
                "relationship_type",
            ],
            "ix_chunk_relationships_source_chunk_id": ["source_chunk_id"],
            "ix_chunk_relationships_target_chunk_id": ["target_chunk_id"],
        },
    )

    op.create_table(
        "chunking_executions",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("chunk_set_id", sa.Integer(), nullable=False),
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
        sa.Column("strategy_name", sa.String(length=100), nullable=False),
        sa.Column("strategy_version", sa.String(length=64), nullable=False),
        sa.Column("node_name", sa.String(length=255), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
        ),
        sa.CheckConstraint(
            "attempt_number > 0",
            name="ck_chunking_executions_attempt_number",
        ),
        sa.CheckConstraint(
            "duration_ms IS NULL OR duration_ms >= 0",
            name="ck_chunking_executions_duration",
        ),
        sa.ForeignKeyConstraint(
            ["chunk_set_id"],
            ["chunk_sets.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "chunk_set_id",
            "attempt_number",
            name="uq_chunking_execution_attempt",
        ),
    )
    _indexes(
        "chunking_executions",
        {
            "ix_chunking_executions_chunk_set_id": ["chunk_set_id"],
            "ix_chunking_executions_error_code": ["error_code"],
            "ix_chunking_executions_status": ["status"],
        },
    )

    op.create_table(
        "chunking_artifacts",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("chunk_set_id", sa.Integer(), nullable=False),
        sa.Column("artifact_type", sa.String(length=50), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("content_json", sa.JSON(), nullable=True),
        sa.Column(
            "content_text",
            sa.Text().with_variant(mysql.LONGTEXT(), "mysql"),
            nullable=True,
        ),
        sa.Column("checksum", sa.String(length=64), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["chunk_set_id"],
            ["chunk_sets.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    _indexes(
        "chunking_artifacts",
        {
            "ix_chunking_artifacts_artifact_type": ["artifact_type"],
            "ix_chunking_artifacts_checksum": ["checksum"],
            "ix_chunking_artifacts_chunk_set_id": ["chunk_set_id"],
            "ix_chunking_artifacts_set_type": [
                "chunk_set_id",
                "artifact_type",
            ],
        },
    )


def downgrade() -> None:
    op.drop_table("chunking_artifacts")
    op.drop_table("chunking_executions")
    op.drop_table("chunk_relationships")
    op.drop_table("chunk_source_spans")

    op.execute(
        sa.text(
            "DELETE FROM knowledge_chunks WHERE chunk_set_id IS NOT NULL"
        )
    )
    for name in (
        "ix_knowledge_chunks_uuid",
        "ix_knowledge_chunks_stable_key",
        "ix_knowledge_chunks_set_type",
        "ix_knowledge_chunks_previous_chunk_id",
        "ix_knowledge_chunks_next_chunk_id",
        "ix_knowledge_chunks_language",
        "ix_knowledge_chunks_content_type",
        "ix_knowledge_chunks_content_hash",
        "ix_knowledge_chunks_chunk_set_id",
    ):
        op.drop_index(name, table_name="knowledge_chunks")
    with op.batch_alter_table("knowledge_chunks") as batch:
        batch.drop_constraint(
            "ck_knowledge_chunks_ordinal",
            type_="check",
        )
        batch.drop_constraint(
            "uq_knowledge_chunk_stable_key",
            type_="unique",
        )
        batch.drop_constraint(
            "uq_knowledge_chunk_ordinal",
            type_="unique",
        )
        batch.drop_constraint(
            "fk_knowledge_chunks_next_chunk_id",
            type_="foreignkey",
        )
        batch.drop_constraint(
            "fk_knowledge_chunks_previous_chunk_id",
            type_="foreignkey",
        )
        batch.drop_constraint(
            "fk_knowledge_chunks_chunk_set_id",
            type_="foreignkey",
        )
        for column in (
            "next_chunk_id",
            "previous_chunk_id",
            "content_hash",
            "character_count",
            "language",
            "heading_context_json",
            "normalized_text",
            "text",
            "content_type",
            "stable_key",
            "ordinal",
            "chunk_set_id",
            "uuid",
        ):
            batch.drop_column(column)
        batch.alter_column(
            "document_id",
            existing_type=sa.Integer(),
            nullable=False,
        )
    op.drop_table("chunk_sets")


def _indexes(
    table_name: str,
    indexes: dict[str, list[str]],
    *,
    unique: set[str] | None = None,
) -> None:
    unique_names = unique or set()
    for name, columns in indexes.items():
        op.create_index(
            name,
            table_name,
            columns,
            unique=name in unique_names,
        )
