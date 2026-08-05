from collections.abc import Generator

from fastapi import Request
from sqlalchemy.orm import Session

from ..database import SessionLocal
from ..services.authorization import Principal
from ..services.exceptions import AuthenticationRequiredError


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_current_principal(request: Request) -> Principal:
    """Build identity claims supplied by a replaceable trusted auth boundary."""

    external_id = (
        request.headers.get("X-Nexora-Principal-Id")
        or request.headers.get("X-Principal-Id")
    )
    role = (
        request.headers.get("X-Nexora-Principal-Role")
        or request.headers.get("X-Principal-Role")
    )
    if external_id is None or role is None:
        raise AuthenticationRequiredError(
            "Academy authentication headers are required"
        )
    raw_course_ids = request.headers.get("X-Nexora-Course-Ids")
    if raw_course_ids is None:
        raw_course_ids = request.headers.get("X-Principal-Course-Ids")
    course_ids: frozenset[int] | None = None
    if raw_course_ids is not None:
        try:
            course_ids = frozenset(
                int(value.strip())
                for value in raw_course_ids.split(",")
                if value.strip()
            )
        except ValueError as exc:
            raise AuthenticationRequiredError(
                "Academy course scope header is invalid"
            ) from exc
    return Principal(
        external_id=external_id,
        role=role,
        course_ids=course_ids,
    )
