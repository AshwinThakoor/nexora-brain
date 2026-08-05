from __future__ import annotations

import pytest
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError

from nexora_knowledge.models import (
    Assessment,
    AssessmentAnswer,
    AssessmentAttempt,
    AssessmentOption,
    AssessmentQuestion,
    Course,
    CourseEnrollment,
    CurriculumPathEnrollment,
    Learner,
    LessonCompletion,
    LessonProgress,
)
from nexora_knowledge.services.curriculum import (
    create_course,
    create_curriculum_path,
    create_degree,
    create_lesson,
    create_module,
    create_school,
)
from nexora_knowledge.services.exceptions import (
    ResourceConflictError,
    ResourceValidationError,
)
from nexora_knowledge.services.learning import (
    add_lesson_time,
    calculate_course_completion,
    calculate_path_completion,
    complete_course_enrollment,
    complete_lesson,
    create_assessment,
    create_learner,
    deactivate_learner,
    enroll_in_course,
    enroll_in_curriculum_path,
    get_course_progress_summary,
    get_learner_progress_summary,
    get_path_progress_summary,
    list_learner_attempts,
    list_learner_enrollments,
    list_lesson_completions,
    reset_lesson_progress,
    start_assessment_attempt,
    start_course_enrollment,
    start_lesson,
    submit_assessment_attempt,
    update_lesson_progress,
)


def learning_hierarchy(db):
    school = create_school(
        db, {"name": "Learning School", "slug": "learning-school"}
    )
    degree = create_degree(
        db,
        {
            "school_id": school.id,
            "name": "Learning Degree",
            "slug": "learning-degree",
            "level": "foundation",
        },
    )
    course = create_course(
        db,
        {
            "degree_id": degree.id,
            "name": "Learning Course",
            "slug": "learning-course",
        },
    )
    module = create_module(
        db,
        {
            "course_id": course.id,
            "name": "Learning Module",
            "slug": "learning-module",
        },
    )
    lessons = [
        create_lesson(
            db,
            {
                "module_id": module.id,
                "title": f"Lesson {index}",
                "slug": f"learning-lesson-{index}",
                "display_order": index,
            },
        )
        for index in range(3)
    ]
    path = create_curriculum_path(
        db,
        {
            "name": "Learning Path",
            "slug": "learning-path",
            "lesson_ids": [lesson.id for lesson in lessons],
        },
    )
    return school, degree, course, module, lessons, path


def learner(db, suffix: str = "one"):
    return create_learner(
        db,
        {
            "external_user_id": f"external-{suffix}",
            "email": f"{suffix}@example.com",
            "display_name": f"Learner {suffix}",
        },
    )


def assessment_payload(lesson_id: int, slug: str, *, mixed: bool = False):
    questions = [
        {
            "question_type": "multiple_choice",
            "prompt": "Choose A",
            "points": 2,
            "options": [
                {"option_text": "A", "is_correct": True},
                {"option_text": "B", "is_correct": False},
            ],
        },
        {
            "question_type": "true_false",
            "prompt": "The statement is true.",
            "points": 1,
            "options": [
                {"option_text": "True", "is_correct": True},
                {"option_text": "False", "is_correct": False},
            ],
        },
    ]
    if mixed:
        questions.append(
            {
                "question_type": "short_answer",
                "prompt": "Explain.",
                "points": 2,
                "options": [],
            }
        )
    return {
        "lesson_id": lesson_id,
        "title": slug.replace("-", " ").title(),
        "slug": slug,
        "passing_score": 70,
        "max_attempts": 2,
        "questions": questions,
    }


def test_learner_identity_uniqueness_and_deactivation(db) -> None:
    first = learner(db)
    assert first.status == "active"
    assert first.email == "one@example.com"

    with pytest.raises(ResourceValidationError):
        create_learner(db, {"display_name": "Missing Identity"})
    with pytest.raises(ResourceConflictError):
        create_learner(
            db,
            {
                "email": "ONE@EXAMPLE.COM",
                "display_name": "Duplicate",
            },
        )

    deactivate_learner(db, first.id)
    assert first.status == "inactive"


def test_enrollment_duplicate_start_complete_and_ordered_listing(db) -> None:
    _, _, course, _, _, path = learning_hierarchy(db)
    student = learner(db)
    course_enrollment = enroll_in_course(db, student.id, course.id)
    path_enrollment = enroll_in_curriculum_path(db, student.id, path.id)

    with pytest.raises(ResourceConflictError):
        enroll_in_course(db, student.id, course.id)
    with pytest.raises(ResourceConflictError):
        enroll_in_curriculum_path(db, student.id, path.id)

    start_course_enrollment(db, course_enrollment.id)
    assert course_enrollment.status == "in_progress"
    first_started_at = course_enrollment.started_at
    start_course_enrollment(db, course_enrollment.id)
    assert course_enrollment.started_at == first_started_at

    complete_course_enrollment(db, course_enrollment.id)
    assert course_enrollment.progress_percent == 100
    assert course_enrollment.completed_at is not None
    assert list_learner_enrollments(db, student.id) == [
        course_enrollment,
        path_enrollment,
    ]


def test_lesson_progress_completion_reset_history_and_rollups(db) -> None:
    _, _, course, _, lessons, path = learning_hierarchy(db)
    student = learner(db)
    course_enrollment = enroll_in_course(db, student.id, course.id)
    path_enrollment = enroll_in_curriculum_path(db, student.id, path.id)

    progress = start_lesson(db, student.id, lessons[0].id)
    assert progress.status == "in_progress"
    assert progress.attempt_count == 1
    add_lesson_time(db, student.id, lessons[0].id, 90)
    update_lesson_progress(db, student.id, lessons[0].id, 50)
    assert progress.time_spent_seconds == 90
    assert progress.progress_percent == 50

    complete_lesson(db, student.id, lessons[0].id)
    complete_lesson(db, student.id, lessons[0].id)
    assert progress.progress_percent == 100
    assert len(list_lesson_completions(db, student.id)) == 1
    assert calculate_course_completion(db, student.id, course.id) == 33.33
    assert calculate_path_completion(db, student.id, path.id) == 33.33

    for lesson in lessons[1:]:
        complete_lesson(db, student.id, lesson.id)
    assert course_enrollment.status == "completed"
    assert path_enrollment.status == "completed"
    assert course_enrollment.progress_percent == 100
    assert path_enrollment.progress_percent == 100

    with pytest.raises(ResourceValidationError):
        reset_lesson_progress(db, student.id, lessons[0].id)
    reset_lesson_progress(
        db, student.id, lessons[0].id, explicit=True
    )
    assert progress.status == "not_started"
    assert course_enrollment.status == "in_progress"
    assert course_enrollment.progress_percent == 66.67
    assert len(list_lesson_completions(db, student.id)) == 3

    complete_lesson(db, student.id, lessons[0].id)
    assert len(
        list_lesson_completions(
            db, student.id, lesson_id=lessons[0].id
        )
    ) == 2
    assert course_enrollment.status == "completed"


def test_progress_validation_and_zero_lesson_rollups(db) -> None:
    _, degree, _, _, lessons, _ = learning_hierarchy(db)
    empty_course = create_course(
        db,
        {
            "degree_id": degree.id,
            "name": "Empty Course",
            "slug": "empty-course",
        },
    )
    empty_path = create_curriculum_path(
        db, {"name": "Empty Path", "slug": "empty-path"}
    )
    student = learner(db)
    empty_course_enrollment = enroll_in_course(
        db, student.id, empty_course.id
    )
    empty_path_enrollment = enroll_in_curriculum_path(
        db, student.id, empty_path.id
    )
    assert empty_course_enrollment.progress_percent == 0
    assert empty_course_enrollment.status == "enrolled"
    assert empty_path_enrollment.progress_percent == 0
    assert empty_path_enrollment.status == "enrolled"

    with pytest.raises(ResourceValidationError):
        update_lesson_progress(db, student.id, lessons[0].id, 101)
    with pytest.raises(ResourceValidationError):
        add_lesson_time(db, student.id, lessons[0].id, -1)


def test_assessment_ownership_and_question_option_validation_is_atomic(
    db,
) -> None:
    _, _, course, module, lessons, _ = learning_hierarchy(db)
    with pytest.raises(ResourceValidationError):
        create_assessment(
            db,
            {
                "lesson_id": lessons[0].id,
                "course_id": course.id,
                "title": "Two Owners",
                "slug": "two-owners",
            },
        )
    with pytest.raises(ResourceValidationError):
        create_assessment(
            db,
            {
                "module_id": module.id,
                "title": "Bad True False",
                "slug": "bad-true-false",
                "questions": [
                    {
                        "question_type": "true_false",
                        "prompt": "Bad options",
                        "options": [
                            {"option_text": "True", "is_correct": True}
                        ],
                    }
                ],
            },
        )
    with pytest.raises(ResourceValidationError):
        create_assessment(
            db,
            {
                "lesson_id": lessons[0].id,
                "title": "Bad Short Answer",
                "slug": "bad-short-answer",
                "questions": [
                    {
                        "question_type": "short_answer",
                        "prompt": "No options allowed",
                        "options": [
                            {"option_text": "Unexpected", "is_correct": True},
                            {"option_text": "Other", "is_correct": False},
                        ],
                    }
                ],
            },
        )
    assert db.scalar(select(func.count()).select_from(Assessment)) == 0
    assert (
        db.scalar(select(func.count()).select_from(AssessmentQuestion)) == 0
    )


def test_assessment_attempt_grading_limits_and_resubmission(db) -> None:
    _, _, _, _, lessons, _ = learning_hierarchy(db)
    student = learner(db)
    assessment = create_assessment(
        db, assessment_payload(lessons[0].id, "automatic-grading")
    )
    first = start_assessment_attempt(db, student.id, assessment.id)
    answers = [
        {
            "question_id": question.id,
            "selected_option_id": next(
                option.id for option in question.options if option.is_correct
            ),
        }
        for question in assessment.questions
    ]
    submitted = submit_assessment_attempt(
        db, first.id, answers, time_spent_seconds=45
    )
    assert submitted.score_percent == 100
    assert submitted.points_earned == 3
    assert submitted.points_possible == 3
    assert submitted.passed is True
    assert submitted.time_spent_seconds == 45
    assert all(answer.is_correct for answer in submitted.answers)

    with pytest.raises(ResourceConflictError):
        submit_assessment_attempt(db, first.id, answers)
    second = start_assessment_attempt(db, student.id, assessment.id)
    assert second.attempt_number == 2
    with pytest.raises(ResourceConflictError):
        start_assessment_attempt(db, student.id, assessment.id)
    assert list_learner_attempts(db, student.id) == [first, second]


def test_short_answer_remains_ungraded_and_wrong_option_is_rejected(db) -> None:
    _, _, _, _, lessons, _ = learning_hierarchy(db)
    student = learner(db)
    mixed = create_assessment(
        db,
        assessment_payload(
            lessons[0].id, "mixed-assessment", mixed=True
        ),
    )
    attempt = start_assessment_attempt(db, student.id, mixed.id)
    answers = []
    for question in mixed.questions:
        if question.question_type == "short_answer":
            answers.append(
                {"question_id": question.id, "text_answer": "Price discovery"}
            )
        else:
            answers.append(
                {
                    "question_id": question.id,
                    "selected_option_id": next(
                        option.id
                        for option in question.options
                        if option.is_correct
                    ),
                }
            )
    result = submit_assessment_attempt(db, attempt.id, answers)
    assert result.score_percent == 60
    assert result.passed is None
    short_answer = next(
        answer
        for answer in result.answers
        if answer.question_id == mixed.questions[-1].id
    )
    assert short_answer.is_correct is None
    assert short_answer.points_awarded is None

    other = create_assessment(
        db, assessment_payload(lessons[1].id, "other-assessment")
    )
    invalid_attempt = start_assessment_attempt(db, student.id, other.id)
    wrong_option_id = mixed.questions[0].options[0].id
    with pytest.raises(ResourceValidationError):
        submit_assessment_attempt(
            db,
            invalid_attempt.id,
            [
                {
                    "question_id": other.questions[0].id,
                    "selected_option_id": wrong_option_id,
                }
            ],
        )
    assert (
        db.scalar(
            select(func.count(AssessmentAnswer.id)).where(
                AssessmentAnswer.attempt_id == invalid_attempt.id
            )
        )
        == 0
    )


def test_summaries_and_historical_rows_are_not_cascade_deleted(db) -> None:
    _, _, course, _, lessons, path = learning_hierarchy(db)
    student = learner(db)
    enroll_in_course(db, student.id, course.id)
    enroll_in_curriculum_path(db, student.id, path.id)
    add_lesson_time(db, student.id, lessons[0].id, 120)
    complete_lesson(db, student.id, lessons[0].id)

    course_summary = get_course_progress_summary(
        db, student.id, course.id
    )
    path_summary = get_path_progress_summary(db, student.id, path.id)
    overall = get_learner_progress_summary(db, student.id)
    assert course_summary.progress_percent == 33.33
    assert path_summary.progress_percent == 33.33
    assert course_summary.time_spent_seconds == 120
    assert overall.completed_lesson_count == 1
    assert overall.completion_event_count == 1
    assert overall.total_time_spent_seconds == 120
    assert overall.recent_activity[0].activity_type == "lesson_completed"

    db.delete(student)
    with pytest.raises(IntegrityError):
        db.commit()
    db.rollback()
    assert db.get(Learner, student.id) is not None
    assert db.scalar(select(func.count()).select_from(LessonCompletion)) == 1


def test_database_constraints_and_assessment_definition_cascade(db) -> None:
    _, _, _, _, lessons, _ = learning_hierarchy(db)
    student = learner(db)
    db.add(
        LessonProgress(
            learner_id=student.id,
            lesson_id=lessons[0].id,
            progress_percent=-1,
        )
    )
    with pytest.raises(IntegrityError):
        db.commit()
    db.rollback()

    assessment = create_assessment(
        db, assessment_payload(lessons[0].id, "cascade-assessment")
    )
    question_ids = [question.id for question in assessment.questions]
    option_ids = [
        option.id
        for question in assessment.questions
        for option in question.options
    ]
    db.delete(assessment)
    db.commit()
    assert db.scalars(
        select(AssessmentQuestion).where(
            AssessmentQuestion.id.in_(question_ids)
        )
    ).all() == []
    assert db.scalars(
        select(AssessmentOption).where(AssessmentOption.id.in_(option_ids))
    ).all() == []
    assert (
        db.scalar(select(func.count()).select_from(AssessmentAttempt)) == 0
    )
    assert (
        db.scalar(select(func.count()).select_from(CourseEnrollment)) == 0
    )
    assert (
        db.scalar(
            select(func.count()).select_from(CurriculumPathEnrollment)
        )
        == 0
    )
