import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.access import AccessLevel, require_patient_access
from app.core.database import get_db
from app.deps import get_current_user
from app.models.observation import Observation
from app.models.user import User
from app.schemas.observation import ObservationCreateRequest, ObservationDto

router = APIRouter()


@router.get("/patients/{patient_id}/observations", response_model=list[ObservationDto])
async def list_observations(
    patient_id: uuid.UUID,
    category: str | None = Query(None),
    from_: str | None = Query(None, alias="from"),
    to: str | None = Query(None),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await require_patient_access(patient_id, user, db)
    q = select(Observation).where(Observation.patient_id == patient_id, Observation.is_deleted == False)  # noqa: E712
    if category:
        q = q.where(Observation.category == category)
    result = await db.execute(q)
    return result.scalars().all()


@router.post("/patients/{patient_id}/observations", response_model=ObservationDto, status_code=status.HTTP_201_CREATED)
async def create_observation(
    patient_id: uuid.UUID,
    body: ObservationCreateRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await require_patient_access(patient_id, user, db, AccessLevel.contribute)
    from app.services.lab_codes import canonical_code, parse_reference_range, resolve_panel

    data = body.model_dump()
    data["code"] = data.get("code") or canonical_code(data.get("code_display"))
    data["panel"] = resolve_panel(data["code"], data.get("panel"))  # ADR 029
    if data.get("reference_range") and data.get("ref_low") is None and data.get("ref_high") is None:
        data["ref_low"], data["ref_high"] = parse_reference_range(data["reference_range"])
    obs = Observation(
        patient_id=patient_id,
        owner_id=user.id,
        **data,
    )
    db.add(obs)
    await db.commit()
    await db.refresh(obs)
    return obs


@router.delete("/observations/{observation_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_observation(
    observation_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Observation).where(Observation.id == observation_id, Observation.is_deleted == False))  # noqa: E712
    obs = result.scalar_one_or_none()
    if not obs:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    await require_patient_access(obs.patient_id, user, db, AccessLevel.contribute)
    obs.is_deleted = True
    await db.commit()
