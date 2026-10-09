import uuid

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import OwnedResource


class Incident(OwnedResource):
    __tablename__ = "incidents"

    patient_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("patients.id"), nullable=False, index=True)
    incident_type: Mapped[str] = mapped_column(String(100), nullable=False)
    incident_type_display: Mapped[str | None] = mapped_column(String(256))
    severity: Mapped[str] = mapped_column(String(50), default="mild")
    status: Mapped[str] = mapped_column(String(50), default="active")
    occurred_at: Mapped[str] = mapped_column(String(50), nullable=False)
    duration_minutes: Mapped[int | None] = mapped_column(Integer)
    resolved_at: Mapped[str | None] = mapped_column(String(50))

    # Environmental context
    location: Mapped[str | None] = mapped_column(String(512))
    geo_location: Mapped[str | None] = mapped_column(String(256))
    weather_condition: Mapped[str | None] = mapped_column(String(100))
    temperature: Mapped[float | None] = mapped_column(Float)
    humidity: Mapped[float | None] = mapped_column(Float)
    pollen_level: Mapped[str | None] = mapped_column(String(50))
    air_quality_index: Mapped[int | None] = mapped_column(Integer)

    # Activity context
    activity_at_time: Mapped[str | None] = mapped_column(String(256))
    hours_since_last_meal: Mapped[float | None] = mapped_column(Float)
    sleep_hours_previous_night: Mapped[float | None] = mapped_column(Float)

    # Clinical details
    suspected_trigger: Mapped[str | None] = mapped_column(Text)
    symptoms: Mapped[str | None] = mapped_column(Text)
    actions_taken: Mapped[str | None] = mapped_column(Text)
    outcome: Mapped[str | None] = mapped_column(Text)
    note: Mapped[str | None] = mapped_column(Text)

    # No correlation fields here on purpose: software-inferred seizure/medication
    # correlation is ruled out by docs/regulatory-positioning.md (#119) — do not
    # re-add without a formal MDR assessment.

    # Provider
    reported_to_provider: Mapped[bool] = mapped_column(Boolean, default=False)
    reported_to_provider_at: Mapped[str | None] = mapped_column(String(50))

    patient: Mapped["Patient"] = relationship("Patient", back_populates="incidents")  # noqa: F821
