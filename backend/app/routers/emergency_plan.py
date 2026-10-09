import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.access import AccessLevel, require_patient_access
from app.core.database import get_db
from app.deps import get_current_user
from app.models.document import DocumentReference
from app.models.emergency_plan import EmergencyPlan
from app.models.medication import MedicationStatement
from app.models.user import User
from app.routers.medications import medication_to_dto
from app.schemas.document import DocumentDto
from app.schemas.emergency_plan import EmergencyPlanDto, EmergencyPlanIn

router = APIRouter()


def _medication_ids(situations: list[dict]) -> set[str]:
    return {s["medication_id"] for sit in situations for s in sit["steps"] if s.get("medication_id")}


async def _patient_rows(db, model, patient_id, ids, live_only=True) -> dict:
    if not ids:
        return {}
    q = select(model).where(model.id.in_(ids), model.patient_id == patient_id)
    if live_only:
        q = q.where(model.is_deleted == False)  # noqa: E712
    return {str(r.id): r for r in (await db.execute(q)).scalars().all()}


async def plan_to_dto(plan: EmergencyPlan, db) -> EmergencyPlanDto:
    meds = await _patient_rows(db, MedicationStatement, plan.patient_id, _medication_ids(plan.situations))
    docs = await _patient_rows(db, DocumentReference, plan.patient_id, plan.document_ids)
    return EmergencyPlanDto(
        situations=[
            {**sit, "steps": [
                {**s, "medication": medication_to_dto(meds[s["medication_id"]]) if s.get("medication_id") in meds else None}
                for s in sit["steps"]
            ]}
            for sit in plan.situations
        ],
        contacts=plan.contacts,
        notes=plan.notes,
        documents=[DocumentDto.model_validate(docs[i]) for i in plan.document_ids if i in docs],
    )


async def _plan_of(patient_id, db) -> EmergencyPlan | None:
    result = await db.execute(select(EmergencyPlan).where(EmergencyPlan.patient_id == patient_id))
    return result.scalar_one_or_none()


@router.get("/patients/{patient_id}/emergency-plan", response_model=EmergencyPlanDto | None)
async def get_emergency_plan(
    patient_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await require_patient_access(patient_id, user, db)
    plan = await _plan_of(patient_id, db)
    return await plan_to_dto(plan, db) if plan else None


@router.put("/patients/{patient_id}/emergency-plan", response_model=EmergencyPlanDto)
async def save_emergency_plan(
    patient_id: uuid.UUID,
    body: EmergencyPlanIn,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await require_patient_access(patient_id, user, db, AccessLevel.contribute)
    data = body.model_dump(mode="json")
    # deleted rows of this Patient may stay pointed at, so a step keeps showing its Medication is gone
    med_ids, doc_ids = _medication_ids(data["situations"]), set(data["document_ids"])
    meds_ok = len(await _patient_rows(db, MedicationStatement, patient_id, med_ids, live_only=False)) == len(med_ids)
    docs_ok = len(await _patient_rows(db, DocumentReference, patient_id, doc_ids, live_only=False)) == len(doc_ids)
    if not (meds_ok and docs_ok):
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Unknown medication or document")

    plan = await _plan_of(patient_id, db)
    if not plan:
        plan = EmergencyPlan(patient_id=patient_id, owner_id=user.id)
        db.add(plan)
    plan.situations, plan.contacts, plan.notes, plan.document_ids = (
        data["situations"], data["contacts"], data["notes"], data["document_ids"])
    await db.commit()
    await db.refresh(plan)
    return await plan_to_dto(plan, db)
