"""The per-Patient ZIP export (ADR 052): FHIR bundle plus every Document as its file."""

import io
import json
import zipfile
from datetime import UTC, datetime

from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.encryption import encrypt_document
from app.core.patient_keys import ensure_patient_kek, get_patient_kek
from app.core.security import hash_password
from app.core.storage import get_storage
from app.models.access import PatientAccess
from app.models.audit import AuditLog
from app.models.document import DocumentReference
from app.models.patient import Patient
from app.models.user import User


async def _user(db: AsyncSession, email: str) -> User:
    u = User(email=email, hashed_password=hash_password("Pass1!"), role="user", is_active=True,
             first_name="T", last_name="User")
    db.add(u)
    await db.commit()
    await db.refresh(u)
    return u


async def _auth(client: AsyncClient, email: str) -> dict:
    r = await client.post("/api/auth/login", json={"email": email, "password": "Pass1!"})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


async def _stored(db: AsyncSession, patient: Patient, owner: User, name: str, payload: bytes | None) -> DocumentReference:
    d = DocumentReference(patient_id=patient.id, owner_id=owner.id, file_name=name, content_type="application/pdf")
    db.add(d)
    await db.commit()
    await db.refresh(d)
    d.storage_path = f"test-export/{d.id}.bin"
    blob, d.encrypted_dek = encrypt_document(payload or b"", await get_patient_kek(db, patient.id))
    if payload is not None:  # None: the file is gone from storage
        get_storage().write(d.storage_path, blob)
    await db.commit()
    return d


async def test_the_zip_holds_the_bundle_and_every_document(client: AsyncClient, db: AsyncSession):
    owner = await _user(db, "zip_owner@t.com")
    await _user(db, "zip_stranger@t.com")
    patient = Patient(given_name="Emma", family_name="Test", birth_date="2015-04-02", created_by=owner.id)
    db.add(patient)
    await db.commit()
    db.add(PatientAccess(patient_id=patient.id, user_id=owner.id, access_level="view", granted_at=datetime.now(UTC)))
    await db.commit()
    await ensure_patient_kek(db, patient.id)
    await _stored(db, patient, owner, "befund.pdf", b"%PDF first")
    await _stored(db, patient, owner, "befund.pdf", b"%PDF second")
    await _stored(db, patient, owner, "weg.pdf", None)

    assert (await client.get(f"/api/patients/{patient.id}/export/zip",
                             headers=await _auth(client, "zip_stranger@t.com"))).status_code == 404  # no grant, no hint it exists

    r = await client.get(f"/api/patients/{patient.id}/export/zip", headers=await _auth(client, "zip_owner@t.com"))
    assert r.status_code == 200
    assert r.headers["content-type"] == "application/zip"
    zf = zipfile.ZipFile(io.BytesIO(r.content))
    assert json.loads(zf.read("fhir.json"))["resourceType"] == "Bundle"
    assert zf.read("documents/befund.pdf") == b"%PDF first"
    assert zf.read("documents/befund (2).pdf") == b"%PDF second"
    assert "documents/weg.pdf" in zf.read("documents/MISSING.txt").decode()

    audit = (await db.execute(select(AuditLog).where(AuditLog.action == "exported",
                                                     AuditLog.entity_id == str(patient.id)))).scalar_one()
    assert audit.changes == {"documents": 3} and audit.user_id == owner.id
