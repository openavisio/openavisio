"""#192 / ADR-037: the iCal feed is one-way, token-only, and rides on PatientAccess.

The two things that must not silently break: revocation (both explicit and via
losing care-circle access), and the floating-time rendering that keeps 09:30 at
09:30 in the subscriber's calendar.
"""

from datetime import UTC, datetime, timedelta

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.patient_keys import ensure_patient_kek
from app.core.security import hash_password
from app.models.access import PatientAccess
from app.models.calendar import CalendarEvent, CalendarFeed, EventCategory
from app.models.patient import Patient
from app.models.user import User
from app.services.calendar_feed import LOOKBACK_DAYS, build_ics, window_start


async def _setup(db: AsyncSession):
    u = User(email="feed@t.com", hashed_password=hash_password("Pass1!"), role="user",
             is_active=True, first_name="T", last_name="User")
    db.add(u)
    await db.commit()
    await db.refresh(u)
    p = Patient(given_name="Emma", family_name="Test", birth_date="2015-04-02", created_by=u.id)
    db.add(p)
    await db.commit()
    await db.refresh(p)
    grant = PatientAccess(patient_id=p.id, user_id=u.id, access_level="admin", granted_at=datetime.now(UTC))
    db.add(grant)
    await db.commit()
    await ensure_patient_kek(db, p.id)
    await db.commit()
    return u, p, grant


async def _auth(client: AsyncClient) -> dict:
    r = await client.post("/api/auth/login", json={"email": "feed@t.com", "password": "Pass1!"})
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def _add_event(db: AsyncSession, patient, user, title, start, **kw):
    ev = CalendarEvent(patient_id=patient.id, owner_id=user.id, title=title, start_at=start,
                       category=kw.pop("category", EventCategory.appointment), **kw)
    db.add(ev)
    return ev


async def _create_feed(client: AsyncClient, patient, h) -> str:
    r = await client.post(f"/api/patients/{patient.id}/calendar/feeds", headers=h)
    assert r.status_code == 201
    return r.json()["url"]


def _token_of(url: str) -> str:
    return url.rsplit("/", 1)[-1].removesuffix(".ics")


async def test_feed_serves_appointments_and_hides_milestones(client: AsyncClient, db: AsyncSession):
    u, p, _ = await _setup(db)
    h = await _auth(client)
    soon = (datetime.now(UTC) + timedelta(days=7)).date().isoformat()
    _add_event(db, p, u, "Neurologie", f"{soon}T09:30:00", provider="Dr. Müller", location="Tübingen")
    _add_event(db, p, u, "Erste Schritte", soon, category=EventCategory.milestone)
    await db.commit()

    url = await _create_feed(client, p, h)
    r = await client.get(f"/api/public/calendar/{_token_of(url)}.ics")
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("text/calendar")
    body = r.text

    assert "Neurologie" in body
    assert "Erste Schritte" not in body, "milestones are not appointments (ADR-037)"
    assert "Dr. Müller" in body and "Tübingen" in body
    # floating time: no Z, no TZID — 09:30 stays 09:30 wherever the subscriber is
    assert f"DTSTART:{soon.replace('-', '')}T093000" in body
    assert "DTSTART;TZID" not in body and "T093000Z" not in body


async def test_date_only_event_becomes_all_day(client: AsyncClient, db: AsyncSession):
    u, p, _ = await _setup(db)
    h = await _auth(client)
    soon = (datetime.now(UTC) + timedelta(days=3)).date().isoformat()
    _add_event(db, p, u, "Kontrolle", soon)
    await db.commit()

    url = await _create_feed(client, p, h)
    body = (await client.get(f"/api/public/calendar/{_token_of(url)}.ics")).text
    assert f"DTSTART;VALUE=DATE:{soon.replace('-', '')}" in body


async def test_window_drops_events_older_than_the_lookback(client: AsyncClient, db: AsyncSession):
    u, p, _ = await _setup(db)
    h = await _auth(client)
    old = (datetime.now(UTC) - timedelta(days=LOOKBACK_DAYS + 10)).date().isoformat()
    recent = (datetime.now(UTC) - timedelta(days=5)).date().isoformat()
    _add_event(db, p, u, "Uralt-Termin", old)
    _add_event(db, p, u, "Neulich-Termin", recent)
    await db.commit()

    url = await _create_feed(client, p, h)
    body = (await client.get(f"/api/public/calendar/{_token_of(url)}.ics")).text
    assert "Neulich-Termin" in body
    assert "Uralt-Termin" not in body


async def test_revoked_feed_is_gone(client: AsyncClient, db: AsyncSession):
    u, p, _ = await _setup(db)
    h = await _auth(client)
    url = await _create_feed(client, p, h)
    token = _token_of(url)
    assert (await client.get(f"/api/public/calendar/{token}.ics")).status_code == 200

    feed_id = (await client.get(f"/api/patients/{p.id}/calendar/feeds", headers=h)).json()[0]["id"]
    assert (await client.post(f"/api/patients/{p.id}/calendar/feeds/{feed_id}/revoke", headers=h)).status_code == 200
    assert (await client.get(f"/api/public/calendar/{token}.ics")).status_code == 404


async def test_losing_patient_access_kills_the_feed(client: AsyncClient, db: AsyncSession):
    """The point of hanging the feed off PatientAccess (ADR-037): no separate step."""
    u, p, grant = await _setup(db)
    h = await _auth(client)
    url = await _create_feed(client, p, h)
    token = _token_of(url)
    assert (await client.get(f"/api/public/calendar/{token}.ics")).status_code == 200

    grant.revoked_at = datetime.now(UTC)
    await db.commit()
    assert (await client.get(f"/api/public/calendar/{token}.ics")).status_code == 404


async def test_unknown_token_is_404_not_a_hint(client: AsyncClient, db: AsyncSession):
    await _setup(db)
    assert (await client.get("/api/public/calendar/definitely-not-a-token.ics")).status_code == 404


async def test_plaintext_token_is_never_stored(client: AsyncClient, db: AsyncSession):
    u, p, _ = await _setup(db)
    h = await _auth(client)
    token = _token_of(await _create_feed(client, p, h))
    feed = (await db.execute(select(CalendarFeed).where(CalendarFeed.patient_id == p.id))).scalar_one()
    assert feed.token_hash != token
    assert len(feed.token_hash) == 64


async def test_patient_erasure_removes_the_feed(client: AsyncClient, db: AsyncSession):
    """A surviving feed would be a working PHI URL for an erased person."""
    u, p, _ = await _setup(db)
    h = await _auth(client)
    token = _token_of(await _create_feed(client, p, h))

    from app.services.erasure import erase_patient
    await erase_patient(p.id, u, db)
    await db.commit()

    assert (await client.get(f"/api/public/calendar/{token}.ics")).status_code == 404
    rows = await db.execute(select(CalendarFeed).where(CalendarFeed.patient_id == p.id))
    assert rows.first() is None


@pytest.mark.parametrize("title,expected", [
    ("Kontrolle; MRT", "Kontrolle\\; MRT"),
    ("Reha, Teil 2", "Reha\\, Teil 2"),
])
def test_ics_escapes_reserved_characters(title, expected):
    ev = CalendarEvent(patient_id=None, owner_id=None, title=title, start_at="2026-03-14")
    ev.id = "x"
    body = build_ics([ev], "Emma Test")
    assert expected in body


def test_window_start_is_the_lookback_boundary():
    from datetime import date
    assert window_start(date(2026, 7, 20)) == (date(2026, 7, 20) - timedelta(days=LOOKBACK_DAYS)).isoformat()
