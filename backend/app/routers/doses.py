"""ADR 060: what was given, never what is due."""

import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, Query, status
from typing import Annotated

from pydantic import Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.access import AccessLevel, resolve_patient_access
from app.core.database import get_db
from app.deps import get_current_user
from app.models.audit import AuditLog
from app.models.dose import Dose
from app.models.incident import Incident
from app.models.medication import MedicationStatement
from app.models.user import User
from app.schemas.dose import DoseDto, DoseIn

router = APIRouter()


def _name(u: User) -> str:
    return " ".join(filter(None, [u.first_name, u.last_name])) or u.email


async def _level(patient_id: uuid.UUID, user: User, db: AsyncSession, minimum: AccessLevel) -> AccessLevel:
    level = await resolve_patient_access(patient_id, user, db)
    if level is None or level < minimum:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    return level


def _dto(d: Dose, user: User, level: AccessLevel | None) -> DoseDto:
    return DoseDto(id=d.id, medication_id=d.medication_id, given_at=d.given_at, given_by=d.given_by, amount=d.amount,
                   note=d.note, incident_id=d.incident_id, entered_by=_name(d.owner),
                   can_edit=d.owner_id == user.id or level == AccessLevel.admin)


async def _apply(row: Dose, body: DoseIn, patient_id: uuid.UUID, db: AsyncSession) -> None:
    med = (await db.execute(select(MedicationStatement.id).where(
        MedicationStatement.id == body.medication_id, MedicationStatement.patient_id == patient_id,
        MedicationStatement.is_deleted == False))).scalar_one_or_none()  # noqa: E712
    inc = body.incident_id and (await db.execute(select(Incident.id).where(
        Incident.id == body.incident_id, Incident.patient_id == patient_id,
        Incident.is_deleted == False))).scalar_one_or_none()  # noqa: E712
    if not med or (body.incident_id and not inc):
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail="Unknown medication or incident")
    row.medication_id = body.medication_id
    row.given_at = body.given_at
    row.given_by = (body.given_by or "").strip() or None
    row.amount = (body.amount or "").strip() or None
    row.note = (body.note or "").strip() or None
    row.incident_id = body.incident_id


@router.get("/patients/{patient_id}/doses", response_model=list[DoseDto])
async def list_doses(
    patient_id: uuid.UUID,
    since: str | None = Query(None, description="YYYY-MM-DD, inclusive"),
    incident_id: uuid.UUID | None = None,
    with_incident: bool = Query(False, description="only Doses that point at an Incident (ADR 062)"),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    level = await _level(patient_id, user, db, AccessLevel.view)
    q = select(Dose).join(MedicationStatement, MedicationStatement.id == Dose.medication_id).where(
        Dose.patient_id == patient_id, Dose.is_deleted == False, MedicationStatement.is_deleted == False)  # noqa: E712
    if since:
        q = q.where(Dose.given_at >= since[:10])
    if incident_id:
        q = q.where(Dose.incident_id == incident_id)
    if with_incident:
        q = q.where(Dose.incident_id.is_not(None))
    rows = (await db.execute(q.order_by(Dose.given_at.desc()))).scalars().all()
    return [_dto(d, user, level) for d in rows]


@router.post("/patients/{patient_id}/doses", response_model=list[DoseDto], status_code=status.HTTP_201_CREATED)
async def create_doses(
    patient_id: uuid.UUID,
    body: Annotated[list[DoseIn], Field(min_length=1, max_length=1000)],
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Several at once: catching up on Doses over a period (ADR 060)."""
    level = await _level(patient_id, user, db, AccessLevel.contribute)
    rows = []
    for item in body:
        row = Dose(patient_id=patient_id, owner_id=user.id)
        await _apply(row, item, patient_id, db)
        db.add(row)
        rows.append(row)
    await db.commit()
    for row in rows:
        await db.refresh(row, ["owner"])
    return [_dto(d, user, level) for d in rows]


async def _editable(dose_id: uuid.UUID, user: User, db: AsyncSession) -> tuple[Dose, AccessLevel]:
    row = (await db.execute(select(Dose).where(Dose.id == dose_id, Dose.is_deleted == False))).scalar_one_or_none()  # noqa: E712
    if not row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    level = await _level(row.patient_id, user, db, AccessLevel.contribute)
    if row.owner_id != user.id and level != AccessLevel.admin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only who entered it or an admin")
    return row, level


def _audit(db: AsyncSession, user: User, action: str, row: Dose) -> None:
    db.add(AuditLog(timestamp=datetime.now(UTC), user_id=user.id, user_name=_name(user), entity_type="Dose",
                    entity_id=str(row.id), action=action,
                    changes={"given_at": row.given_at, "given_by": row.given_by, "amount": row.amount}))


@router.put("/doses/{dose_id}", response_model=DoseDto)
async def update_dose(
    dose_id: uuid.UUID,
    body: DoseIn,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    row, level = await _editable(dose_id, user, db)
    _audit(db, user, "updated", row)
    await _apply(row, body, row.patient_id, db)
    await db.commit()
    await db.refresh(row, ["owner"])
    return _dto(row, user, level)


@router.delete("/doses/{dose_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_dose(
    dose_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    row, _ = await _editable(dose_id, user, db)
    _audit(db, user, "deleted", row)
    row.is_deleted = True
    await db.commit()
