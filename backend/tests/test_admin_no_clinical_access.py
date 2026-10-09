"""ADR 025: admin/manager roles have no blanket clinical access (issue #65)."""

from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import hash_password
from app.models.document import DocumentReference
from datetime import UTC, datetime

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


async def _patient_with_doc(db: AsyncSession, owner: User):
    p = Patient(given_name="Emma", family_name="Test", birth_date="2015-04-02", created_by=owner.id)
    db.add(p)
    await db.commit()
    await db.refresh(p)
    db.add(PatientAccess(patient_id=p.id, user_id=owner.id, access_level="admin",
                         granted_by_user_id=owner.id, granted_at=datetime.now(UTC)))
    await db.commit()
    d = DocumentReference(patient_id=p.id, owner_id=owner.id, file_name="befund.pdf", type="lab_report")
    db.add(d)
    await db.commit()
    await db.refresh(d)
    return p, d


async def test_admin_role_cannot_read_clinical_data(client: AsyncClient, db: AsyncSession):
    owner = await _user(db, "owner65@t.com")
    await _user(db, "admin65@t.com", role="admin")
    patient, doc = await _patient_with_doc(db, owner)
    admin_h = await _auth(client, "admin65@t.com")

    assert (await client.get(f"/api/patients/{patient.id}", headers=admin_h)).status_code == 404
    assert (await client.get(f"/api/patients/{patient.id}/documents", headers=admin_h)).status_code == 404
    assert (await client.get(f"/api/documents/{doc.id}", headers=admin_h)).status_code == 404


async def test_admin_role_does_not_see_patients_in_list(client: AsyncClient, db: AsyncSession):
    owner = await _user(db, "owner65b@t.com")
    await _user(db, "admin65b@t.com", role="admin")
    await _patient_with_doc(db, owner)

    admin_h = await _auth(client, "admin65b@t.com")
    r = await client.get("/api/patients", headers=admin_h)
    assert r.status_code == 200
    assert r.json() == []

    owner_h = await _auth(client, "owner65b@t.com")
    r = await client.get("/api/patients", headers=owner_h)
    assert len(r.json()) == 1


async def test_manager_role_has_no_bypass_either(client: AsyncClient, db: AsyncSession):
    owner = await _user(db, "owner65c@t.com")
    await _user(db, "manager65c@t.com", role="manager")
    patient, _ = await _patient_with_doc(db, owner)

    manager_h = await _auth(client, "manager65c@t.com")
    assert (await client.get(f"/api/patients/{patient.id}", headers=manager_h)).status_code == 404


async def test_owner_retains_full_access(client: AsyncClient, db: AsyncSession):
    owner = await _user(db, "owner65d@t.com")
    patient, doc = await _patient_with_doc(db, owner)
    owner_h = await _auth(client, "owner65d@t.com")

    assert (await client.get(f"/api/patients/{patient.id}", headers=owner_h)).status_code == 200
    assert (await client.get(f"/api/patients/{patient.id}/documents", headers=owner_h)).status_code == 200
