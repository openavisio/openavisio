"""#68: medication start/end, derived is_active, stop sets end date, calendar pills."""

from datetime import UTC, date, datetime, timedelta

from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import hash_password
from app.models.access import PatientAccess
from app.models.patient import Patient
from app.models.user import User


async def _setup(db: AsyncSession):
    u = User(email="med@t.com", hashed_password=hash_password("Pass1!"), role="user",
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
    r = await client.post("/api/auth/login", json={"email": "med@t.com", "password": "Pass1!"})
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


async def test_ongoing_vs_ended_is_active(client: AsyncClient, db: AsyncSession):
    _, p = await _setup(db)
    h = await _auth(client)
    past = (date.today() - timedelta(days=10)).isoformat()
    future = (date.today() + timedelta(days=10)).isoformat()

    ongoing = (await client.post(f"/api/patients/{p.id}/medications",
        json={"medication_display": "Valproat", "effective_start": past}, headers=h)).json()
    ended = (await client.post(f"/api/patients/{p.id}/medications",
        json={"medication_display": "Ibuprofen", "effective_start": past, "effective_end": past}, headers=h)).json()
    future_end = (await client.post(f"/api/patients/{p.id}/medications",
        json={"medication_display": "Melatonin", "effective_start": past, "effective_end": future}, headers=h)).json()

    assert ongoing["is_active"] is True       # no end date
    assert ended["is_active"] is False        # end in the past (retroactive course)
    assert future_end["is_active"] is True     # end in the future


async def test_stop_sets_end_date(client: AsyncClient, db: AsyncSession):
    _, p = await _setup(db)
    h = await _auth(client)
    med = (await client.post(f"/api/patients/{p.id}/medications",
        json={"medication_display": "Valproat"}, headers=h)).json()
    assert med["is_active"] is True

    r = await client.put(f"/api/medications/{med['id']}", json={"status": "stopped"}, headers=h)
    assert r.status_code == 200
    stopped = r.json()
    assert stopped["is_active"] is False
    assert stopped["effective_end"] == date.today().isoformat()


async def test_calendar_feed_returns_one_span_per_medication(client: AsyncClient, db: AsyncSession):
    """A medication is a period, not two loose pills (#130)."""
    _, p = await _setup(db)
    h = await _auth(client)
    start = (date.today() - timedelta(days=5)).isoformat()
    end = (date.today() - timedelta(days=1)).isoformat()
    await client.post(f"/api/patients/{p.id}/medications",
        json={"medication_display": "Valproat", "effective_start": start, "effective_end": end}, headers=h)

    feed = (await client.get(f"/api/patients/{p.id}/calendar/feed", headers=h)).json()
    meds = [i for i in feed if i["type"] == "medication"]
    assert len(meds) == 1, "one course, one item"
    assert meds[0]["start"] == start and meds[0]["end"] == end
    assert meds[0]["title"] == "Valproat"  # no dosage set -> bare name


async def test_a_medication_spanning_the_window_still_shows(client: AsyncClient, db: AsyncSession):
    """The range filter tested each endpoint on its own, so a medication that began
    before the visible month and ends after it produced NO items — it vanished from
    the very month it was being taken in (#130)."""
    _, p = await _setup(db)
    h = await _auth(client)
    await client.post(f"/api/patients/{p.id}/medications",
        json={"medication_display": "Folsäure",
              "effective_start": "2020-01-01", "effective_end": "2030-01-01"}, headers=h)

    feed = (await client.get(f"/api/patients/{p.id}/calendar/feed",
                             params={"from": "2026-07-01", "to": "2026-07-31"}, headers=h)).json()
    assert [i["title"] for i in feed if i["type"] == "medication"] == ["Folsäure"]


async def test_an_undated_medication_is_not_drawn_from_the_beginning_of_time(client: AsyncClient, db: AsyncSession):
    """No start date, no bar — inventing one would be a lie (#130)."""
    _, p = await _setup(db)
    h = await _auth(client)
    await client.post(f"/api/patients/{p.id}/medications",
                      json={"medication_display": "Unbekannt"}, headers=h)

    feed = (await client.get(f"/api/patients/{p.id}/calendar/feed", headers=h)).json()
    assert [i for i in feed if i["type"] == "medication"] == []


async def test_stop_honours_the_date_the_caller_gives(client: AsyncClient, db: AsyncSession):
    """Stopping must not silently mean "today" (#128).

    The UI now asks when the drug was last taken. A caregiver stopping a
    medication in July that ran out in March must be able to say so.
    """
    _, p = await _setup(db)
    h = await _auth(client)
    r = await client.post(f"/api/patients/{p.id}/medications",
                          json={"medication_display": "Valproat", "effective_start": "2024-03-19"}, headers=h)
    med_id = r.json()["id"]

    r = await client.put(f"/api/medications/{med_id}",
                         json={"status": "stopped", "effective_end": "2026-03-01"}, headers=h)
    assert r.status_code == 200
    assert r.json()["effective_end"] == "2026-03-01", "the caller's date must win over today"


async def test_a_wrong_date_can_be_cleared(client: AsyncClient, db: AsyncSession):
    """An explicit null must clear a field (#128).

    The update used exclude_none, so a null was dropped on the floor and a wrong
    extracted start date could never be removed — only overwritten with another
    wrong one.
    """
    _, p = await _setup(db)
    h = await _auth(client)
    r = await client.post(f"/api/patients/{p.id}/medications",
                          json={"medication_display": "Folsäure", "effective_start": "2020-01-01"}, headers=h)
    med_id = r.json()["id"]

    r = await client.put(f"/api/medications/{med_id}", json={"effective_start": None}, headers=h)
    assert r.status_code == 200
    assert r.json()["effective_start"] is None


def test_condition_normaliser_folds_noise_not_meaning():
    """What may be treated as the same diagnosis — and what may not (#129).

    The tester's daughter had 34 conditions, most of them the same handful over
    and over, because every verified document re-added its diagnoses. Verification
    now skips a diagnosis the patient already has, matched on this normaliser.

    It folds noise: case, whitespace, a trailing colon or full stop. It must NOT
    fold meaning — deciding that "Ataxie" and "Leichte Ataxie" are the same
    condition is a medical judgement, not a string operation (#113).
    """
    from app.routers.documents import _norm_condition as n

    assert n("Globale Entwicklungsverzögerung") == n("globale  entwicklungsverzögerung")
    assert n("Muskelhypotonie ") == n("Muskelhypotonie")
    assert n("Hyperopie.") == n("Hyperopie")

    assert n("Ataxie") != n("Leichte Ataxie")
    assert n("Knick-Senkfüße") != n("Knick-Senkfüße bds.")
    assert n("Dup15q Syndrom") != n("15q11-q13 Mikroduplikationssyndrom")


async def test_an_ongoing_medication_does_not_claim_the_future(client: AsyncClient, db: AsyncSession):
    """"Still running" means today — not 2030 (#130).

    An open-ended course has no end date, so it matched every future month and the
    bar marched through 2027, 2028, forever. That is a claim about the future we
    have no business making.
    """
    _, p = await _setup(db)
    h = await _auth(client)
    await client.post(f"/api/patients/{p.id}/medications",
                      json={"medication_display": "Valproat",
                            "effective_start": (date.today() - timedelta(days=3)).isoformat()}, headers=h)

    # this month: it is being taken, so it shows
    now = date.today()
    feed = (await client.get(f"/api/patients/{p.id}/calendar/feed", headers=h,
                             params={"from": now.replace(day=1).isoformat(), "to": now.isoformat()})).json()
    assert [i["title"] for i in feed if i["type"] == "medication"] == ["Valproat"]

    # three years out: we do not know, so we say nothing
    feed = (await client.get(f"/api/patients/{p.id}/calendar/feed", headers=h,
                             params={"from": f"{now.year + 3}-01-01", "to": f"{now.year + 3}-01-31"})).json()
    assert [i for i in feed if i["type"] == "medication"] == []
