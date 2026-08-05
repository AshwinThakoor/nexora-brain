from __future__ import annotations

import pytest
from pydantic import ValidationError

from nexora_knowledge.schemas.learning import (
    AssessmentCreate,
    LearnerCreate,
    LessonProgressCreate,
)


def test_learning_schemas_validate_identity_progress_and_owner() -> None:
    learner = LearnerCreate(
        email="  PERSON@EXAMPLE.COM  ",
        display_name=" Person ",
    )
    assert learner.email == "person@example.com"
    assert learner.display_name == "Person"

    with pytest.raises(ValidationError):
        LearnerCreate(display_name="Missing Identity")
    with pytest.raises(ValidationError):
        LessonProgressCreate(
            learner_id=1,
            lesson_id=1,
            progress_percent=100.01,
        )
    with pytest.raises(ValidationError):
        AssessmentCreate(
            lesson_id=1,
            course_id=1,
            title="Two Owners",
            slug="two-owners",
        )


def test_nested_assessment_schema_round_trip() -> None:
    assessment = AssessmentCreate(
        lesson_id=1,
        title="Knowledge Check",
        slug="knowledge-check",
        questions=[
            {
                "question_type": "true_false",
                "prompt": "Markets match participants.",
                "options": [
                    {"option_text": "True", "is_correct": True},
                    {"option_text": "False", "is_correct": False},
                ],
            }
        ],
    )
    assert assessment.questions[0].question_type.value == "true_false"
    assert len(assessment.questions[0].options) == 2
