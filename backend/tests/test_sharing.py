"""Tests for consent-gated file sharing (Sharing Purposes / Shares)."""


from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import hash_password
from app.models.document import DocumentReference
from datetime import UTC, datetime

from app.models.access import PatientAccess
from app.models.patient import Patient
from app.models.sharing import Share, ShareDecline
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
    await _user(db, "mgr2@test.com", role="manager")
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
    await _user(db, "mgr3@test.com", role="manager")
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


# --- Data Set (ADR 064) --------------------------------------------------------

async def _attempt(db: AsyncSession, patient: Patient, owner: User, on: str, outcome: str, reason: str | None = None):
    from app.models.development import TestAttempt
    t = TestAttempt(patient_id=patient.id, owner_id=owner.id, test_name="SON-R 2-8", attempted_on=on,
                    outcome=outcome, reason=reason)
    db.add(t)
    await db.commit()
    await db.refresh(t)
    return t


async def test_data_set_snapshot_is_frozen_and_downloads_as_csv(client: AsyncClient, db: AsyncSession):
    await _user(db, "mgr8@test.com", role="manager")
    owner = await _user(db, "owner8@test.com", role="user")
    patient = await _patient(db, owner)
    patient.birth_date = "2020-05-20"
    await db.commit()
    await _attempt(db, patient, owner, "2023-01", "completed")  # before since: never offered
    kept = await _attempt(db, patient, owner, "2024-06-19", "refused", "=cried at the door")
    dropped = await _attempt(db, patient, owner, "2024-09", "stopped")

    mgr_h = await _auth(client, "mgr8@test.com")
    owner_h = await _auth(client, "owner8@test.com")
    purpose_id = (await client.post("/api/sharing-purposes", headers=mgr_h, json={
        "name": "Registry", "identification_mode": "anonymous",
        "data_set": "test_attempts", "data_set_since": "2024-01-01",
    })).json()["id"]

    rows = (await client.get(f"/api/patients/{patient.id}/sharing/purposes/{purpose_id}/rows", headers=owner_h)).json()
    assert [r["id"] for r in rows] == [str(kept.id), str(dropped.id)]
    assert rows[0]["values"]["age_months"] == 48  # 20 May 2020 to 19 Jun 2024

    r = await client.post(f"/api/patients/{patient.id}/sharing/purposes/{purpose_id}/consent",
                          json={"record_ids": [str(kept.id)]}, headers=owner_h)
    assert r.status_code == 200, r.text
    assert r.json()[0]["row_count"] == 1

    kept.reason = "edited later"  # does not reach the snapshot
    await db.commit()

    csv = (await client.get(f"/api/sharing-purposes/{purpose_id}/download", headers=mgr_h)).content.decode()
    assert csv.startswith("﻿patient;test;date;age_months")
    lines = csv.strip().splitlines()
    assert len(lines) == 2
    assert lines[1].startswith("Patient #") and "Emma" not in lines[1]
    assert "'=cried at the door" in lines[1] and "edited later" not in lines[1]


async def test_data_set_no_empty_consent_and_sharing_again_replaces(client: AsyncClient, db: AsyncSession):
    await _user(db, "mgr9@test.com", role="manager")
    owner = await _user(db, "owner9@test.com", role="user")
    patient = await _patient(db, owner)

    mgr_h = await _auth(client, "mgr9@test.com")
    owner_h = await _auth(client, "owner9@test.com")
    purpose_id = (await client.post("/api/sharing-purposes", headers=mgr_h,
                                    json={"name": "R", "data_set": "test_attempts"})).json()["id"]
    consent = f"/api/patients/{patient.id}/sharing/purposes/{purpose_id}/consent"

    assert (await client.post(consent, json={"record_ids": []}, headers=owner_h)).status_code == 400
    open_ids = [p["id"] for p in (await client.get(f"/api/patients/{patient.id}/sharing/open-requests", headers=owner_h)).json()]
    assert purpose_id in open_ids

    a = await _attempt(db, patient, owner, "2024-03", "refused")
    await client.post(consent, json={"record_ids": [str(a.id)]}, headers=owner_h)
    b = await _attempt(db, patient, owner, "2024-04", "completed")
    await client.post(consent, json={"record_ids": [str(a.id), str(b.id)]}, headers=owner_h)

    shares = (await db.execute(select(Share).where(Share.sharing_purpose_id == purpose_id))).scalars().all()
    assert len(shares) == 1 and len(shares[0].rows) == 2

    share_id = (await client.get(f"/api/patients/{patient.id}/sharing/shares", headers=owner_h)).json()[0]["id"]
    await client.post(f"/api/patients/{patient.id}/sharing/shares/{share_id}/revoke", headers=owner_h)
    assert (await client.get(f"/api/sharing-purposes/{purpose_id}/download", headers=mgr_h)).status_code == 404


async def test_data_set_domain_filters_observations_only(client: AsyncClient, db: AsyncSession):
    await _user(db, "mgr10@test.com", role="manager")
    mgr_h = await _auth(client, "mgr10@test.com")
    bad = {"name": "R", "data_set": "test_attempts", "data_set_domain": "motor"}
    assert (await client.post("/api/sharing-purposes", json=bad, headers=mgr_h)).status_code == 422


def test_age_months():
    from app.services.data_set import age_months
    assert age_months("2020-05-20", "2024-05") == 48
    assert age_months("2020-05-20", "2024-05-19") == 47
    assert age_months("2020-05-20", "2020-04") is None
    assert age_months(None, "2024-05") is None
