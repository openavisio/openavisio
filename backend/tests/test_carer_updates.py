"""Carer Updates (ADR 049): kept as told, with who told it."""

from datetime import UTC, datetime

from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.patient_keys import ensure_patient_kek
from app.core.security import hash_password
from app.models.access import PatientAccess
from app.models.carer_update import CarerUpdate
from app.models.correspondent import Correspondent
from app.models.organization import Organization
from app.models.patient import Patient
from app.models.user import User
from app.routers import chat as chat_router
from app.services.handout import render_html


async def _setup(db: AsyncSession, email="kita@t.com"):
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


async def _correspondent(db: AsyncSession, name="Kita Sonnenschein") -> Correspondent:
    org = (await db.execute(select(Organization))).scalars().first()
    if not org:
        org = Organization(name="Test")
        db.add(org)
        await db.commit()
    c = Correspondent(name=name, organization_id=org.id)
    db.add(c)
    await db.commit()
    await db.refresh(c)
    return c


async def _auth(client: AsyncClient, email="kita@t.com") -> dict:
    r = await client.post("/api/auth/login", json={"email": email, "password": "Pass1!"})
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def _body(c, **kw):
    return {"correspondent_id": str(c.id), "day": "2026-03-03", "text": "Hat gut gegessen.", **kw}


async def test_updates_are_listed_newest_day_first(client: AsyncClient, db: AsyncSession):
    _, p = await _setup(db)
    kita, school = await _correspondent(db), await _correspondent(db, "Grundschule")
    h = await _auth(client)
    url = f"/api/patients/{p.id}/carer-updates"
    r = await client.post(url, headers=h, json=_body(kita, person="  Frau M.  ", retold=True))
    assert r.status_code == 201
    assert r.json()["correspondent_name"] == "Kita Sonnenschein"
    assert r.json()["person"] == "Frau M." and r.json()["retold"] is True
    await client.post(url, headers=h, json=_body(school, day="2026-03-05", person="  "))

    rows = (await client.get(url, headers=h)).json()
    assert [u["day"] for u in rows] == ["2026-03-05", "2026-03-03"]
    assert rows[0]["person"] is None


async def test_a_source_and_some_text_are_required(client: AsyncClient, db: AsyncSession):
    _, p = await _setup(db)
    kita = await _correspondent(db)
    h = await _auth(client)
    url = f"/api/patients/{p.id}/carer-updates"
    assert (await client.post(url, headers=h, json=_body(kita, text="   "))).status_code == 422
    kita.is_deleted = True
    await db.commit()
    assert (await client.post(url, headers=h, json=_body(kita))).status_code == 422


async def test_a_deleted_source_keeps_its_name_on_old_updates(client: AsyncClient, db: AsyncSession):
    _, p = await _setup(db)
    kita = await _correspondent(db)
    h = await _auth(client)
    await client.post(f"/api/patients/{p.id}/carer-updates", headers=h, json=_body(kita))
    assert (await client.delete(f"/api/correspondents/{kita.id}", headers=h)).status_code == 204
    rows = (await client.get(f"/api/patients/{p.id}/carer-updates", headers=h)).json()
    assert rows[0]["correspondent_name"] == "Kita Sonnenschein"


async def test_an_update_is_edited_and_deleted(client: AsyncClient, db: AsyncSession):
    _, p = await _setup(db)
    kita = await _correspondent(db)
    h = await _auth(client)
    uid = (await client.post(f"/api/patients/{p.id}/carer-updates", headers=h, json=_body(kita))).json()["id"]
    r = await client.put(f"/api/carer-updates/{uid}", headers=h, json=_body(kita, text="Hat wenig gegessen.", day="2026-03-04"))
    assert r.json()["text"] == "Hat wenig gegessen." and r.json()["day"] == "2026-03-04"
    assert (await client.delete(f"/api/carer-updates/{uid}", headers=h)).status_code == 204
    assert (await client.get(f"/api/patients/{p.id}/carer-updates", headers=h)).json() == []


async def test_without_access_the_updates_are_unreachable(client: AsyncClient, db: AsyncSession):
    _, p = await _setup(db)
    kita = await _correspondent(db)
    h = await _auth(client)
    uid = (await client.post(f"/api/patients/{p.id}/carer-updates", headers=h, json=_body(kita))).json()["id"]
    await _setup(db, email="stranger4@t.com")
    s = await _auth(client, email="stranger4@t.com")
    assert (await client.get(f"/api/patients/{p.id}/carer-updates", headers=s)).status_code in (403, 404)
    assert (await client.post(f"/api/patients/{p.id}/carer-updates", headers=s, json=_body(kita))).status_code in (403, 404)
    assert (await client.put(f"/api/carer-updates/{uid}", headers=s, json=_body(kita))).status_code in (403, 404)
    assert (await client.delete(f"/api/carer-updates/{uid}", headers=s)).status_code in (403, 404)


async def test_the_chat_sees_who_reported_it_and_how(client: AsyncClient, db: AsyncSession):
    u, p = await _setup(db)
    kita = await _correspondent(db)
    db.add(CarerUpdate(patient_id=p.id, owner_id=u.id, correspondent_id=kita.id, person="Frau M.",
                       day="2026-03-03", text="Mittagsschlaf nur 20 Minuten.", retold=True))
    await db.commit()
    lines, months = await chat_router._structured_context(p.id, db, "de")
    assert "Rückmeldung | 2026-03-03 | Kita Sonnenschein | Frau M. | mündlich, nacherzählt | Mittagsschlaf nur 20 Minuten." in lines
    assert "2026-03" in months


async def test_the_doctor_handout_offers_them_unselected_and_marks_retold(client: AsyncClient, db: AsyncSession):
    u, p = await _setup(db)
    kita = await _correspondent(db)
    db.add(CarerUpdate(patient_id=p.id, owner_id=u.id, correspondent_id=kita.id,
                       day="2026-03-03", text="Zwei Absencen im Morgenkreis.", retold=True))
    await db.commit()
    h = await _auth(client)
    body = (await client.get(f"/api/patients/{p.id}/handouts/doctors", headers=h)).json()
    section = next(s for s in body["sections"] if s["key"] == "carer_updates")
    assert section["preselected"] is False
    entry = section["entries"][0]
    assert entry["text"] == "Kita Sonnenschein" and entry["detail"] == "Zwei Absencen im Morgenkreis."
    html = render_html(body, "de")
    assert "Zwei Absencen im Morgenkreis." in html and "mündlich, nacherzählt" in html
    assert "Zwei Absencen" not in render_html(body, "de", exclude={entry["id"]})


async def test_only_the_doctor_and_authority_handouts_offer_them(client: AsyncClient, db: AsyncSession):
    _, p = await _setup(db)
    h = await _auth(client)
    offered = set()
    for variant in ("doctors", "authorities", "emergency", "steckbrief"):
        body = (await client.get(f"/api/patients/{p.id}/handouts/{variant}", headers=h)).json()
        if any(s["key"] == "carer_updates" and not s["preselected"] for s in body["sections"]):
            offered.add(variant)
    assert offered == {"doctors", "authorities"}


async def test_patient_erasure_deletes_the_updates(client: AsyncClient, db: AsyncSession):
    u, p = await _setup(db)
    kita = await _correspondent(db)
    h = await _auth(client)
    await client.post(f"/api/patients/{p.id}/carer-updates", headers=h, json=_body(kita))

    from app.services.erasure import erase_patient
    await erase_patient(p.id, u, db)
    await db.commit()

    assert (await db.execute(select(CarerUpdate).where(CarerUpdate.patient_id == p.id))).first() is None
