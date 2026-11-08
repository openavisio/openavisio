import uuid
from datetime import datetime
from enum import StrEnum

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, String, Text, UniqueConstraint, func, text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import BaseModel


class IdentificationMode(StrEnum):
    identified = "identified"
    anonymous = "anonymous"


class DataSet(StrEnum):
    test_attempts = "test_attempts"
    ability_observations = "ability_observations"


class SharingPurposeStatus(StrEnum):
    open = "open"
    closed = "closed"


class ShareStatus(StrEnum):
    active = "active"
    revoked = "revoked"


class SharingPurpose(BaseModel):
    """A named reason for which a Coordinator collects Patient files (e.g. a study).

    Role-owned: belongs to the Organization, managed by any Coordinator/admin.
    ``created_by_user_id`` is recorded for accountability only.
    """

    __tablename__ = "sharing_purposes"

    name: Mapped[str] = mapped_column(String(256), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    identification_mode: Mapped[str] = mapped_column(String(20), default=IdentificationMode.identified)
    status: Mapped[str] = mapped_column(String(20), default=SharingPurposeStatus.open, index=True)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=True
    )
    # ADR 064: set only at creation; NULL asks for Documents
    data_set: Mapped[str | None] = mapped_column(String(30))
    data_set_since: Mapped[str | None] = mapped_column(String(10))  # YYYY-MM-DD
    data_set_domain: Mapped[str | None] = mapped_column(String(20))


class Share(BaseModel):
    """A consented link between a Sharing Purpose and one Document or a frozen Data Set snapshot (ADR 064)."""

    __tablename__ = "shares"
    __table_args__ = (
        UniqueConstraint("sharing_purpose_id", "document_id", name="uq_share_purpose_document"),
        Index("uq_share_purpose_patient_data_set", "sharing_purpose_id", "patient_id",
              unique=True, postgresql_where=text("document_id IS NULL")),
    )

    sharing_purpose_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("sharing_purposes.id"), nullable=False, index=True
    )
    document_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("document_references.id"), nullable=True, index=True
    )
    rows: Mapped[list | None] = mapped_column(JSONB)  # Data Set snapshot, frozen at consent
    patient_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("patients.id"), nullable=False, index=True
    )
    status: Mapped[str] = mapped_column(String(20), default=ShareStatus.active, index=True)
    consented_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=True
    )
    consented_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    consented_legal: Mapped[bool] = mapped_column(Boolean, default=False)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class ShareDecline(BaseModel):
    """Records that a Patient declined a Sharing Purpose, so the nudge stops."""

    __tablename__ = "share_declines"
    __table_args__ = (
        UniqueConstraint("sharing_purpose_id", "patient_id", name="uq_decline_purpose_patient"),
    )

    sharing_purpose_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("sharing_purposes.id"), nullable=False, index=True
    )
    patient_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("patients.id"), nullable=False, index=True
    )
    declined_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=True
    )
    declined_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
