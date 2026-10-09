"""External document share links — see docs/adr/021-external-document-share-links.md.

A Caregiver generates a time-limited, read-only, anonymous link granting an
external specialist access to a fixed (snapshot) set of a Patient's Documents.
Only the token *hash* is stored; the plaintext token lives solely in the URL.
"""

import uuid
from datetime import datetime
from enum import StrEnum

from sqlalchemy import Boolean, DateTime, ForeignKey, LargeBinary, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import BaseModel


class ShareLinkStatus(StrEnum):
    active = "active"
    revoked = "revoked"


class DocumentShareLink(BaseModel):
    """A time-limited, anonymous, read-only link to a set of Documents."""

    __tablename__ = "document_share_links"

    patient_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("patients.id"), nullable=False, index=True
    )
    token_hash: Mapped[str] = mapped_column(String(64), nullable=False, unique=True, index=True)
    status: Mapped[str] = mapped_column(String(20), default=ShareLinkStatus.active, index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=True
    )
    created_legal: Mapped[bool] = mapped_column(Boolean, default=False)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    items: Mapped[list["DocumentShareLinkItem"]] = relationship(
        "DocumentShareLinkItem", back_populates="share_link", lazy="selectin",
        cascade="all, delete-orphan",
    )


class DocumentShareLinkItem(BaseModel):
    """One Document included in a share link's snapshot set."""

    __tablename__ = "document_share_link_items"
    __table_args__ = (
        UniqueConstraint("share_link_id", "document_id", name="uq_share_link_document"),
    )

    share_link_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("document_share_links.id"), nullable=False, index=True
    )
    document_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("document_references.id"), nullable=False, index=True
    )
    patient_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("patients.id"), nullable=False, index=True
    )

    share_link: Mapped["DocumentShareLink"] = relationship("DocumentShareLink", back_populates="items")


class DocumentShareLinkHandout(BaseModel):
    """ADR 048: a Handout frozen into a link at creation, the PDF envelope-encrypted."""

    __tablename__ = "document_share_link_handouts"

    share_link_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("document_share_links.id"), nullable=False, unique=True
    )
    patient_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("patients.id"), nullable=False, index=True
    )
    variant: Mapped[str] = mapped_column(String(20), nullable=False)
    lang: Mapped[str] = mapped_column(String(2), nullable=False)
    pdf: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    encrypted_dek: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
