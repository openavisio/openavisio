import uuid

from sqlalchemy import Boolean, Float, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import OwnedResource


class DiaryEntry(OwnedResource):
    __tablename__ = "diary_entries"

    patient_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("patients.id"), nullable=False, index=True)
    subject: Mapped[str | None] = mapped_column(String(512))
    entry_date: Mapped[str] = mapped_column(String(20), nullable=False)
    entry_time: Mapped[str | None] = mapped_column(String(10))
    mood: Mapped[int | None] = mapped_column(Integer)
    pain_level: Mapped[int | None] = mapped_column(Integer)
    mobility: Mapped[int | None] = mapped_column(Integer)
    sleep_hours: Mapped[float | None] = mapped_column(Float)
    sleep_quality: Mapped[int | None] = mapped_column(Integer)
    nutrition_notes: Mapped[str | None] = mapped_column(Text)
    bowel_movement: Mapped[bool | None] = mapped_column(Boolean)
    medication_compliance: Mapped[bool | None] = mapped_column(Boolean)
    general_notes: Mapped[str | None] = mapped_column(Text)
    custom_fields: Mapped[dict | None] = mapped_column(JSONB)

    patient: Mapped["Patient"] = relationship("Patient", back_populates="diary_entries")  # noqa: F821
    chunks: Mapped[list["DocumentChunk"]] = relationship("DocumentChunk", back_populates="diary_entry", lazy="select")  # noqa: F821


class DiaryTemplate(OwnedResource):
    __tablename__ = "diary_templates"

    patient_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("patients.id"), nullable=True)
    name: Mapped[str] = mapped_column(String(256), nullable=False)
    fields: Mapped[list] = mapped_column(JSONB, default=list)
    is_default: Mapped[bool] = mapped_column(Boolean, default=False)
