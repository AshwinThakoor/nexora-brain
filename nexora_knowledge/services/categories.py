from collections.abc import Mapping
from typing import Any

from sqlalchemy import func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..models import Category
from .exceptions import (
    ResourceConflictError,
    ResourceNotFoundError,
    ResourceValidationError,
)


def get_category(db: Session, category_id: int) -> Category:
    category = db.get(Category, category_id)
    if category is None:
        raise ResourceNotFoundError("Category", category_id)
    return category


def _validate_parent(
    db: Session,
    parent_id: int | None,
    category_id: int | None = None,
) -> None:
    if parent_id is None:
        return
    if category_id is not None and parent_id == category_id:
        raise ResourceValidationError("A category cannot be its own parent")

    parent = db.get(Category, parent_id)
    if parent is None:
        raise ResourceNotFoundError("Parent category", parent_id)

    visited: set[int] = set()
    current = parent
    while current is not None:
        if current.id in visited:
            raise ResourceValidationError("Category hierarchy contains a cycle")
        if category_id is not None and current.id == category_id:
            raise ResourceValidationError("Category parent would create a cycle")
        visited.add(current.id)
        current = current.parent


def _ensure_unique(
    db: Session,
    name: str,
    slug: str,
    exclude_id: int | None = None,
) -> None:
    statement = select(Category).where(
        or_(Category.name == name, Category.slug == slug)
    )
    if exclude_id is not None:
        statement = statement.where(Category.id != exclude_id)
    if db.scalar(statement) is not None:
        raise ResourceConflictError("Category name or slug already exists")


def create_category(db: Session, values: Mapping[str, Any]) -> Category:
    data = dict(values)
    _validate_parent(db, data.get("parent_id"))
    _ensure_unique(db, data["name"], data["slug"])
    category = Category(**data)
    db.add(category)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise ResourceConflictError(
            "Category name or slug already exists"
        ) from exc
    db.refresh(category)
    return category


def list_categories(
    db: Session,
    *,
    skip: int = 0,
    limit: int = 50,
    parent_id: int | None = None,
    name: str | None = None,
) -> tuple[list[Category], int]:
    filters = []
    if parent_id is not None:
        filters.append(Category.parent_id == parent_id)
    if name:
        filters.append(Category.name.ilike(f"%{name}%"))

    total = db.scalar(
        select(func.count()).select_from(Category).where(*filters)
    ) or 0
    items = list(
        db.scalars(
            select(Category)
            .where(*filters)
            .order_by(Category.id)
            .offset(skip)
            .limit(limit)
        )
    )
    return items, total


def update_category(
    db: Session,
    category_id: int,
    values: Mapping[str, Any],
) -> Category:
    category = get_category(db, category_id)
    data = dict(values)
    if not data:
        return category

    parent_id = data.get("parent_id", category.parent_id)
    _validate_parent(db, parent_id, category_id)
    name = data.get("name", category.name)
    slug = data.get("slug", category.slug)
    if name is None or slug is None:
        raise ResourceValidationError("Category name and slug cannot be null")
    _ensure_unique(db, name, slug, exclude_id=category_id)

    for field, value in data.items():
        setattr(category, field, value)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise ResourceConflictError(
            "Category name or slug already exists"
        ) from exc
    db.refresh(category)
    return category


def delete_category(db: Session, category_id: int) -> None:
    category = get_category(db, category_id)
    db.delete(category)
    db.commit()


create = create_category
get = get_category
list_all = list_categories
update = update_category
delete = delete_category
