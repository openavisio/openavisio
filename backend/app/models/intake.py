import uuid
from datetime import datetime

from sqlalchemy import BigInteger, DateTime, ForeignKey, LargeBinary, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import OwnedResource


class IntakeForm(OwnedResource):
    """ADR 047. The uploaded original is kept as the record of what was asked, but it
    is not a Document: no extraction, no chunks, never searched."""

    __tablename__ = "intake_forms"

    patient_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("patients.id"), nullable=False, index=True)
    title: Mapped[str | None] = mapped_column(String(256))  # who handed it out
    file_name: Mapped[str | None] = mapped_column(String(512))
    content_type: Mapped[str | None] = mapped_column(String(100))
    size: Mapped[int | None] = mapped_column(BigInteger)
    storage_path: Mapped[str] = mapped_column(String(1024), nullable=False)
    encrypted_dek: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="reading")  # reading | draft | released | failed
    processing_error: Mapped[str | None] = mapped_column(Text)
    # the answer sheet, JSON encrypted under the patient KEK: it can quote Document passages (ADR-031)
    sheet: Mapped[str | None] = mapped_column(Text)
    released_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class HistoryFact(OwnedResource):
    """ADR 047: one piece of history with no other home in the record."""

    __tablename__ = "history_facts"

    patient_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("patients.id"), nullable=False, index=True)
    question: Mapped[str] = mapped_column(Text, nullable=False)  # as the form asked it
    answer: Mapped[str] = mapped_column(Text, nullable=False)
    aging: Mapped[str] = mapped_column(String(20), nullable=False)  # lasting | changeable | visit_only
    confirmed_on: Mapped[str] = mapped_column(String(10), nullable=False)  # ISO date, matches the string-date convention
    source: Mapped[str] = mapped_column(String(20), default="caregiver")  # caregiver | document
    document_reference_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("document_references.id"))
    # a visit-only fact stays with the form it answered and goes with it
    intake_form_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("intake_forms.id", ondelete="SET NULL"))
