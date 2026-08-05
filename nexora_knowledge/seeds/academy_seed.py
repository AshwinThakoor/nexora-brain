from __future__ import annotations

import json
from typing import Any

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from ..database import SessionLocal
from ..models import KnowledgeArticle, School
from ..services.curriculum import (
    create_course,
    create_curriculum_path,
    create_degree,
    create_learning_objective,
    create_lesson,
    create_lesson_prerequisite,
    create_module,
    create_school,
)
from ..services.exceptions import ResourceConflictError


ACADEMY_SCHOOL_SLUG = "financial-markets"
LESSON_DEFINITIONS = (
    {
        "title": "What is a Financial Market?",
        "slug": "what-is-a-financial-market",
        "summary": (
            "An introduction to financial markets, their purpose, and their "
            "main participants."
        ),
        "estimated_minutes": 15,
        "objective": (
            "Explain what a financial market is and identify its core "
            "functions."
        ),
    },
    {
        "title": "Supply and Demand",
        "slug": "supply-and-demand",
        "summary": (
            "How buyers, sellers, scarcity, and willingness to transact "
            "influence market prices."
        ),
        "estimated_minutes": 20,
        "objective": (
            "Describe how changes in supply and demand can affect price."
        ),
    },
    {
        "title": "Liquidity",
        "slug": "liquidity",
        "summary": (
            "A foundation for understanding market depth, transaction ease, "
            "and trading costs."
        ),
        "estimated_minutes": 20,
        "objective": (
            "Define liquidity and explain why it matters to market "
            "participants."
        ),
    },
)


def _matching_article(
    db: Session,
    *,
    title: str,
    slug: str,
) -> KnowledgeArticle | None:
    return db.scalar(
        select(KnowledgeArticle)
        .where(
            or_(
                KnowledgeArticle.slug == slug,
                KnowledgeArticle.title == title,
            )
        )
        .order_by(
            (KnowledgeArticle.slug == slug).desc(),
            KnowledgeArticle.id,
        )
    )


def seed_academy(db: Session) -> dict[str, Any]:
    """Seed the single Pack 2D Academy example as one transaction."""
    existing = db.scalar(
        select(School.id).where(School.slug == ACADEMY_SCHOOL_SLUG)
    )
    if existing is not None:
        raise ResourceConflictError("NEXORA Academy seed data already exists")

    article_matches = {
        lesson["slug"]: _matching_article(
            db,
            title=lesson["title"],
            slug=lesson["slug"],
        )
        for lesson in LESSON_DEFINITIONS
    }

    try:
        school = create_school(
            db,
            {
                "name": "Financial Markets",
                "slug": ACADEMY_SCHOOL_SLUG,
                "description": (
                    "Foundational education about financial markets and "
                    "their operation."
                ),
                "icon": "chart-line",
                "display_order": 0,
                "is_active": True,
            },
            commit=False,
        )
        degree = create_degree(
            db,
            {
                "school_id": school.id,
                "name": "Financial Markets Foundation",
                "slug": "financial-markets-foundation",
                "description": (
                    "A beginner pathway through essential market concepts."
                ),
                "level": "foundation",
                "estimated_hours": 1.0,
                "display_order": 0,
            },
            commit=False,
        )
        course = create_course(
            db,
            {
                "degree_id": degree.id,
                "name": "Market Basics",
                "slug": "market-basics",
                "description": (
                    "Core terminology and mechanisms used across financial "
                    "markets."
                ),
                "estimated_hours": 1.0,
                "display_order": 0,
            },
            commit=False,
        )
        module = create_module(
            db,
            {
                "course_id": course.id,
                "name": "Introduction",
                "slug": "introduction",
                "description": "The first principles of market activity.",
                "estimated_minutes": 55,
                "display_order": 0,
            },
            commit=False,
        )

        lessons = []
        for display_order, definition in enumerate(LESSON_DEFINITIONS):
            article = article_matches[definition["slug"]]
            lesson = create_lesson(
                db,
                {
                    "module_id": module.id,
                    "knowledge_article_id": (
                        article.id if article is not None else None
                    ),
                    "concept_id": (
                        article.concept_id if article is not None else None
                    ),
                    "title": definition["title"],
                    "slug": definition["slug"],
                    "summary": definition["summary"],
                    "estimated_minutes": definition["estimated_minutes"],
                    "difficulty_level": "beginner",
                    "status": "draft",
                    "display_order": display_order,
                },
                commit=False,
            )
            create_learning_objective(
                db,
                {
                    "lesson_id": lesson.id,
                    "objective": definition["objective"],
                    "display_order": 0,
                },
                commit=False,
            )
            lessons.append(lesson)

        create_lesson_prerequisite(
            db,
            {
                "lesson_id": lessons[1].id,
                "prerequisite_lesson_id": lessons[0].id,
            },
            commit=False,
        )
        create_lesson_prerequisite(
            db,
            {
                "lesson_id": lessons[2].id,
                "prerequisite_lesson_id": lessons[1].id,
            },
            commit=False,
        )
        path = create_curriculum_path(
            db,
            {
                "name": "Financial Markets Foundation",
                "slug": "financial-markets-foundation-path",
                "description": (
                    "The ordered introductory path through Market Basics."
                ),
                "lesson_ids": [lesson.id for lesson in lessons],
            },
            commit=False,
        )
        db.commit()
    except Exception:
        db.rollback()
        raise

    return {
        "school_id": school.id,
        "degree_id": degree.id,
        "course_id": course.id,
        "module_id": module.id,
        "lesson_ids": [lesson.id for lesson in lessons],
        "curriculum_path_id": path.id,
        "knowledge_article_links": {
            definition["slug"]: (
                article_matches[definition["slug"]].id
                if article_matches[definition["slug"]] is not None
                else None
            )
            for definition in LESSON_DEFINITIONS
        },
    }


def main() -> None:
    with SessionLocal() as db:
        result = seed_academy(db)
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
