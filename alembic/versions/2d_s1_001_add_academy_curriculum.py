"""add NEXORA Academy curriculum

Revision ID: 2d_s1_001
Revises: 2c_s1_001
Create Date: 2026-07-26 21:30:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "2d_s1_001"
down_revision: Union[str, Sequence[str], None] = "2c_s1_001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create the Pack 2D Academy curriculum hierarchy."""
    op.create_table(
        "schools",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("slug", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("icon", sa.String(length=255), nullable=True),
        sa.Column("display_order", sa.Integer(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "display_order >= 0",
            name="ck_schools_display_order_nonnegative",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_schools_slug", "schools", ["slug"], unique=True)

    op.create_table(
        "curriculum_paths",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("slug", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_curriculum_paths_slug",
        "curriculum_paths",
        ["slug"],
        unique=True,
    )

    op.create_table(
        "degrees",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("school_id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("slug", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("level", sa.String(length=100), nullable=False),
        sa.Column("estimated_hours", sa.Float(), nullable=False),
        sa.Column("display_order", sa.Integer(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "display_order >= 0",
            name="ck_degrees_display_order_nonnegative",
        ),
        sa.CheckConstraint(
            "estimated_hours >= 0",
            name="ck_degrees_estimated_hours_nonnegative",
        ),
        sa.ForeignKeyConstraint(
            ["school_id"],
            ["schools.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_degrees_school_id",
        "degrees",
        ["school_id"],
        unique=False,
    )
    op.create_index("ix_degrees_slug", "degrees", ["slug"], unique=True)

    op.create_table(
        "courses",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("degree_id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("slug", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("estimated_hours", sa.Float(), nullable=False),
        sa.Column("display_order", sa.Integer(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "display_order >= 0",
            name="ck_courses_display_order_nonnegative",
        ),
        sa.CheckConstraint(
            "estimated_hours >= 0",
            name="ck_courses_estimated_hours_nonnegative",
        ),
        sa.ForeignKeyConstraint(
            ["degree_id"],
            ["degrees.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_courses_degree_id",
        "courses",
        ["degree_id"],
        unique=False,
    )
    op.create_index("ix_courses_slug", "courses", ["slug"], unique=True)

    op.create_table(
        "modules",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("course_id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("slug", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("estimated_minutes", sa.Integer(), nullable=False),
        sa.Column("display_order", sa.Integer(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "display_order >= 0",
            name="ck_modules_display_order_nonnegative",
        ),
        sa.CheckConstraint(
            "estimated_minutes >= 0",
            name="ck_modules_estimated_minutes_nonnegative",
        ),
        sa.ForeignKeyConstraint(
            ["course_id"],
            ["courses.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_modules_course_id",
        "modules",
        ["course_id"],
        unique=False,
    )
    op.create_index("ix_modules_slug", "modules", ["slug"], unique=True)

    op.create_table(
        "lessons",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("module_id", sa.Integer(), nullable=False),
        sa.Column("knowledge_article_id", sa.Integer(), nullable=True),
        sa.Column("concept_id", sa.Integer(), nullable=True),
        sa.Column("title", sa.String(length=500), nullable=False),
        sa.Column("slug", sa.String(length=255), nullable=False),
        sa.Column("summary", sa.Text(), nullable=True),
        sa.Column("estimated_minutes", sa.Integer(), nullable=False),
        sa.Column("difficulty_level", sa.String(length=50), nullable=False),
        sa.Column("status", sa.String(length=50), nullable=False),
        sa.Column("display_order", sa.Integer(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "display_order >= 0",
            name="ck_lessons_display_order_nonnegative",
        ),
        sa.CheckConstraint(
            "estimated_minutes >= 0",
            name="ck_lessons_estimated_minutes_nonnegative",
        ),
        sa.ForeignKeyConstraint(
            ["concept_id"],
            ["concepts.id"],
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["knowledge_article_id"],
            ["knowledge_articles.id"],
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["module_id"],
            ["modules.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_lessons_concept_id",
        "lessons",
        ["concept_id"],
        unique=False,
    )
    op.create_index(
        "ix_lessons_knowledge_article_id",
        "lessons",
        ["knowledge_article_id"],
        unique=False,
    )
    op.create_index(
        "ix_lessons_module_id",
        "lessons",
        ["module_id"],
        unique=False,
    )
    op.create_index("ix_lessons_slug", "lessons", ["slug"], unique=True)

    op.create_table(
        "learning_objectives",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("lesson_id", sa.Integer(), nullable=False),
        sa.Column("objective", sa.Text(), nullable=False),
        sa.Column("display_order", sa.Integer(), nullable=False),
        sa.CheckConstraint(
            "display_order >= 0",
            name="ck_learning_objectives_display_order_nonnegative",
        ),
        sa.ForeignKeyConstraint(
            ["lesson_id"],
            ["lessons.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_learning_objectives_lesson_id",
        "learning_objectives",
        ["lesson_id"],
        unique=False,
    )

    op.create_table(
        "lesson_prerequisites",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("lesson_id", sa.Integer(), nullable=False),
        sa.Column("prerequisite_lesson_id", sa.Integer(), nullable=False),
        sa.CheckConstraint(
            "lesson_id != prerequisite_lesson_id",
            name="ck_lesson_prerequisite_not_self",
        ),
        sa.ForeignKeyConstraint(
            ["lesson_id"],
            ["lessons.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["prerequisite_lesson_id"],
            ["lessons.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "lesson_id",
            "prerequisite_lesson_id",
            name="uq_lesson_prerequisite_pair",
        ),
    )
    op.create_index(
        "ix_lesson_prerequisites_lesson_id",
        "lesson_prerequisites",
        ["lesson_id"],
        unique=False,
    )
    op.create_index(
        "ix_lesson_prerequisites_prerequisite_lesson_id",
        "lesson_prerequisites",
        ["prerequisite_lesson_id"],
        unique=False,
    )

    op.create_table(
        "curriculum_path_lessons",
        sa.Column("curriculum_path_id", sa.Integer(), nullable=False),
        sa.Column("lesson_id", sa.Integer(), nullable=False),
        sa.Column("display_order", sa.Integer(), nullable=False),
        sa.CheckConstraint(
            "display_order >= 0",
            name="ck_curriculum_path_lessons_display_order_nonnegative",
        ),
        sa.ForeignKeyConstraint(
            ["curriculum_path_id"],
            ["curriculum_paths.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["lesson_id"],
            ["lessons.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("curriculum_path_id", "lesson_id"),
        sa.UniqueConstraint(
            "curriculum_path_id",
            "display_order",
            name="uq_curriculum_path_lesson_order",
        ),
        sa.UniqueConstraint(
            "curriculum_path_id",
            "lesson_id",
            name="uq_curriculum_path_lesson_pair",
        ),
    )
    op.create_index(
        "ix_curriculum_path_lessons_lesson_id",
        "curriculum_path_lessons",
        ["lesson_id"],
        unique=False,
    )


def downgrade() -> None:
    """Remove the Pack 2D Academy curriculum hierarchy."""
    op.drop_index(
        "ix_curriculum_path_lessons_lesson_id",
        table_name="curriculum_path_lessons",
    )
    op.drop_table("curriculum_path_lessons")

    op.drop_index(
        "ix_lesson_prerequisites_prerequisite_lesson_id",
        table_name="lesson_prerequisites",
    )
    op.drop_index(
        "ix_lesson_prerequisites_lesson_id",
        table_name="lesson_prerequisites",
    )
    op.drop_table("lesson_prerequisites")

    op.drop_index(
        "ix_learning_objectives_lesson_id",
        table_name="learning_objectives",
    )
    op.drop_table("learning_objectives")

    op.drop_index("ix_lessons_slug", table_name="lessons")
    op.drop_index("ix_lessons_module_id", table_name="lessons")
    op.drop_index(
        "ix_lessons_knowledge_article_id",
        table_name="lessons",
    )
    op.drop_index("ix_lessons_concept_id", table_name="lessons")
    op.drop_table("lessons")

    op.drop_index("ix_modules_slug", table_name="modules")
    op.drop_index("ix_modules_course_id", table_name="modules")
    op.drop_table("modules")

    op.drop_index("ix_courses_slug", table_name="courses")
    op.drop_index("ix_courses_degree_id", table_name="courses")
    op.drop_table("courses")

    op.drop_index("ix_degrees_slug", table_name="degrees")
    op.drop_index("ix_degrees_school_id", table_name="degrees")
    op.drop_table("degrees")

    op.drop_index("ix_curriculum_paths_slug", table_name="curriculum_paths")
    op.drop_table("curriculum_paths")

    op.drop_index("ix_schools_slug", table_name="schools")
    op.drop_table("schools")
