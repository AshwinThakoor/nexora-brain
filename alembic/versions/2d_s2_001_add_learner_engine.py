"""add NEXORA Academy learner and assessment engine

Revision ID: 2d_s2_001
Revises: 2d_s1_001
Create Date: 2026-07-28 12:00:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "2d_s2_001"
down_revision: Union[str, Sequence[str], None] = "2d_s1_001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create learner progress, completion, and assessment tables."""
    op.create_table(
        "learners",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("external_user_id", sa.String(length=255), nullable=True),
        sa.Column("email", sa.String(length=320), nullable=True),
        sa.Column("display_name", sa.String(length=255), nullable=False),
        sa.Column("status", sa.String(length=50), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_learners_email",
        "learners",
        ["email"],
        unique=True,
    )
    op.create_index(
        "ix_learners_external_user_id",
        "learners",
        ["external_user_id"],
        unique=True,
    )

    op.create_table(
        "course_enrollments",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("learner_id", sa.Integer(), nullable=False),
        sa.Column("course_id", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=50), nullable=False),
        sa.Column(
            "enrolled_at",
            sa.DateTime(timezone=True),
            nullable=False,
        ),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "last_accessed_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
        sa.Column("progress_percent", sa.Float(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "progress_percent >= 0.0 AND progress_percent <= 100.0",
            name="ck_course_enrollments_progress_range",
        ),
        sa.ForeignKeyConstraint(
            ["course_id"],
            ["courses.id"],
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["learner_id"],
            ["learners.id"],
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "learner_id",
            "course_id",
            name="uq_course_enrollment_learner_course",
        ),
    )
    op.create_index(
        "ix_course_enrollments_course_id",
        "course_enrollments",
        ["course_id"],
        unique=False,
    )
    op.create_index(
        "ix_course_enrollments_learner_id",
        "course_enrollments",
        ["learner_id"],
        unique=False,
    )

    op.create_table(
        "curriculum_path_enrollments",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("learner_id", sa.Integer(), nullable=False),
        sa.Column("curriculum_path_id", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=50), nullable=False),
        sa.Column(
            "enrolled_at",
            sa.DateTime(timezone=True),
            nullable=False,
        ),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "last_accessed_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
        sa.Column("progress_percent", sa.Float(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "progress_percent >= 0.0 AND progress_percent <= 100.0",
            name="ck_path_enrollments_progress_range",
        ),
        sa.ForeignKeyConstraint(
            ["curriculum_path_id"],
            ["curriculum_paths.id"],
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["learner_id"],
            ["learners.id"],
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "learner_id",
            "curriculum_path_id",
            name="uq_path_enrollment_learner_path",
        ),
    )
    op.create_index(
        "ix_curriculum_path_enrollments_curriculum_path_id",
        "curriculum_path_enrollments",
        ["curriculum_path_id"],
        unique=False,
    )
    op.create_index(
        "ix_curriculum_path_enrollments_learner_id",
        "curriculum_path_enrollments",
        ["learner_id"],
        unique=False,
    )

    op.create_table(
        "lesson_progress",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("learner_id", sa.Integer(), nullable=False),
        sa.Column("lesson_id", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=50), nullable=False),
        sa.Column("progress_percent", sa.Float(), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "last_accessed_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
        sa.Column("time_spent_seconds", sa.Integer(), nullable=False),
        sa.Column("attempt_count", sa.Integer(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "attempt_count >= 0",
            name="ck_lesson_progress_attempts_nonnegative",
        ),
        sa.CheckConstraint(
            "progress_percent >= 0.0 AND progress_percent <= 100.0",
            name="ck_lesson_progress_percent_range",
        ),
        sa.CheckConstraint(
            "time_spent_seconds >= 0",
            name="ck_lesson_progress_time_nonnegative",
        ),
        sa.ForeignKeyConstraint(
            ["learner_id"],
            ["learners.id"],
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["lesson_id"],
            ["lessons.id"],
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "learner_id",
            "lesson_id",
            name="uq_lesson_progress_learner_lesson",
        ),
    )
    op.create_index(
        "ix_lesson_progress_learner_id",
        "lesson_progress",
        ["learner_id"],
        unique=False,
    )
    op.create_index(
        "ix_lesson_progress_lesson_id",
        "lesson_progress",
        ["lesson_id"],
        unique=False,
    )

    op.create_table(
        "lesson_completions",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("learner_id", sa.Integer(), nullable=False),
        sa.Column("lesson_id", sa.Integer(), nullable=False),
        sa.Column(
            "completed_at",
            sa.DateTime(timezone=True),
            nullable=False,
        ),
        sa.Column("completion_source", sa.String(length=50), nullable=False),
        sa.Column("metadata_json", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["learner_id"],
            ["learners.id"],
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["lesson_id"],
            ["lessons.id"],
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_lesson_completions_completed_at",
        "lesson_completions",
        ["completed_at"],
        unique=False,
    )
    op.create_index(
        "ix_lesson_completions_learner_id",
        "lesson_completions",
        ["learner_id"],
        unique=False,
    )
    op.create_index(
        "ix_lesson_completions_lesson_id",
        "lesson_completions",
        ["lesson_id"],
        unique=False,
    )

    op.create_table(
        "assessments",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("lesson_id", sa.Integer(), nullable=True),
        sa.Column("module_id", sa.Integer(), nullable=True),
        sa.Column("course_id", sa.Integer(), nullable=True),
        sa.Column("title", sa.String(length=500), nullable=False),
        sa.Column("slug", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("assessment_type", sa.String(length=50), nullable=False),
        sa.Column("passing_score", sa.Float(), nullable=False),
        sa.Column("max_attempts", sa.Integer(), nullable=True),
        sa.Column("time_limit_minutes", sa.Integer(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("display_order", sa.Integer(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "("
            "(lesson_id IS NOT NULL AND module_id IS NULL "
            "AND course_id IS NULL) OR "
            "(lesson_id IS NULL AND module_id IS NOT NULL "
            "AND course_id IS NULL) OR "
            "(lesson_id IS NULL AND module_id IS NULL "
            "AND course_id IS NOT NULL)"
            ")",
            name="ck_assessments_exactly_one_owner",
        ),
        sa.CheckConstraint(
            "display_order >= 0",
            name="ck_assessments_display_order_nonnegative",
        ),
        sa.CheckConstraint(
            "max_attempts IS NULL OR max_attempts > 0",
            name="ck_assessments_max_attempts_positive",
        ),
        sa.CheckConstraint(
            "passing_score >= 0.0 AND passing_score <= 100.0",
            name="ck_assessments_passing_score_range",
        ),
        sa.CheckConstraint(
            "time_limit_minutes IS NULL OR time_limit_minutes > 0",
            name="ck_assessments_time_limit_positive",
        ),
        sa.ForeignKeyConstraint(
            ["course_id"],
            ["courses.id"],
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["lesson_id"],
            ["lessons.id"],
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["module_id"],
            ["modules.id"],
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_assessments_course_id",
        "assessments",
        ["course_id"],
        unique=False,
    )
    op.create_index(
        "ix_assessments_lesson_id",
        "assessments",
        ["lesson_id"],
        unique=False,
    )
    op.create_index(
        "ix_assessments_module_id",
        "assessments",
        ["module_id"],
        unique=False,
    )
    op.create_index(
        "ix_assessments_slug",
        "assessments",
        ["slug"],
        unique=True,
    )

    op.create_table(
        "assessment_questions",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("assessment_id", sa.Integer(), nullable=False),
        sa.Column("question_type", sa.String(length=50), nullable=False),
        sa.Column("prompt", sa.Text(), nullable=False),
        sa.Column("explanation", sa.Text(), nullable=True),
        sa.Column("points", sa.Float(), nullable=False),
        sa.Column("display_order", sa.Integer(), nullable=False),
        sa.Column("metadata_json", sa.JSON(), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "display_order >= 0",
            name="ck_assessment_questions_display_order_nonnegative",
        ),
        sa.CheckConstraint(
            "points >= 0.0",
            name="ck_assessment_questions_points_nonnegative",
        ),
        sa.ForeignKeyConstraint(
            ["assessment_id"],
            ["assessments.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_assessment_questions_assessment_id",
        "assessment_questions",
        ["assessment_id"],
        unique=False,
    )

    op.create_table(
        "assessment_options",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("question_id", sa.Integer(), nullable=False),
        sa.Column("option_text", sa.Text(), nullable=False),
        sa.Column("is_correct", sa.Boolean(), nullable=False),
        sa.Column("display_order", sa.Integer(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "display_order >= 0",
            name="ck_assessment_options_display_order_nonnegative",
        ),
        sa.ForeignKeyConstraint(
            ["question_id"],
            ["assessment_questions.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_assessment_options_question_id",
        "assessment_options",
        ["question_id"],
        unique=False,
    )

    op.create_table(
        "assessment_attempts",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("learner_id", sa.Integer(), nullable=False),
        sa.Column("assessment_id", sa.Integer(), nullable=False),
        sa.Column("attempt_number", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=50), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("submitted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("score_percent", sa.Float(), nullable=True),
        sa.Column("points_earned", sa.Float(), nullable=True),
        sa.Column("points_possible", sa.Float(), nullable=True),
        sa.Column("passed", sa.Boolean(), nullable=True),
        sa.Column("time_spent_seconds", sa.Integer(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "attempt_number > 0",
            name="ck_assessment_attempt_number_positive",
        ),
        sa.CheckConstraint(
            "points_earned IS NULL OR points_earned >= 0.0",
            name="ck_assessment_attempt_points_earned_nonnegative",
        ),
        sa.CheckConstraint(
            "points_possible IS NULL OR points_possible >= 0.0",
            name="ck_assessment_attempt_points_possible_nonnegative",
        ),
        sa.CheckConstraint(
            "score_percent IS NULL OR "
            "(score_percent >= 0.0 AND score_percent <= 100.0)",
            name="ck_assessment_attempt_score_range",
        ),
        sa.CheckConstraint(
            "time_spent_seconds >= 0",
            name="ck_assessment_attempt_time_nonnegative",
        ),
        sa.ForeignKeyConstraint(
            ["assessment_id"],
            ["assessments.id"],
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["learner_id"],
            ["learners.id"],
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "learner_id",
            "assessment_id",
            "attempt_number",
            name="uq_assessment_attempt_number",
        ),
    )
    op.create_index(
        "ix_assessment_attempts_assessment_id",
        "assessment_attempts",
        ["assessment_id"],
        unique=False,
    )
    op.create_index(
        "ix_assessment_attempts_learner_id",
        "assessment_attempts",
        ["learner_id"],
        unique=False,
    )

    op.create_table(
        "assessment_answers",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("attempt_id", sa.Integer(), nullable=False),
        sa.Column("question_id", sa.Integer(), nullable=False),
        sa.Column("selected_option_id", sa.Integer(), nullable=True),
        sa.Column("text_answer", sa.Text(), nullable=True),
        sa.Column("is_correct", sa.Boolean(), nullable=True),
        sa.Column("points_awarded", sa.Float(), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "points_awarded IS NULL OR points_awarded >= 0.0",
            name="ck_assessment_answers_points_nonnegative",
        ),
        sa.ForeignKeyConstraint(
            ["attempt_id"],
            ["assessment_attempts.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["question_id"],
            ["assessment_questions.id"],
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["selected_option_id"],
            ["assessment_options.id"],
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "attempt_id",
            "question_id",
            name="uq_assessment_answer_attempt_question",
        ),
    )
    op.create_index(
        "ix_assessment_answers_attempt_id",
        "assessment_answers",
        ["attempt_id"],
        unique=False,
    )
    op.create_index(
        "ix_assessment_answers_question_id",
        "assessment_answers",
        ["question_id"],
        unique=False,
    )
    op.create_index(
        "ix_assessment_answers_selected_option_id",
        "assessment_answers",
        ["selected_option_id"],
        unique=False,
    )


def downgrade() -> None:
    """Remove learner progress, completion, and assessment tables."""
    op.drop_table("assessment_answers")
    op.drop_table("assessment_attempts")
    op.drop_table("assessment_options")
    op.drop_table("assessment_questions")
    op.drop_table("assessments")
    op.drop_table("lesson_completions")
    op.drop_table("lesson_progress")
    op.drop_table("curriculum_path_enrollments")
    op.drop_table("course_enrollments")
    op.drop_table("learners")
