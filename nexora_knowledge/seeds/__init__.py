"""Optional development-only seed data."""

from typing import Any

from sqlalchemy.orm import Session

from .rich_knowledge_examples import seed_rich_knowledge_examples


def seed_academy(db: Session) -> dict[str, Any]:
    """Load the Academy seed lazily so its module remains directly runnable."""
    from .academy_seed import seed_academy as run_seed

    return run_seed(db)


def seed_learning(db: Session) -> dict[str, Any]:
    """Load the learner-engine seed lazily for direct module execution."""
    from .learning_seed import seed_learning as run_seed

    return run_seed(db)


__all__ = [
    "seed_academy",
    "seed_learning",
    "seed_rich_knowledge_examples",
]
