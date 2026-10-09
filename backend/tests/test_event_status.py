"""Closing an event: `done`/`cancelled` and what they switch off (ADR 041, step B).

Marking a Widerspruch deadline as acted on is not decoration — it is what stops the
reminders. A caregiver who already objected and still gets "3 days left" stops
believing the next reminder, whatever it is about.
"""

from datetime import UTC, datetime, timedelta

from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.patient_keys import ensure_patient_kek
from app.core.security import hash_password
from app.models.access import PatientAccess
from app.models.calendar import CalendarEvent, EventCategory
from app.models.patient import Patient
from app.models.user import User


async def _setup(db: AsyncSession):
    u = User(email="status@t.com", hashed_password=hash_password("Pass1!"), role="user",
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
    return u, p


async def _auth(client: AsyncClient) -> dict:
    r = await client.post("/api/auth/login", json={"email": "status@t.com", "password": "Pass1!"})
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def _deadline(db: AsyncSession, patient, user, days: int = 10) -> CalendarEvent:
    ev = CalendarEvent(
        patient_id=patient.id, owner_id=user.id, title="Widerspruchsfrist: Pflegegrad",
        start_at=(datetime.now(UTC) + timedelta(days=days)).date().isoformat(),
        all_day=True, category=EventCategory.deadline, source="pipeline",
    )
    db.add(ev)
    return ev


async def test_a_new_deadline_is_scheduled(client: AsyncClient, db: AsyncSession):
    u, p = await _setup(db)
    ev = _deadline(db, p, u)
    await db.commit()
    assert ev.status == "scheduled"
    assert ev.reminder_stage == 0


async def test_closing_a_deadline_takes_it_out_of_the_reminder_set(client: AsyncClient, db: AsyncSession):
    u, p = await _setup(db)
    ev = _deadline(db, p, u)
    await db.commit()
    h = await _auth(client)

    r = await client.put(f"/api/calendar/events/{ev.id}", headers=h, json={
        "title": ev.title, "start_at": ev.start_at, "all_day": True,
        "category": "deadline", "status": "done",
    })
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "done"

    # The scheduler picks its candidates by this filter; an objection already raised
    # must fall out of it, or the reminders keep coming.
    pending = (await db.execute(select(CalendarEvent).where(
        CalendarEvent.is_deleted.is_(False), CalendarEvent.status == "scheduled",
    ))).scalars().all()
    assert ev.id not in [e.id for e in pending]


async def test_cancelled_is_a_separate_outcome_from_done(client: AsyncClient, db: AsyncSession):
    """"I objected" and "I let it lapse on purpose" are different facts, and the second
    is the one nobody remembers a year later."""
    u, p = await _setup(db)
    ev = _deadline(db, p, u)
    await db.commit()
    h = await _auth(client)

    r = await client.put(f"/api/calendar/events/{ev.id}", headers=h, json={
        "title": ev.title, "start_at": ev.start_at, "all_day": True,
        "category": "deadline", "status": "cancelled",
    })
    assert r.status_code == 200
    assert r.json()["status"] == "cancelled"


async def test_an_unknown_status_is_refused(client: AsyncClient, db: AsyncSession):
    u, p = await _setup(db)
    ev = _deadline(db, p, u)
    await db.commit()
    h = await _auth(client)

    r = await client.put(f"/api/calendar/events/{ev.id}", headers=h, json={
        "title": ev.title, "start_at": ev.start_at, "all_day": True,
        "category": "deadline", "status": "widersprochen",
    })
    assert r.status_code == 422
