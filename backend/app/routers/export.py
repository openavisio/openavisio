import json
import logging
import re
import tempfile
import uuid
import zipfile
from datetime import UTC, datetime

from fastapi import APIRouter, Depends
from fastapi.responses import Response, StreamingResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.access import require_patient_access
from app.core.database import get_db
from app.core.encryption import decrypt_document
from app.core.patient_keys import get_patient_kek
from app.core.storage import get_storage
from app.models.audit import AuditLog
from app.deps import get_current_user
from app.models.calendar import CalendarEvent
from app.models.chat import ChatMessage
from app.models.condition import Condition
from app.models.document import DocumentReference
from app.models.emergency_plan import EmergencyPlan
from app.models.incident import Incident
from app.models.intake import HistoryFact
from app.models.medication import MedicationStatement
from app.models.observation import Observation
from app.models.patient import Patient
from app.models.recommendation import Recommendation
from app.models.diary import DiaryEntry
from app.models.user import User

router = APIRouter()
log = logging.getLogger(__name__)

_PATIENT_REF = lambda pid: {"reference": f"urn:uuid:{pid}"}  # noqa: E731


@router.get("/patients/{patient_id}/export/fhir")
async def export_fhir(
    patient_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await require_patient_access(patient_id, user, db)
    return Response(
        content=json.dumps(await _bundle(patient_id, db), indent=2),
        media_type="application/fhir+json",
        headers={"Content-Disposition": f'attachment; filename="patient-{patient_id}-fhir.json"'},
    )


@router.get("/patients/{patient_id}/export/zip")
async def export_zip(
    patient_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Everything a family takes with it (ADR 052): the FHIR bundle and every Document as its file."""
    await require_patient_access(patient_id, user, db)
    bundle = await _bundle(patient_id, db)
    docs = (await db.execute(select(DocumentReference).where(
        DocumentReference.patient_id == patient_id, DocumentReference.is_deleted == False,  # noqa: E712
        DocumentReference.storage_path != None,  # noqa: E711
    ).order_by(DocumentReference.created_at))).scalars().all()
    kek = await get_patient_kek(db, patient_id) if docs else None

    # a temp file, not memory: a record with years of scans would not fit next to five Deployments
    out = tempfile.TemporaryFile()
    used: set[str] = set()
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("fhir.json", json.dumps(bundle, indent=2))
        missing = []
        for doc in docs:
            name = _unique(f"documents/{_safe(doc.file_name or str(doc.id))}", used)
            try:
                zf.writestr(name, decrypt_document(get_storage().read(doc.storage_path), doc.encrypted_dek, kek))
            except Exception:  # one unreadable file must not cost the family the rest of its export
                log.exception("export: document %s unreadable", doc.id)
                missing.append(name)
        if missing:
            zf.writestr("documents/MISSING.txt", "These documents could not be read:\n" + "\n".join(missing) + "\n")
    out.seek(0)

    name = " ".join(filter(None, [user.first_name, user.last_name])) or user.email
    db.add(AuditLog(timestamp=datetime.now(UTC), user_id=user.id, user_name=name, entity_type="Patient",
                    entity_id=str(patient_id), action="exported", changes={"documents": len(docs)}))
    await db.commit()

    def chunks():
        with out:
            while block := out.read(1 << 20):
                yield block
    return StreamingResponse(chunks(), media_type="application/zip",
                             headers={"Content-Disposition": f'attachment; filename="openavisio-{patient_id}.zip"'})


def _safe(name: str) -> str:
    return re.sub(r'[\\/:*?"<>|\x00-\x1f]', "_", name).strip(". ") or "document"


def _unique(path: str, used: set[str]) -> str:
    stem, dot, ext = path.rpartition(".") if "." in path.rsplit("/", 1)[-1] else (path, "", "")
    candidate, n = path, 2
    while candidate in used:
        candidate, n = f"{stem} ({n}){dot}{ext}", n + 1
    used.add(candidate)
    return candidate


async def _bundle(patient_id: uuid.UUID, db: AsyncSession) -> dict:
    entries = []

    # --- Patient ---
    patient_result = await db.execute(
        select(Patient).where(Patient.id == patient_id, Patient.is_deleted == False)  # noqa: E712
    )
    patient = patient_result.scalar_one_or_none()
    if patient:
        entries.append({
            "fullUrl": f"urn:uuid:{patient.id}",
            "resource": {
                "resourceType": "Patient",
                "id": str(patient.id),
                "name": [{"family": patient.family_name, "given": [patient.given_name]}],
                "birthDate": str(patient.birth_date) if patient.birth_date else None,
                "gender": patient.gender,
            },
        })

    pid = patient_id

    # --- Observations (Measurements + Lab Results) ---
    for obs in (await db.execute(
        select(Observation).where(Observation.patient_id == pid, Observation.is_deleted == False)  # noqa: E712
    )).scalars().all():
        entries.append({
            "fullUrl": f"urn:uuid:{obs.id}",
            "resource": {
                "resourceType": "Observation",
                "id": str(obs.id),
                "status": obs.status or "final",
                "category": [{"coding": [{"code": obs.category}]}] if obs.category else [],
                "code": {
                    "text": obs.code_display,
                    "coding": [{"code": obs.code}] if obs.code else [],
                },
                "subject": _PATIENT_REF(pid),
                "effectiveDateTime": obs.effective_date_time,
                "valueQuantity": {"value": obs.value_quantity, "unit": obs.value_unit} if obs.value_quantity is not None else None,
                "valueString": obs.value_string,
            },
        })

    # --- Conditions (Diagnoses) ---
    for cond in (await db.execute(
        select(Condition).where(Condition.patient_id == pid, Condition.is_deleted == False)  # noqa: E712
    )).scalars().all():
        entries.append({
            "fullUrl": f"urn:uuid:{cond.id}",
            "resource": {
                "resourceType": "Condition",
                "id": str(cond.id),
                "subject": _PATIENT_REF(pid),
                "code": {"text": cond.code_display, "coding": [{"code": cond.code}] if cond.code else []},
                "clinicalStatus": {"coding": [{"code": cond.clinical_status}]} if cond.clinical_status else None,
                "verificationStatus": {"coding": [{"code": cond.verification_status}]} if cond.verification_status else None,
                "severity": {"text": cond.severity} if cond.severity else None,
                "onsetDateTime": cond.onset_date_time,
            },
        })

    # --- MedicationStatements (Medications) ---
    for med in (await db.execute(
        select(MedicationStatement).where(MedicationStatement.patient_id == pid, MedicationStatement.is_deleted == False)  # noqa: E712
    )).scalars().all():
        entries.append({
            "fullUrl": f"urn:uuid:{med.id}",
            "resource": {
                "resourceType": "MedicationStatement",
                "id": str(med.id),
                "status": med.status or "active",
                "subject": _PATIENT_REF(pid),
                "medicationCodeableConcept": {"text": med.medication_display},
                "dosage": [{"text": med.dosage_text}] if med.dosage_text else [],
            },
        })

    # --- AdverseEvents (Incidents) ---
    for inc in (await db.execute(
        select(Incident).where(Incident.patient_id == pid, Incident.is_deleted == False)  # noqa: E712
    )).scalars().all():
        entries.append({
            "fullUrl": f"urn:uuid:{inc.id}",
            "resource": {
                "resourceType": "AdverseEvent",
                "id": str(inc.id),
                "actuality": "actual",
                "subject": _PATIENT_REF(pid),
                "event": {"text": inc.incident_type_display or inc.incident_type},
                "date": inc.occurred_at,
                "severity": {"text": inc.severity} if inc.severity else None,
                "outcome": {"text": inc.outcome} if inc.outcome else None,
                "description": inc.note,
                "suspectEntity": [{"instance": {"display": t.strip()}} for t in (inc.suspected_trigger or "").split(",") if t.strip()],
            },
        })

    # --- Appointments (Events / CalendarEvents) ---
    for evt in (await db.execute(
        select(CalendarEvent).where(CalendarEvent.patient_id == pid, CalendarEvent.is_deleted == False)  # noqa: E712
    )).scalars().all():
        entries.append({
            "fullUrl": f"urn:uuid:{evt.id}",
            "resource": {
                "resourceType": "Appointment",
                "id": str(evt.id),
                "status": evt.status or "booked",
                "description": evt.title,
                "comment": evt.purpose,
                "start": evt.start_at,
                "end": evt.end_at,
                "participant": [{"actor": _PATIENT_REF(pid), "status": "accepted"}],
                "serviceType": [{"text": evt.provider}] if evt.provider else [],
                "location": [{"location": {"display": evt.location}}] if evt.location else [],
            },
        })

    # --- Observations (Health Logs / DiaryEntries, category: survey) ---
    # diary notes are ciphertext at rest (ADR-031); decrypt for the export
    from app.core.encryption import decrypt_str
    from app.core.patient_keys import get_patient_kek
    try:
        _diary_kek = await get_patient_kek(db, pid)
    except KeyError:
        _diary_kek = None  # patient never had encrypted free text
    for entry in (await db.execute(
        select(DiaryEntry).where(DiaryEntry.patient_id == pid, DiaryEntry.is_deleted == False)  # noqa: E712
    )).scalars().all():
        components = []
        _field = lambda code, display, val: components.append({  # noqa: E731
            "code": {"text": display},
            "valueInteger": val,
        }) if val is not None else None
        _field("mood", "Mood", entry.mood)
        _field("pain", "Pain Level", entry.pain_level)
        _field("mobility", "Mobility", entry.mobility)
        _field("sleep-quality", "Sleep Quality", entry.sleep_quality)
        if entry.sleep_hours is not None:
            components.append({"code": {"text": "Sleep Hours"}, "valueQuantity": {"value": entry.sleep_hours, "unit": "h"}})
        if entry.bowel_movement is not None:
            components.append({"code": {"text": "Bowel Movement"}, "valueBoolean": entry.bowel_movement})
        if entry.medication_compliance is not None:
            components.append({"code": {"text": "Medication Compliance"}, "valueBoolean": entry.medication_compliance})
        if entry.nutrition_notes:
            components.append({"code": {"text": "Nutrition Notes"}, "valueString": decrypt_str(entry.nutrition_notes, _diary_kek)})
        if entry.general_notes:
            components.append({"code": {"text": "General Notes"}, "valueString": decrypt_str(entry.general_notes, _diary_kek)})

        effective = entry.entry_date
        if entry.entry_time:
            effective = f"{entry.entry_date}T{entry.entry_time}"

        entries.append({
            "fullUrl": f"urn:uuid:{entry.id}",
            "resource": {
                "resourceType": "Observation",
                "id": str(entry.id),
                "status": "final",
                "category": [{"coding": [{"system": "http://terminology.hl7.org/CodeSystem/observation-category", "code": "survey"}]}],
                "code": {"text": entry.subject or "Daily Health Log"},
                "subject": _PATIENT_REF(pid),
                "effectiveDateTime": effective,
                "component": components,
            },
        })

    # --- Observations (History Facts, ADR 047): all of them, visit-only included ---
    for fact in (await db.execute(
        select(HistoryFact).where(HistoryFact.patient_id == pid, HistoryFact.is_deleted == False)  # noqa: E712
    )).scalars().all():
        entries.append({
            "fullUrl": f"urn:uuid:{fact.id}",
            "resource": {
                "resourceType": "Observation",
                "id": str(fact.id),
                "status": "final",
                "category": [{"coding": [{"system": "http://terminology.hl7.org/CodeSystem/observation-category", "code": "survey"}]}],
                "code": {"text": fact.question},
                "subject": _PATIENT_REF(pid),
                "effectiveDateTime": fact.confirmed_on,
                "valueString": fact.answer,
                "note": [{"text": f"History fact, {fact.aging.replace('_', '-')}, source: {fact.source}"}],
            },
        })

    # --- Tasks (Recommendations) ---
    for rec in (await db.execute(
        select(Recommendation).where(Recommendation.patient_id == pid, Recommendation.is_deleted == False)  # noqa: E712
    )).scalars().all():
        entries.append({
            "fullUrl": f"urn:uuid:{rec.id}",
            "resource": {
                "resourceType": "Task",
                "id": str(rec.id),
                "status": rec.status or "requested",
                "intent": "proposal",
                "for": _PATIENT_REF(pid),
                "description": rec.text,
            },
        })

    # --- Communications (AI Health Assistant messages) ---
    for msg in (await db.execute(
        select(ChatMessage).where(ChatMessage.patient_id == pid)
    )).scalars().all():
        entries.append({
            "fullUrl": f"urn:uuid:{msg.id}",
            "resource": {
                "resourceType": "Communication",
                "id": str(msg.id),
                "status": "completed",
                "subject": _PATIENT_REF(pid),
                "sender": {"display": "AI Health Assistant"} if msg.role == "assistant" else _PATIENT_REF(pid),
                # chat content is ciphertext at rest (ADR-031); _diary_kek is the same patient KEK
                "payload": [{"contentString": decrypt_str(msg.content, _diary_kek)}],
            },
        })

    # --- DocumentReferences (Document metadata) ---
    for doc in (await db.execute(
        select(DocumentReference).where(DocumentReference.patient_id == pid, DocumentReference.is_deleted == False)  # noqa: E712
    )).scalars().all():
        entries.append({
            "fullUrl": f"urn:uuid:{doc.id}",
            "resource": {
                "resourceType": "DocumentReference",
                "id": str(doc.id),
                "status": "current",
                "subject": _PATIENT_REF(pid),
                "date": str(doc.issued_date) if doc.issued_date else None,
                "description": doc.description,
                "type": {"text": doc.type} if doc.type else None,
                "content": [{"attachment": {"title": doc.file_name, "contentType": doc.content_type}}],
            },
        })

    # --- CarePlan (Emergency Plan, ADR 048) ---
    plan = (await db.execute(select(EmergencyPlan).where(EmergencyPlan.patient_id == pid))).scalar_one_or_none()
    if plan:
        exported = {e["fullUrl"] for e in entries}
        refs = [f"urn:uuid:{r}" for r in dict.fromkeys(
            [s["medication_id"] for sit in plan.situations for s in sit["steps"] if s.get("medication_id")] + plan.document_ids)]
        notes = [t for t in [*(", ".join(filter(None, [c["name"], c.get("role"), c.get("phone")])) for c in plan.contacts),
                             plan.notes] if t]
        care_plan = {
            "fullUrl": f"urn:uuid:{plan.id}",
            "resource": {
                "resourceType": "CarePlan",
                "id": str(plan.id),
                "status": "active",
                "intent": "plan",
                "title": "Emergency Plan",
                "subject": _PATIENT_REF(pid),
                "activity": [{"detail": {
                    "status": "not-started",
                    "description": f"{sit['trigger']}: " + " ".join(f"{i}. {s['text']}" for i, s in enumerate(sit["steps"], 1)),
                }} for sit in plan.situations],
                # FHIR forbids empty arrays, and a reference must resolve inside the bundle
                "supportingInfo": [{"reference": r} for r in refs if r in exported],
                "note": [{"text": t} for t in notes],
            },
        }
        care_plan["resource"] = {k: v for k, v in care_plan["resource"].items() if v != []}
        entries.append(care_plan)

    # GDPR governance metadata: lawful basis + retention per data category (#15/#16)
    from app.models.governance import DataCategory
    cats = (await db.execute(select(DataCategory).order_by(DataCategory.label))).scalars().all()
    governance = {
        "categories": [
            {
                "code": c.code,
                "label": c.label,
                "lawful_basis": c.lawful_basis,
                "retention_days": c.retention_days,
            }
            for c in cats
        ],
    }

    return {
        "resourceType": "Bundle",
        "type": "collection",
        "timestamp": datetime.now(UTC).replace(tzinfo=None).isoformat() + "Z",
        "total": len(entries),
        "entry": entries,
        "_governance": governance,
    }

