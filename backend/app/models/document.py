import uuid
from datetime import date as DateType

from sqlalchemy import BigInteger, Date, Float, ForeignKey, LargeBinary, SmallInteger, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import OwnedResource
from app.models.correspondent import Correspondent  # noqa: F401


class DocumentReference(OwnedResource):
    __tablename__ = "document_references"

    patient_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("patients.id"), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(50), default="current")
    type: Mapped[str | None] = mapped_column(String(100))
    description: Mapped[str | None] = mapped_column(Text)
    issued_date: Mapped[DateType | None] = mapped_column(Date)

    # File storage
    file_name: Mapped[str | None] = mapped_column(String(512))
    content_type: Mapped[str | None] = mapped_column(String(100))
    size: Mapped[int | None] = mapped_column(BigInteger)
    storage_path: Mapped[str | None] = mapped_column(String(1024))
    hash: Mapped[str | None] = mapped_column(String(64))
    # Every stored file is envelope-encrypted (ADR-022): the blob is ciphertext,
    # the wrapped DEK lives here, kek_version records which KEK generation wrapped it.
    encrypted_dek: Mapped[bytes | None] = mapped_column(LargeBinary, nullable=True)
    kek_version: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=1, server_default="1")

    # Processing pipeline
    processing_status: Mapped[str] = mapped_column(String(50), default="pending")
    pipeline_stage: Mapped[str | None] = mapped_column(String(50))
    processing_error: Mapped[str | None] = mapped_column(Text)
    hangfire_job_id: Mapped[str | None] = mapped_column(String(100))

    # OCR / AI results
    extracted_text: Mapped[str | None] = mapped_column(Text)
    extraction_confidence: Mapped[float | None] = mapped_column(Float)
    ocr_confidence: Mapped[float | None] = mapped_column(Float)
    document_classification: Mapped[str | None] = mapped_column(String(100))
    detected_provider: Mapped[str | None] = mapped_column(String(256))
    extraction_json: Mapped[dict | None] = mapped_column(JSONB)

    # Correspondent (issuer)
    correspondent_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("correspondents.id"), nullable=True)

    # Verification
    verification_status: Mapped[str] = mapped_column(String(50), default="pending")

    patient: Mapped["Patient"] = relationship("Patient", back_populates="documents")  # noqa: F821
    correspondent: Mapped["Correspondent | None"] = relationship("Correspondent", lazy="selectin")
    chunks: Mapped[list["DocumentChunk"]] = relationship("DocumentChunk", back_populates="document", lazy="select")  # noqa: F821
