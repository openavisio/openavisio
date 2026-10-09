"""Tests for milestone Event category + developmental domain (issue #11)."""

from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import hash_password
from datetime import UTC, datetime

from app.models.access import PatientAccess
from app.models.patient import Patient
from app.models.user import User


async def _user(db: AsyncSession, email: str) -> User:
    u = User(email=email, hashed_password=hash_password("Pass1!"), role="user", is_active=True,
             first_name="T", last_name="User")
    db.add(u)
    await db.commit()
    await db.refresh(u)
    return u


async def _patient(db: AsyncSession, owner: User) -> Patient:
    p = Patient(given_name="Emma", family_name="Test", birth_date="2024-01-15", created_by=owner.id)
    db.add(p)
    await db.commit()
    await db.refresh(p)
    db.add(PatientAccess(patient_id=p.id, user_id=owner.id, access_level="admin",
                         granted_by_user_id=owner.id, granted_at=datetime.now(UTC)))
    await db.commit()
    return p


async def _auth(client: AsyncClient, email: str) -> dict:
    r = await client.post("/api/auth/login", json={"email": email, "password": "Pass1!"})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


async def _setup(client, db, email):
    owner = await _user(db, email)
    patient = await _patient(db, owner)
    return patient, await _auth(client, email)


async def test_create_milestone(client: AsyncClient, db: AsyncSession):
    patient, h = await _setup(client, db, "ms1@test.com")
    r = await client.post(
        f"/api/patients/{patient.id}/calendar/events",
        json={"title": "First steps", "start_at": "2025-03-01", "all_day": True,
              "category": "milestone", "developmental_domain": "motor"},
        headers=h,
    )
    assert r.status_code == 201, r.text
    d = r.json()
    assert d["category"] == "milestone"
    assert d["developmental_domain"] == "motor"


async def test_appointment_is_default_and_unaffected(client: AsyncClient, db: AsyncSession):
    patient, h = await _setup(client, db, "ms2@test.com")
    # No category supplied → defaults to appointment, no domain.
    r = await client.post(
        f"/api/patients/{patient.id}/calendar/events",
        json={"title": "Neurology visit", "start_at": "2026-05-10T09:00:00"},
        headers=h,
    )
    assert r.status_code == 201, r.text
    d = r.json()
    assert d["category"] == "appointment"
    assert d["developmental_domain"] is None


async def test_domain_requires_milestone(client: AsyncClient, db: AsyncSession):
    patient, h = await _setup(client, db, "ms3@test.com")
    r = await client.post(
        f"/api/patients/{patient.id}/calendar/events",
        json={"title": "x", "start_at": "2025-01-01", "category": "appointment",
              "developmental_domain": "speech"},
        headers=h,
    )
    assert r.status_code == 422


async def test_invalid_category_and_domain_rejected(client: AsyncClient, db: AsyncSession):
    patient, h = await _setup(client, db, "ms4@test.com")
    assert (await client.post(
        f"/api/patients/{patient.id}/calendar/events",
        json={"title": "x", "start_at": "2025-01-01", "category": "birthday"}, headers=h,
    )).status_code == 422
    assert (await client.post(
        f"/api/patients/{patient.id}/calendar/events",
        json={"title": "x", "start_at": "2025-01-01", "category": "milestone",
              "developmental_domain": "emotional"}, headers=h,
    )).status_code == 422


async def test_feed_distinguishes_milestone(client: AsyncClient, db: AsyncSession):
    patient, h = await _setup(client, db, "ms5@test.com")
    await client.post(
        f"/api/patients/{patient.id}/calendar/events",
        json={"title": "First word", "start_at": "2025-02-01", "all_day": True,
              "category": "milestone", "developmental_domain": "speech"}, headers=h,
    )
    await client.post(
        f"/api/patients/{patient.id}/calendar/events",
        json={"title": "Checkup", "start_at": "2026-02-01T10:00:00"}, headers=h,
    )
    feed = (await client.get(f"/api/patients/{patient.id}/calendar/feed", headers=h)).json()
    by_title = {i["title"]: i for i in feed}
    assert by_title["First word"]["type"] == "milestone"
    assert by_title["First word"]["developmental_domain"] == "speech"
    assert by_title["Checkup"]["type"] == "appointment"
    assert by_title["Checkup"]["developmental_domain"] is None

    # Filtering by type=milestone returns only the milestone
    ms_only = (await client.get(
        f"/api/patients/{patient.id}/calendar/feed?types=milestone", headers=h)).json()
    assert [i["title"] for i in ms_only] == ["First word"]
