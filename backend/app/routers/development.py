"""ADR 063: Abilities are observed, never assessed; Test Attempts record how a test went."""

import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.access import AccessLevel
from app.core.database import get_db
from app.deps import get_current_user
from app.models.audit import AuditLog
from app.models.correspondent import Correspondent
from app.models.development import Ability, AbilityObservation, TestAttempt, no_longer
from app.models.document import DocumentReference
from app.models.medication import MedicationStatement
from app.models.user import User
from app.routers.doses import _level, _name
from app.schemas.development import (
    AbilityDto,
    AbilityIn,
    AbilityObservationDto,
    AbilityObservationIn,
    TestAttemptDto,
    TestAttemptIn,
)

router = APIRouter()


def _can_edit(row, user: User, level: AccessLevel | None) -> bool:
    return row.owner_id == user.id or level == AccessLevel.admin


def _obs_dto(o: AbilityObservation, user: User, level: AccessLevel | None, lapsed: set[uuid.UUID]) -> AbilityObservationDto:
    return AbilityObservationDto(id=o.id, ability_id=o.ability_id, observed_on=o.observed_on, place=o.place, works=o.works,
                                 with_help=o.with_help, no_longer=o.id in lapsed, note=o.note, source=o.source,
                                 document_id=o.document_id, entered_by=_name(o.owner), can_edit=_can_edit(o, user, level))


def _audit(db: AsyncSession, user: User, action: str, entity: str, row_id: uuid.UUID, changes: dict) -> None:
    db.add(AuditLog(timestamp=datetime.now(UTC), user_id=user.id, user_name=_name(user), entity_type=entity,
                    entity_id=str(row_id), action=action, changes=changes))


async def _editable(model, row_id: uuid.UUID, user: User, db: AsyncSession):
    row = (await db.execute(select(model).where(model.id == row_id, model.is_deleted.is_(False)))).unique().scalar_one_or_none()
    if not row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    level = await _level(row.patient_id, user, db, AccessLevel.contribute)
    if not _can_edit(row, user, level):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only who entered it or an admin")
    return row, level


async def _check_document(document_id: uuid.UUID | None, patient_id: uuid.UUID, db: AsyncSession) -> None:
    if document_id and not (await db.execute(select(DocumentReference.id).where(
            DocumentReference.id == document_id, DocumentReference.patient_id == patient_id,
            DocumentReference.is_deleted.is_(False)))).scalar_one_or_none():
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail="Unknown document")


# --- Abilities ---------------------------------------------------------------

async def _ability_named(patient_id: uuid.UUID, name: str, db: AsyncSession) -> Ability | None:
    return (await db.execute(select(Ability).where(
        Ability.patient_id == patient_id, Ability.is_deleted.is_(False),
        func.lower(Ability.name) == name.lower()))).scalar_one_or_none()


async def _drop_if_empty(ability_id: uuid.UUID, db: AsyncSession) -> None:
    # an Ability exists through its Observations; without one it has nothing to say
    left = (await db.execute(select(func.count()).where(
        AbilityObservation.ability_id == ability_id, AbilityObservation.is_deleted.is_(False)))).scalar_one()
    if not left:
        ability = await db.get(Ability, ability_id)
        ability.is_deleted = True


@router.get("/patients/{patient_id}/abilities", response_model=list[AbilityDto])
async def list_abilities(patient_id: uuid.UUID, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    level = await _level(patient_id, user, db, AccessLevel.view)
    rows = (await db.execute(select(Ability).where(Ability.patient_id == patient_id, Ability.is_deleted.is_(False))
                             .order_by(func.lower(Ability.name)))).scalars().all()
    out = []
    for a in rows:
        lapsed = no_longer(a.observations)
        out.append(AbilityDto(id=a.id, name=a.name, domain=a.domain, can_edit=_can_edit(a, user, level),
                              observations=[_obs_dto(o, user, level, lapsed) for o in a.observations]))
    return out


async def _apply_observation(row: AbilityObservation, body: AbilityObservationIn, user: User, db: AsyncSession) -> None:
    ability = await _ability_named(row.patient_id, body.ability_name, db)
    if not ability:
        ability = Ability(patient_id=row.patient_id, owner_id=user.id, name=body.ability_name, domain=body.domain)
        db.add(ability)
        await db.flush()
    row.ability_id = ability.id
    row.observed_on = body.observed_on
    row.place = body.place
    row.works = body.works
    row.with_help = body.with_help
    row.note = (body.note or "").strip() or None


async def _observation_out(row: AbilityObservation, user: User, level: AccessLevel, db: AsyncSession) -> AbilityObservationDto:
    await db.commit()
    await db.refresh(row, ["owner", "ability"])
    await db.refresh(row.ability, ["observations"])
    return _obs_dto(row, user, level, no_longer(row.ability.observations))


@router.post("/patients/{patient_id}/ability-observations", response_model=AbilityObservationDto,
             status_code=status.HTTP_201_CREATED)
async def create_observation(patient_id: uuid.UUID, body: AbilityObservationIn, user: User = Depends(get_current_user),
                             db: AsyncSession = Depends(get_db)):
    level = await _level(patient_id, user, db, AccessLevel.contribute)
    row = AbilityObservation(patient_id=patient_id, owner_id=user.id, source="family")
    await _apply_observation(row, body, user, db)
    db.add(row)
    return await _observation_out(row, user, level, db)


@router.put("/ability-observations/{observation_id}", response_model=AbilityObservationDto)
async def update_observation(observation_id: uuid.UUID, body: AbilityObservationIn, user: User = Depends(get_current_user),
                             db: AsyncSession = Depends(get_db)):
    row, level = await _editable(AbilityObservation, observation_id, user, db)
    before = row.ability_id
    _audit(db, user, "updated", "AbilityObservation", row.id, {"ability": row.ability.name, "observed_on": row.observed_on})
    await _apply_observation(row, body, user, db)
    await db.flush()
    if row.ability_id != before:
        await _drop_if_empty(before, db)
    return await _observation_out(row, user, level, db)


@router.delete("/ability-observations/{observation_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_observation(observation_id: uuid.UUID, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    row, _ = await _editable(AbilityObservation, observation_id, user, db)
    _audit(db, user, "deleted", "AbilityObservation", row.id, {"ability": row.ability.name, "observed_on": row.observed_on})
    row.is_deleted = True
    await db.flush()
    await _drop_if_empty(row.ability_id, db)
    await db.commit()


@router.put("/abilities/{ability_id}", response_model=AbilityDto)
async def update_ability(ability_id: uuid.UUID, body: AbilityIn, user: User = Depends(get_current_user),
                         db: AsyncSession = Depends(get_db)):
    row, level = await _editable(Ability, ability_id, user, db)
    same = await _ability_named(row.patient_id, body.name, db)
    if same and same.id != row.id:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="An Ability with this name exists")
    _audit(db, user, "updated", "Ability", row.id, {"name": row.name, "domain": row.domain})
    row.name, row.domain = body.name, body.domain
    await db.commit()
    await db.refresh(row, ["observations"])
    lapsed = no_longer(row.observations)
    return AbilityDto(id=row.id, name=row.name, domain=row.domain, can_edit=True,
                      observations=[_obs_dto(o, user, level, lapsed) for o in row.observations])


# --- Test Attempts -----------------------------------------------------------

def _on_day(m: MedicationStatement, day: str) -> bool:
    # compared at the precision of the attempt: a month-only attempt matches a plan running in that month
    start, end = (m.effective_start or "")[:len(day)], (m.effective_end or "")[:len(day)]
    return bool(start) and start <= day and (not end or end >= day)


def _test_dto(t: TestAttempt, user: User, level: AccessLevel | None, meds: list[MedicationStatement]) -> TestAttemptDto:
    return TestAttemptDto(id=t.id, test_name=t.test_name, attempted_on=t.attempted_on, correspondent_id=t.correspondent_id,
                          correspondent_name=t.correspondent.name if t.correspondent else None, setting=t.setting,
                          duration_minutes=t.duration_minutes, outcome=t.outcome, reason=t.reason, document_id=t.document_id,
                          medications=sorted({m.medication_display for m in meds if _on_day(m, t.attempted_on)}),
                          entered_by=_name(t.owner), can_edit=_can_edit(t, user, level))


async def _meds(patient_id: uuid.UUID, db: AsyncSession) -> list[MedicationStatement]:
    return list((await db.execute(select(MedicationStatement).where(
        MedicationStatement.patient_id == patient_id, MedicationStatement.is_deleted.is_(False)))).scalars().all())


async def _apply_test(row: TestAttempt, body: TestAttemptIn, db: AsyncSession) -> None:
    if body.correspondent_id and not (await db.execute(select(Correspondent.id).where(
            Correspondent.id == body.correspondent_id, Correspondent.is_deleted.is_(False)))).scalar_one_or_none():
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail="Unknown correspondent")
    await _check_document(body.document_id, row.patient_id, db)
    row.test_name = body.test_name
    row.attempted_on = body.attempted_on
    row.correspondent_id = body.correspondent_id
    row.setting = body.setting
    row.duration_minutes = body.duration_minutes
    row.outcome = body.outcome
    row.reason = (body.reason or "").strip() or None
    row.document_id = body.document_id


async def _test_out(row: TestAttempt, user: User, level: AccessLevel, db: AsyncSession) -> TestAttemptDto:
    await db.commit()
    await db.refresh(row, ["owner", "correspondent"])
    return _test_dto(row, user, level, await _meds(row.patient_id, db))


@router.get("/patients/{patient_id}/test-attempts", response_model=list[TestAttemptDto])
async def list_test_attempts(patient_id: uuid.UUID, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    level = await _level(patient_id, user, db, AccessLevel.view)
    rows = (await db.execute(select(TestAttempt).where(TestAttempt.patient_id == patient_id, TestAttempt.is_deleted.is_(False))
                             .order_by(TestAttempt.attempted_on.desc()))).scalars().all()
    meds = await _meds(patient_id, db)
    return [_test_dto(t, user, level, meds) for t in rows]


@router.post("/patients/{patient_id}/test-attempts", response_model=TestAttemptDto, status_code=status.HTTP_201_CREATED)
async def create_test_attempt(patient_id: uuid.UUID, body: TestAttemptIn, user: User = Depends(get_current_user),
                              db: AsyncSession = Depends(get_db)):
    level = await _level(patient_id, user, db, AccessLevel.contribute)
    row = TestAttempt(patient_id=patient_id, owner_id=user.id)
    await _apply_test(row, body, db)
    db.add(row)
    return await _test_out(row, user, level, db)


@router.put("/test-attempts/{attempt_id}", response_model=TestAttemptDto)
async def update_test_attempt(attempt_id: uuid.UUID, body: TestAttemptIn, user: User = Depends(get_current_user),
                              db: AsyncSession = Depends(get_db)):
    row, level = await _editable(TestAttempt, attempt_id, user, db)
    _audit(db, user, "updated", "TestAttempt", row.id, {"test_name": row.test_name, "attempted_on": row.attempted_on})
    await _apply_test(row, body, db)
    return await _test_out(row, user, level, db)


@router.delete("/test-attempts/{attempt_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_test_attempt(attempt_id: uuid.UUID, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    row, _ = await _editable(TestAttempt, attempt_id, user, db)
    _audit(db, user, "deleted", "TestAttempt", row.id, {"test_name": row.test_name, "attempted_on": row.attempted_on})
    row.is_deleted = True
    await db.commit()
