"""ADR 063: Abilities are observed, never assessed; a Test Attempt records how a test went, not its score."""

import uuid

from sqlalchemy import Boolean, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import OwnedResource

LABELS = {
    "de": {
        "communication": "Kommunikation", "daily_living": "Alltag", "social": "Sozialverhalten", "motor": "Motorik",
        "learning": "Lernen", "home": "zuhause", "kita_school": "Kita/Schule", "therapy": "Therapie",
        "out": "unterwegs", "clinic": "Klinik/SPZ", "practice": "Praxis", "completed": "durchgeführt",
        "stopped": "abgebrochen", "refused": "verweigert", "not_attempted": "nicht versucht",
        "works": "klappt", "fails": "klappt nicht", "no_longer": "klappt nicht mehr", "alone": "allein",
        "with_help": "mit Hilfe", "intake_form": "laut Anamnesebogen", "document": "laut Dokument",
    },
    "en": {
        "communication": "Communication", "daily_living": "Daily living", "social": "Social", "motor": "Motor",
        "learning": "Learning", "home": "at home", "kita_school": "Kita/school", "therapy": "therapy",
        "out": "out and about", "clinic": "clinic/SPZ", "practice": "practice", "completed": "completed",
        "stopped": "stopped", "refused": "refused", "not_attempted": "not attempted",
        "works": "works", "fails": "does not work", "no_longer": "no longer works", "alone": "on its own",
        "with_help": "with help", "intake_form": "per intake form", "document": "per document",
    },
}


class Ability(OwnedResource):
    """Named in the family's words; its state is its latest Observation, never a field."""

    __tablename__ = "abilities"

    patient_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("patients.id"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(256), nullable=False)
    domain: Mapped[str | None] = mapped_column(String(20))  # values: schemas/development.py

    observations: Mapped[list["AbilityObservation"]] = relationship(
        "AbilityObservation", back_populates="ability", lazy="selectin",
        primaryjoin="and_(Ability.id == AbilityObservation.ability_id, AbilityObservation.is_deleted == False)",
        order_by="AbilityObservation.observed_on", viewonly=True)


class AbilityObservation(OwnedResource):
    """Owner is who entered it. "No longer" is derived from the history, never stored."""

    __tablename__ = "ability_observations"

    patient_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("patients.id"), nullable=False, index=True)
    ability_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("abilities.id"), nullable=False, index=True)
    observed_on: Mapped[str] = mapped_column(String(10), nullable=False)  # YYYY-MM or YYYY-MM-DD
    place: Mapped[str | None] = mapped_column(String(20))  # values: schemas/development.py
    works: Mapped[bool] = mapped_column(Boolean, nullable=False)
    with_help: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    note: Mapped[str | None] = mapped_column(Text)
    source: Mapped[str] = mapped_column(String(20), nullable=False, default="family")  # family | intake_form | document
    document_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("document_references.id"))

    ability: Mapped[Ability] = relationship(Ability, lazy="joined")
    owner: Mapped["User"] = relationship("User", lazy="joined")  # noqa: F821
    document: Mapped["DocumentReference | None"] = relationship("DocumentReference", lazy="joined")  # noqa: F821

    def sender(self) -> str | None:
        """Who wrote the report it came from, so "at home, not at the SPZ" stays visible (#465)."""
        d = self.document
        return (d.correspondent.name if d.correspondent else d.detected_provider or d.file_name) if d else None


class TestAttempt(OwnedResource):
    """No score field: a completed test's number is in its report (ADR 063)."""

    __tablename__ = "test_attempts"
    __test__ = False  # not a pytest class

    patient_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("patients.id"), nullable=False, index=True)
    test_name: Mapped[str] = mapped_column(String(256), nullable=False)
    attempted_on: Mapped[str] = mapped_column(String(10), nullable=False)  # YYYY-MM or YYYY-MM-DD
    correspondent_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("correspondents.id"))
    setting: Mapped[str | None] = mapped_column(String(20))  # values: schemas/development.py
    duration_minutes: Mapped[int | None] = mapped_column(Integer)
    outcome: Mapped[str] = mapped_column(String(20), nullable=False)  # values: schemas/development.py
    reason: Mapped[str | None] = mapped_column(Text)
    document_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("document_references.id"))

    correspondent: Mapped["Correspondent | None"] = relationship("Correspondent", lazy="joined")  # noqa: F821
    owner: Mapped["User"] = relationship("User", lazy="joined")  # noqa: F821


def no_longer(observations: list[AbilityObservation]) -> set[uuid.UUID]:
    """Ids of Observations that did not work after an earlier one did, in date order."""
    seen_working, out = False, set()
    for o in sorted(observations, key=lambda o: o.observed_on):
        if o.works:
            seen_working = True
        elif seen_working:
            out.add(o.id)
    return out
