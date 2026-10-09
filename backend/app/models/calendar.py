import uuid
from datetime import datetime
from enum import StrEnum

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import BaseModel, OwnedResource


class EventCategory(StrEnum):
    appointment = "appointment"
    milestone = "milestone"
    deadline = "deadline"  # a last date with a consequence for missing it — ADR 041


class DevelopmentalDomain(StrEnum):
    motor = "motor"
    speech = "speech"
    cognitive = "cognitive"
    social = "social"


class CalendarFeed(BaseModel):
    """A subscribable iCal URL for one Caregiver on one Patient — ADR-037.

    Anonymous and token-only, like DocumentShareLink (ADR-021), but deliberately
    without an expiry: a family calendar that silently stops updating is a missed
    appointment, not a safety feature. Lifetime is bounded by revocation and by
    `user_id`'s PatientAccess, which the endpoint re-checks on every fetch — so
    removing a Caregiver from the care circle kills their feed with no extra step.
    """

    __tablename__ = "calendar_feeds"

    patient_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("patients.id"), nullable=False, index=True)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True)
    token_hash: Mapped[str] = mapped_column(String(64), nullable=False, unique=True, index=True)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_accessed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class CalendarEvent(OwnedResource):
    __tablename__ = "calendar_events"

    patient_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("patients.id"), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(512), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    # Milestone support (issue #11): appointment | milestone | deadline; domain only for milestones.
    category: Mapped[str] = mapped_column(String(20), nullable=False, default=EventCategory.appointment, index=True)
    developmental_domain: Mapped[str | None] = mapped_column(String(20))
    start_at: Mapped[str] = mapped_column(String(50), nullable=False)
    end_at: Mapped[str | None] = mapped_column(String(50))
    all_day: Mapped[bool] = mapped_column(Boolean, default=False)
    provider: Mapped[str | None] = mapped_column(String(256))
    location: Mapped[str | None] = mapped_column(String(512))
    purpose: Mapped[str | None] = mapped_column(Text)
    source: Mapped[str] = mapped_column(String(50), default="manual")
    status: Mapped[str] = mapped_column(String(50), default="scheduled")
    document_reference_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("document_references.id"), nullable=True)
    reminder_sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    # Deadlines get two reminders instead of one (ADR 041), so a single timestamp no
    # longer says how far along we are: 0 = none sent, 1 = first stage, 2 = done.
    reminder_stage: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")

    patient: Mapped["Patient"] = relationship("Patient", back_populates="calendar_events")  # noqa: F821
