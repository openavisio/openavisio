import uuid

from sqlalchemy import DateTime, Float, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import OwnedResource


class Observation(OwnedResource):
    __tablename__ = "observations"

    patient_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("patients.id"), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(50), default="final")
    code: Mapped[str | None] = mapped_column(String(100))
    code_display: Mapped[str | None] = mapped_column(String(256))
    category: Mapped[str | None] = mapped_column(String(100))
    panel: Mapped[str | None] = mapped_column(String(128))  # #69: report section, e.g. "Blutbild"
    effective_date_time: Mapped[str | None] = mapped_column(String(50))
    value_quantity: Mapped[float | None] = mapped_column(Float)
    value_unit: Mapped[str | None] = mapped_column(String(50))
    value_string: Mapped[str | None] = mapped_column(Text)
    reference_range: Mapped[str | None] = mapped_column(String(100))  # #69: raw printed range
    ref_low: Mapped[float | None] = mapped_column(Float)
    ref_high: Mapped[float | None] = mapped_column(Float)
    document_reference_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("document_references.id"), nullable=True)

    patient: Mapped["Patient"] = relationship("Patient", back_populates="observations")  # noqa: F821
