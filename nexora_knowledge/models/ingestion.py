from __future__ import annotations

from datetime import datetime
from uuid import uuid4

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    event,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import TypeDecorator

from ..database import Base
from .common import CreatedAtMixin, TimestampMixin, utc_now
from .enums import AttemptStatus, JobStatus


def _new_uuid() -> str:
    return str(uuid4())


class ActiveReservationFlag(TypeDecorator[bool]):
    """Persist inactive as NULL for a portable one-active-row constraint."""

    impl = Boolean
    cache_ok = True

    def process_bind_param(self, value: bool | None, dialect) -> bool | None:
        del dialect
        return True if value else None

    def process_result_value(self, value: bool | None, dialect) -> bool:
        del dialect
        return bool(value)


class IngestionJob(TimestampMixin, Base):
    __tablename__ = "ingestion_jobs"
    __table_args__ = (
        CheckConstraint(
            "priority >= 0",
            name="ck_ingestion_jobs_priority",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    uuid: Mapped[str] = mapped_column(
        String(36),
        nullable=False,
        unique=True,
        index=True,
        default=_new_uuid,
    )
    document_id: Mapped[int] = mapped_column(
        ForeignKey("documents.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    status: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        index=True,
        default=JobStatus.NEW.value,
    )
    priority: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        index=True,
        default=100,
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True)
    )
    last_error: Mapped[str | None] = mapped_column(Text)

    document: Mapped["Document"] = relationship(
        back_populates="ingestion_jobs"
    )
    attempts: Mapped[list["IngestionAttempt"]] = relationship(
        back_populates="job",
        cascade="all, delete-orphan",
        passive_deletes=True,
        order_by="IngestionAttempt.attempt_number",
    )
    audit_events: Mapped[list["IngestionAuditEvent"]] = relationship(
        back_populates="job",
        cascade="all, delete-orphan",
        passive_deletes=True,
        order_by="IngestionAuditEvent.id",
    )
    reservations: Mapped[list["JobReservation"]] = relationship(
        back_populates="job",
        cascade="all, delete-orphan",
        passive_deletes=True,
        order_by="JobReservation.id",
    )
    parse_results: Mapped[list["ParseResult"]] = relationship(
        "ParseResult",
        back_populates="ingestion_job",
        order_by="ParseResult.id",
    )

    @property
    def current_reservation(self) -> JobReservation | None:
        return next(
            (
                reservation
                for reservation in reversed(self.reservations)
                if reservation.active_slot
                and reservation.released_at is None
            ),
            None,
        )

    @property
    def is_active(self) -> bool:
        return self.status not in {
            JobStatus.SUCCEEDED.value,
            JobStatus.CANCELLED.value,
        }


class IngestionAttempt(Base):
    __tablename__ = "ingestion_attempts"
    __table_args__ = (
        CheckConstraint(
            "attempt_number > 0",
            name="ck_ingestion_attempts_number",
        ),
        CheckConstraint(
            "duration_ms IS NULL OR duration_ms >= 0",
            name="ck_ingestion_attempts_duration",
        ),
        UniqueConstraint(
            "job_id",
            "attempt_number",
            name="uq_ingestion_attempt_number",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    job_id: Mapped[int] = mapped_column(
        ForeignKey("ingestion_jobs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    attempt_number: Mapped[int] = mapped_column(Integer, nullable=False)
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=utc_now,
    )
    finished_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True)
    )
    status: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        index=True,
        default=AttemptStatus.RUNNING.value,
    )
    error_message: Mapped[str | None] = mapped_column(Text)
    duration_ms: Mapped[int | None] = mapped_column(Integer)

    job: Mapped[IngestionJob] = relationship(back_populates="attempts")


class IngestionAuditEvent(CreatedAtMixin, Base):
    __tablename__ = "ingestion_audit_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    job_id: Mapped[int] = mapped_column(
        ForeignKey("ingestion_jobs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    event_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        index=True,
    )
    previous_status: Mapped[str | None] = mapped_column(String(50))
    new_status: Mapped[str] = mapped_column(String(50), nullable=False)
    reason: Mapped[str | None] = mapped_column(Text)

    job: Mapped[IngestionJob] = relationship(back_populates="audit_events")


@event.listens_for(IngestionAuditEvent, "before_update")
@event.listens_for(IngestionAuditEvent, "before_delete")
def _protect_audit_event(mapper, connection, target) -> None:
    del mapper, connection, target
    raise ValueError("Ingestion audit events are immutable")


class ProcessingNode(Base):
    __tablename__ = "processing_nodes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    node_name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        unique=True,
        index=True,
    )
    node_version: Mapped[str] = mapped_column(String(100), nullable=False)
    hostname: Mapped[str] = mapped_column(String(255), nullable=False)
    last_heartbeat: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        index=True,
        default=utc_now,
    )
    active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        index=True,
        default=True,
    )

    reservations: Mapped[list["JobReservation"]] = relationship(
        back_populates="node",
        order_by="JobReservation.id",
    )


class JobReservation(Base):
    __tablename__ = "job_reservations"
    __table_args__ = (
        CheckConstraint(
            "expires_at > reserved_at",
            name="ck_job_reservations_expiry",
        ),
        CheckConstraint(
            "(released_at IS NULL AND active_slot = 1) OR "
            "(released_at IS NOT NULL AND active_slot IS NULL)",
            name="ck_job_reservations_active",
        ),
        UniqueConstraint(
            "job_id",
            "active_slot",
            name="uq_job_active_reservation",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    job_id: Mapped[int] = mapped_column(
        ForeignKey("ingestion_jobs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    node_id: Mapped[int] = mapped_column(
        ForeignKey("processing_nodes.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    reserved_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=utc_now,
    )
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        index=True,
    )
    released_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True)
    )
    active_slot: Mapped[bool] = mapped_column(
        ActiveReservationFlag(),
        nullable=True,
        default=True,
    )

    job: Mapped[IngestionJob] = relationship(back_populates="reservations")
    node: Mapped[ProcessingNode] = relationship(back_populates="reservations")


__all__ = [
    "ActiveReservationFlag",
    "IngestionAttempt",
    "IngestionAuditEvent",
    "IngestionJob",
    "JobReservation",
    "ProcessingNode",
]
