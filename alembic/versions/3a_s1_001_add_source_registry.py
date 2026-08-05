"""add the Pack 3 source registry

Revision ID: 3a_s1_001
Revises: 2d_s3_001
Create Date: 2026-07-28
"""

from collections.abc import Sequence
from uuid import uuid4

from alembic import op
import sqlalchemy as sa


revision: str = "3a_s1_001"
down_revision: str | None = "2d_s3_001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "source_organizations",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("slug", sa.String(length=255), nullable=False),
        sa.Column("website", sa.String(length=2048), nullable=True),
        sa.Column("country", sa.String(length=100), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_source_organizations_name",
        "source_organizations",
        ["name"],
        unique=True,
    )
    op.create_index(
        "ix_source_organizations_slug",
        "source_organizations",
        ["slug"],
        unique=True,
    )

    op.create_table(
        "source_licenses",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("slug", sa.String(length=255), nullable=False),
        sa.Column("url", sa.String(length=2048), nullable=True),
        sa.Column(
            "allows_ingestion",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
        sa.Column(
            "allows_distribution",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_source_licenses_name",
        "source_licenses",
        ["name"],
        unique=True,
    )
    op.create_index(
        "ix_source_licenses_slug",
        "source_licenses",
        ["slug"],
        unique=True,
    )

    with op.batch_alter_table("sources") as batch_op:
        batch_op.add_column(
            sa.Column("uuid", sa.String(length=36), nullable=True)
        )
        batch_op.add_column(
            sa.Column("slug", sa.String(length=255), nullable=True)
        )
        batch_op.add_column(
            sa.Column("subtitle", sa.String(length=500), nullable=True)
        )
        batch_op.add_column(
            sa.Column("description", sa.Text(), nullable=True)
        )
        batch_op.add_column(
            sa.Column(
                "language",
                sa.String(length=16),
                nullable=False,
                server_default="en",
            )
        )
        batch_op.add_column(
            sa.Column(
                "trust_level",
                sa.String(length=50),
                nullable=False,
                server_default="medium",
            )
        )
        batch_op.add_column(
            sa.Column("publication_date", sa.Date(), nullable=True)
        )
        batch_op.add_column(
            sa.Column("isbn", sa.String(length=32), nullable=True)
        )
        batch_op.add_column(
            sa.Column("doi", sa.String(length=255), nullable=True)
        )
        batch_op.add_column(
            sa.Column(
                "external_identifier",
                sa.String(length=255),
                nullable=True,
            )
        )
        batch_op.add_column(
            sa.Column("organization_id", sa.Integer(), nullable=True)
        )
        batch_op.add_column(
            sa.Column("license_id", sa.Integer(), nullable=True)
        )
        batch_op.add_column(
            sa.Column(
                "active",
                sa.Boolean(),
                nullable=False,
                server_default=sa.true(),
            )
        )
        batch_op.add_column(
            sa.Column(
                "archived",
                sa.Boolean(),
                nullable=False,
                server_default=sa.false(),
            )
        )
        batch_op.create_foreign_key(
            "fk_sources_organization_id",
            "source_organizations",
            ["organization_id"],
            ["id"],
            ondelete="SET NULL",
        )
        batch_op.create_foreign_key(
            "fk_sources_license_id",
            "source_licenses",
            ["license_id"],
            ["id"],
            ondelete="SET NULL",
        )

    connection = op.get_bind()
    source_ids = connection.execute(
        sa.text("SELECT id FROM sources WHERE uuid IS NULL OR slug IS NULL")
    ).scalars()
    for source_id in source_ids:
        connection.execute(
            sa.text(
                "UPDATE sources SET uuid = :uuid, slug = :slug WHERE id = :id"
            ),
            {
                "uuid": str(uuid4()),
                "slug": f"source-{source_id}",
                "id": source_id,
            },
        )

    with op.batch_alter_table("sources") as batch_op:
        batch_op.alter_column(
            "uuid",
            existing_type=sa.String(length=36),
            nullable=False,
        )
        batch_op.alter_column(
            "slug",
            existing_type=sa.String(length=255),
            nullable=False,
        )
        batch_op.create_index("ix_sources_uuid", ["uuid"], unique=True)
        batch_op.create_index("ix_sources_slug", ["slug"], unique=True)
        batch_op.create_index("ix_sources_isbn", ["isbn"], unique=True)
        batch_op.create_index("ix_sources_doi", ["doi"], unique=True)
        batch_op.create_index(
            "ix_sources_external_identifier",
            ["external_identifier"],
            unique=False,
        )
        batch_op.create_index(
            "ix_sources_organization_id",
            ["organization_id"],
            unique=False,
        )
        batch_op.create_index(
            "ix_sources_license_id",
            ["license_id"],
            unique=False,
        )

    op.create_table(
        "source_aliases",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("source_id", sa.Integer(), nullable=False),
        sa.Column("alias", sa.String(length=500), nullable=False),
        sa.ForeignKeyConstraint(
            ["source_id"],
            ["sources.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "source_id",
            "alias",
            name="uq_source_alias",
        ),
    )
    op.create_index(
        "ix_source_aliases_source_id",
        "source_aliases",
        ["source_id"],
        unique=False,
    )

    op.create_table(
        "source_versions",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("source_id", sa.Integer(), nullable=False),
        sa.Column("version", sa.String(length=100), nullable=False),
        sa.Column("checksum", sa.String(length=128), nullable=False),
        sa.Column("release_date", sa.Date(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(
            ["source_id"],
            ["sources.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "source_id",
            "checksum",
            name="uq_source_version_checksum",
        ),
        sa.UniqueConstraint(
            "source_id",
            "version",
            name="uq_source_version",
        ),
    )
    op.create_index(
        "ix_source_versions_source_id",
        "source_versions",
        ["source_id"],
        unique=False,
    )

    op.create_table(
        "source_tags",
        sa.Column("source_id", sa.Integer(), nullable=False),
        sa.Column("tag_id", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(
            ["source_id"],
            ["sources.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["tag_id"],
            ["tags.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("source_id", "tag_id"),
    )


def downgrade() -> None:
    op.drop_table("source_tags")
    op.drop_index(
        "ix_source_versions_source_id",
        table_name="source_versions",
    )
    op.drop_table("source_versions")
    op.drop_index(
        "ix_source_aliases_source_id",
        table_name="source_aliases",
    )
    op.drop_table("source_aliases")

    with op.batch_alter_table("sources") as batch_op:
        batch_op.drop_index("ix_sources_license_id")
        batch_op.drop_index("ix_sources_organization_id")
        batch_op.drop_index("ix_sources_external_identifier")
        batch_op.drop_index("ix_sources_doi")
        batch_op.drop_index("ix_sources_isbn")
        batch_op.drop_index("ix_sources_slug")
        batch_op.drop_index("ix_sources_uuid")
        batch_op.drop_constraint(
            "fk_sources_license_id",
            type_="foreignkey",
        )
        batch_op.drop_constraint(
            "fk_sources_organization_id",
            type_="foreignkey",
        )
        batch_op.drop_column("archived")
        batch_op.drop_column("active")
        batch_op.drop_column("license_id")
        batch_op.drop_column("organization_id")
        batch_op.drop_column("external_identifier")
        batch_op.drop_column("doi")
        batch_op.drop_column("isbn")
        batch_op.drop_column("publication_date")
        batch_op.drop_column("trust_level")
        batch_op.drop_column("language")
        batch_op.drop_column("description")
        batch_op.drop_column("subtitle")
        batch_op.drop_column("slug")
        batch_op.drop_column("uuid")

    op.drop_index(
        "ix_source_licenses_slug",
        table_name="source_licenses",
    )
    op.drop_index(
        "ix_source_licenses_name",
        table_name="source_licenses",
    )
    op.drop_table("source_licenses")
    op.drop_index(
        "ix_source_organizations_slug",
        table_name="source_organizations",
    )
    op.drop_index(
        "ix_source_organizations_name",
        table_name="source_organizations",
    )
    op.drop_table("source_organizations")
