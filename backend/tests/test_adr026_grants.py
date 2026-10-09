"""ADR 026: creation auto-grant, last-admin-grant rules, user-erasure block."""

from datetime import UTC, datetime

from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import hash_password
from app.models.access import PatientAccess
from app.models.patient import Patient
from app.models.user import User


async def _user(db: AsyncSession, email: str, role: str = "manager") -> User:
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


async def test_create_patient_auto_grants_admin_level(client: AsyncClient, db: AsyncSession):
    creator = await _user(db, "creator26@t.com")
    h = await _auth(client, "creator26@t.com")
    r = await client.post("/api/patients", json={"given_name": "Neo", "family_name": "Grant"}, headers=h)
    assert r.status_code == 201, r.text
    pid = r.json()["id"]

    grant = (await db.execute(select(PatientAccess).where(PatientAccess.patient_id == pid))).scalar_one()
    assert grant.user_id == creator.id
    assert grant.access_level == "admin"

    # creator works through the grant, not through creation
    assert (await client.get(f"/api/patients/{pid}", headers=h)).status_code == 200


async def test_last_admin_grant_cannot_be_revoked_or_downgraded(client: AsyncClient, db: AsyncSession):
    await _user(db, "solo26@t.com")
    h = await _auth(client, "solo26@t.com")
    pid = (await client.post("/api/patients", json={"given_name": "Last", "family_name": "Grant"}, headers=h)).json()["id"]
    grant_id = str((await db.execute(select(PatientAccess.id).where(PatientAccess.patient_id == pid))).scalar_one())

    assert (await client.delete(f"/api/access/{grant_id}", headers=h)).status_code == 409
    assert (await client.patch(f"/api/access/{grant_id}", json={"access_level": "view"}, headers=h)).status_code == 409


async def test_handover_second_admin_grant_then_revoke_own(client: AsyncClient, db: AsyncSession):
    await _user(db, "staff26@t.com")
    parent = await _user(db, "parent26@t.com", role="user")
    staff_h = await _auth(client, "staff26@t.com")
    pid = (await client.post("/api/patients", json={"given_name": "Hand", "family_name": "Over"}, headers=staff_h)).json()["id"]

    r = await client.post(f"/api/patients/{pid}/access",
                          json={"email": "parent26@t.com", "access_level": "admin"}, headers=staff_h)
    assert r.status_code in (200, 201), r.text

    staff_grant = (await db.execute(select(PatientAccess.id).where(
        PatientAccess.patient_id == pid,
        PatientAccess.user_id != parent.id,
    ))).scalar_one()
    assert (await client.delete(f"/api/access/{staff_grant}", headers=staff_h)).status_code == 204

    # staff is out, parent is in
    assert (await client.get(f"/api/patients/{pid}", headers=staff_h)).status_code == 404
    parent_h = await _auth(client, "parent26@t.com")
    assert (await client.get(f"/api/patients/{pid}", headers=parent_h)).status_code == 200


async def test_full_grant_holder_cannot_grant_admin_level(client: AsyncClient, db: AsyncSession):
    await _user(db, "boss26@t.com")
    await _user(db, "helper26@t.com", role="user")
    await _user(db, "target26@t.com", role="user")
    boss_h = await _auth(client, "boss26@t.com")
    pid = (await client.post("/api/patients", json={"given_name": "Priv", "family_name": "Esc"}, headers=boss_h)).json()["id"]
    assert (await client.post(f"/api/patients/{pid}/access",
                              json={"email": "helper26@t.com", "access_level": "full"}, headers=boss_h)).status_code in (200, 201)

    helper_h = await _auth(client, "helper26@t.com")
    r = await client.post(f"/api/patients/{pid}/access",
                          json={"email": "target26@t.com", "access_level": "admin"}, headers=helper_h)
    assert r.status_code == 404  # requires admin level, resolves below → not found


async def test_user_erasure_blocked_while_last_admin_grant_holder(client: AsyncClient, db: AsyncSession):
    solo = await _user(db, "erasme26@t.com")
    h = await _auth(client, "erasme26@t.com")
    pid = (await client.post("/api/patients", json={"given_name": "Block", "family_name": "Er"}, headers=h)).json()["id"]

    r = await client.post(f"/api/admin/users/{solo.id}/erase",
                          json={"confirm_email": "erasme26@t.com"}, headers=h)
    assert r.status_code == 409, r.text
    assert pid in str(r.json())
