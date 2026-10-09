"""#70: patient favorites — add/remove, access-checked, revoke drops them."""

from datetime import UTC, datetime

from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import hash_password
from app.models.access import PatientAccess
from app.models.patient import Patient
from app.models.user import User


async def _user(db: AsyncSession, email: str, role: str = "user") -> User:
    u = User(email=email, hashed_password=hash_password("Pass1!"), role=role, is_active=True,
             first_name="T", last_name="User")
    db.add(u)
    await db.commit()
    await db.refresh(u)
    return u


async def _auth(client: AsyncClient, email: str) -> dict:
    r = await client.post("/api/auth/login", json={"email": email, "password": "Pass1!"})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


async def _patient(db: AsyncSession, creator: User, level: str = "admin") -> Patient:
    p = Patient(given_name="Emma", family_name="Test", birth_date="2015-04-02", created_by=creator.id)
    db.add(p)
    await db.commit()
    await db.refresh(p)
    db.add(PatientAccess(patient_id=p.id, user_id=creator.id, access_level=level,
                         granted_at=datetime.now(UTC)))
    await db.commit()
    return p


async def test_add_remove_favorite_and_flag(client: AsyncClient, db: AsyncSession):
    owner = await _user(db, "fav_owner@t.com")
    p = await _patient(db, owner)
    h = await _auth(client, "fav_owner@t.com")

    assert (await client.put(f"/api/patients/{p.id}/favorite", headers=h)).status_code == 204
    # is_favorite reflected in list + favorites endpoint
    lst = (await client.get("/api/patients", headers=h)).json()
    assert [x["is_favorite"] for x in lst if x["id"] == str(p.id)] == [True]
    favs = (await client.get("/api/patients/favorites", headers=h)).json()
    assert [x["id"] for x in favs] == [str(p.id)]

    # idempotent add
    assert (await client.put(f"/api/patients/{p.id}/favorite", headers=h)).status_code == 204
    assert len((await client.get("/api/patients/favorites", headers=h)).json()) == 1

    assert (await client.delete(f"/api/patients/{p.id}/favorite", headers=h)).status_code == 204
    assert (await client.get("/api/patients/favorites", headers=h)).json() == []


async def test_cannot_favorite_without_access(client: AsyncClient, db: AsyncSession):
    owner = await _user(db, "fav_owner2@t.com")
    stranger = await _user(db, "fav_stranger@t.com")
    p = await _patient(db, owner)
    h = await _auth(client, "fav_stranger@t.com")
    assert (await client.put(f"/api/patients/{p.id}/favorite", headers=h)).status_code == 404


async def test_favorite_hidden_after_access_revoked(client: AsyncClient, db: AsyncSession):
    from sqlalchemy import select
    owner = await _user(db, "fav_owner3@t.com")
    helper = await _user(db, "fav_helper@t.com")
    p = await _patient(db, owner)
    # grant helper view access, they favorite it
    db.add(PatientAccess(patient_id=p.id, user_id=helper.id, access_level="view", granted_at=datetime.now(UTC)))
    await db.commit()
    hh = await _auth(client, "fav_helper@t.com")
    assert (await client.put(f"/api/patients/{p.id}/favorite", headers=hh)).status_code == 204
    assert len((await client.get("/api/patients/favorites", headers=hh)).json()) == 1

    # revoke helper's grant → favorite no longer surfaces
    grant = (await db.execute(select(PatientAccess).where(
        PatientAccess.patient_id == p.id, PatientAccess.user_id == helper.id))).scalar_one()
    grant.revoked_at = datetime.now(UTC)
    await db.commit()
    assert (await client.get("/api/patients/favorites", headers=hh)).json() == []
