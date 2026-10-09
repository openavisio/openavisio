import uuid

from sqlalchemy import Float, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import OwnedResource


class Einstufung(OwnedResource):
    """One grading of a Patient's care need by a Pflegekasse (ADR 042).

    A record per assessment, not a field on the Patient: an upgrade commonly takes
    effect retroactively to the month of application, so "which Pflegegrad applied in
    April" is a question with money attached, and an overwritten field cannot answer
    it. The current Pflegegrad is the most recent Einstufung.

    The six module scores are the reason the history is worth keeping: the grade is
    one number that says nothing about what changed, the modules say where the care
    need moved. Six columns because § 15 SGB XI fixes the list at six.
    """

    __tablename__ = "einstufungen"

    patient_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("patients.id"), nullable=False, index=True)
    pflegegrad: Mapped[int | None] = mapped_column(Integer)  # 1..5, null while an application is pending
    total_points: Mapped[float | None] = mapped_column(Float)  # weighted, as printed
    valid_from: Mapped[str | None] = mapped_column(String(50))  # ISO date, matches the string-date convention
    valid_until: Mapped[str | None] = mapped_column(String(50))  # set only when the Bescheid says befristet
    note: Mapped[str | None] = mapped_column(Text)
    authority: Mapped[str | None] = mapped_column(String(256))  # the deciding Pflegekasse
    file_reference: Mapped[str | None] = mapped_column(String(128))  # Aktenzeichen

    # § 15 SGB XI, in the order the law numbers them. Null where the Bescheid printed
    # no table, or where the arithmetic guards rejected what was read.
    module_mobility: Mapped[float | None] = mapped_column(Float)
    module_cognitive: Mapped[float | None] = mapped_column(Float)
    module_behaviour: Mapped[float | None] = mapped_column(Float)
    module_self_care: Mapped[float | None] = mapped_column(Float)
    module_therapy_demands: Mapped[float | None] = mapped_column(Float)
    module_daily_life: Mapped[float | None] = mapped_column(Float)

    source: Mapped[str] = mapped_column(String(20), default="manual")  # manual | pipeline
    document_reference_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("document_references.id"), nullable=True)

    patient: Mapped["Patient"] = relationship("Patient")  # noqa: F821
