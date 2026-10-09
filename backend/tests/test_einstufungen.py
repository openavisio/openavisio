"""Einstufungen through the API (ADR 042): history, current, scale, and the limits
the entry form has to respect.
"""

from datetime import UTC, datetime

from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.patient_keys import ensure_patient_kek
from app.core.security import hash_password
from app.models.access import PatientAccess
from app.models.patient import Patient
from app.models.user import User


async def _setup(db: AsyncSession):
    u = User(email="einstufung@t.com", hashed_password=hash_password("Pass1!"), role="user",
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


async def _auth(client: AsyncClient) -> dict:
    r = await client.post("/api/auth/login", json={"email": "einstufung@t.com", "password": "Pass1!"})
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


async def test_the_current_einstufung_is_the_latest_by_valid_from(client: AsyncClient, db: AsyncSession):
    """Not the most recently created one: a Bescheid arriving in July can take
    effect in March, and an older record entered later must not win."""
    _, p = await _setup(db)
    h = await _auth(client)

    await client.post(f"/api/patients/{p.id}/einstufungen", headers=h,
                      json={"pflegegrad": 2, "total_points": 42.5, "valid_from": "2026-06-01"})
    # entered afterwards, but takes effect earlier
    await client.post(f"/api/patients/{p.id}/einstufungen", headers=h,
                      json={"pflegegrad": 1, "total_points": 20.0, "valid_from": "2024-01-01"})

    r = await client.get(f"/api/patients/{p.id}/einstufungen/current", headers=h)
    assert r.status_code == 200
    assert r.json()["pflegegrad"] == 2

    hist = await client.get(f"/api/patients/{p.id}/einstufungen", headers=h)
    assert [e["pflegegrad"] for e in hist.json()] == [2, 1]


async def test_the_history_keeps_what_a_field_would_have_overwritten(client: AsyncClient, db: AsyncSession):
    """An upgrade often takes effect retroactively, so 'which grade applied when' has
    to stay answerable."""
    _, p = await _setup(db)
    h = await _auth(client)
    for grade, since in ((1, "2024-01-01"), (2, "2025-03-01"), (3, "2026-06-01")):
        await client.post(f"/api/patients/{p.id}/einstufungen", headers=h,
                          json={"pflegegrad": grade, "valid_from": since})
    rows = (await client.get(f"/api/patients/{p.id}/einstufungen", headers=h)).json()
    assert len(rows) == 3


async def test_the_scale_reports_a_position(client: AsyncClient, db: AsyncSession):
    _, p = await _setup(db)
    h = await _auth(client)
    await client.post(f"/api/patients/{p.id}/einstufungen", headers=h,
                      json={"pflegegrad": 2, "total_points": 42.5, "valid_from": "2026-06-01"})
    r = await client.get(f"/api/patients/{p.id}/einstufungen/scale", headers=h)
    assert r.status_code == 200
    body = r.json()
    assert body["total"] == 42.5 and body["grade"] == 2
    assert len(body["thresholds"]) == 5


async def test_no_einstufung_means_no_scale_and_no_current(client: AsyncClient, db: AsyncSession):
    _, p = await _setup(db)
    h = await _auth(client)
    assert (await client.get(f"/api/patients/{p.id}/einstufungen/scale", headers=h)).json() is None
    assert (await client.get(f"/api/patients/{p.id}/einstufungen/current", headers=h)).json() is None


async def test_a_grade_outside_the_scale_is_refused(client: AsyncClient, db: AsyncSession):
    _, p = await _setup(db)
    h = await _auth(client)
    r = await client.post(f"/api/patients/{p.id}/einstufungen", headers=h, json={"pflegegrad": 6})
    assert r.status_code == 422


async def test_a_module_over_its_statutory_cap_is_refused(client: AsyncClient, db: AsyncSession):
    """Mobility weighs ten points at most; 15 means someone typed the raw column."""
    _, p = await _setup(db)
    h = await _auth(client)
    r = await client.post(f"/api/patients/{p.id}/einstufungen", headers=h,
                          json={"pflegegrad": 2, "module_mobility": 15.0})
    assert r.status_code == 422


async def test_deleting_one_leaves_the_rest(client: AsyncClient, db: AsyncSession):
    _, p = await _setup(db)
    h = await _auth(client)
    a = (await client.post(f"/api/patients/{p.id}/einstufungen", headers=h,
                           json={"pflegegrad": 1, "valid_from": "2024-01-01"})).json()
    await client.post(f"/api/patients/{p.id}/einstufungen", headers=h,
                      json={"pflegegrad": 2, "valid_from": "2026-01-01"})
    assert (await client.delete(f"/api/einstufungen/{a['id']}", headers=h)).status_code == 204
    rows = (await client.get(f"/api/patients/{p.id}/einstufungen", headers=h)).json()
    assert [e["pflegegrad"] for e in rows] == [2]
