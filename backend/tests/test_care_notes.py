"""Care Notes through the API (ADR 048): six fixed headings, one set per Patient."""

from datetime import UTC, datetime

from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.patient_keys import ensure_patient_kek
from app.core.security import hash_password
from app.models.access import PatientAccess
from app.models.care_notes import CareNotes
from app.models.patient import Patient
from app.models.user import User


async def _setup(db: AsyncSession, email="alltag@t.com"):
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


async def _auth(client: AsyncClient, email="alltag@t.com") -> dict:
    r = await client.post("/api/auth/login", json={"email": email, "password": "Pass1!"})
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


async def test_no_care_notes_yet_reads_as_null(client: AsyncClient, db: AsyncSession):
    _, p = await _setup(db)
    h = await _auth(client)
    r = await client.get(f"/api/patients/{p.id}/care-notes", headers=h)
    assert r.status_code == 200 and r.json() is None


async def test_headings_are_filled_edited_and_cleared(client: AsyncClient, db: AsyncSession):
    _, p = await _setup(db)
    h = await _auth(client)
    r = await client.put(f"/api/patients/{p.id}/care-notes", headers=h,
                         json={"communication": "Nods for yes", "sleep": "Night light on"})
    assert r.status_code == 200
    assert r.json()["communication"] == "Nods for yes" and r.json()["eating_drinking"] is None

    r = await client.put(f"/api/patients/{p.id}/care-notes", headers=h,
                         json={"communication": "Nods for yes, shakes head for no", "sleep": "  "})
    body = r.json()
    assert body["communication"] == "Nods for yes, shakes head for no"
    assert body["sleep"] is None  # blank clears the heading
    rows = (await db.execute(select(CareNotes).where(CareNotes.patient_id == p.id))).all()
    assert len(rows) == 1


async def test_without_access_the_care_notes_are_unreachable(client: AsyncClient, db: AsyncSession):
    _, p = await _setup(db)
    await _setup(db, email="stranger2@t.com")
    h = await _auth(client, email="stranger2@t.com")
    assert (await client.get(f"/api/patients/{p.id}/care-notes", headers=h)).status_code in (403, 404)
    assert (await client.put(f"/api/patients/{p.id}/care-notes", headers=h, json={})).status_code in (403, 404)


async def test_patient_erasure_deletes_the_care_notes(client: AsyncClient, db: AsyncSession):
    u, p = await _setup(db)
    h = await _auth(client)
    await client.put(f"/api/patients/{p.id}/care-notes", headers=h, json={"aids": "Wheelchair"})

    from app.services.erasure import erase_patient
    await erase_patient(p.id, u, db)
    await db.commit()

    assert (await db.execute(select(CareNotes).where(CareNotes.patient_id == p.id))).first() is None
