from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from nexora_knowledge.api import app
from nexora_knowledge.api.dependencies import get_db
from nexora_knowledge.database import Base
from nexora_knowledge.services.curriculum import (
    create_course,
    create_curriculum_path,
    create_degree,
    create_lesson,
    create_module,
    create_school,
)
from nexora_knowledge.services.learning import (
    create_assessment,
    create_learner,
    start_assessment_attempt,
    submit_assessment_attempt,
)


@pytest.fixture
def academy_client():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    @event.listens_for(engine, "connect")
    def enable_foreign_keys(dbapi_connection, connection_record):
        del connection_record
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    Base.metadata.create_all(engine)
    test_session = sessionmaker(bind=engine, expire_on_commit=False)

    def override_get_db():
        with test_session() as session:
            yield session

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as client:
        yield client, test_session
    app.dependency_overrides.clear()
    engine.dispose()


def principal_headers(external_id: str, role: str) -> dict[str, str]:
    return {
        "X-Nexora-Principal-Id": external_id,
        "X-Nexora-Principal-Role": role,
    }


def seed_academy(session_factory):
    with session_factory() as db:
        school_a = create_school(
            db,
            {
                "name": "Alpha School",
                "slug": "alpha-school",
                "display_order": 1,
            },
        )
        create_school(
            db,
            {
                "name": "Zulu School",
                "slug": "zulu-school",
                "display_order": 2,
            },
        )
        degree = create_degree(
            db,
            {
                "school_id": school_a.id,
                "name": "Foundation Degree",
                "slug": "foundation-degree-api",
                "level": "foundation",
            },
        )
        course = create_course(
            db,
            {
                "degree_id": degree.id,
                "name": "Market Basics",
                "slug": "market-basics-api",
            },
        )
        module = create_module(
            db,
            {
                "course_id": course.id,
                "name": "Core Module",
                "slug": "core-module-api",
            },
        )
        lesson = create_lesson(
            db,
            {
                "module_id": module.id,
                "title": "Published Lesson",
                "slug": "published-lesson-api",
                "status": "published",
            },
        )
        draft_lesson = create_lesson(
            db,
            {
                "module_id": module.id,
                "title": "Draft Lesson",
                "slug": "draft-lesson-api",
                "status": "draft",
            },
        )
        path = create_curriculum_path(
            db,
            {
                "name": "Foundation Path",
                "slug": "foundation-path-api",
                "lesson_ids": [lesson.id, draft_lesson.id],
            },
        )
        learner = create_learner(
            db,
            {
                "external_user_id": "learner-api",
                "email": "learner-api@example.com",
                "display_name": "API Learner",
            },
        )
        other = create_learner(
            db,
            {
                "external_user_id": "other-api",
                "email": "other-api@example.com",
                "display_name": "Other Learner",
            },
        )
        assessment = create_assessment(
            db,
            {
                "lesson_id": lesson.id,
                "title": "Safe Assessment",
                "slug": "safe-assessment-api",
                "questions": [
                    {
                        "question_type": "multiple_choice",
                        "prompt": "Choose the supported statement",
                        "points": 2,
                        "options": [
                            {
                                "option_text": "Supported",
                                "is_correct": True,
                            },
                            {
                                "option_text": "Unsupported",
                                "is_correct": False,
                            },
                        ],
                    },
                    {
                        "question_type": "short_answer",
                        "prompt": "Explain risk",
                        "points": 3,
                        "options": [],
                    },
                ],
            },
        )
        attempt = start_assessment_attempt(
            db, learner.id, assessment.id
        )
        attempt = submit_assessment_attempt(
            db,
            attempt.id,
            [
                {
                    "question_id": assessment.questions[0].id,
                    "selected_option_id": (
                        assessment.questions[0].options[0].id
                    ),
                },
                {
                    "question_id": assessment.questions[1].id,
                    "text_answer": "Risk must be constrained.",
                },
            ],
        )
        short_answer = next(
            item
            for item in attempt.answers
            if item.question_id == assessment.questions[1].id
        )
        return {
            "school": school_a.id,
            "course": course.id,
            "lesson": lesson.id,
            "draft_lesson": draft_lesson.id,
            "path": path.id,
            "learner": learner.id,
            "other": other.id,
            "assessment": assessment.id,
            "attempt": attempt.id,
            "short_answer": short_answer.id,
        }


def test_academy_requires_auth_and_catalog_is_filtered_and_paginated(
    academy_client,
) -> None:
    client, sessions = academy_client
    ids = seed_academy(sessions)
    assert client.get(
        "/api/v1/academy/catalog/schools"
    ).status_code == 401

    headers = principal_headers("learner-api", "learner")
    schools = client.get(
        "/api/v1/academy/catalog/schools",
        params={"limit": 1},
        headers=headers,
    )
    assert schools.status_code == 200
    assert schools.json()["total"] == 2
    assert schools.json()["items"][0]["id"] == ids["school"]
    assert schools.json()["offset"] == schools.json()["skip"] == 0

    lessons = client.get(
        "/api/v1/academy/catalog/lessons",
        headers=headers,
    ).json()
    assert [item["id"] for item in lessons["items"]] == [ids["lesson"]]
    assert client.get(
        f"/api/v1/academy/catalog/lessons/{ids['draft_lesson']}",
        headers=headers,
    ).status_code == 404

    path = client.get(
        f"/api/v1/academy/catalog/curriculum-paths/{ids['path']}",
        headers=headers,
    ).json()
    assert [item["id"] for item in path["lessons"]] == [ids["lesson"]]


def test_learner_profile_enrollment_progress_and_duplicate_conflict(
    academy_client,
) -> None:
    client, sessions = academy_client
    ids = seed_academy(sessions)
    headers = principal_headers("learner-api", "learner")
    profile = client.get(
        "/api/v1/academy/learners/me", headers=headers
    )
    assert profile.status_code == 200
    assert profile.json()["id"] == ids["learner"]

    enrollment = client.post(
        "/api/v1/academy/enrollments/courses",
        headers=headers,
        json={"course_id": ids["course"]},
    )
    assert enrollment.status_code == 201
    assert client.post(
        "/api/v1/academy/enrollments/courses",
        headers=headers,
        json={"course_id": ids["course"]},
    ).status_code == 409

    assert client.post(
        f"/api/v1/academy/progress/lessons/{ids['lesson']}/start",
        headers=headers,
    ).status_code == 200
    updated = client.patch(
        f"/api/v1/academy/progress/lessons/{ids['lesson']}",
        headers=headers,
        json={"progress_percent": 50, "time_spent_seconds": 30},
    )
    assert updated.status_code == 200
    assert updated.json()["progress_percent"] == 50
    assert updated.json()["time_spent_seconds"] == 30
    completed = client.post(
        f"/api/v1/academy/progress/lessons/{ids['lesson']}/complete",
        headers=headers,
    )
    assert completed.json()["status"] == "completed"
    assert client.get(
        "/api/v1/academy/learners/me/dashboard",
        headers=headers,
    ).status_code == 200


def test_learner_assessment_has_no_answer_key_and_ownership_is_enforced(
    academy_client,
) -> None:
    client, sessions = academy_client
    ids = seed_academy(sessions)
    learner_headers = principal_headers("learner-api", "learner")
    detail = client.get(
        f"/api/v1/academy/assessments/{ids['assessment']}",
        headers=learner_headers,
    )
    assert detail.status_code == 200
    assert "is_correct" not in detail.text
    assert "explanation" not in detail.text

    own_result = client.get(
        f"/api/v1/academy/assessments/attempts/{ids['attempt']}/result",
        headers=learner_headers,
    )
    assert own_result.status_code == 200
    assert own_result.json()["final_score_percent"] is None
    assert own_result.json()["provisional_score_percent"] == 40

    other_headers = principal_headers("other-api", "learner")
    assert client.get(
        f"/api/v1/academy/assessments/attempts/{ids['attempt']}",
        headers=other_headers,
    ).status_code == 403


def test_role_boundaries_manual_grading_review_and_admin_lookup(
    academy_client,
) -> None:
    client, sessions = academy_client
    ids = seed_academy(sessions)
    learner_headers = principal_headers("learner-api", "learner")
    grade_url = (
        f"/api/v1/academy/grading/answers/{ids['short_answer']}"
    )
    assert client.post(
        grade_url,
        headers=learner_headers,
        json={"points_awarded": 3},
    ).status_code == 403

    instructor_headers = principal_headers(
        "instructor-api", "instructor"
    )
    wrong_scope_headers = {
        **instructor_headers,
        "X-Nexora-Course-Ids": "999999",
    }
    scoped_list = client.get(
        "/api/v1/academy/grading/attempts",
        headers=wrong_scope_headers,
    )
    assert scoped_list.status_code == 200
    assert scoped_list.json()["total"] == 0
    assert client.get(
        f"/api/v1/academy/grading/attempts/{ids['attempt']}",
        headers=wrong_scope_headers,
    ).status_code == 403
    grade = client.post(
        grade_url,
        headers=instructor_headers,
        json={
            "points_awarded": 3,
            "is_correct": True,
            "feedback": "Meets the rubric",
        },
    )
    assert grade.status_code == 201, grade.text
    history = client.get(
        f"{grade_url}/history",
        headers=instructor_headers,
    )
    assert len(history.json()["grades"]) == 1

    requested = client.post(
        f"/api/v1/academy/reviews/attempts/{ids['attempt']}/request",
        headers=instructor_headers,
        json={"reason": "Quality check"},
    )
    assert requested.status_code == 201
    reviewer_headers = principal_headers("reviewer-api", "reviewer")
    approved = client.post(
        f"/api/v1/academy/reviews/attempts/{ids['attempt']}/approve",
        headers=reviewer_headers,
        json={"reason": "Verified against rubric"},
    )
    assert approved.status_code == 200

    assert client.get(
        "/api/v1/academy/admin/learners",
        headers=reviewer_headers,
    ).status_code == 403
    admin_headers = principal_headers("admin-api", "admin")
    admin_lookup = client.get(
        "/api/v1/academy/admin/learners",
        headers=admin_headers,
    )
    assert admin_lookup.status_code == 200
    assert admin_lookup.json()["total"] == 2
    assert client.get(
        "/api/v1/academy/admin/audit-events",
        headers=admin_headers,
    ).status_code == 200


def test_academy_schema_and_missing_entity_errors(academy_client) -> None:
    client, sessions = academy_client
    seed_academy(sessions)
    headers = principal_headers("learner-api", "learner")
    assert client.get(
        "/api/v1/academy/catalog/courses/9999",
        headers=headers,
    ).status_code == 404
    assert client.get(
        "/api/v1/academy/catalog/schools",
        params={"limit": 101},
        headers=headers,
    ).status_code == 422
    assert client.patch(
        "/api/v1/academy/progress/lessons/1",
        headers=headers,
        json={},
    ).status_code == 422
