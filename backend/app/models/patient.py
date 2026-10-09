import uuid

from sqlalchemy import Boolean, Date, ForeignKey, LargeBinary, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import BaseModel


class Patient(BaseModel):
    __tablename__ = "patients"

    # audit only, never access-relevant (ADR 026)
    created_by: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)

    given_name: Mapped[str] = mapped_column(String(100), nullable=False)
    family_name: Mapped[str] = mapped_column(String(100), nullable=False)
    birth_date: Mapped[str | None] = mapped_column(String(20))  # ISO date string
    gender: Mapped[str | None] = mapped_column(String(20))
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    identifier: Mapped[str | None] = mapped_column(String(256))
    group_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("groups.id"), nullable=True)

    # Optional patient photo — PHI, so stored envelope-encrypted like a document:
    # blob under a per-photo DEK wrapped by the patient KEK (ADR-031).
    photo_storage_path: Mapped[str | None] = mapped_column(String(1024))
    photo_dek: Mapped[bytes | None] = mapped_column(LargeBinary)
    photo_content_type: Mapped[str | None] = mapped_column(String(100))

    # Relationships
    observations: Mapped[list["Observation"]] = relationship("Observation", back_populates="patient", lazy="select")  # noqa: F821
    conditions: Mapped[list["Condition"]] = relationship("Condition", back_populates="patient", lazy="select")  # noqa: F821
    medications: Mapped[list["MedicationStatement"]] = relationship("MedicationStatement", back_populates="patient", lazy="select")  # noqa: F821
    documents: Mapped[list["DocumentReference"]] = relationship("DocumentReference", back_populates="patient", lazy="select")  # noqa: F821
    incidents: Mapped[list["Incident"]] = relationship("Incident", back_populates="patient", lazy="select")  # noqa: F821
    diary_entries: Mapped[list["DiaryEntry"]] = relationship("DiaryEntry", back_populates="patient", lazy="select")  # noqa: F821
    calendar_events: Mapped[list["CalendarEvent"]] = relationship("CalendarEvent", back_populates="patient", lazy="select")  # noqa: F821
    access_grants: Mapped[list["PatientAccess"]] = relationship("PatientAccess", back_populates="patient", lazy="select")  # noqa: F821
    group: Mapped["Group | None"] = relationship("Group", back_populates="patients", foreign_keys=[group_id])  # noqa: F821
