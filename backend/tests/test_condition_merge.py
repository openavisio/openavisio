"""#159: merging two conditions — winner keeps name/severity/status, earliest
onset survives, sources and notes are unioned, the loser is soft-deleted with a
pointer at its survivor."""

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
    u = User(email="merge@t.com", hashed_password=hash_password("Pass1!"), role="user",
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
    return u, p


async def _auth(client: AsyncClient) -> dict:
    r = await client.post("/api/auth/login", json={"email": "merge@t.com", "password": "Pass1!"})
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


async def _cond(db, user, patient, name, onset=None, severity=None, note=None, docs=()):
    c = Condition(patient_id=patient.id, owner_id=user.id, code_display=name,
                  onset_date_time=onset, severity=severity, note=note)
    for d in docs:
        c.sources.append(ConditionSource(document_reference_id=d.id))
    db.add(c)
    await db.commit()
    await db.refresh(c)
    return c


async def _doc(db, user, patient, name):
    d = DocumentReference(patient_id=patient.id, owner_id=user.id, file_name=name,
                          issued_date=date(2024, 1, 1))
    db.add(d)
    await db.commit()
    await db.refresh(d)
    return d


async def test_merge_unions_sources_keeps_earliest_onset(client: AsyncClient, db: AsyncSession):
    u, p = await _setup(db)
    h = await _auth(client)
    doc_a = await _doc(db, u, p, "a.pdf")
    doc_b = await _doc(db, u, p, "b.pdf")
    winner = await _cond(db, u, p, "Ataxie", onset="2024-06-01", severity="mild", note="W", docs=(doc_a,))
    loser = await _cond(db, u, p, "Leichte Ataxie", onset="2023-02-01", note="L", docs=(doc_a, doc_b))

    r = await client.post(f"/api/conditions/{winner.id}/merge", json={"other_id": str(loser.id)}, headers=h)
    assert r.status_code == 200
    body = r.json()
    assert body["code_display"] == "Ataxie", "winner keeps its name"
    assert body["severity"] == "mild", "severity travels with the name"
    assert body["onset_date_time"] == "2023-02-01", "the earliest documented onset survives"
    assert body["note"] == "W\nL"
    assert {s["document_reference_id"] for s in body["sources"]} == {str(doc_a.id), str(doc_b.id)}, "union, deduped"

    dead = (await db.execute(select(Condition).where(Condition.id == loser.id))).scalar_one()
    assert dead.is_deleted is True
    assert dead.merged_into_id == winner.id, "the audit pointer"
    assert (await db.execute(select(ConditionSource).where(
        ConditionSource.condition_id == loser.id))).scalars().all() == [], "loser keeps no citations"

    # the list shows one condition afterwards
    r = await client.get(f"/api/patients/{p.id}/conditions", headers=h)
    assert len(r.json()) == 1


async def test_merge_guards(client: AsyncClient, db: AsyncSession):
    u, p = await _setup(db)
    h = await _auth(client)
    a = await _cond(db, u, p, "A")

    # itself
    r = await client.post(f"/api/conditions/{a.id}/merge", json={"other_id": str(a.id)}, headers=h)
    assert r.status_code == 400

    # cross-patient: the other condition belongs to someone else → 404, no leak
    p2 = Patient(given_name="Other", family_name="Kid", created_by=u.id)
    db.add(p2)
    await db.commit()
    await db.refresh(p2)
    foreign = Condition(patient_id=p2.id, owner_id=u.id, code_display="B")
    db.add(foreign)
    await db.commit()
    await db.refresh(foreign)
    r = await client.post(f"/api/conditions/{a.id}/merge", json={"other_id": str(foreign.id)}, headers=h)
    assert r.status_code == 404
