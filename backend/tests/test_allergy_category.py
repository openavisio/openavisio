"""#191: an allergy is a Condition carrying category="allergy".

No new model, no filtering — allergies sit in the diagnosis list, as they do in a
German doctor's letter. This pins the one thing that could silently regress: the
pipeline actually persisting the category the extractor sent.
"""

from datetime import UTC, date, datetime

from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.patient_keys import ensure_patient_kek
from app.core.security import hash_password
from app.models.access import PatientAccess
from app.models.condition import Condition
from app.models.document import DocumentReference
from app.models.patient import Patient
from app.models.user import User


async def _setup(db: AsyncSession):
    u = User(email="allergy@t.com", hashed_password=hash_password("Pass1!"), role="user",
             is_active=True, first_name="T", last_name="User")
    db.add(u)
    await db.commit()
    await db.refresh(u)
    p = Patient(given_name="Emma", family_name="Test", birth_date="2015-04-02", created_by=u.id)
    db.add(p)
    await db.commit()
    await db.refresh(p)
    db.add(PatientAccess(patient_id=p.id, user_id=u.id, access_level="admin", granted_at=datetime.now(UTC)))
    await db.commit()
    await ensure_patient_kek(db, p.id)
    await db.commit()
    d = DocumentReference(patient_id=p.id, owner_id=u.id, file_name="brief.pdf",
                          issued_date=date.fromisoformat("2026-03-14"), processing_status="extracted",
                          verification_status="extracted")
    db.add(d)
    await db.commit()
    await db.refresh(d)
    return u, p, d


async def _auth(client: AsyncClient) -> dict:
    r = await client.post("/api/auth/login", json={"email": "allergy@t.com", "password": "Pass1!"})
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


async def test_allergy_category_is_persisted_and_diagnoses_stay_null(client: AsyncClient, db: AsyncSession):
    _, p, doc = await _setup(db)
    h = await _auth(client)

    body = {"diagnoses": [
        {"name": "Penicillin-Allergie", "category": "allergy"},
        {"name": "Epilepsie"},
    ]}
    assert (await client.post(f"/api/documents/{doc.id}/verify", json=body, headers=h)).status_code == 200

    r = await db.execute(select(Condition).where(
        Condition.patient_id == p.id, Condition.is_deleted == False))  # noqa: E712
    conds = {c.code_display: c for c in r.scalars().all()}
    assert conds["Penicillin-Allergie"].category == "allergy"
    assert conds["Epilepsie"].category is None, "a plain diagnosis must not gain a category"

    # no filtering by design (#191): the allergy is in the same list the UI reads
    listed = (await client.get(f"/api/patients/{p.id}/conditions", headers=h)).json()
    assert {c["code_display"] for c in listed} == {"Penicillin-Allergie", "Epilepsie"}


async def test_reaction_the_user_confirmed_lands_in_note(client: AsyncClient, db: AsyncSession):
    _, p, doc = await _setup(db)
    h = await _auth(client)

    body = {"diagnoses": [{"name": "Penicillin-Allergie", "category": "allergy", "reaction": "Exanthem"}]}
    assert (await client.post(f"/api/documents/{doc.id}/verify", json=body, headers=h)).status_code == 200

    listed = (await client.get(f"/api/patients/{p.id}/conditions", headers=h)).json()
    assert listed[0]["note"] == "Exanthem"


async def test_reaction_fills_an_empty_note_on_re_mention_and_skips_non_allergies(client: AsyncClient, db: AsyncSession):
    u, p, doc = await _setup(db)
    h = await _auth(client)
    first = {"diagnoses": [{"name": "Penicillin-Allergie", "category": "allergy"},
                           {"name": "Epilepsie", "reaction": "Krampfanfall"}]}
    assert (await client.post(f"/api/documents/{doc.id}/verify", json=first, headers=h)).status_code == 200

    later = DocumentReference(patient_id=p.id, owner_id=u.id, file_name="brief2.pdf", processing_status="extracted",
                              verification_status="extracted")
    db.add(later)
    await db.commit()
    again = {"diagnoses": [{"name": "Penicillin-Allergie", "category": "allergy", "reaction": "Exanthem"}]}
    assert (await client.post(f"/api/documents/{later.id}/verify", json=again, headers=h)).status_code == 200

    listed = {c["code_display"]: c for c in (await client.get(f"/api/patients/{p.id}/conditions", headers=h)).json()}
    assert listed["Penicillin-Allergie"]["note"] == "Exanthem"
    assert listed["Epilepsie"]["note"] is None
