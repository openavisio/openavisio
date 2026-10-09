import uuid

from sqlalchemy import ForeignKey, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import OwnedResource


class EmergencyPlan(OwnedResource):
    """ADR 048"""

    __tablename__ = "emergency_plans"

    patient_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("patients.id"), nullable=False, unique=True)
    # ponytail: JSONB saved whole, last save wins; per-item rows if concurrent editing ever hurts
    situations: Mapped[list] = mapped_column(JSONB, default=list)  # [{trigger, steps: [{text, medication_id}]}]
    contacts: Mapped[list] = mapped_column(JSONB, default=list)  # [{name, role, phone}]
    notes: Mapped[str | None] = mapped_column(Text)
    document_ids: Mapped[list] = mapped_column(JSONB, default=list)
