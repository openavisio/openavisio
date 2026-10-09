import uuid
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.access import AccessLevel, require_patient_access
from app.core.database import get_db
from app.deps import get_current_user
from app.models.medication import MedicationStatement
from app.models.user import User
from app.schemas.medication import MedicationCreateRequest, MedicationDto, MedicationUpdateRequest

router = APIRouter()


def parse_med_date(s: str | None) -> date | None:
    """Best-effort ISO date parse; unparseable/empty → None (treated as open-ended)."""
    if not s:
        return None
    try:
        return date.fromisoformat(s[:10])
    except ValueError:
        return None


def med_is_active(med: MedicationStatement) -> bool:
    """Currently active = not manually stopped/completed and not past its end date (#68)."""
    if med.status in ("stopped", "completed"):
        return False
    end = parse_med_date(med.effective_end)
    return end is None or end >= date.today()


def medication_to_dto(med: MedicationStatement) -> MedicationDto:
    dto = MedicationDto.model_validate(med)
    dto.is_active = med_is_active(med)
    return dto


@router.get("/patients/{patient_id}/medications", response_model=list[MedicationDto])
async def list_medications(
    patient_id: uuid.UUID,
    med_status: str | None = Query(None, alias="status"),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await require_patient_access(patient_id, user, db)
    q = select(MedicationStatement).where(MedicationStatement.patient_id == patient_id, MedicationStatement.is_deleted == False)  # noqa: E712
    if med_status:
        q = q.where(MedicationStatement.status == med_status)
    result = await db.execute(q)
    return [medication_to_dto(m) for m in result.scalars().all()]


@router.post("/patients/{patient_id}/medications", response_model=MedicationDto, status_code=status.HTTP_201_CREATED)
async def create_medication(
    patient_id: uuid.UUID,
    body: MedicationCreateRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await require_patient_access(patient_id, user, db, AccessLevel.contribute)
    med = MedicationStatement(patient_id=patient_id, owner_id=user.id, **body.model_dump())
    db.add(med)
    await db.commit()
    await db.refresh(med)
    return medication_to_dto(med)


@router.get("/medications/{medication_id}", response_model=MedicationDto)
async def get_medication(
    medication_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(MedicationStatement).where(MedicationStatement.id == medication_id, MedicationStatement.is_deleted == False))  # noqa: E712
    med = result.scalar_one_or_none()
    if not med:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    await require_patient_access(med.patient_id, user, db)
    return medication_to_dto(med)


@router.put("/medications/{medication_id}", response_model=MedicationDto)
async def update_medication(
    medication_id: uuid.UUID,
    body: MedicationUpdateRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(MedicationStatement).where(MedicationStatement.id == medication_id, MedicationStatement.is_deleted == False))  # noqa: E712
    med = result.scalar_one_or_none()
    if not med:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    await require_patient_access(med.patient_id, user, db, AccessLevel.contribute)
    # exclude_unset, not exclude_none: a client must be able to CLEAR a date by
    # sending null. With exclude_none an explicit null was silently dropped, so a
    # wrong extracted date could never be removed (#128).
    for field, value in body.model_dump(exclude_unset=True).items():
        setattr(med, field, value)
    # Last resort only. The UI asks for the date (#128) — this catches API clients
    # that stop a medication without saying when.
    if med.status in ("stopped", "completed") and not med.effective_end:
        med.effective_end = date.today().isoformat()
    await db.commit()
    await db.refresh(med)
    return medication_to_dto(med)


@router.delete("/medications/{medication_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_medication(
    medication_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(MedicationStatement).where(MedicationStatement.id == medication_id, MedicationStatement.is_deleted == False))  # noqa: E712
    med = result.scalar_one_or_none()
    if not med:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    await require_patient_access(med.patient_id, user, db, AccessLevel.contribute)
    med.is_deleted = True
    await db.commit()
