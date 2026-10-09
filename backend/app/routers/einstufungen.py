import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.access import AccessLevel, require_patient_access
from app.core.database import get_db
from app.deps import get_current_user
from app.models.einstufung import Einstufung
from app.models.user import User
from app.schemas.einstufung import (
    EinstufungCreateRequest,
    EinstufungDto,
    EinstufungScaleDto,
    EinstufungUpdateRequest,
)
from app.services.pflegegrad import scale_position

router = APIRouter()


def _base_query(patient_id):
    return select(Einstufung).where(
        Einstufung.patient_id == patient_id,
        Einstufung.is_deleted == False,  # noqa: E712
    )


def _ordered(patient_id):
    """Newest first. valid_from is the date that decides which one is current, not
    created_at: a Bescheid arriving in July can take effect in March."""
    return _base_query(patient_id).order_by(
        Einstufung.valid_from.desc().nullslast(), Einstufung.created_at.desc()
    )


async def _get_owned(einstufung_id, user, db, level=AccessLevel.contribute) -> Einstufung:
    result = await db.execute(select(Einstufung).where(
        Einstufung.id == einstufung_id, Einstufung.is_deleted == False,  # noqa: E712
    ))
    row = result.scalar_one_or_none()
    if not row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    await require_patient_access(row.patient_id, user, db, level)
    return row


@router.get("/patients/{patient_id}/einstufungen", response_model=list[EinstufungDto])
async def list_einstufungen(
    patient_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await require_patient_access(patient_id, user, db)
    return (await db.execute(_ordered(patient_id))).scalars().all()


@router.get("/patients/{patient_id}/einstufungen/current", response_model=EinstufungDto | None)
async def get_current_einstufung(
    patient_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """The Einstufung in force: the one with the latest valid_from."""
    await require_patient_access(patient_id, user, db)
    return (await db.execute(_ordered(patient_id).limit(1))).scalar_one_or_none()


@router.get("/patients/{patient_id}/einstufungen/scale", response_model=EinstufungScaleDto | None)
async def get_scale(
    patient_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Where the current total sits between the statutory thresholds."""
    await require_patient_access(patient_id, user, db)
    current = (await db.execute(_ordered(patient_id).limit(1))).scalar_one_or_none()
    if not current:
        return None
    return scale_position(current.total_points)


@router.post("/patients/{patient_id}/einstufungen", response_model=EinstufungDto, status_code=status.HTTP_201_CREATED)
async def create_einstufung(
    patient_id: uuid.UUID,
    body: EinstufungCreateRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await require_patient_access(patient_id, user, db, AccessLevel.contribute)
    row = Einstufung(patient_id=patient_id, owner_id=user.id, source="manual",
                     **body.model_dump(exclude_none=True))
    db.add(row)
    await db.commit()
    await db.refresh(row)
    return row


@router.put("/einstufungen/{einstufung_id}", response_model=EinstufungDto)
async def update_einstufung(
    einstufung_id: uuid.UUID,
    body: EinstufungUpdateRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    row = await _get_owned(einstufung_id, user, db)
    for field, value in body.model_dump(exclude_unset=True).items():
        setattr(row, field, value)
    await db.commit()
    await db.refresh(row)
    return row


@router.delete("/einstufungen/{einstufung_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_einstufung(
    einstufung_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    row = await _get_owned(einstufung_id, user, db)
    row.is_deleted = True
    await db.commit()
