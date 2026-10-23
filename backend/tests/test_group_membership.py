"""ADR 025: a system role does not open a Group it is not a member of."""

from datetime import UTC, datetime

from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import hash_password
from app.models.group import Group, GroupMembership
from app.models.patient import Patient
from app.models.user import User


async def _user(db: AsyncSession, email: str, role: str) -> User:
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


async def test_admin_outside_a_group_cannot_open_or_join_it(client: AsyncClient, db: AsyncSession):
    owner = await _user(db, "gowner@t.com", "manager")
    await _user(db, "gadmin@t.com", "admin")
    group = Group(name="Station 2", owner_id=owner.id)
    db.add(group)
    await db.flush()
    mem = GroupMembership(group_id=group.id, user_id=owner.id, role="owner", status="active",
                          invited_at=datetime.now(UTC), accepted_at=datetime.now(UTC))
    db.add(mem)
    db.add(Patient(given_name="Emma", family_name="Test", birth_date="2015-04-02",
                   created_by=owner.id, group_id=group.id))
    await db.commit()

    admin_h = await _auth(client, "gadmin@t.com")
    base = f"/api/groups/{group.id}"
    assert (await client.get(base, headers=admin_h)).status_code == 404
    assert (await client.get(f"{base}/patients", headers=admin_h)).status_code == 404
    assert (await client.get(f"{base}/members", headers=admin_h)).status_code == 404
    r = await client.post(f"{base}/members/invite", json={"email": "gadmin@t.com"}, headers=admin_h)
    assert r.status_code == 404
    r = await client.put(f"{base}/members/{mem.id}/role", json={"role": "viewer"}, headers=admin_h)
    assert r.status_code == 404
    assert (await client.delete(f"{base}/members/{mem.id}", headers=admin_h)).status_code == 404

    owner_h = await _auth(client, "gowner@t.com")
    r = await client.get(f"{base}/patients", headers=owner_h)
    assert r.status_code == 200 and [p["given_name"] for p in r.json()] == ["Emma"]
    r = await client.post(f"{base}/members/invite", json={"email": "new@t.com"}, headers=owner_h)
    assert r.status_code == 201


async def test_group_manager_cannot_touch_the_owner_role(client: AsyncClient, db: AsyncSession):
    owner = await _user(db, "o2@t.com", "manager")
    mgr = await _user(db, "m2@t.com", "manager")
    group = Group(name="Station 3", owner_id=owner.id)
    db.add(group)
    await db.flush()
    now = datetime.now(UTC)
    owner_mem = GroupMembership(group_id=group.id, user_id=owner.id, role="owner", status="active",
                                invited_at=now, accepted_at=now)
    mgr_mem = GroupMembership(group_id=group.id, user_id=mgr.id, role="manager", status="active",
                              invited_at=now, accepted_at=now)
    db.add_all([owner_mem, mgr_mem])
    await db.commit()

    base = f"/api/groups/{group.id}/members"
    mgr_h = await _auth(client, "m2@t.com")
    assert (await client.put(f"{base}/{mgr_mem.id}/role", json={"role": "owner"}, headers=mgr_h)).status_code == 403
    assert (await client.put(f"{base}/{owner_mem.id}/role", json={"role": "viewer"}, headers=mgr_h)).status_code == 403
    assert (await client.delete(f"{base}/{owner_mem.id}", headers=mgr_h)).status_code == 403
    assert (await client.put(f"{base}/{mgr_mem.id}/role", json={"role": "god"}, headers=mgr_h)).status_code == 422

    owner_h = await _auth(client, "o2@t.com")
    assert (await client.put(f"{base}/{mgr_mem.id}/role", json={"role": "owner"}, headers=owner_h)).status_code == 200


async def test_invite_role_applies_on_accept_and_owner_invites_are_owner_only(client: AsyncClient, db: AsyncSession):
    owner = await _user(db, "o3@t.com", "manager")
    mgr = await _user(db, "m3@t.com", "manager")
    await _user(db, "new3@t.com", "user")
    group = Group(name="Station 4", owner_id=owner.id)
    db.add(group)
    await db.flush()
    now = datetime.now(UTC)
    db.add_all([
        GroupMembership(group_id=group.id, user_id=owner.id, role="owner", status="active", invited_at=now, accepted_at=now),
        GroupMembership(group_id=group.id, user_id=mgr.id, role="manager", status="active", invited_at=now, accepted_at=now),
    ])
    await db.commit()

    base = f"/api/groups/{group.id}/members"
    mgr_h = await _auth(client, "m3@t.com")
    r = await client.post(f"{base}/invite", json={"email": "new3@t.com", "role": "owner"}, headers=mgr_h)
    assert r.status_code == 403
    r = await client.post(f"{base}/invite", json={"email": "New3@t.com", "role": "manager"}, headers=mgr_h)
    assert r.status_code == 201
    token = r.json()["token"]

    assert (await client.post(f"/api/groups/invite/accept?token={token}", headers=mgr_h)).status_code == 403
    new_h = await _auth(client, "new3@t.com")
    assert (await client.post(f"/api/groups/invite/accept?token={token}", headers=new_h)).status_code == 200
    owner_h = await _auth(client, "o3@t.com")
    roles = {m["user_email"]: m["role"] for m in (await client.get(base, headers=owner_h)).json()}
    assert roles["new3@t.com"] == "manager"
