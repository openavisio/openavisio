import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.access import AccessLevel, require_patient_access
from app.core.database import get_db
from app.deps import get_current_user
from app.models.carer_update import CarerUpdate
from app.models.correspondent import Correspondent
from app.models.user import User
from app.schemas.carer_update import CarerUpdateDto, CarerUpdateIn

router = APIRouter()


async def _apply(row: CarerUpdate, body: CarerUpdateIn, db: AsyncSession) -> None:
    c = (await db.execute(select(Correspondent).where(
        Correspondent.id == body.correspondent_id, Correspondent.is_deleted == False,  # noqa: E712
    ))).scalar_one_or_none()
    if not c:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail="Unknown correspondent")
    row.correspondent = c
    row.person = (body.person or "").strip() or None
    row.day = body.day.isoformat()
    row.text = body.text
    row.retold = body.retold


async def _get_owned(update_id, user, db) -> CarerUpdate:
    row = (await db.execute(select(CarerUpdate).where(
        CarerUpdate.id == update_id, CarerUpdate.is_deleted == False,  # noqa: E712
    ))).scalar_one_or_none()
    if not row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    await require_patient_access(row.patient_id, user, db, AccessLevel.contribute)
    return row


@router.get("/patients/{patient_id}/carer-updates", response_model=list[CarerUpdateDto])
async def list_carer_updates(
    patient_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await require_patient_access(patient_id, user, db)
    q = select(CarerUpdate).where(CarerUpdate.patient_id == patient_id, CarerUpdate.is_deleted == False)  # noqa: E712
    return (await db.execute(q.order_by(CarerUpdate.day.desc(), CarerUpdate.created_at.desc()))).scalars().all()


@router.post("/patients/{patient_id}/carer-updates", response_model=CarerUpdateDto, status_code=status.HTTP_201_CREATED)
async def create_carer_update(
    patient_id: uuid.UUID,
    body: CarerUpdateIn,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await require_patient_access(patient_id, user, db, AccessLevel.contribute)
    row = CarerUpdate(patient_id=patient_id, owner_id=user.id)
    await _apply(row, body, db)
    db.add(row)
    await db.commit()
    await db.refresh(row)
    return row


@router.put("/carer-updates/{update_id}", response_model=CarerUpdateDto)
async def update_carer_update(
    update_id: uuid.UUID,
    body: CarerUpdateIn,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    row = await _get_owned(update_id, user, db)
    await _apply(row, body, db)
    await db.commit()
    await db.refresh(row)
    return row


@router.delete("/carer-updates/{update_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_carer_update(
    update_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    row = await _get_owned(update_id, user, db)
    row.is_deleted = True
    await db.commit()
