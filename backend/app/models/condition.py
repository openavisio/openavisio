import uuid

from sqlalchemy import ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import BaseModel, OwnedResource


class Condition(OwnedResource):
    __tablename__ = "conditions"

    patient_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("patients.id"), nullable=False, index=True)
    clinical_status: Mapped[str] = mapped_column(String(50), default="active")
    verification_status: Mapped[str | None] = mapped_column(String(50))
    category: Mapped[str | None] = mapped_column(String(100))
    severity: Mapped[str | None] = mapped_column(String(50))
    code: Mapped[str | None] = mapped_column(String(100))
    code_display: Mapped[str] = mapped_column(String(256), nullable=False)
    recorded_date: Mapped[str | None] = mapped_column(String(50))
    onset_date_time: Mapped[str | None] = mapped_column(String(50))
    abatement_date_time: Mapped[str | None] = mapped_column(String(50))
    note: Mapped[str | None] = mapped_column(Text)
    document_reference_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("document_references.id"), nullable=True)
    # set on soft-deleted rows that were merged away — the audit trail of a merge (#159)
    merged_into_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("conditions.id"), nullable=True)

    patient: Mapped["Patient"] = relationship("Patient", back_populates="conditions")  # noqa: F821
    sources: Mapped[list["ConditionSource"]] = relationship(
        "ConditionSource", back_populates="condition", cascade="all, delete-orphan"
    )


class ConditionSource(BaseModel):
    """Every document that names a condition (#133).

    document_reference_id on Condition is the origin; this table is the full
    citation list, so the eighth letter naming a diagnosis is attached instead
    of discarded — a history, not a pile of paper.
    """

    __tablename__ = "condition_sources"
    __table_args__ = (UniqueConstraint("condition_id", "document_reference_id"),)

    condition_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("conditions.id"), nullable=False, index=True
    )
    document_reference_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("document_references.id"), nullable=False
    )

    condition: Mapped["Condition"] = relationship("Condition", back_populates="sources")
    document: Mapped["DocumentReference"] = relationship("DocumentReference")  # noqa: F821

    # read by ConditionSourceDto via from_attributes; needs `document` eager-loaded
    @property
    def issued_date(self) -> str | None:
        return self.document.issued_date.isoformat() if self.document and self.document.issued_date else None

    @property
    def label(self) -> str | None:
        d = self.document
        return (d.detected_provider or d.file_name) if d else None

    @property
    def doc_type(self) -> str | None:
        return self.document.type if self.document else None
