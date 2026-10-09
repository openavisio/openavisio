import uuid

from sqlalchemy import Boolean, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import OwnedResource


class CarerUpdate(OwnedResource):
    """ADR 049"""

    __tablename__ = "carer_updates"

    patient_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("patients.id"), nullable=False, index=True)
    correspondent_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("correspondents.id"), nullable=False)
    person: Mapped[str | None] = mapped_column(String(256))
    day: Mapped[str] = mapped_column(String(10), nullable=False)  # ISO date, matches the string-date convention
    text: Mapped[str] = mapped_column(Text, nullable=False)
    retold: Mapped[bool] = mapped_column(Boolean, default=False)  # told at pickup, not copied word for word

    # a soft-deleted Correspondent keeps its name here
    correspondent: Mapped["Correspondent"] = relationship("Correspondent", lazy="joined")  # noqa: F821

    @property
    def correspondent_name(self) -> str:
        return self.correspondent.name
