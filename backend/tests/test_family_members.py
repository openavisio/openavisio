"""Removing a member and revoking an invitation (ADR 052)."""

from datetime import UTC, datetime, timedelta

from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import hash_password
from app.models.access import PatientAccess
from app.models.patient import Patient
from app.models.system import UserInvitation
from app.models.user import User


async def _user(db: AsyncSession, email: str, role: str = "user") -> User:
    u = User(email=email, hashed_password=hash_password("Pass1!"), role=role, is_active=True, first_name="T", last_name="U")
    db.add(u)
    await db.commit()
    await db.refresh(u)
    return u


async def _auth(client: AsyncClient, email: str) -> dict:
    r = await client.post("/api/auth/login", json={"email": email, "password": "Pass1!"})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


async def _patient(db: AsyncSession, grants: dict[User, str]) -> Patient:
    p = Patient(given_name="Emma", family_name="Test", birth_date="2015-04-02", created_by=next(iter(grants)).id)
    db.add(p)
    await db.commit()
    for u, level in grants.items():
        db.add(PatientAccess(patient_id=p.id, user_id=u.id, access_level=level, granted_at=datetime.now(UTC)))
    await db.commit()
    return p


async def _active(db: AsyncSession, patient: Patient) -> dict:
    rows = (await db.execute(select(PatientAccess).where(
        PatientAccess.patient_id == patient.id, PatientAccess.revoked_at == None))).scalars().all()  # noqa: E711
    return {g.user_id: g.access_level for g in rows}


async def test_removing_a_member_ends_their_login_and_access(client: AsyncClient, db: AsyncSession):
    mama = await _user(db, "fam_mama@t.com", "admin")
    papa = await _user(db, "fam_papa@t.com")
    shared = await _patient(db, {mama: "admin", papa: "full"})
    papas = await _patient(db, {papa: "admin"})        # Papa created this child; nobody else has it
    viewed = await _patient(db, {papa: "admin", mama: "view"})
    h = await _auth(client, "fam_mama@t.com")

    assert (await client.post(f"/api/admin/users/{mama.id}/remove", headers=h)).status_code == 400
    assert (await client.post(f"/api/admin/users/{papa.id}/remove", headers=h)).status_code == 200

    await db.refresh(papa)
    assert papa.is_active is False
    assert (await client.post("/api/auth/login", json={"email": "fam_papa@t.com", "password": "Pass1!"})).status_code != 200
    assert await _active(db, shared) == {mama.id: "admin"}
    assert await _active(db, papas) == {mama.id: "admin"}   # handed over, not orphaned
    assert await _active(db, viewed) == {mama.id: "admin"}  # her view grant is raised


async def test_only_the_household_manager_removes(client: AsyncClient, db: AsyncSession):
    await _user(db, "fam_a@t.com", "admin")
    b = await _user(db, "fam_b@t.com")
    c = await _user(db, "fam_c@t.com")
    assert (await client.post(f"/api/admin/users/{c.id}/remove", headers=await _auth(client, "fam_b@t.com"))).status_code == 403
    assert b.is_active


async def test_an_open_invitation_can_be_revoked_an_accepted_one_not(client: AsyncClient, db: AsyncSession):
    admin = await _user(db, "fam_inv@t.com", "admin")
    soon = datetime.now(UTC) + timedelta(days=7)
    open_ = UserInvitation(email="x@t.com", token="tok-open", expires_at=soon, created_by_user_id=admin.id)
    used = UserInvitation(email="y@t.com", token="tok-used", expires_at=soon, created_by_user_id=admin.id, is_used=True)
    db.add_all([open_, used])
    await db.commit()
    h = await _auth(client, "fam_inv@t.com")

    assert (await client.delete(f"/api/admin/invitations/{open_.id}", headers=h)).status_code == 204
    assert (await client.delete(f"/api/admin/invitations/{used.id}", headers=h)).status_code == 409
    tokens = {i["token"] for i in (await client.get("/api/admin/invitations", headers=h)).json()}
    assert "tok-open" not in tokens and "tok-used" in tokens
