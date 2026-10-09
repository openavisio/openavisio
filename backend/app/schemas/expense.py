import uuid
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel

from app.schemas.common import OrmBase


class ExpenseDto(OrmBase):
    id: uuid.UUID
    patient_id: uuid.UUID
    amount: Decimal
    incurred_on: str | None
    category: str
    note: str | None
    reimbursed_amount: Decimal | None
    status: str
    source: str
    correspondent_id: uuid.UUID | None
    document_reference_id: uuid.UUID | None
    created_at: datetime


class ExpenseCreateRequest(BaseModel):
    amount: Decimal
    incurred_on: str | None = None
    category: str = "other"
    note: str | None = None
    reimbursed_amount: Decimal | None = None
    correspondent_id: uuid.UUID | None = None
    document_reference_id: uuid.UUID | None = None


class ExpenseUpdateRequest(BaseModel):
    amount: Decimal | None = None
    incurred_on: str | None = None
    category: str | None = None
    note: str | None = None
    reimbursed_amount: Decimal | None = None
    correspondent_id: uuid.UUID | None = None
    status: str | None = None


class ExpenseSummaryDto(BaseModel):
    total: Decimal            # confirmed only
    total_reimbursed: Decimal
    total_open: Decimal       # deductible / still-open remainder = total - reimbursed
    count: int                # confirmed
    proposed_count: int       # extracted, awaiting confirmation (not in the totals)
    by_category: dict[str, Decimal]
