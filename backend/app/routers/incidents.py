import uuid
from collections import Counter

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.access import AccessLevel, require_patient_access
from app.core.database import get_db
from app.deps import get_current_user
from app.models.incident import Incident
from app.models.user import User
from app.schemas.incident import IncidentCreateRequest, IncidentDto, IncidentSummaryDto, IncidentUpdateRequest

router = APIRouter()


def _incident_query(patient_id, base):
    return base.where(Incident.patient_id == patient_id, Incident.is_deleted == False)  # noqa: E712


@router.get("/patients/{patient_id}/incidents", response_model=list[IncidentDto])
async def list_incidents(
    patient_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await require_patient_access(patient_id, user, db)
    result = await db.execute(_incident_query(patient_id, select(Incident)))
    return result.scalars().all()


@router.get("/patients/{patient_id}/incidents/summary", response_model=IncidentSummaryDto)
async def get_incident_summary(
    patient_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await require_patient_access(patient_id, user, db)
    from datetime import UTC, datetime, timedelta
    result = await db.execute(_incident_query(patient_id, select(Incident)))
    incidents = result.scalars().all()
    cutoff = (datetime.now(UTC) - timedelta(days=30)).isoformat()
    last30 = [i for i in incidents if i.occurred_at >= cutoff]
    by_type = Counter(i.incident_type for i in incidents)
    by_sev = Counter(i.severity for i in incidents)
    triggers = [i.suspected_trigger for i in incidents if i.suspected_trigger]
    most_trigger = Counter(triggers).most_common(1)[0][0] if triggers else None
    most_type = by_type.most_common(1)[0][0] if by_type else None
    return IncidentSummaryDto(
        total_count=len(incidents),
        last_30_days=len(last30),
        count_by_type=dict(by_type),
        count_by_severity=dict(by_sev),
        most_common_type=most_type,
        most_common_trigger=most_trigger,
    )


@router.get("/patients/{patient_id}/incidents/by-date", response_model=list[IncidentDto])
async def list_incidents_by_date(
    patient_id: uuid.UUID,
    from_: str | None = Query(None, alias="from"),
    to: str | None = Query(None),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await require_patient_access(patient_id, user, db)
    q = _incident_query(patient_id, select(Incident))
    if from_:
        q = q.where(Incident.occurred_at >= from_)
    if to:
        q = q.where(Incident.occurred_at <= to)
    result = await db.execute(q)
    return result.scalars().all()


@router.get("/patients/{patient_id}/incidents/by-type/{inc_type}", response_model=list[IncidentDto])
async def list_incidents_by_type(
    patient_id: uuid.UUID,
    inc_type: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await require_patient_access(patient_id, user, db)
    result = await db.execute(_incident_query(patient_id, select(Incident)).where(Incident.incident_type == inc_type))
    return result.scalars().all()


@router.get("/incidents/{incident_id}", response_model=IncidentDto)
async def get_incident(
    incident_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Incident).where(Incident.id == incident_id, Incident.is_deleted == False))  # noqa: E712
    inc = result.scalar_one_or_none()
    if not inc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    await require_patient_access(inc.patient_id, user, db)
    return inc


@router.post("/patients/{patient_id}/incidents", response_model=IncidentDto, status_code=status.HTTP_201_CREATED)
async def create_incident(
    patient_id: uuid.UUID,
    body: IncidentCreateRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await require_patient_access(patient_id, user, db, AccessLevel.contribute)
    inc = Incident(patient_id=patient_id, owner_id=user.id, **body.model_dump())
    db.add(inc)
    await db.commit()
    await db.refresh(inc)
    return inc


@router.put("/incidents/{incident_id}", response_model=IncidentDto)
async def update_incident(
    incident_id: uuid.UUID,
    body: IncidentUpdateRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Incident).where(Incident.id == incident_id, Incident.is_deleted == False))  # noqa: E712
    inc = result.scalar_one_or_none()
    if not inc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    await require_patient_access(inc.patient_id, user, db, AccessLevel.contribute)
    for field, value in body.model_dump(exclude_none=True).items():
        setattr(inc, field, value)
    await db.commit()
    await db.refresh(inc)
    return inc


@router.delete("/incidents/{incident_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_incident(
    incident_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Incident).where(Incident.id == incident_id, Incident.is_deleted == False))  # noqa: E712
    inc = result.scalar_one_or_none()
    if not inc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    await require_patient_access(inc.patient_id, user, db, AccessLevel.contribute)
    inc.is_deleted = True
    await db.commit()
