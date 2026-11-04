"""ADR 062: what happened, for everyone who cares for the Patient; no assessment (#119)."""

import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.access import AccessLevel
from app.core.database import get_db
from app.deps import get_current_user
from app.models.audit import AuditLog
from app.models.dose import Dose
from app.models.incident import Incident
from app.models.user import User
from app.routers.doses import _level, _name
from app.schemas.incident import IncidentDto, IncidentIn

router = APIRouter()


def _dto(i: Incident, user: User, level: AccessLevel | None) -> IncidentDto:
    return IncidentDto(id=i.id, patient_id=i.patient_id, incident_type=i.incident_type,
                       incident_type_display=i.incident_type_display, occurred_at=i.occurred_at,
                       duration_minutes=i.duration_minutes, actions_taken=i.actions_taken, note=i.note,
                       entered_by=_name(i.owner), can_edit=i.owner_id == user.id or level == AccessLevel.admin)


def _apply(row: Incident, body: IncidentIn) -> None:
    row.incident_type = body.incident_type
    row.incident_type_display = (body.incident_type_display or "").strip() or None
    row.occurred_at = body.occurred_at
    row.duration_minutes = body.duration_minutes
    row.actions_taken = (body.actions_taken or "").strip() or None
    row.note = (body.note or "").strip() or None


@router.get("/patients/{patient_id}/incidents", response_model=list[IncidentDto])
async def list_incidents(patient_id: uuid.UUID, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    level = await _level(patient_id, user, db, AccessLevel.view)
    rows = (await db.execute(select(Incident).where(Incident.patient_id == patient_id, Incident.is_deleted == False)  # noqa: E712
                             .order_by(Incident.occurred_at.desc()))).scalars().all()
    return [_dto(i, user, level) for i in rows]


async def _get(incident_id: uuid.UUID, user: User, db: AsyncSession, minimum: AccessLevel) -> tuple[Incident, AccessLevel]:
    row = (await db.execute(select(Incident).where(Incident.id == incident_id, Incident.is_deleted == False))).scalar_one_or_none()  # noqa: E712
    if not row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    return row, await _level(row.patient_id, user, db, minimum)


@router.post("/patients/{patient_id}/incidents", response_model=IncidentDto, status_code=status.HTTP_201_CREATED)
async def create_incident(patient_id: uuid.UUID, body: IncidentIn, user: User = Depends(get_current_user),
                          db: AsyncSession = Depends(get_db)):
    level = await _level(patient_id, user, db, AccessLevel.contribute)
    row = Incident(patient_id=patient_id, owner_id=user.id)
    _apply(row, body)
    db.add(row)
    await db.commit()
    await db.refresh(row, ["owner"])
    return _dto(row, user, level)


async def _editable(incident_id: uuid.UUID, user: User, db: AsyncSession) -> tuple[Incident, AccessLevel]:
    row, level = await _get(incident_id, user, db, AccessLevel.contribute)
    if row.owner_id != user.id and level != AccessLevel.admin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only who entered it or an admin")
    return row, level


def _audit(db: AsyncSession, user: User, action: str, row: Incident) -> None:
    db.add(AuditLog(timestamp=datetime.now(UTC), user_id=user.id, user_name=_name(user), entity_type="Incident",
                    entity_id=str(row.id), action=action,
                    changes={"incident_type": row.incident_type, "occurred_at": row.occurred_at}))


@router.put("/incidents/{incident_id}", response_model=IncidentDto)
async def update_incident(incident_id: uuid.UUID, body: IncidentIn, user: User = Depends(get_current_user),
                          db: AsyncSession = Depends(get_db)):
    row, level = await _editable(incident_id, user, db)
    _audit(db, user, "updated", row)
    _apply(row, body)
    await db.commit()
    await db.refresh(row, ["owner"])
    return _dto(row, user, level)


@router.delete("/incidents/{incident_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_incident(incident_id: uuid.UUID, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    row, _ = await _editable(incident_id, user, db)
    _audit(db, user, "deleted", row)
    row.is_deleted = True
    # its Doses were still given, possibly by someone else: they stay, only the link goes
    await db.execute(update(Dose).where(Dose.incident_id == row.id).values(incident_id=None))
    await db.commit()
