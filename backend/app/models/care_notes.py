import uuid

from sqlalchemy import ForeignKey, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import OwnedResource

HEADINGS = ("communication", "eating_drinking", "sleep", "aids", "what_helps", "what_overwhelms")


class CareNotes(OwnedResource):
    """ADR 048"""

    __tablename__ = "care_notes"

    patient_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("patients.id"), nullable=False, unique=True)
    communication: Mapped[str | None] = mapped_column(Text)
    eating_drinking: Mapped[str | None] = mapped_column(Text)
    sleep: Mapped[str | None] = mapped_column(Text)
    aids: Mapped[str | None] = mapped_column(Text)
    what_helps: Mapped[str | None] = mapped_column(Text)
    what_overwhelms: Mapped[str | None] = mapped_column(Text)
