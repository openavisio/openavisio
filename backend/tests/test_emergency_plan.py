"""The Emergency Plan through the API (ADR 048): one per Patient, written by a
Caregiver, and a step that gives a rescue medication shows the dose from the record.
"""

from datetime import UTC, date, datetime

from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.patient_keys import ensure_patient_kek
from app.core.security import hash_password
from app.models.access import PatientAccess
from app.models.document import DocumentReference
from app.models.emergency_plan import EmergencyPlan
from app.models.medication import MedicationStatement
from app.models.patient import Patient
from app.models.user import User


async def _setup(db: AsyncSession, email="notfall@t.com"):
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


async def _auth(client: AsyncClient, email="notfall@t.com") -> dict:
    r = await client.post("/api/auth/login", json={"email": email, "password": "Pass1!"})
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


async def _med(db, u, p, **kw) -> MedicationStatement:
    m = MedicationStatement(patient_id=p.id, owner_id=u.id, medication_display="Buccolam",
                            dosage_text="5 mg buccal", **kw)
    db.add(m)
    await db.commit()
    await db.refresh(m)
    return m


def _plan(med_id=None, doc_ids=()):
    return {
        "situations": [{
            "trigger": "Seizure longer than 3 minutes",
            "steps": [
                {"text": "Lay her on her side"},
                {"text": "Give rescue medication", "medication_id": str(med_id) if med_id else None},
                {"text": "Call 112"},
            ],
        }],
        "contacts": [{"name": "Dr. Weber", "role": "Neuropediatrics", "phone": "06221 123"}],
        "notes": "Bag with medication is in the hallway.",
        "document_ids": [str(d) for d in doc_ids],
    }


async def test_no_plan_yet_reads_as_null(client: AsyncClient, db: AsyncSession):
    _, p = await _setup(db)
    h = await _auth(client)
    r = await client.get(f"/api/patients/{p.id}/emergency-plan", headers=h)
    assert r.status_code == 200
    assert r.json() is None


async def test_a_plan_is_written_and_rewritten(client: AsyncClient, db: AsyncSession):
    """One per Patient: saving again replaces, it never adds a second plan."""
    _, p = await _setup(db)
    h = await _auth(client)
    r = await client.put(f"/api/patients/{p.id}/emergency-plan", headers=h, json=_plan())
    assert r.status_code == 200
    body = r.json()
    assert [s["text"] for s in body["situations"][0]["steps"]] == [
        "Lay her on her side", "Give rescue medication", "Call 112"]
    assert body["contacts"][0]["phone"] == "06221 123"

    edited = _plan()
    edited["situations"] = []
    edited["contacts"].append({"name": "Grandma", "phone": "0170 1"})
    await client.put(f"/api/patients/{p.id}/emergency-plan", headers=h, json=edited)

    body = (await client.get(f"/api/patients/{p.id}/emergency-plan", headers=h)).json()
    assert body["situations"] == []
    assert [c["name"] for c in body["contacts"]] == ["Dr. Weber", "Grandma"]
    rows = (await db.execute(select(EmergencyPlan).where(EmergencyPlan.patient_id == p.id))).all()
    assert len(rows) == 1


async def test_a_step_shows_the_current_dose_of_its_medication(client: AsyncClient, db: AsyncSession):
    """The dose has one home: changing the Medication changes what the plan shows."""
    u, p = await _setup(db)
    h = await _auth(client)
    m = await _med(db, u, p)
    await client.put(f"/api/patients/{p.id}/emergency-plan", headers=h, json=_plan(m.id))

    await client.put(f"/api/medications/{m.id}", headers=h, json={"dosage_text": "7.5 mg buccal"})

    step = (await client.get(f"/api/patients/{p.id}/emergency-plan", headers=h)).json()["situations"][0]["steps"][1]
    assert step["medication"]["dosage_text"] == "7.5 mg buccal"
    assert step["medication"]["is_active"] is True


async def test_a_stopped_medication_is_reported_as_stopped(client: AsyncClient, db: AsyncSession):
    u, p = await _setup(db)
    h = await _auth(client)
    m = await _med(db, u, p, status="stopped", effective_end=str(date.today()))
    await client.put(f"/api/patients/{p.id}/emergency-plan", headers=h, json=_plan(m.id))
    step = (await client.get(f"/api/patients/{p.id}/emergency-plan", headers=h)).json()["situations"][0]["steps"][1]
    assert step["medication"]["is_active"] is False


async def test_a_deleted_medication_leaves_no_stale_dose(client: AsyncClient, db: AsyncSession):
    """The step keeps saying it points at a Medication, but shows none."""
    u, p = await _setup(db)
    h = await _auth(client)
    m = await _med(db, u, p)
    await client.put(f"/api/patients/{p.id}/emergency-plan", headers=h, json=_plan(m.id))
    await client.delete(f"/api/medications/{m.id}", headers=h)

    step = (await client.get(f"/api/patients/{p.id}/emergency-plan", headers=h)).json()["situations"][0]["steps"][1]
    assert step["medication_id"] == str(m.id)
    assert step["medication"] is None


async def test_documents_are_listed_with_date_and_sender(client: AsyncClient, db: AsyncSession):
    u, p = await _setup(db)
    h = await _auth(client)
    d = DocumentReference(patient_id=p.id, owner_id=u.id, description="Notfallplan Neuropädiatrie",
                          issued_date=date(2026, 3, 1), detected_provider="Uniklinik Heidelberg")
    db.add(d)
    await db.commit()
    await db.refresh(d)
    await client.put(f"/api/patients/{p.id}/emergency-plan", headers=h, json=_plan(doc_ids=[d.id]))

    docs = (await client.get(f"/api/patients/{p.id}/emergency-plan", headers=h)).json()["documents"]
    assert [(x["id"], x["issued_date"], x["detected_provider"]) for x in docs] == [
        (str(d.id), "2026-03-01", "Uniklinik Heidelberg")]


async def test_another_patients_medication_or_document_is_refused(client: AsyncClient, db: AsyncSession):
    """Otherwise the plan would show another person's dose or file."""
    u, p = await _setup(db)
    h = await _auth(client)
    other = Patient(given_name="Max", family_name="Other", birth_date="2018-01-01", created_by=u.id)
    db.add(other)
    await db.commit()
    await db.refresh(other)
    m = await _med(db, u, other)
    d = DocumentReference(patient_id=other.id, owner_id=u.id, description="x")
    db.add(d)
    await db.commit()
    await db.refresh(d)

    r1 = await client.put(f"/api/patients/{p.id}/emergency-plan", headers=h, json=_plan(m.id))
    r2 = await client.put(f"/api/patients/{p.id}/emergency-plan", headers=h, json=_plan(doc_ids=[d.id]))
    assert r1.status_code == 422 and r2.status_code == 422


async def test_without_access_the_plan_is_unreachable(client: AsyncClient, db: AsyncSession):
    _, p = await _setup(db)
    await _setup(db, email="stranger@t.com")
    h = await _auth(client, email="stranger@t.com")
    assert (await client.get(f"/api/patients/{p.id}/emergency-plan", headers=h)).status_code in (403, 404)
    assert (await client.put(f"/api/patients/{p.id}/emergency-plan", headers=h, json=_plan())).status_code in (403, 404)


async def test_patient_erasure_deletes_the_plan(client: AsyncClient, db: AsyncSession):
    u, p = await _setup(db)
    h = await _auth(client)
    await client.put(f"/api/patients/{p.id}/emergency-plan", headers=h, json=_plan())

    from app.services.erasure import erase_patient
    await erase_patient(p.id, u, db)
    await db.commit()

    rows = await db.execute(select(EmergencyPlan).where(EmergencyPlan.patient_id == p.id))
    assert rows.first() is None


async def test_the_plan_still_saves_after_a_steps_medication_was_deleted(client: AsyncClient, db: AsyncSession):
    """The dead pointer stays, so the step keeps saying its Medication is gone."""
    u, p = await _setup(db)
    h = await _auth(client)
    m = await _med(db, u, p)
    await client.put(f"/api/patients/{p.id}/emergency-plan", headers=h, json=_plan(m.id))
    await client.delete(f"/api/medications/{m.id}", headers=h)

    r = await client.put(f"/api/patients/{p.id}/emergency-plan", headers=h, json=_plan(m.id))
    assert r.status_code == 200
    step = r.json()["situations"][0]["steps"][1]
    assert step["medication_id"] == str(m.id) and step["medication"] is None
