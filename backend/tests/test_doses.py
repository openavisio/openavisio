"""ADR 060: a Dose records what was given, never what is due."""

from datetime import UTC, datetime

from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import hash_password
from app.models.access import PatientAccess
from app.models.emergency_plan import EmergencyPlan
from app.models.incident import Incident
from app.models.medication import MedicationStatement
from app.models.user import User
from app.routers import chat as chat_router
from app.services.erasure import erase_patient
from tests.test_carer_updates import _auth, _setup


async def _med(db, u, p, name="Keppra", **kw):
    m = MedicationStatement(patient_id=p.id, owner_id=u.id, medication_display=name, dosage_text="250 mg 1-0-1", **kw)
    db.add(m)
    await db.commit()
    await db.refresh(m)
    return m


async def _member(db, p, email, level):
    u = User(email=email, hashed_password=hash_password("Pass1!"), role="user", is_active=True, first_name="Oma")
    db.add(u)
    await db.commit()
    db.add(PatientAccess(patient_id=p.id, user_id=u.id, access_level=level, granted_at=datetime.now(UTC)))
    await db.commit()


async def test_one_dose_and_a_period_caught_up(client: AsyncClient, db: AsyncSession):
    u, p = await _setup(db, "dose@t.com")
    m = await _med(db, u, p)
    h = await _auth(client, "dose@t.com")
    url = f"/api/patients/{p.id}/doses"
    r = await client.post(url, headers=h, json=[{"medication_id": str(m.id), "given_at": "2026-11-02T08:00"}])
    assert r.status_code == 201
    d = r.json()[0]
    assert d["given_by"] is None and d["entered_by"] == "T User" and d["can_edit"] is True
    batch = [{"medication_id": str(m.id), "given_at": f"2026-10-{day}T{t}", "given_by": " Kita "}
             for day in ("30", "31") for t in ("08:00", "20:00")]
    assert (await client.post(url, headers=h, json=batch)).status_code == 201
    rows = (await client.get(url, headers=h, params={"since": "2026-10-31"})).json()
    assert [x["given_at"] for x in rows] == ["2026-11-02T08:00", "2026-10-31T20:00", "2026-10-31T08:00"]
    assert rows[1]["given_by"] == "Kita"
    assert (await client.post(url, headers=h, json=[{"medication_id": str(m.id), "given_at": "heute"}])).status_code == 422
    assert (await client.post(url, headers=h, json=[])).status_code == 422


async def test_only_who_entered_it_or_an_admin_changes_it(client: AsyncClient, db: AsyncSession):
    u, p = await _setup(db, "dose2@t.com")
    m = await _med(db, u, p)
    await _member(db, p, "oma@t.com", "contribute")
    await _member(db, p, "opa@t.com", "view")
    oma, opa, admin = (await _auth(client, "oma@t.com"), await _auth(client, "opa@t.com"),
                       await _auth(client, "dose2@t.com"))
    url = f"/api/patients/{p.id}/doses"
    body = [{"medication_id": str(m.id), "given_at": "2026-11-02T08:00"}]
    assert (await client.post(url, headers=opa, json=body)).status_code == 404
    mine = (await client.post(url, headers=oma, json=body)).json()[0]
    theirs = (await client.post(url, headers=admin, json=body)).json()[0]
    assert (await client.put(f"/api/doses/{theirs['id']}", headers=oma, json=body[0])).status_code == 403
    assert (await client.delete(f"/api/doses/{theirs['id']}", headers=oma)).status_code == 403
    assert (await client.put(f"/api/doses/{mine['id']}", headers=oma, json={**body[0], "amount": "5 ml"})).json()["amount"] == "5 ml"
    assert (await client.delete(f"/api/doses/{mine['id']}", headers=admin)).status_code == 204
    assert [x["id"] for x in (await client.get(url, headers=opa)).json()] == [theirs["id"]]


async def test_a_medication_or_incident_of_another_patient_is_refused(client: AsyncClient, db: AsyncSession):
    u, p = await _setup(db, "dose3@t.com")
    u2, p2 = await _setup(db, "dose4@t.com")
    other = await _med(db, u2, p2)
    m = await _med(db, u, p)
    inc = Incident(patient_id=p2.id, owner_id=u2.id, incident_type="seizure", occurred_at="2026-11-01T10:00")
    db.add(inc)
    await db.commit()
    h = await _auth(client, "dose3@t.com")
    url = f"/api/patients/{p.id}/doses"
    assert (await client.post(url, headers=h, json=[{"medication_id": str(other.id), "given_at": "2026-11-02T08:00"}])).status_code == 422
    assert (await client.post(url, headers=h, json=[{"medication_id": str(m.id), "given_at": "2026-11-02T08:00",
                                                     "incident_id": str(inc.id)}])).status_code == 422


async def test_chat_quotes_and_doctor_handout_offers_only_rescue_doses(client: AsyncClient, db: AsyncSession):
    u, p = await _setup(db, "dose5@t.com")
    keppra, buccolam = await _med(db, u, p), await _med(db, u, p, "Buccolam")
    db.add(EmergencyPlan(patient_id=p.id, owner_id=u.id, situations=[{"trigger": "Anfall > 3 min",
                                                       "steps": [{"text": "geben", "medication_id": str(buccolam.id)}]}]))
    await db.commit()
    h = await _auth(client, "dose5@t.com")
    await client.post(f"/api/patients/{p.id}/doses", headers=h, json=[
        {"medication_id": str(keppra.id), "given_at": "2026-11-02T08:00", "given_by": "Oma"},
        {"medication_id": str(buccolam.id), "given_at": "2026-10-20T14:05", "amount": "5 mg"}])
    lines, _ = await chat_router._structured_context(p.id, db, "de")
    assert "Gabe | 2026-11-02 | 08:00 | Keppra | gegeben von Oma" in lines
    body = (await client.get(f"/api/patients/{p.id}/handouts/doctors", headers=h)).json()
    section = next(s for s in body["sections"] if s["key"] == "rescue_doses")
    assert not section["preselected"]
    assert [(e["text"], e["detail"], e["date"]) for e in section["entries"]] == [("Buccolam", "14:05, 5 mg", "2026-10-20")]
    emergency = (await client.get(f"/api/patients/{p.id}/handouts/emergency", headers=h)).json()
    assert "rescue_doses" not in {s["key"] for s in emergency["sections"]}


async def test_erasure_takes_the_doses_along(client: AsyncClient, db: AsyncSession):
    u, p = await _setup(db, "dose6@t.com")
    m = await _med(db, u, p)
    h = await _auth(client, "dose6@t.com")
    await client.post(f"/api/patients/{p.id}/doses", headers=h, json=[{"medication_id": str(m.id), "given_at": "2026-11-02T08:00"}])
    await erase_patient(p.id, u, db)
    from sqlalchemy import select

    from app.models.dose import Dose
    assert (await db.execute(select(Dose))).first() is None


async def test_the_fhir_export_holds_the_doses(client: AsyncClient, db: AsyncSession):
    u, p = await _setup(db, "dose7@t.com")
    m = await _med(db, u, p)
    h = await _auth(client, "dose7@t.com")
    await client.post(f"/api/patients/{p.id}/doses", headers=h, json=[{"medication_id": str(m.id), "given_at": "2026-11-02T08:00"}])
    bundle = (await client.get(f"/api/patients/{p.id}/export/fhir", headers=h)).json()
    admin = [e["resource"] for e in bundle["entry"] if e["resource"]["resourceType"] == "MedicationAdministration"]
    assert admin[0]["effectiveDateTime"] == "2026-11-02T08:00" and admin[0]["performer"][0]["actor"]["display"] == "T User"
