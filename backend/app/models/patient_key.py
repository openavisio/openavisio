import uuid

from sqlalchemy import ForeignKey, LargeBinary, SmallInteger
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import BaseModel


class PatientKey(BaseModel):
    """Per-patient KEK, wrapped under the master KEK (ADR-031).

    Lives in its own table so deployment can back it up as a SEPARATE,
    short-retention stream — deleting the row crypto-shreds that patient's
    encrypted PHI in backups, not just live data. The row's existence is the
    invariant; its deletion is erasure.
    """

    __tablename__ = "patient_keys"

    patient_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("patients.id", ondelete="CASCADE"), unique=True, index=True, nullable=False
    )
    wrapped_kek: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    kek_version: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=1, server_default="1")
