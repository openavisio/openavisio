"""#133: a condition cites every document that names it.

Before, the eighth letter naming a diagnosis was silently discarded (#129 dedup).
Now it attaches as a further source — and a re-verify that drops the mention only
kills the condition when nothing else backs it.
"""

import uuid
from datetime import UTC, date, datetime

from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import hash_password
from app.models.access import PatientAccess
from app.models.condition import Condition, ConditionSource
from app.models.document import DocumentReference
from app.models.patient import Patient
from app.models.user import User


async def _setup(db: AsyncSession):
    u = User(email="cond@t.com", hashed_password=hash_password("Pass1!"), role="user",
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
    # verify ends in _reveal(), which needs the patient KEK — a keyless patient 500s
    from app.core.patient_keys import ensure_patient_kek
    await ensure_patient_kek(db, p.id)
    await db.commit()
    return u, p


async def _doc(db: AsyncSession, user: User, patient: Patient, name: str, issued: str) -> DocumentReference:
    d = DocumentReference(patient_id=patient.id, owner_id=user.id, file_name=name,
                          issued_date=date.fromisoformat(issued), processing_status="extracted",
                          verification_status="extracted")
    db.add(d)
    await db.commit()
    await db.refresh(d)
    return d


async def _auth(client: AsyncClient) -> dict:
    r = await client.post("/api/auth/login", json={"email": "cond@t.com", "password": "Pass1!"})
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


async def _conditions(db: AsyncSession, patient_id) -> list[Condition]:
    r = await db.execute(select(Condition).where(
        Condition.patient_id == patient_id, Condition.is_deleted == False))  # noqa: E712
    return list(r.scalars().all())


async def _sources(db: AsyncSession, condition_id) -> set[uuid.UUID]:
    r = await db.execute(select(ConditionSource.document_reference_id).where(
        ConditionSource.condition_id == condition_id))
    return set(r.scalars().all())


async def test_second_mention_attaches_instead_of_vanishing(client: AsyncClient, db: AsyncSession):
    u, p = await _setup(db)
    h = await _auth(client)
    doc_a = await _doc(db, u, p, "tuebingen.pdf", "2024-02-06")
    doc_b = await _doc(db, u, p, "ulm.pdf", "2026-06-18")

    dx = {"diagnoses": [{"name": "15q11-q13 Mikroduplikationssyndrom"}]}
    assert (await client.post(f"/api/documents/{doc_a.id}/verify", json=dx, headers=h)).status_code == 200
    assert (await client.post(f"/api/documents/{doc_b.id}/verify", json=dx, headers=h)).status_code == 200

    conds = await _conditions(db, p.id)
    assert len(conds) == 1, "the second letter must not create a second row (#129)"
    assert await _sources(db, conds[0].id) == {doc_a.id, doc_b.id}, "…but it must be cited (#133)"

    # the API exposes the citations, oldest-first data included
    r = await client.get(f"/api/patients/{p.id}/conditions", headers=h)
    src = r.json()[0]["sources"]
    assert {s["issued_date"] for s in src} == {"2024-02-06", "2026-06-18"}

    # re-verifying the same doc with the same diagnoses is a no-op, not a crash
    assert (await client.post(f"/api/documents/{doc_b.id}/verify", json=dx, headers=h)).status_code == 200
    conds = await _conditions(db, p.id)
    assert len(conds) == 1
    assert await _sources(db, conds[0].id) == {doc_a.id, doc_b.id}


async def test_reverify_keeps_condition_alive_while_another_doc_backs_it(client: AsyncClient, db: AsyncSession):
    u, p = await _setup(db)
    h = await _auth(client)
    doc_a = await _doc(db, u, p, "a.pdf", "2024-01-01")
    doc_b = await _doc(db, u, p, "b.pdf", "2025-01-01")

    dx = {"diagnoses": [{"name": "Globale Entwicklungsverzögerung"}]}
    await client.post(f"/api/documents/{doc_a.id}/verify", json=dx, headers=h)
    await client.post(f"/api/documents/{doc_b.id}/verify", json=dx, headers=h)

    # correction round: doc A turns out not to name it after all
    await client.post(f"/api/documents/{doc_a.id}/verify", json={"diagnoses": []}, headers=h)
    conds = await _conditions(db, p.id)
    assert len(conds) == 1, "doc B still names it — it must survive"
    assert await _sources(db, conds[0].id) == {doc_b.id}
    assert conds[0].document_reference_id == doc_b.id, "origin repoints to a surviving source"

    # …and when the last backer withdraws, it goes
    await client.post(f"/api/documents/{doc_b.id}/verify", json={"diagnoses": []}, headers=h)
    assert await _conditions(db, p.id) == []


async def test_manual_condition_survives_source_games(client: AsyncClient, db: AsyncSession):
    u, p = await _setup(db)
    h = await _auth(client)
    doc = await _doc(db, u, p, "letter.pdf", "2024-05-01")

    manual = (await client.post(f"/api/patients/{p.id}/conditions",
                                json={"code_display": "Epilepsie"}, headers=h)).json()

    # a letter confirms the manual diagnosis → cited, no duplicate row
    await client.post(f"/api/documents/{doc.id}/verify",
                      json={"diagnoses": [{"name": "Epilepsie"}]}, headers=h)
    conds = await _conditions(db, p.id)
    assert len(conds) == 1
    assert await _sources(db, conds[0].id) == {doc.id}

    # the letter withdraws → the manual condition stays (it never came from a doc)
    await client.post(f"/api/documents/{doc.id}/verify", json={"diagnoses": []}, headers=h)
    conds = await _conditions(db, p.id)
    assert len(conds) == 1
    assert conds[0].id == uuid.UUID(manual["id"])
    assert await _sources(db, conds[0].id) == set()


async def test_same_diagnosis_twice_in_one_payload_cites_once(client: AsyncClient, db: AsyncSession):
    u, p = await _setup(db)
    h = await _auth(client)
    doc = await _doc(db, u, p, "letter.pdf", "2024-05-01")

    await client.post(f"/api/documents/{doc.id}/verify",
                      json={"diagnoses": [{"name": "Hyperopie"}, {"name": "hyperopie "}]}, headers=h)
    conds = await _conditions(db, p.id)
    assert len(conds) == 1
    assert len(await _sources(db, conds[0].id)) == 1, "one doc = one citation, however often it repeats itself"


async def test_suspicion_is_marked_confirmed_by_a_later_letter_and_never_downgraded(
    client: AsyncClient, db: AsyncSession,
):
    # #271: "V.a. Epilepsie" is kept, but as provisional. A letter that states it
    # clears the mark; a further suspicion must not put it back.
    u, p = await _setup(db)
    h = await _auth(client)
    suspected = {"diagnoses": [{"name": "Epilepsie", "verification_status": "provisional"}]}
    stated = {"diagnoses": [{"name": "Epilepsie"}]}

    doc_a = await _doc(db, u, p, "ueberweisung.pdf", "2024-03-01")
    assert (await client.post(f"/api/documents/{doc_a.id}/verify", json=suspected, headers=h)).status_code == 200
    [cond] = await _conditions(db, p.id)
    assert cond.verification_status == "provisional"

    doc_b = await _doc(db, u, p, "arztbrief.pdf", "2024-06-01")
    assert (await client.post(f"/api/documents/{doc_b.id}/verify", json=stated, headers=h)).status_code == 200
    await db.refresh(cond)
    assert cond.verification_status is None

    doc_c = await _doc(db, u, p, "kontrolle.pdf", "2025-01-10")
    assert (await client.post(f"/api/documents/{doc_c.id}/verify", json=suspected, headers=h)).status_code == 200
    await db.refresh(cond)
    assert cond.verification_status is None, "a later suspicion must not downgrade a confirmed Diagnosis"
