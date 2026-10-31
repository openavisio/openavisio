import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import BaseModel


class Proposal(BaseModel):
    """One extracted entry awaiting the User's decision (ADR 058).

    payload is the extracted entry as JSON, ciphertext under the patient KEK
    like extraction_json (ADR 031); `index` is its position in that JSON.
    """

    __tablename__ = "proposals"

    patient_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("patients.id"), nullable=False, index=True)
    document_reference_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("document_references.id"), nullable=False, index=True)
    kind: Mapped[str] = mapped_column(String(32), nullable=False)  # "diagnosis"
    index: Mapped[int] = mapped_column(nullable=False)
    payload: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(16), default="open")  # open | accepted | rejected
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    decided_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"))
    # the record row an accepted Proposal landed in; a later per-Document verify keeps it
    record_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))


class NameGrouping(BaseModel):
    """The model's grouping of a Patient's diagnosis names, kept until the names change (ADR 058).

    payload is {"names": [...], "groups": [[...]]} as ciphertext under the patient KEK;
    the names are compared after decrypting, so no hash of them is stored.
    """

    __tablename__ = "name_groupings"
    __table_args__ = (UniqueConstraint("patient_id", "kind"),)

    patient_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("patients.id"), nullable=False)
    kind: Mapped[str] = mapped_column(String(32), nullable=False)  # "diagnosis"
    payload: Mapped[str] = mapped_column(Text, nullable=False)
