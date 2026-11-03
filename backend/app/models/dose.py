import uuid

from sqlalchemy import ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import OwnedResource


class Dose(OwnedResource):
    """ADR 060; owner is who entered it."""

    __tablename__ = "doses"

    patient_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("patients.id"), nullable=False, index=True)
    medication_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("medication_statements.id"), nullable=False, index=True)
    given_at: Mapped[str] = mapped_column(String(16), nullable=False)  # local wall time YYYY-MM-DDTHH:MM, like Incident.occurred_at
    given_by: Mapped[str | None] = mapped_column(String(256))  # free text; None = who entered it
    amount: Mapped[str | None] = mapped_column(String(256))  # None = the dose of the plan
    note: Mapped[str | None] = mapped_column(Text)
    incident_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("incidents.id"))

    owner: Mapped["User"] = relationship("User", lazy="joined")  # noqa: F821
