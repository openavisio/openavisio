"""Tests for consent-gated file sharing (Sharing Purposes / Shares)."""

import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import hash_password
from app.models.document import DocumentReference
from datetime import UTC, datetime

from app.models.access import PatientAccess
from app.models.patient import Patient
from app.models.sharing import Share, ShareDecline, SharingPurpose
from app.models.user import User
from app.services.erasure import erase_patient


# --- fixtures / helpers ------------------------------------------------------

async def _user(db: AsyncSession, email: str, role: str = "user") -> User:
    u = User(email=email, hashed_password=hash_password("Pass1!"), role=role, is_active=True,
             first_name="T", last_name="User")
    db.add(u)
    await db.commit()
    await db.refresh(u)
    return u


async def _patient(db: AsyncSession, owner: User) -> Patient:
    p = Patient(given_name="Emma", family_name="Test", created_by=owner.id)
    db.add(p)
    await db.commit()
    await db.refresh(p)
    db.add(PatientAccess(patient_id=p.id, user_id=owner.id, access_level="admin",
                         granted_by_user_id=owner.id, granted_at=datetime.now(UTC)))
    await db.commit()
    return p


async def _document(db: AsyncSession, patient: Patient, owner: User, name: str = "eeg.edf") -> DocumentReference:
    d = DocumentReference(patient_id=patient.id, owner_id=owner.id, file_name=name,
                          content_type="application/octet-stream")
    db.add(d)
    await db.commit()
    await db.refresh(d)
    return d


async def _auth(client: AsyncClient, email: str) -> dict:
    r = await client.post("/api/auth/login", json={"email": email, "password": "Pass1!"})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


# --- tests -------------------------------------------------------------------

async def test_create_purpose_requires_manager(client: AsyncClient, db: AsyncSession):
    await _user(db, "plain@test.com", role="user")
    await _user(db, "mgr@test.com", role="manager")

    plain = await _auth(client, "plain@test.com")
    mgr = await _auth(client, "mgr@test.com")

    body = {"name": "Epilepsy Study", "description": "EEG data", "identification_mode": "identified"}
    assert (await client.post("/api/sharing-purposes", json=body, headers=plain)).status_code == 403
    r = await client.post("/api/sharing-purposes", json=body, headers=mgr)
    assert r.status_code == 201
    assert r.json()["status"] == "open"


async def test_open_request_consent_and_collection(client: AsyncClient, db: AsyncSession):
    mgr = await _user(db, "mgr2@test.com", role="manager")
    owner = await _user(db, "owner2@test.com", role="user")
    patient = await _patient(db, owner)
    doc = await _document(db, patient, owner)

    mgr_h = await _auth(client, "mgr2@test.com")
    owner_h = await _auth(client, "owner2@test.com")

    purpose_id = (await client.post(
        "/api/sharing-purposes",
        json={"name": "Study", "description": "EEG", "identification_mode": "identified"},
        headers=mgr_h,
    )).json()["id"]

    # Caregiver sees one open request
    reqs = (await client.get(f"/api/patients/{patient.id}/sharing/open-requests", headers=owner_h)).json()
    assert [r["id"] for r in reqs] == [purpose_id]

    # Consent with the document
    r = await client.post(
        f"/api/patients/{patient.id}/sharing/purposes/{purpose_id}/consent",
        json={"document_ids": [str(doc.id)]}, headers=owner_h,
    )
    assert r.status_code == 200
    assert len(r.json()) == 1 and r.json()[0]["status"] == "active"

    # Nudge cleared
    reqs = (await client.get(f"/api/patients/{patient.id}/sharing/open-requests", headers=owner_h)).json()
    assert reqs == []

    # Manager collection view shows the file under the patient's name
    collected = (await client.get(f"/api/sharing-purposes/{purpose_id}/shares", headers=mgr_h)).json()
    assert len(collected) == 1
    assert collected[0]["patient_label"] == "Test, Emma"
    assert collected[0]["patient_id"] == str(patient.id)
    assert collected[0]["file_name"] == "eeg.edf"


async def test_terms_freeze_after_first_share(client: AsyncClient, db: AsyncSession):
    mgr = await _user(db, "mgr3@test.com", role="manager")
    owner = await _user(db, "owner3@test.com", role="user")
    patient = await _patient(db, owner)
    doc = await _document(db, patient, owner)

    mgr_h = await _auth(client, "mgr3@test.com")
    owner_h = await _auth(client, "owner3@test.com")

    purpose_id = (await client.post(
        "/api/sharing-purposes", json={"name": "S", "description": "EEG", "identification_mode": "identified"},
        headers=mgr_h,
    )).json()["id"]

    # Editable before any share
    assert (await client.patch(f"/api/sharing-purposes/{purpose_id}",
                               json={"description": "EEG + MRI"}, headers=mgr_h)).status_code == 200

    await client.post(f"/api/patients/{patient.id}/sharing/purposes/{purpose_id}/consent",
                      json={"document_ids": [str(doc.id)]}, headers=owner_h)

    # Description now frozen
    assert (await client.patch(f"/api/sharing-purposes/{purpose_id}",
                               json={"description": "changed"}, headers=mgr_h)).status_code == 409
    assert (await client.patch(f"/api/sharing-purposes/{purpose_id}",
                               json={"identification_mode": "anonymous"}, headers=mgr_h)).status_code == 409
    # Name still editable
    assert (await client.patch(f"/api/sharing-purposes/{purpose_id}",
                               json={"name": "Renamed"}, headers=mgr_h)).status_code == 200


async def test_decline_clears_request(client: AsyncClient, db: AsyncSession):
    await _user(db, "mgr4@test.com", role="manager")
    owner = await _user(db, "owner4@test.com", role="user")
    patient = await _patient(db, owner)

    mgr_h = await _auth(client, "mgr4@test.com")
    owner_h = await _auth(client, "owner4@test.com")
    purpose_id = (await client.post("/api/sharing-purposes", json={"name": "S", "description": "EEG"},
                                    headers=mgr_h)).json()["id"]

    r = await client.post(f"/api/patients/{patient.id}/sharing/purposes/{purpose_id}/decline", headers=owner_h)
    assert r.status_code == 204
    reqs = (await client.get(f"/api/patients/{patient.id}/sharing/open-requests", headers=owner_h)).json()
    assert reqs == []


async def test_revoke_reopens_request(client: AsyncClient, db: AsyncSession):
    await _user(db, "mgr5@test.com", role="manager")
    owner = await _user(db, "owner5@test.com", role="user")
    patient = await _patient(db, owner)
    doc = await _document(db, patient, owner)

    mgr_h = await _auth(client, "mgr5@test.com")
    owner_h = await _auth(client, "owner5@test.com")
    purpose_id = (await client.post("/api/sharing-purposes", json={"name": "S", "description": "EEG"},
                                    headers=mgr_h)).json()["id"]
    share_id = (await client.post(f"/api/patients/{patient.id}/sharing/purposes/{purpose_id}/consent",
                                  json={"document_ids": [str(doc.id)]}, headers=owner_h)).json()[0]["id"]

    r = await client.post(f"/api/patients/{patient.id}/sharing/shares/{share_id}/revoke", headers=owner_h)
    assert r.status_code == 200 and r.json()["status"] == "revoked"

    # No active share, no decline -> request surfaces again
    reqs = (await client.get(f"/api/patients/{patient.id}/sharing/open-requests", headers=owner_h)).json()
    assert [x["id"] for x in reqs] == [purpose_id]
    # Revoked share no longer in the manager's collection
    assert (await client.get(f"/api/sharing-purposes/{purpose_id}/shares", headers=mgr_h)).json() == []


async def test_anonymous_mode_hides_identity(client: AsyncClient, db: AsyncSession):
    await _user(db, "mgr6@test.com", role="manager")
    owner = await _user(db, "owner6@test.com", role="user")
    patient = await _patient(db, owner)
    doc = await _document(db, patient, owner)

    mgr_h = await _auth(client, "mgr6@test.com")
    owner_h = await _auth(client, "owner6@test.com")
    purpose_id = (await client.post("/api/sharing-purposes",
                                    json={"name": "S", "description": "EEG", "identification_mode": "anonymous"},
                                    headers=mgr_h)).json()["id"]
    await client.post(f"/api/patients/{patient.id}/sharing/purposes/{purpose_id}/consent",
                      json={"document_ids": [str(doc.id)]}, headers=owner_h)

    collected = (await client.get(f"/api/sharing-purposes/{purpose_id}/shares", headers=mgr_h)).json()
    assert collected[0]["patient_id"] is None
    assert collected[0]["patient_label"].startswith("Patient #")
    assert "Emma" not in collected[0]["patient_label"]


async def test_patient_erasure_deletes_shares(client: AsyncClient, db: AsyncSession):
    mgr = await _user(db, "mgr7@test.com", role="manager")
    owner = await _user(db, "owner7@test.com", role="user")
    patient = await _patient(db, owner)
    doc = await _document(db, patient, owner)

    mgr_h = await _auth(client, "mgr7@test.com")
    owner_h = await _auth(client, "owner7@test.com")
    purpose_id = (await client.post("/api/sharing-purposes", json={"name": "S", "description": "EEG"},
                                    headers=mgr_h)).json()["id"]
    await client.post(f"/api/patients/{patient.id}/sharing/purposes/{purpose_id}/consent",
                      json={"document_ids": [str(doc.id)]}, headers=owner_h)

    pid = patient.id
    await erase_patient(pid, mgr, db)

    assert (await db.execute(select(Share).where(Share.patient_id == pid))).first() is None
    assert (await db.execute(select(ShareDecline).where(ShareDecline.patient_id == pid))).first() is None
