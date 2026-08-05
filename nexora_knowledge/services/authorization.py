from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import AcademyRole, Learner
from .exceptions import (
    AuthenticationRequiredError,
    AuthorizationDeniedError,
    ResourceNotFoundError,
)


@dataclass(frozen=True, slots=True)
class Principal:
    """Provider-neutral identity claims accepted by Academy policies."""

    external_id: str
    role: AcademyRole | str
    course_ids: frozenset[int] | None = None

    def __post_init__(self) -> None:
        external_id = self.external_id.strip()
        if not external_id:
            raise AuthenticationRequiredError(
                "Authenticated principal external ID is required"
            )
        try:
            role = (
                self.role
                if isinstance(self.role, AcademyRole)
                else AcademyRole(str(self.role).strip().lower())
            )
        except ValueError as exc:
            raise AuthenticationRequiredError(
                "Authenticated principal role is invalid"
            ) from exc
        object.__setattr__(self, "external_id", external_id)
        object.__setattr__(self, "role", role)
        if self.course_ids is not None:
            object.__setattr__(
                self,
                "course_ids",
                frozenset(int(item) for item in self.course_ids),
            )


LEARNER_ROLES = frozenset({AcademyRole.LEARNER})
GRADING_ROLES = frozenset({AcademyRole.INSTRUCTOR, AcademyRole.ADMIN})
STAFF_ROLES = frozenset(
    {AcademyRole.INSTRUCTOR, AcademyRole.REVIEWER, AcademyRole.ADMIN}
)
REVIEW_ROLES = frozenset({AcademyRole.REVIEWER, AcademyRole.ADMIN})
REVIEW_REQUEST_ROLES = frozenset(
    {AcademyRole.INSTRUCTOR, AcademyRole.REVIEWER, AcademyRole.ADMIN}
)
ADMIN_ROLES = frozenset({AcademyRole.ADMIN})
SOURCE_READ_ROLES = frozenset(
    {
        AcademyRole.LEARNER,
        AcademyRole.INSTRUCTOR,
        AcademyRole.REVIEWER,
        AcademyRole.ADMIN,
    }
)
SOURCE_WRITE_ROLES = ADMIN_ROLES
DOCUMENT_READ_ROLES = SOURCE_READ_ROLES
DOCUMENT_WRITE_ROLES = ADMIN_ROLES
INGESTION_READ_ROLES = frozenset(
    {
        AcademyRole.INSTRUCTOR,
        AcademyRole.REVIEWER,
        AcademyRole.ADMIN,
    }
)
INGESTION_WRITE_ROLES = ADMIN_ROLES
STORAGE_CONTROL_ROLES = ADMIN_ROLES
PARSER_CONTROL_ROLES = ADMIN_ROLES
PARSE_RESULT_READ_ROLES = INGESTION_READ_ROLES
PARSE_HISTORY_READ_ROLES = REVIEW_ROLES
CHUNK_CONTROL_ROLES = ADMIN_ROLES
CHUNK_METADATA_READ_ROLES = frozenset(
    {AcademyRole.INSTRUCTOR, AcademyRole.REVIEWER, AcademyRole.ADMIN}
)
CHUNK_PROVENANCE_READ_ROLES = REVIEW_ROLES


def require_roles(
    principal: Principal,
    roles: Iterable[AcademyRole],
) -> Principal:
    allowed = frozenset(roles)
    if principal.role not in allowed:
        raise AuthorizationDeniedError(
            "Principal is not authorized for this Academy operation"
        )
    return principal


def require_learner(principal: Principal) -> Principal:
    return require_roles(principal, LEARNER_ROLES)


def require_grader(principal: Principal) -> Principal:
    return require_roles(principal, GRADING_ROLES)


def require_staff(principal: Principal) -> Principal:
    return require_roles(principal, STAFF_ROLES)


def require_reviewer(principal: Principal) -> Principal:
    return require_roles(principal, REVIEW_ROLES)


def require_review_requester(principal: Principal) -> Principal:
    return require_roles(principal, REVIEW_REQUEST_ROLES)


def require_admin(principal: Principal) -> Principal:
    return require_roles(principal, ADMIN_ROLES)


def require_source_reader(principal: Principal) -> Principal:
    return require_roles(principal, SOURCE_READ_ROLES)


def require_source_admin(principal: Principal) -> Principal:
    return require_roles(principal, SOURCE_WRITE_ROLES)


def require_document_reader(principal: Principal) -> Principal:
    return require_roles(principal, DOCUMENT_READ_ROLES)


def require_document_admin(principal: Principal) -> Principal:
    return require_roles(principal, DOCUMENT_WRITE_ROLES)


def require_ingestion_reader(principal: Principal) -> Principal:
    return require_roles(principal, INGESTION_READ_ROLES)


def require_ingestion_admin(principal: Principal) -> Principal:
    return require_roles(principal, INGESTION_WRITE_ROLES)


def require_storage_admin(principal: Principal) -> Principal:
    return require_roles(principal, STORAGE_CONTROL_ROLES)


def require_parser_admin(principal: Principal) -> Principal:
    return require_roles(principal, PARSER_CONTROL_ROLES)


def require_parse_result_reader(principal: Principal) -> Principal:
    return require_roles(principal, PARSE_RESULT_READ_ROLES)


def require_parse_history_reader(principal: Principal) -> Principal:
    return require_roles(principal, PARSE_HISTORY_READ_ROLES)


def require_chunk_admin(principal: Principal) -> Principal:
    return require_roles(principal, CHUNK_CONTROL_ROLES)


def require_chunk_reader(principal: Principal) -> Principal:
    return require_roles(principal, CHUNK_METADATA_READ_ROLES)


def require_chunk_provenance_reader(principal: Principal) -> Principal:
    return require_roles(principal, CHUNK_PROVENANCE_READ_ROLES)


def resolve_learner(db: Session, principal: Principal) -> Learner:
    require_learner(principal)
    learner = db.scalar(
        select(Learner).where(
            Learner.external_user_id == principal.external_id
        )
    )
    if learner is None:
        raise ResourceNotFoundError("Learner identity", principal.external_id)
    return learner


def require_learner_ownership(
    principal: Principal,
    *,
    owner_external_id: str | None,
) -> None:
    require_learner(principal)
    if (
        owner_external_id is None
        or owner_external_id != principal.external_id
    ):
        raise AuthorizationDeniedError(
            "Learners may access only their own Academy records"
        )


def require_owned_learner_id(
    db: Session,
    principal: Principal,
    learner_id: int,
) -> Learner:
    learner = db.get(Learner, learner_id)
    if learner is None:
        raise ResourceNotFoundError("Learner", learner_id)
    require_learner_ownership(
        principal,
        owner_external_id=learner.external_user_id,
    )
    return learner


def require_course_scope(
    principal: Principal,
    course_id: int | None,
) -> None:
    """Enforce course claims when an identity provider supplies them.

    ``None`` means assignment enforcement remains with the upstream identity
    provider. A concrete set is enforced here, including an empty set.
    """

    require_staff(principal)
    if principal.role == AcademyRole.ADMIN:
        return
    if (
        principal.course_ids is not None
        and course_id not in principal.course_ids
    ):
        raise AuthorizationDeniedError(
            "Resource is outside the principal's assigned course scope"
        )


def scoped_course_ids(principal: Principal) -> frozenset[int] | None:
    """Return locally enforceable staff scope, or ``None`` if unrestricted."""

    require_staff(principal)
    if principal.role == AcademyRole.ADMIN:
        return None
    return principal.course_ids


__all__ = [
    "ADMIN_ROLES",
    "CHUNK_CONTROL_ROLES",
    "CHUNK_METADATA_READ_ROLES",
    "CHUNK_PROVENANCE_READ_ROLES",
    "DOCUMENT_READ_ROLES",
    "DOCUMENT_WRITE_ROLES",
    "GRADING_ROLES",
    "INGESTION_READ_ROLES",
    "INGESTION_WRITE_ROLES",
    "LEARNER_ROLES",
    "PARSER_CONTROL_ROLES",
    "PARSE_HISTORY_READ_ROLES",
    "PARSE_RESULT_READ_ROLES",
    "Principal",
    "REVIEW_REQUEST_ROLES",
    "REVIEW_ROLES",
    "STAFF_ROLES",
    "STORAGE_CONTROL_ROLES",
    "SOURCE_READ_ROLES",
    "SOURCE_WRITE_ROLES",
    "require_admin",
    "require_chunk_admin",
    "require_chunk_provenance_reader",
    "require_chunk_reader",
    "require_document_admin",
    "require_document_reader",
    "require_course_scope",
    "require_grader",
    "require_ingestion_admin",
    "require_ingestion_reader",
    "require_learner",
    "require_learner_ownership",
    "require_owned_learner_id",
    "require_parser_admin",
    "require_parse_history_reader",
    "require_parse_result_reader",
    "require_reviewer",
    "require_review_requester",
    "require_roles",
    "require_staff",
    "require_storage_admin",
    "require_source_admin",
    "require_source_reader",
    "resolve_learner",
    "scoped_course_ids",
]
