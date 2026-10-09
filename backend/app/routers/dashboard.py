import uuid
from collections import Counter

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.access import require_patient_access
from app.core.database import get_db
from app.deps import get_current_user
from app.models.condition import Condition
from app.models.document import DocumentReference
from app.models.incident import Incident
from app.models.medication import MedicationStatement
from app.models.observation import Observation
from app.models.user import User
from app.schemas.dashboard import (
    ConditionTimelineDto,
    IncidentFrequencyDto,
    MedicationTimelineDto,
    ObservationDataPointDto,
    ObservationTrendDto,
    PatientDashboardDto,
)

router = APIRouter()


@router.get("/patients/{patient_id}/dashboard", response_model=PatientDashboardDto)
async def get_dashboard(
    patient_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await require_patient_access(patient_id, user, db)

    # Observation trends — group by code
    obs_result = await db.execute(
        select(Observation).where(Observation.patient_id == patient_id, Observation.is_deleted == False)  # noqa: E712
    )
    observations = obs_result.scalars().all()
    trends_map: dict[str, list] = {}
    for obs in observations:
        key = obs.code or obs.code_display or "unknown"
        trends_map.setdefault(key, []).append(obs)
    observation_trends = [
        ObservationTrendDto(
            code=key,
            display=items[0].code_display or key,
            unit=items[0].value_unit,
            data_points=[ObservationDataPointDto(date=o.effective_date_time or str(o.created_at)[:10], value=o.value_quantity) for o in items if o.value_quantity is not None],
        )
        for key, items in list(trends_map.items())[:5]
    ]

    # Medications
    med_result = await db.execute(
        select(MedicationStatement).where(MedicationStatement.patient_id == patient_id, MedicationStatement.is_deleted == False)  # noqa: E712
    )
    meds = med_result.scalars().all()
    medication_timeline = [
        MedicationTimelineDto(id=str(m.id), display=m.medication_display, status=m.status, start=m.effective_start, end=m.effective_end)
        for m in meds
    ]

    # Incident frequency
    inc_result = await db.execute(
        select(Incident).where(Incident.patient_id == patient_id, Incident.is_deleted == False)  # noqa: E712
    )
    incidents = inc_result.scalars().all()
    by_type = Counter(i.incident_type for i in incidents)
    incident_frequency = [IncidentFrequencyDto(type=t, count=c) for t, c in by_type.most_common(10)]

    # Document counts
    doc_result = await db.execute(
        select(func.count()).where(DocumentReference.patient_id == patient_id, DocumentReference.is_deleted == False)  # noqa: E712
    )
    total_docs = doc_result.scalar() or 0
    verified_result = await db.execute(
        select(func.count()).where(DocumentReference.patient_id == patient_id, DocumentReference.verification_status == "verified", DocumentReference.is_deleted == False)  # noqa: E712
    )
    verified_docs = verified_result.scalar() or 0

    # Conditions
    cond_result = await db.execute(
        select(Condition).where(Condition.patient_id == patient_id, Condition.is_deleted == False)  # noqa: E712
    )
    conditions = cond_result.scalars().all()
    condition_timeline = [
        ConditionTimelineDto(id=str(c.id), display=c.code_display, status=c.clinical_status, onset=c.onset_date_time, severity=c.severity)
        for c in conditions
    ]

    return PatientDashboardDto(
        observation_trends=observation_trends,
        medication_timeline=medication_timeline,
        incident_frequency=incident_frequency,
        total_documents=total_docs,
        verified_documents=verified_docs,
        condition_timeline=condition_timeline,
    )
