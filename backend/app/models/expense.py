import uuid
from decimal import Decimal

from sqlalchemy import ForeignKey, Numeric, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import OwnedResource

# Fixed, coarse vocabulary — enough to group and sum in the overview/export,
# cheap to maintain. Stored as a plain string like the other models' enums
# (see Incident.severity); no DB enum type.
EXPENSE_CATEGORIES = ("pflegehilfsmittel", "medication_copay", "therapy", "aid", "travel", "other")


class Expense(OwnedResource):
    """A monetary amount a caregiver paid or owes for a Patient's care, optionally
    backed by an invoice Document. Structured for insurance applications and tax
    returns (#218). Not a clinical record — a financial one attached to a Patient.

    Amount is Numeric, never float: a wrong sum lands in a tax return. Extracted
    amounts arrive as status="proposed" and count in totals/export only once the
    User confirms them.
    """

    __tablename__ = "expenses"

    patient_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("patients.id"), nullable=False, index=True)
    amount: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    # ponytail: EUR-only for the German care-cost use case; add a currency column if non-EUR receipts appear.
    incurred_on: Mapped[str | None] = mapped_column(String(50))  # ISO date, matches the string-date convention (Incident.occurred_at)
    category: Mapped[str] = mapped_column(String(50), default="other")
    note: Mapped[str | None] = mapped_column(Text)
    reimbursed_amount: Mapped[Decimal | None] = mapped_column(Numeric(10, 2))  # null = still open; deductible remainder = amount - reimbursed
    status: Mapped[str] = mapped_column(String(20), default="confirmed")  # proposed | confirmed
    source: Mapped[str] = mapped_column(String(20), default="manual")     # manual | pipeline
    correspondent_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("correspondents.id"), nullable=True)
    document_reference_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("document_references.id"), nullable=True)

    correspondent: Mapped["Correspondent"] = relationship("Correspondent")  # noqa: F821
