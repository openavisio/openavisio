"""GDPR data-governance models: lawful basis + retention per category (#15/#16),
and onboarding consent records (#15).
"""

import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import BaseModel


class DataCategory(BaseModel):
    """A category of patient data with its documented lawful basis and retention.

    Built-in categories map to a concrete table in the purge service; custom
    categories (``is_builtin = False``) are documentation-only (no auto-purge).
    """

    __tablename__ = "data_categories"

    code: Mapped[str] = mapped_column(String(50), nullable=False, unique=True, index=True)
    label: Mapped[str] = mapped_column(String(100), nullable=False)
    is_builtin: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    lawful_basis: Mapped[str | None] = mapped_column(String(50))
    retention_days: Mapped[int | None] = mapped_column(Integer)  # None = keep indefinitely


class ConsentRecord(BaseModel):
    """Proof that a User consented to processing at onboarding (GDPR Art. 7).

    Withdrawal is handled by the existing account/patient erasure flow, not a
    separate mechanism — see docs/adr and issue #15.
    """

    __tablename__ = "consent_records"

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True
    )
    consented_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    policy_version: Mapped[str] = mapped_column(String(20), nullable=False, default="1")
    withdrawn_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
