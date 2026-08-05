"""add Academy authentication-era grading and review records

Revision ID: 2d_s3_001
Revises: 2d_s2_001
Create Date: 2026-07-28
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "2d_s3_001"
down_revision: str | None = "2d_s2_001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "manual_grades",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("assessment_answer_id", sa.Integer(), nullable=False),
        sa.Column("grader_external_id", sa.String(length=255), nullable=True),
        sa.Column("grader_role", sa.String(length=50), nullable=False),
        sa.Column("points_awarded", sa.Float(), nullable=False),
        sa.Column("is_correct", sa.Boolean(), nullable=True),
        sa.Column("feedback", sa.Text(), nullable=True),
        sa.Column("grading_reason", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "points_awarded >= 0.0",
            name="ck_manual_grades_points_nonnegative",
        ),
        sa.ForeignKeyConstraint(
            ["assessment_answer_id"],
            ["assessment_answers.id"],
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_manual_grades_assessment_answer_id",
        "manual_grades",
        ["assessment_answer_id"],
        unique=False,
    )
    op.create_index(
        "ix_manual_grades_grader_external_id",
        "manual_grades",
        ["grader_external_id"],
        unique=False,
    )

    with op.batch_alter_table("assessment_answers") as batch_op:
        batch_op.add_column(
            sa.Column("current_manual_grade_id", sa.Integer(), nullable=True)
        )
        batch_op.add_column(
            sa.Column(
                "grading_status",
                sa.String(length=50),
                nullable=False,
                server_default="pending",
            )
        )
        batch_op.add_column(
            sa.Column("graded_at", sa.DateTime(timezone=True), nullable=True)
        )
        batch_op.create_foreign_key(
            "fk_answers_current_manual_grade",
            "manual_grades",
            ["current_manual_grade_id"],
            ["id"],
            ondelete="RESTRICT",
        )
        batch_op.create_index(
            "ix_assessment_answers_current_manual_grade_id",
            ["current_manual_grade_id"],
            unique=False,
        )

    with op.batch_alter_table("assessment_attempts") as batch_op:
        batch_op.add_column(
            sa.Column("automatic_score_percent", sa.Float(), nullable=True)
        )
        batch_op.add_column(
            sa.Column("automatic_points_earned", sa.Float(), nullable=True)
        )
        batch_op.add_column(
            sa.Column(
                "grading_status",
                sa.String(length=50),
                nullable=False,
                server_default="pending",
            )
        )
        batch_op.add_column(
            sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True)
        )
        batch_op.add_column(
            sa.Column("final_score_percent", sa.Float(), nullable=True)
        )
        batch_op.add_column(
            sa.Column("final_passed", sa.Boolean(), nullable=True)
        )
        batch_op.create_check_constraint(
            "ck_attempt_automatic_score_range",
            "automatic_score_percent IS NULL OR "
            "(automatic_score_percent >= 0.0 "
            "AND automatic_score_percent <= 100.0)",
        )
        batch_op.create_check_constraint(
            "ck_attempt_automatic_points_nonnegative",
            "automatic_points_earned IS NULL "
            "OR automatic_points_earned >= 0.0",
        )
        batch_op.create_check_constraint(
            "ck_assessment_attempt_final_score_range",
            "final_score_percent IS NULL OR "
            "(final_score_percent >= 0.0 AND final_score_percent <= 100.0)",
        )

    # Preserve and explicitly classify Sprint 2 provisional grading values.
    op.execute(
        sa.text(
            "UPDATE assessment_answers "
            "SET grading_status = CASE "
            "WHEN points_awarded IS NOT NULL THEN 'automatic_graded' "
            "ELSE 'manual_grading_required' END"
        )
    )
    op.execute(
        sa.text(
            "UPDATE assessment_attempts "
            "SET automatic_score_percent = score_percent, "
            "automatic_points_earned = points_earned, "
            "final_score_percent = CASE "
            "WHEN status = 'submitted' AND passed IS NOT NULL "
            "THEN score_percent ELSE NULL END, "
            "final_passed = CASE "
            "WHEN status = 'submitted' AND passed IS NOT NULL "
            "THEN passed ELSE NULL END, "
            "grading_status = CASE "
            "WHEN status != 'submitted' THEN 'pending' "
            "WHEN passed IS NOT NULL THEN 'final' "
            "ELSE 'manual_grading_required' END"
        )
    )

    op.create_table(
        "assessment_reviews",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("assessment_attempt_id", sa.Integer(), nullable=False),
        sa.Column("reviewer_external_id", sa.String(length=255), nullable=True),
        sa.Column("review_status", sa.String(length=50), nullable=False),
        sa.Column("review_reason", sa.Text(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["assessment_attempt_id"],
            ["assessment_attempts.id"],
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "assessment_attempt_id",
            name="uq_assessment_reviews_attempt",
        ),
    )
    op.create_index(
        "ix_assessment_reviews_assessment_attempt_id",
        "assessment_reviews",
        ["assessment_attempt_id"],
        unique=False,
    )
    op.create_index(
        "ix_assessment_reviews_reviewer_external_id",
        "assessment_reviews",
        ["reviewer_external_id"],
        unique=False,
    )

    op.create_table(
        "grading_audit_events",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("assessment_attempt_id", sa.Integer(), nullable=False),
        sa.Column("assessment_answer_id", sa.Integer(), nullable=True),
        sa.Column("actor_external_id", sa.String(length=255), nullable=True),
        sa.Column("actor_role", sa.String(length=50), nullable=False),
        sa.Column("event_type", sa.String(length=100), nullable=False),
        sa.Column("previous_values_json", sa.JSON(), nullable=True),
        sa.Column("new_values_json", sa.JSON(), nullable=True),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["assessment_answer_id"],
            ["assessment_answers.id"],
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["assessment_attempt_id"],
            ["assessment_attempts.id"],
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_grading_audit_events_assessment_answer_id",
        "grading_audit_events",
        ["assessment_answer_id"],
        unique=False,
    )
    op.create_index(
        "ix_grading_audit_events_assessment_attempt_id",
        "grading_audit_events",
        ["assessment_attempt_id"],
        unique=False,
    )
    op.create_index(
        "ix_grading_audit_events_actor_external_id",
        "grading_audit_events",
        ["actor_external_id"],
        unique=False,
    )
    op.create_index(
        "ix_grading_audit_events_event_type",
        "grading_audit_events",
        ["event_type"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_table("grading_audit_events")
    op.drop_table("assessment_reviews")

    with op.batch_alter_table("assessment_attempts") as batch_op:
        batch_op.drop_constraint(
            "ck_attempt_automatic_points_nonnegative",
            type_="check",
        )
        batch_op.drop_constraint(
            "ck_attempt_automatic_score_range",
            type_="check",
        )
        batch_op.drop_constraint(
            "ck_assessment_attempt_final_score_range",
            type_="check",
        )
        batch_op.drop_column("final_passed")
        batch_op.drop_column("final_score_percent")
        batch_op.drop_column("reviewed_at")
        batch_op.drop_column("grading_status")
        batch_op.drop_column("automatic_points_earned")
        batch_op.drop_column("automatic_score_percent")

    with op.batch_alter_table("assessment_answers") as batch_op:
        batch_op.drop_index(
            "ix_assessment_answers_current_manual_grade_id"
        )
        batch_op.drop_constraint(
            "fk_answers_current_manual_grade",
            type_="foreignkey",
        )
        batch_op.drop_column("graded_at")
        batch_op.drop_column("grading_status")
        batch_op.drop_column("current_manual_grade_id")

    op.drop_table("manual_grades")
