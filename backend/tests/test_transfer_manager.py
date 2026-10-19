"""Exactly one Household Manager, handed over in one step (ADR 052, #349, #351)."""

from sqlalchemy import select

from app.core.security import hash_password
from app.models.audit import AuditLog
from app.models.organization import Organization
from app.models.user import User


async def _user(db, email, role="user", active=True) -> User:
    u = User(email=email, hashed_password=hash_password("Pass1!"), role=role, is_active=active,
             first_name="T", last_name="User")
    db.add(u)
    await db.commit()
    await db.refresh(u)
    return u


async def _login(client, email) -> dict:
    r = await client.post("/api/auth/login", json={"email": email, "password": "Pass1!"})
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


async def test_the_manager_hands_over_and_becomes_a_member(client, db):
    db.add(Organization(name="Familie T", is_household=True))
    await db.commit()
    mama = await _user(db, "mama@t.com", role="admin")
    papa = await _user(db, "papa@t.com")
    gone = await _user(db, "gone@t.com", active=False)
    h = await _login(client, "mama@t.com")

    assert (await client.post(f"/api/admin/users/{gone.id}/make-manager", headers=h)).status_code == 409
    assert (await client.post(f"/api/admin/users/{mama.id}/make-manager", headers=h)).status_code == 409
    r = await client.post(f"/api/admin/users/{papa.id}/make-manager", headers=h)
    assert r.status_code == 200, r.text

    await db.refresh(mama)
    await db.refresh(papa)
    assert (mama.role, papa.role) == ("user", "admin")
    audit = (await db.execute(select(AuditLog).where(AuditLog.action == "manager_transferred"))).scalar_one()
    assert audit.changes == {"from": "mama@t.com", "to": "papa@t.com"} and audit.user_id == mama.id
    assert (await client.post(f"/api/admin/users/{mama.id}/make-manager", headers=h)).status_code == 403


async def test_outside_a_household_there_is_nothing_to_hand_over(client, db):
    db.add(Organization(name="Heim", is_household=False))
    await db.commit()
    await _user(db, "chef@t.com", role="admin")
    other = await _user(db, "kollege@t.com")
    r = await client.post(f"/api/admin/users/{other.id}/make-manager", headers=await _login(client, "chef@t.com"))
    assert r.status_code == 409
