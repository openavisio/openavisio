import csv
import io
import uuid
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.access import AccessLevel, require_patient_access
from app.core.database import get_db
from app.deps import get_current_user
from app.models.correspondent import Correspondent
from app.models.expense import EXPENSE_CATEGORIES, Expense
from app.models.user import User
from app.schemas.expense import (
    ExpenseCreateRequest,
    ExpenseDto,
    ExpenseSummaryDto,
    ExpenseUpdateRequest,
)

router = APIRouter()

ZERO = Decimal("0.00")


def summarize(expenses) -> ExpenseSummaryDto:
    """Pure money math over a list of expense rows.

    Only *confirmed* expenses count toward the totals — a proposed (extracted,
    unconfirmed) amount must never inflate a tax or insurance sum. Kept pure and
    DB-free so it is unit-testable without a database (see tests/test_expense_summary.py).
    """
    confirmed = [e for e in expenses if e.status == "confirmed"]
    proposed_count = sum(1 for e in expenses if e.status == "proposed")
    total = sum((e.amount for e in confirmed), ZERO)
    total_reimbursed = sum((e.reimbursed_amount or ZERO for e in confirmed), ZERO)
    by_category: dict[str, Decimal] = {}
    for e in confirmed:
        by_category[e.category] = by_category.get(e.category, ZERO) + e.amount
    return ExpenseSummaryDto(
        total=total,
        total_reimbursed=total_reimbursed,
        total_open=total - total_reimbursed,
        count=len(confirmed),
        proposed_count=proposed_count,
        by_category=by_category,
    )


def _validate_category(category: str | None) -> None:
    if category is not None and category not in EXPENSE_CATEGORIES:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"category must be one of {EXPENSE_CATEGORIES}",
        )


def _base_query(patient_id):
    return select(Expense).where(Expense.patient_id == patient_id, Expense.is_deleted == False)  # noqa: E712


async def _get_owned(expense_id, user, db, level=AccessLevel.contribute) -> Expense:
    result = await db.execute(select(Expense).where(Expense.id == expense_id, Expense.is_deleted == False))  # noqa: E712
    exp = result.scalar_one_or_none()
    if not exp:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    await require_patient_access(exp.patient_id, user, db, level)
    return exp


@router.get("/patients/{patient_id}/expenses", response_model=list[ExpenseDto])
async def list_expenses(
    patient_id: uuid.UUID,
    expense_status: str | None = Query(None, alias="status"),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await require_patient_access(patient_id, user, db)
    q = _base_query(patient_id)
    if expense_status:
        q = q.where(Expense.status == expense_status)
    result = await db.execute(q.order_by(Expense.incurred_on.desc().nullslast()))
    return result.scalars().all()


@router.get("/patients/{patient_id}/expenses/summary", response_model=ExpenseSummaryDto)
async def get_expense_summary(
    patient_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await require_patient_access(patient_id, user, db)
    result = await db.execute(_base_query(patient_id))
    return summarize(result.scalars().all())


@router.get("/patients/{patient_id}/expenses/export.csv")
async def export_expenses_csv(
    patient_id: uuid.UUID,
    from_: str | None = Query(None, alias="from"),
    to: str | None = Query(None),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """CSV of confirmed expenses for a tax advisor or an insurance application."""
    await require_patient_access(patient_id, user, db)
    q = _base_query(patient_id).where(Expense.status == "confirmed")
    if from_:
        q = q.where(Expense.incurred_on >= from_)
    if to:
        q = q.where(Expense.incurred_on <= to)
    rows = (await db.execute(q.order_by(Expense.incurred_on.asc().nullsfirst()))).scalars().all()

    corr_ids = {r.correspondent_id for r in rows if r.correspondent_id}
    names: dict[uuid.UUID, str] = {}
    if corr_ids:
        cres = await db.execute(select(Correspondent.id, Correspondent.name).where(Correspondent.id.in_(corr_ids)))
        names = {cid: name for cid, name in cres.all()}

    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["date", "category", "payee", "note", "amount_eur", "reimbursed_eur", "open_eur"])
    for r in rows:
        reimbursed = r.reimbursed_amount or ZERO
        w.writerow([
            r.incurred_on or "",
            r.category,
            names.get(r.correspondent_id, ""),
            (r.note or "").replace("\n", " "),
            f"{r.amount:.2f}",
            f"{reimbursed:.2f}",
            f"{r.amount - reimbursed:.2f}",
        ])
    return Response(
        content=buf.getvalue(),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="expenses-{patient_id}.csv"'},
    )


@router.post("/patients/{patient_id}/expenses", response_model=ExpenseDto, status_code=status.HTTP_201_CREATED)
async def create_expense(
    patient_id: uuid.UUID,
    body: ExpenseCreateRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await require_patient_access(patient_id, user, db, AccessLevel.contribute)
    _validate_category(body.category)
    # Manually entered expenses are confirmed on creation; only extracted ones are proposed.
    exp = Expense(patient_id=patient_id, owner_id=user.id, status="confirmed", source="manual", **body.model_dump())
    db.add(exp)
    await db.commit()
    await db.refresh(exp)
    return exp


@router.put("/expenses/{expense_id}", response_model=ExpenseDto)
async def update_expense(
    expense_id: uuid.UUID,
    body: ExpenseUpdateRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    exp = await _get_owned(expense_id, user, db)
    _validate_category(body.category)
    for field, value in body.model_dump(exclude_none=True).items():
        setattr(exp, field, value)
    await db.commit()
    await db.refresh(exp)
    return exp


@router.post("/expenses/{expense_id}/confirm", response_model=ExpenseDto)
async def confirm_expense(
    expense_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    exp = await _get_owned(expense_id, user, db)
    exp.status = "confirmed"
    await db.commit()
    await db.refresh(exp)
    return exp


@router.delete("/expenses/{expense_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_expense(
    expense_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    exp = await _get_owned(expense_id, user, db)
    exp.is_deleted = True
    await db.commit()
