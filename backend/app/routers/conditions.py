import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.auth.access import AccessLevel, require_patient_access
from app.core.database import get_db
from app.deps import get_current_user
from app.models.condition import Condition, ConditionSource
from app.models.user import User
from app.schemas.condition import ConditionCreateRequest, ConditionDto, ConditionMergeRequest, ConditionUpdateRequest

router = APIRouter()


@router.get("/patients/{patient_id}/conditions", response_model=list[ConditionDto])
async def list_conditions(
    patient_id: uuid.UUID,
    cond_status: str | None = Query(None, alias="status"),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await require_patient_access(patient_id, user, db)
    q = select(Condition).options(selectinload(Condition.sources).selectinload(ConditionSource.document)).where(Condition.patient_id == patient_id, Condition.is_deleted == False)  # noqa: E712
    if cond_status:
        q = q.where(Condition.clinical_status == cond_status)
    result = await db.execute(q)
    return result.scalars().all()


@router.post("/patients/{patient_id}/conditions", response_model=ConditionDto, status_code=status.HTTP_201_CREATED)
async def create_condition(
    patient_id: uuid.UUID,
    body: ConditionCreateRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await require_patient_access(patient_id, user, db, AccessLevel.contribute)
    cond = Condition(patient_id=patient_id, owner_id=user.id, **body.model_dump())
    db.add(cond)
    await db.commit()
    await db.refresh(cond, ["sources"])
    return cond


@router.get("/conditions/{condition_id}", response_model=ConditionDto)
async def get_condition(
    condition_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Condition).options(selectinload(Condition.sources).selectinload(ConditionSource.document)).where(Condition.id == condition_id, Condition.is_deleted == False))  # noqa: E712
    cond = result.scalar_one_or_none()
    if not cond:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    await require_patient_access(cond.patient_id, user, db)
    return cond


@router.put("/conditions/{condition_id}", response_model=ConditionDto)
async def update_condition(
    condition_id: uuid.UUID,
    body: ConditionUpdateRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Condition).options(selectinload(Condition.sources).selectinload(ConditionSource.document)).where(Condition.id == condition_id, Condition.is_deleted == False))  # noqa: E712
    cond = result.scalar_one_or_none()
    if not cond:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    await require_patient_access(cond.patient_id, user, db, AccessLevel.contribute)
    for field, value in body.model_dump(exclude_none=True).items():
        setattr(cond, field, value)
    await db.commit()
    # expire_on_commit=False: sources (with documents) stay loaded from the select above
    return cond


@router.post("/conditions/{condition_id}/merge", response_model=ConditionDto)
async def merge_condition(
    condition_id: uuid.UUID,
    body: ConditionMergeRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Merge another condition into this one (#159). The path id is the winner:
    it keeps name, severity, status; onset becomes the earliest documented one;
    sources and notes are unioned. The loser is soft-deleted with a pointer —
    recoverable, but deliberately no automatic unmerge."""
    if body.other_id == condition_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Cannot merge a condition into itself")
    q = select(Condition).options(selectinload(Condition.sources).selectinload(ConditionSource.document))
    winner = (await db.execute(q.where(Condition.id == condition_id, Condition.is_deleted == False))).scalar_one_or_none()  # noqa: E712
    loser = (await db.execute(q.where(Condition.id == body.other_id, Condition.is_deleted == False))).scalar_one_or_none()  # noqa: E712
    if not winner or not loser:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    if winner.patient_id != loser.patient_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    await require_patient_access(winner.patient_id, user, db, AccessLevel.contribute)

    # earliest documented onset survives — the beginning of a condition is a fact
    # about the patient, not about the spelling
    onsets = [d for d in (winner.onset_date_time, loser.onset_date_time) if d]
    if onsets:
        winner.onset_date_time = min(onsets)
    if loser.note:
        winner.note = f"{winner.note}\n{loser.note}" if winner.note else loser.note

    have = {s.document_reference_id for s in winner.sources}
    for s in list(loser.sources):
        if s.document_reference_id not in have:
            winner.sources.append(ConditionSource(document_reference_id=s.document_reference_id))
            have.add(s.document_reference_id)
        await db.delete(s)

    loser.is_deleted = True
    loser.merged_into_id = winner.id
    await db.commit()

    result = await db.execute(q.where(Condition.id == condition_id))
    return result.scalar_one()


@router.delete("/conditions/{condition_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_condition(
    condition_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Condition).options(selectinload(Condition.sources).selectinload(ConditionSource.document)).where(Condition.id == condition_id, Condition.is_deleted == False))  # noqa: E712
    cond = result.scalar_one_or_none()
    if not cond:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    await require_patient_access(cond.patient_id, user, db, AccessLevel.contribute)
    cond.is_deleted = True
    await db.commit()
