import uuid

from sqlalchemy import ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import OwnedResource

TYPES = ("seizure", "fall", "allergic_reaction", "other")
TYPE_LABELS = {
    "de": {"seizure": "Anfall", "fall": "Sturz", "allergic_reaction": "Allergische Reaktion", "other": "Sonstiges"},
    "en": {"seizure": "Seizure", "fall": "Fall", "allergic_reaction": "Allergic reaction", "other": "Other"},
}


class Incident(OwnedResource):
    """ADR 062: what happened, no context fields; correlation is ruled out (#119). Owner is who entered it."""

    __tablename__ = "incidents"

    patient_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("patients.id"), nullable=False, index=True)
    incident_type: Mapped[str] = mapped_column(String(100), nullable=False)  # one of TYPES
    incident_type_display: Mapped[str | None] = mapped_column(String(256))  # the family's own word, e.g. "Absence"
    occurred_at: Mapped[str] = mapped_column(String(50), nullable=False)  # local wall time YYYY-MM-DDTHH:MM
    duration_minutes: Mapped[int | None] = mapped_column(Integer)
    actions_taken: Mapped[str | None] = mapped_column(Text)
    note: Mapped[str | None] = mapped_column(Text)

    patient: Mapped["Patient"] = relationship("Patient", back_populates="incidents")  # noqa: F821
    owner: Mapped["User"] = relationship("User", lazy="joined")  # noqa: F821
