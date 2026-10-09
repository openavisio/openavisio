import uuid

from sqlalchemy import ForeignKey, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import BaseModel


class PatientFavorite(BaseModel):
    __tablename__ = "patient_favorites"
    __table_args__ = (UniqueConstraint("user_id", "patient_id", name="uq_patient_favorite"),)

    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True)
    patient_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("patients.id"), nullable=False, index=True)


class DocumentFavorite(BaseModel):
    """Per-user pin for the documents a caregiver reaches for at every appointment."""
    __tablename__ = "document_favorites"
    __table_args__ = (UniqueConstraint("user_id", "document_id", name="uq_document_favorite"),)

    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True)
    document_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("document_references.id"), nullable=False, index=True)
