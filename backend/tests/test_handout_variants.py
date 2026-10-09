"""Emergency Handout and Steckbrief (ADR 048): what the family wrote goes in, the
emergency one fits a page, the Steckbrief offers Diagnoses without preselecting them.
"""

from datetime import UTC, date, datetime

from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.patient_keys import ensure_patient_kek
from app.core.security import hash_password
from app.models.access import PatientAccess
from app.models.condition import Condition
from app.models.correspondent import Correspondent
from app.models.document import DocumentReference
from app.models.medication import MedicationStatement
from app.models.observation import Observation
from app.models.organization import Organization
from app.models.patient import Patient
from app.models.user import User
from app.services.handout import render_document, render_html


async def _setup(db: AsyncSession, email="variants@t.com"):
    u = User(email=email, hashed_password=hash_password("Pass1!"), role="user",
             is_active=True, first_name="T", last_name="User")
    db.add(u)
    await db.commit()
    await db.refresh(u)
    p = Patient(given_name="Lena", family_name="Test", birth_date="2019-05-14", created_by=u.id)
    db.add(p)
    await db.commit()
    await db.refresh(p)
    db.add(PatientAccess(patient_id=p.id, user_id=u.id, access_level="admin", granted_at=datetime.now(UTC)))
    await db.commit()
    await ensure_patient_kek(db, p.id)
    await db.commit()
    return u, p


async def _auth(client: AsyncClient, email="variants@t.com") -> dict:
    r = await client.post("/api/auth/login", json={"email": email, "password": "Pass1!"})
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


async def _record(db, u, p):
    own = dict(patient_id=p.id, owner_id=u.id)
    rescue = MedicationStatement(**own, medication_display="Buccolam", dosage_text="5 mg buccal")
    gone = MedicationStatement(**own, medication_display="Gone", is_deleted=True)
    db.add_all([rescue, gone])
    org = (await db.execute(select(Organization))).scalars().first()
    if org is None:
        org = Organization()
        db.add(org)
    await db.commit()
    corr = Correspondent(name="Uniklinik Heidelberg", organization_id=org.id)
    db.add(corr)
    await db.commit()
    clinic_plan = DocumentReference(**own, description="Notfallplan der Klinik", issued_date=date(2026, 3, 1),
                                    correspondent_id=corr.id, verification_status="verified")
    db.add_all([
        clinic_plan,
        Condition(**own, code_display="Penicillin", category="allergy"),
        Condition(**own, code_display="Fokale Epilepsie"),
        Observation(**own, code="body-weight", category="measurement", value_quantity=18.4, value_unit="kg",
                    effective_date_time="2026-09-01"),
    ])
    await db.commit()
    return rescue, gone, clinic_plan


async def _plan(client, h, p, rescue, gone, clinic_plan, steps=None):
    await client.put(f"/api/patients/{p.id}/emergency-plan", headers=h, json={
        "situations": [{"trigger": "Seizure longer than 3 minutes", "steps": steps or [
            {"text": "Give rescue medication", "medication_id": str(rescue.id)},
            {"text": "Old step", "medication_id": str(gone.id)},
            {"text": "Call 112"},
        ]}],
        "contacts": [{"name": "Dr. Weber", "phone": "06221 123"}],
        "notes": "Bag is in the hallway.",
        "document_ids": [str(clinic_plan.id)],
    })


def _section(body, key):
    return next((s for s in body["sections"] if s["key"] == key), None)


async def test_the_emergency_handout_starts_with_allergies_and_weight(client: AsyncClient, db: AsyncSession):
    u, p = await _setup(db)
    h = await _auth(client)
    await _record(db, u, p)
    body = (await client.get(f"/api/patients/{p.id}/handouts/emergency", headers=h)).json()
    assert [s["key"] for s in body["sections"]][:2] == ["allergies", "weight"]
    assert "diagnoses_resolved" not in [s["key"] for s in body["sections"]]


async def test_rescue_steps_show_the_dose_from_the_record(client: AsyncClient, db: AsyncSession):
    u, p = await _setup(db)
    h = await _auth(client)
    rescue, gone, clinic_plan = await _record(db, u, p)
    await _plan(client, h, p, rescue, gone, clinic_plan)
    await client.put(f"/api/medications/{rescue.id}", headers=h, json={"dosage_text": "7.5 mg buccal"})

    body = (await client.get(f"/api/patients/{p.id}/handouts/emergency", headers=h)).json()
    situation = _section(body, "emergency_plan")["entries"][0]
    assert situation["text"] == "Seizure longer than 3 minutes"
    give, old, call = situation["items"]
    assert give == {"text": "Give rescue medication: Buccolam, 7.5 mg buccal", "flag": None}
    assert old == {"text": "Old step", "flag": "medication_deleted"}
    assert call == {"text": "Call 112", "flag": None}


async def test_documents_the_plan_points_at_are_named_with_date_and_sender(client: AsyncClient, db: AsyncSession):
    u, p = await _setup(db)
    h = await _auth(client)
    rescue, gone, clinic_plan = await _record(db, u, p)
    await _plan(client, h, p, rescue, gone, clinic_plan)
    body = (await client.get(f"/api/patients/{p.id}/handouts/emergency", headers=h)).json()
    doc = _section(body, "emergency_documents")["entries"][0]
    assert (doc["text"], doc["detail"], doc["date"]) == ("Notfallplan der Klinik", "Uniklinik Heidelberg", "2026-03-01")


async def test_the_steckbrief_offers_diagnoses_without_preselecting_them(client: AsyncClient, db: AsyncSession):
    u, p = await _setup(db)
    h = await _auth(client)
    await _record(db, u, p)
    await client.put(f"/api/patients/{p.id}/care-notes", headers=h, json={"sleep": "Night light on"})
    body = (await client.get(f"/api/patients/{p.id}/handouts/steckbrief", headers=h)).json()
    assert _section(body, "allergies")["preselected"] is True
    assert _section(body, "diagnoses_active")["preselected"] is False
    assert _section(body, "care_sleep")["entries"][0]["text"] == "Night light on"
    assert _section(body, "care_communication")["entries"] == []
    assert _section(body, "weight") is None


async def test_a_missing_plan_or_care_notes_is_named_in_the_preview_only(client: AsyncClient, db: AsyncSession):
    u, p = await _setup(db)
    h = await _auth(client)
    body = (await client.get(f"/api/patients/{p.id}/handouts/steckbrief", headers=h)).json()
    assert body["missing"] == ["emergency_plan", "care_notes"]
    html = render_html(body, "de")
    assert "Notfallplan" not in html and "Schlafen" not in html


async def test_the_emergency_handout_fits_one_page_even_when_long(client: AsyncClient, db: AsyncSession):
    u, p = await _setup(db)
    h = await _auth(client)
    rescue, gone, clinic_plan = await _record(db, u, p)
    await _plan(client, h, p, rescue, gone, clinic_plan,
                steps=[{"text": f"Step number {i} with some words to make it wrap a little"} for i in range(30)])
    body = (await client.get(f"/api/patients/{p.id}/handouts/emergency", headers=h)).json()
    assert len(render_document(body, "de", set()).pages) == 1


async def test_empty_care_notes_count_as_missing(client: AsyncClient, db: AsyncSession):
    u, p = await _setup(db)
    h = await _auth(client)
    await client.put(f"/api/patients/{p.id}/care-notes", headers=h, json={"sleep": "  "})
    body = (await client.get(f"/api/patients/{p.id}/handouts/steckbrief", headers=h)).json()
    assert "care_notes" in body["missing"]


async def test_an_unverified_plan_document_is_named_without_its_model_read_date(client: AsyncClient, db: AsyncSession):
    u, p = await _setup(db)
    h = await _auth(client)
    rescue, gone, clinic_plan = await _record(db, u, p)
    clinic_plan.verification_status = "extracted"
    await db.commit()
    await _plan(client, h, p, rescue, gone, clinic_plan)
    body = (await client.get(f"/api/patients/{p.id}/handouts/emergency", headers=h)).json()
    doc = _section(body, "emergency_documents")["entries"][0]
    assert doc["text"] == "Notfallplan der Klinik" and not doc["date"]
