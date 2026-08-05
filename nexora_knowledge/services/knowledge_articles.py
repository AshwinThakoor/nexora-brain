from __future__ import annotations

import re
import unicodedata
from collections.abc import Mapping
from typing import Any, TypeVar

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from ..models import Concept, ConceptAlias, FAQ, KnowledgeArticle, KnowledgeSection
from ..models.enums import (
    DifficultyLevel,
    KnowledgeLifecycleStatus,
    KnowledgeSectionType,
    ReviewStatus,
)
from .exceptions import (
    ResourceConflictError,
    ResourceNotFoundError,
    ResourceValidationError,
)


ModelT = TypeVar("ModelT")


def normalize_alias(value: str) -> str:
    normalized = unicodedata.normalize("NFKC", value)
    return " ".join(normalized.casefold().split())


def normalize_slug(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value)
    ascii_value = normalized.encode("ascii", "ignore").decode("ascii")
    slug = re.sub(r"[^a-z0-9]+", "-", ascii_value.casefold()).strip("-")
    if not slug:
        raise ResourceValidationError("A non-empty slug is required")
    return slug


def _validate_concept(db: Session, concept_id: int | None) -> None:
    if concept_id is not None and db.get(Concept, concept_id) is None:
        raise ResourceNotFoundError("Concept", concept_id)


def _validate_article(db: Session, article_id: int) -> KnowledgeArticle:
    article = db.get(KnowledgeArticle, article_id)
    if article is None:
        raise ResourceNotFoundError("KnowledgeArticle", article_id)
    return article


def _enum_value(value: Any) -> str:
    return getattr(value, "value", value)


def _validate_enum(field: str, value: Any, enum_type: type) -> None:
    if value is None:
        return
    allowed = {member.value for member in enum_type}
    if _enum_value(value) not in allowed:
        raise ResourceValidationError(
            f"{field} must be one of: {', '.join(sorted(allowed))}"
        )


def _validate_article_values(values: Mapping[str, Any]) -> None:
    score = values.get("confidence_score")
    if score is not None and not 0.0 <= score <= 1.0:
        raise ResourceValidationError(
            "confidence_score must be between 0.0 and 1.0"
        )
    version = values.get("version")
    if version is not None and version < 1:
        raise ResourceValidationError("version must be at least 1")
    _validate_enum(
        "difficulty_level",
        values.get("difficulty_level"),
        DifficultyLevel,
    )
    _validate_enum(
        "lifecycle_status",
        values.get("lifecycle_status"),
        KnowledgeLifecycleStatus,
    )
    _validate_enum("review_status", values.get("review_status"), ReviewStatus)


def _commit(
    db: Session,
    *,
    conflict_message: str,
    commit: bool,
) -> None:
    try:
        if commit:
            db.commit()
        else:
            db.flush()
    except IntegrityError as exc:
        db.rollback()
        raise ResourceConflictError(conflict_message) from exc


def get_knowledge_article(db: Session, article_id: int) -> KnowledgeArticle:
    article = db.scalar(
        select(KnowledgeArticle)
        .where(KnowledgeArticle.id == article_id)
        .options(
            selectinload(KnowledgeArticle.sections),
            selectinload(KnowledgeArticle.faqs),
        )
    )
    if article is None:
        raise ResourceNotFoundError("KnowledgeArticle", article_id)
    return article


def create_knowledge_article(
    db: Session,
    values: Mapping[str, Any],
    *,
    commit: bool = True,
) -> KnowledgeArticle:
    data = dict(values)
    sections = list(data.pop("sections", []))
    faqs = list(data.pop("faqs", []))
    _validate_concept(db, data.get("concept_id"))
    _validate_article_values(data)
    data["slug"] = normalize_slug(data.get("slug") or data["title"])
    if db.scalar(
        select(KnowledgeArticle.id).where(
            KnowledgeArticle.slug == data["slug"]
        )
    ) is not None:
        raise ResourceConflictError("KnowledgeArticle slug already exists")

    article = KnowledgeArticle(**data)
    section_positions: set[int] = set()
    for raw_section in sorted(
        sections,
        key=lambda item: item["position"],
    ):
        section_data = dict(raw_section)
        section_data.pop("article_id", None)
        position = section_data["position"]
        if position in section_positions:
            raise ResourceConflictError(
                "KnowledgeArticle section positions must be unique"
            )
        section_positions.add(position)
        _validate_enum(
            "section_type",
            section_data.get("section_type"),
            KnowledgeSectionType,
        )
        article.sections.append(KnowledgeSection(**section_data))

    faq_positions: set[int] = set()
    for raw_faq in sorted(
        faqs,
        key=lambda item: item["position"],
    ):
        faq_data = dict(raw_faq)
        faq_data.pop("article_id", None)
        position = faq_data["position"]
        if position in faq_positions:
            raise ResourceConflictError(
                "KnowledgeArticle FAQ positions must be unique"
            )
        faq_positions.add(position)
        _validate_enum(
            "difficulty_level",
            faq_data.get("difficulty_level"),
            DifficultyLevel,
        )
        article.faqs.append(FAQ(**faq_data))

    db.add(article)
    _commit(
        db,
        conflict_message="KnowledgeArticle could not be created",
        commit=commit,
    )
    return get_knowledge_article(db, article.id)


def update_knowledge_article(
    db: Session,
    article_id: int,
    values: Mapping[str, Any],
    *,
    commit: bool = True,
) -> KnowledgeArticle:
    article = get_knowledge_article(db, article_id)
    data = dict(values)
    if not data:
        return article
    if "concept_id" in data:
        _validate_concept(db, data["concept_id"])
    _validate_article_values(data)
    required = {
        "title",
        "slug",
        "difficulty_level",
        "language",
        "lifecycle_status",
        "review_status",
        "version",
    }
    if any(field in data and data[field] is None for field in required):
        raise ResourceValidationError(
            "Required KnowledgeArticle fields cannot be null"
        )
    if "slug" in data:
        data["slug"] = normalize_slug(data["slug"])
        existing = db.scalar(
            select(KnowledgeArticle.id).where(
                KnowledgeArticle.slug == data["slug"],
                KnowledgeArticle.id != article_id,
            )
        )
        if existing is not None:
            raise ResourceConflictError("KnowledgeArticle slug already exists")
    for field, value in data.items():
        setattr(article, field, value)
    _commit(
        db,
        conflict_message="KnowledgeArticle could not be updated",
        commit=commit,
    )
    return get_knowledge_article(db, article_id)


def delete_knowledge_article(
    db: Session,
    article_id: int,
    *,
    commit: bool = True,
) -> None:
    article = get_knowledge_article(db, article_id)
    db.delete(article)
    _commit(
        db,
        conflict_message="KnowledgeArticle could not be deleted",
        commit=commit,
    )


def _get_child(db: Session, model: type[ModelT], item_id: int) -> ModelT:
    item = db.get(model, item_id)
    if item is None:
        raise ResourceNotFoundError(model.__name__, item_id)
    return item


def create_knowledge_section(
    db: Session,
    values: Mapping[str, Any],
    *,
    commit: bool = True,
) -> KnowledgeSection:
    data = dict(values)
    _validate_article(db, data["article_id"])
    _validate_enum("section_type", data.get("section_type"), KnowledgeSectionType)
    if data["position"] < 0:
        raise ResourceValidationError("position must be non-negative")
    section = KnowledgeSection(**data)
    db.add(section)
    _commit(
        db,
        conflict_message="KnowledgeSection position already exists",
        commit=commit,
    )
    return section


def get_knowledge_section(db: Session, section_id: int) -> KnowledgeSection:
    return _get_child(db, KnowledgeSection, section_id)


def update_knowledge_section(
    db: Session,
    section_id: int,
    values: Mapping[str, Any],
    *,
    commit: bool = True,
) -> KnowledgeSection:
    section = get_knowledge_section(db, section_id)
    data = dict(values)
    if "article_id" in data:
        _validate_article(db, data["article_id"])
    _validate_enum("section_type", data.get("section_type"), KnowledgeSectionType)
    for field, value in data.items():
        setattr(section, field, value)
    _commit(
        db,
        conflict_message="KnowledgeSection could not be updated",
        commit=commit,
    )
    return section


def delete_knowledge_section(
    db: Session,
    section_id: int,
    *,
    commit: bool = True,
) -> None:
    db.delete(get_knowledge_section(db, section_id))
    _commit(
        db,
        conflict_message="KnowledgeSection could not be deleted",
        commit=commit,
    )


def create_concept_alias(
    db: Session,
    values: Mapping[str, Any],
    *,
    commit: bool = True,
) -> ConceptAlias:
    data = dict(values)
    _validate_concept(db, data["concept_id"])
    data["alias"] = " ".join(data["alias"].split())
    data["normalized_alias"] = normalize_alias(data["alias"])
    if not data["normalized_alias"]:
        raise ResourceValidationError("alias must contain usable text")
    alias = ConceptAlias(**data)
    db.add(alias)
    _commit(
        db,
        conflict_message="ConceptAlias already exists",
        commit=commit,
    )
    return alias


def get_concept_alias(db: Session, alias_id: int) -> ConceptAlias:
    return _get_child(db, ConceptAlias, alias_id)


def update_concept_alias(
    db: Session,
    alias_id: int,
    values: Mapping[str, Any],
    *,
    commit: bool = True,
) -> ConceptAlias:
    alias = get_concept_alias(db, alias_id)
    data = dict(values)
    if "concept_id" in data:
        _validate_concept(db, data["concept_id"])
    if "alias" in data:
        data["alias"] = " ".join(data["alias"].split())
        data["normalized_alias"] = normalize_alias(data["alias"])
    for field, value in data.items():
        setattr(alias, field, value)
    _commit(
        db,
        conflict_message="ConceptAlias already exists",
        commit=commit,
    )
    return alias


def delete_concept_alias(
    db: Session,
    alias_id: int,
    *,
    commit: bool = True,
) -> None:
    db.delete(get_concept_alias(db, alias_id))
    _commit(
        db,
        conflict_message="ConceptAlias could not be deleted",
        commit=commit,
    )


def create_faq(
    db: Session,
    values: Mapping[str, Any],
    *,
    commit: bool = True,
) -> FAQ:
    data = dict(values)
    _validate_article(db, data["article_id"])
    _validate_enum(
        "difficulty_level",
        data.get("difficulty_level"),
        DifficultyLevel,
    )
    if data["position"] < 0:
        raise ResourceValidationError("position must be non-negative")
    faq = FAQ(**data)
    db.add(faq)
    _commit(
        db,
        conflict_message="FAQ position already exists",
        commit=commit,
    )
    return faq


def get_faq(db: Session, faq_id: int) -> FAQ:
    return _get_child(db, FAQ, faq_id)


def update_faq(
    db: Session,
    faq_id: int,
    values: Mapping[str, Any],
    *,
    commit: bool = True,
) -> FAQ:
    faq = get_faq(db, faq_id)
    data = dict(values)
    if "article_id" in data:
        _validate_article(db, data["article_id"])
    _validate_enum(
        "difficulty_level",
        data.get("difficulty_level"),
        DifficultyLevel,
    )
    for field, value in data.items():
        setattr(faq, field, value)
    _commit(
        db,
        conflict_message="FAQ could not be updated",
        commit=commit,
    )
    return faq


def delete_faq(
    db: Session,
    faq_id: int,
    *,
    commit: bool = True,
) -> None:
    db.delete(get_faq(db, faq_id))
    _commit(
        db,
        conflict_message="FAQ could not be deleted",
        commit=commit,
    )


create_article = create_knowledge_article
get_article = get_knowledge_article
update_article = update_knowledge_article
delete_article = delete_knowledge_article
