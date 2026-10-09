from datetime import UTC, datetime

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import hash_password
from app.models.access import PatientAccess
from app.models.patient import Patient
from app.models.user import User


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

async def _create_user(
    db: AsyncSession,
    email: str,
    role: str = "user",
    password: str = "Password1!",
) -> User:
    user = User(email=email, hashed_password=hash_password(password), role=role, is_active=True)
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user


async def _login(client: AsyncClient, email: str, password: str = "Password1!") -> dict:
    r = await client.post("/api/auth/login", json={"email": email, "password": password})
    assert r.status_code == 200
    return r.json()


def _auth(tokens: dict) -> dict:
    return {"Authorization": f"Bearer {tokens['access_token']}"}


async def _create_patient(db: AsyncSession, owner: User, given: str = "Test", family: str = "Patient") -> Patient:
    p = Patient(created_by=owner.id, given_name=given, family_name=family)
    db.add(p)
    await db.commit()
    await db.refresh(p)
    db.add(PatientAccess(patient_id=p.id, user_id=owner.id, access_level="admin",
                         granted_by_user_id=owner.id, granted_at=datetime.now(UTC)))
    await db.commit()
    return p


# ---------------------------------------------------------------------------
# Create patient
# ---------------------------------------------------------------------------

async def test_create_patient_as_admin(client: AsyncClient, db: AsyncSession):
    await _create_user(db, "admin_create@test.com", role="admin")
    tokens = await _login(client, "admin_create@test.com")
    r = await client.post(
        "/api/patients",
        json={"given_name": "Alice", "family_name": "Smith"},
        headers=_auth(tokens),
    )
    assert r.status_code == 201
    assert r.json()["given_name"] == "Alice"


async def test_create_patient_as_manager(client: AsyncClient, db: AsyncSession):
    await _create_user(db, "mgr_create@test.com", role="manager")
    tokens = await _login(client, "mgr_create@test.com")
    r = await client.post(
        "/api/patients",
        json={"given_name": "Bob", "family_name": "Jones"},
        headers=_auth(tokens),
    )
    assert r.status_code == 201


async def test_create_patient_as_plain_user_denied(client: AsyncClient, db: AsyncSession):
    await _create_user(db, "plain_create@test.com", role="user")
    tokens = await _login(client, "plain_create@test.com")
    r = await client.post(
        "/api/patients",
        json={"given_name": "X", "family_name": "Y"},
        headers=_auth(tokens),
    )
    assert r.status_code == 403


# ---------------------------------------------------------------------------
# Read patient
# ---------------------------------------------------------------------------

async def test_get_patient_as_owner(client: AsyncClient, db: AsyncSession):
    owner = await _create_user(db, "owner_read@test.com", role="admin")
    patient = await _create_patient(db, owner)
    tokens = await _login(client, "owner_read@test.com")
    r = await client.get(f"/api/patients/{patient.id}", headers=_auth(tokens))
    assert r.status_code == 200
    assert r.json()["id"] == str(patient.id)


async def test_get_patient_as_unrelated_user_returns_404(client: AsyncClient, db: AsyncSession):
    owner = await _create_user(db, "owner_read2@test.com", role="admin")
    other = await _create_user(db, "other_read@test.com", role="user")
    patient = await _create_patient(db, owner)
    tokens = await _login(client, "other_read@test.com")
    r = await client.get(f"/api/patients/{patient.id}", headers=_auth(tokens))
    assert r.status_code == 404


# ---------------------------------------------------------------------------
# Update patient
# ---------------------------------------------------------------------------

async def test_update_patient_as_owner(client: AsyncClient, db: AsyncSession):
    owner = await _create_user(db, "owner_upd@test.com", role="admin")
    patient = await _create_patient(db, owner)
    tokens = await _login(client, "owner_upd@test.com")
    r = await client.put(
        f"/api/patients/{patient.id}",
        json={"given_name": "Updated"},
        headers=_auth(tokens),
    )
    assert r.status_code == 200
    assert r.json()["given_name"] == "Updated"


async def test_update_patient_with_view_grant_denied(client: AsyncClient, db: AsyncSession):
    owner = await _create_user(db, "owner_upd2@test.com", role="admin")
    viewer = await _create_user(db, "viewer_upd@test.com", role="user")
    patient = await _create_patient(db, owner)

    grant = PatientAccess(
        patient_id=patient.id,
        user_id=viewer.id,
        access_level="view",
        granted_by_user_id=owner.id,
        granted_at=datetime.now(UTC),
    )
    db.add(grant)
    await db.commit()

    tokens = await _login(client, "viewer_upd@test.com")
    r = await client.put(
        f"/api/patients/{patient.id}",
        json={"given_name": "Hacked"},
        headers=_auth(tokens),
    )
    assert r.status_code == 404


# ---------------------------------------------------------------------------
# Delete patient
# ---------------------------------------------------------------------------

async def test_delete_patient_as_owner(client: AsyncClient, db: AsyncSession):
    owner = await _create_user(db, "owner_del@test.com", role="admin")
    patient = await _create_patient(db, owner)
    tokens = await _login(client, "owner_del@test.com")
    r = await client.delete(f"/api/patients/{patient.id}", headers=_auth(tokens))
    assert r.status_code == 204


async def test_delete_patient_as_unrelated_user_returns_404(client: AsyncClient, db: AsyncSession):
    owner = await _create_user(db, "owner_del2@test.com", role="admin")
    other = await _create_user(db, "other_del@test.com", role="user")
    patient = await _create_patient(db, owner)
    tokens = await _login(client, "other_del@test.com")
    r = await client.delete(f"/api/patients/{patient.id}", headers=_auth(tokens))
    assert r.status_code == 404


# ---------------------------------------------------------------------------
# List patients
# ---------------------------------------------------------------------------

async def test_list_patients_returns_only_accessible(client: AsyncClient, db: AsyncSession):
    owner = await _create_user(db, "owner_list@test.com", role="admin")
    other = await _create_user(db, "other_list@test.com", role="user")

    mine = await _create_patient(db, owner, given="Mine")
    theirs = await _create_patient(db, other, given="Theirs")

    # Grant 'other' view access to 'mine'
    grant = PatientAccess(
        patient_id=mine.id,
        user_id=other.id,
        access_level="view",
        granted_by_user_id=owner.id,
        granted_at=datetime.now(UTC),
    )
    db.add(grant)
    await db.commit()

    tokens = await _login(client, "other_list@test.com")
    r = await client.get("/api/patients", headers=_auth(tokens))
    assert r.status_code == 200
    ids = {p["id"] for p in r.json()}
    assert str(mine.id) in ids
    assert str(theirs.id) in ids  # other owns this one


async def test_list_patients_excludes_inaccessible(client: AsyncClient, db: AsyncSession):
    owner = await _create_user(db, "owner_excl@test.com", role="admin")
    stranger = await _create_user(db, "stranger_excl@test.com", role="user")
    patient = await _create_patient(db, owner, given="Private")

    tokens = await _login(client, "stranger_excl@test.com")
    r = await client.get("/api/patients", headers=_auth(tokens))
    assert r.status_code == 200
    ids = {p["id"] for p in r.json()}
    assert str(patient.id) not in ids
