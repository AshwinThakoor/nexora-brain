from __future__ import annotations

import pytest

from nexora_knowledge.models import Concept, KnowledgeArticle
from nexora_knowledge.seeds.academy_seed import seed_academy
from nexora_knowledge.services.curriculum import (
    get_curriculum_path,
    get_school,
)
from nexora_knowledge.services.exceptions import ResourceConflictError


def test_academy_seed_builds_complete_ordered_example_and_links_articles(
    db,
) -> None:
    concept = Concept(
        title="Liquidity",
        slug="liquidity-concept",
    )
    article = KnowledgeArticle(
        concept=concept,
        title="Liquidity",
        slug="liquidity",
    )
    db.add(article)
    db.commit()

    result = seed_academy(db)

    school = get_school(db, result["school_id"])
    assert school.name == "Financial Markets"
    degree = school.degrees[0]
    assert degree.name == "Financial Markets Foundation"
    course = degree.courses[0]
    assert course.name == "Market Basics"
    module = course.modules[0]
    assert module.name == "Introduction"
    assert [lesson.title for lesson in module.lessons] == [
        "What is a Financial Market?",
        "Supply and Demand",
        "Liquidity",
    ]
    assert module.lessons[0].knowledge_article_id is None
    assert module.lessons[2].knowledge_article_id == article.id
    assert module.lessons[2].concept_id == concept.id
    assert all(len(lesson.objectives) == 1 for lesson in module.lessons)
    assert len(module.lessons[1].prerequisite_links) == 1
    assert len(module.lessons[2].prerequisite_links) == 1

    path = get_curriculum_path(db, result["curriculum_path_id"])
    assert [lesson.title for lesson in path.lessons] == [
        "What is a Financial Market?",
        "Supply and Demand",
        "Liquidity",
    ]
    assert result["knowledge_article_links"]["liquidity"] == article.id

    with pytest.raises(ResourceConflictError):
        seed_academy(db)

