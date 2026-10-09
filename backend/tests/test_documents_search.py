"""Tests for the document list `q` search parameter (documents-page filter bar)."""

from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import hash_password
from app.models.correspondent import Correspondent
from app.models.document import DocumentReference
from app.models.organization import Organization
from datetime import UTC, datetime

from app.models.access import PatientAccess
from app.models.patient import Patient
from app.models.user import User


async def _setup(db: AsyncSession):
    user = User(email="search@t.com", hashed_password=hash_password("Pass1!"), role="user",
                is_active=True, first_name="T", last_name="User")
    db.add(user)
    await db.commit()
    await db.refresh(user)

    patient = Patient(given_name="Emma", family_name="Test", birth_date="2015-04-02", created_by=user.id)
    db.add(patient)
    await db.commit()
    await db.refresh(patient)
    db.add(PatientAccess(patient_id=patient.id, user_id=user.id, access_level="admin",
                         granted_by_user_id=user.id, granted_at=datetime.now(UTC)))
    await db.commit()

    org = (await db.execute(select(Organization))).scalars().first()
    if org is None:
        org = Organization()
        db.add(org)
        await db.commit()
        await db.refresh(org)
    corr = Correspondent(name="Dr. Meier", organization_id=org.id)
    db.add(corr)
    await db.commit()
    await db.refresh(corr)

    docs = [
        DocumentReference(patient_id=patient.id, owner_id=user.id, file_name="eeg-bericht.pdf",
                          type="report", extracted_text="EEG unauffällig, keine epilepsietypischen Potentiale"),
        DocumentReference(patient_id=patient.id, owner_id=user.id, file_name="labor.pdf",
                          type="lab_report", extracted_text="Valproat-Spiegel im therapeutischen Bereich",
                          correspondent_id=corr.id),
        DocumentReference(patient_id=patient.id, owner_id=user.id, file_name="impfpass.jpg",
                          type="other", extracted_text=None),
    ]
    db.add_all(docs)
    await db.commit()
    return user, patient


async def _auth(client: AsyncClient) -> dict:
    r = await client.post("/api/auth/login", json={"email": "search@t.com", "password": "Pass1!"})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


async def test_q_does_not_search_encrypted_body(client: AsyncClient, db: AsyncSession):
    _, patient = await _setup(db)
    headers = await _auth(client)
    # extracted_text is ciphertext at rest (ADR-031); body-text search is
    # embeddings-only now, so a body-only term no longer matches via `q`.
    r = await client.get(f"/api/patients/{patient.id}/documents?q=valproat", headers=headers)
    assert r.status_code == 200
    assert r.json() == []


async def test_q_searches_file_name_case_insensitive(client: AsyncClient, db: AsyncSession):
    _, patient = await _setup(db)
    headers = await _auth(client)
    r = await client.get(f"/api/patients/{patient.id}/documents?q=EEG", headers=headers)
    assert r.status_code == 200
    assert [d["file_name"] for d in r.json()] == ["eeg-bericht.pdf"]


async def test_q_no_match_returns_empty(client: AsyncClient, db: AsyncSession):
    _, patient = await _setup(db)
    headers = await _auth(client)
    r = await client.get(f"/api/patients/{patient.id}/documents?q=nichtvorhanden", headers=headers)
    assert r.status_code == 200
    assert r.json() == []


async def test_without_q_returns_all(client: AsyncClient, db: AsyncSession):
    _, patient = await _setup(db)
    headers = await _auth(client)
    r = await client.get(f"/api/patients/{patient.id}/documents", headers=headers)
    assert r.status_code == 200
    assert len(r.json()) == 3
