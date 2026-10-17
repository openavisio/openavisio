"""Demo instances lock uploads to the bundled sample (by sha256).

The demo shares one admin account with every visitor — without this lock the
public demo is a 24h anonymous file drop under our domain.
"""

import hashlib
from datetime import UTC, datetime

from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.security import hash_password
from app.models.access import PatientAccess
from app.models.patient import Patient
from app.models.user import User

SAMPLE = b"%PDF-1.4 demo sample content"
SAMPLE_SHA = hashlib.sha256(SAMPLE).hexdigest()


async def _setup(db: AsyncSession):
    u = User(email="demo@t.com", hashed_password=hash_password("Pass1!"), role="user",
             is_active=True, first_name="T", last_name="User")
    db.add(u)
    await db.commit()
    await db.refresh(u)
    p = Patient(given_name="Emma", family_name="Test", created_by=u.id)
    db.add(p)
    await db.commit()
    await db.refresh(p)
    db.add(PatientAccess(patient_id=p.id, user_id=u.id, access_level="admin", granted_at=datetime.now(UTC)))
    await db.commit()
    return u, p


async def _auth(client: AsyncClient) -> dict:
    r = await client.post("/api/auth/login", json={"email": "demo@t.com", "password": "Pass1!"})
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


async def test_demo_lock_refuses_foreign_files_allows_the_sample(client: AsyncClient, db: AsyncSession, monkeypatch):
    _, p = await _setup(db)
    h = await _auth(client)
    monkeypatch.setattr(settings, "demo_locked_upload_sha256", SAMPLE_SHA)

    r = await client.post(f"/api/patients/{p.id}/documents/upload", headers=h,
                          files={"file": ("evil.pdf", b"%PDF-1.4 something else", "application/pdf")})
    assert r.status_code == 403, "a foreign file must be refused"

    r = await client.post(f"/api/patients/{p.id}/documents/upload", headers=h,
                          files={"file": ("sample.pdf", SAMPLE, "application/pdf")})
    assert r.status_code == 201, "the bundled sample must pass"

    r = await client.post(f"/api/patients/{p.id}/photo", headers=h,
                          files={"file": ("x.png", b"png", "image/png")})
    assert r.status_code == 403, "photo upload is disabled on a demo"

    r = await client.post(f"/api/patients/{p.id}/intake-forms", headers=h,
                          files={"file": ("sample.pdf", SAMPLE, "application/pdf")})
    assert r.status_code == 403, "intake form upload is disabled on a demo, even for the sample"


async def test_no_lock_means_normal_uploads(client: AsyncClient, db: AsyncSession, monkeypatch):
    _, p = await _setup(db)
    h = await _auth(client)
    monkeypatch.setattr(settings, "demo_locked_upload_sha256", "")
    r = await client.post(f"/api/patients/{p.id}/documents/upload", headers=h,
                          files={"file": ("normal.pdf", b"%PDF-1.4 anything", "application/pdf")})
    assert r.status_code == 201


async def test_the_demo_is_read_only_but_for_the_sample_and_the_chat(client: AsyncClient, db: AsyncSession, monkeypatch):
    """Every visitor shares one login: what one writes, all others read until the nightly reset."""
    from sqlalchemy import func, select

    from app.models.chat import ChatMessage
    from tests.test_chat_fhir_emergency_plan import _fake_aiservice

    _, p = await _setup(db)
    h = await _auth(client)
    monkeypatch.setattr(settings, "demo_locked_upload_sha256", SAMPLE_SHA)

    r = await client.post(f"/api/patients/{p.id}/diary", headers=h, json={"content": "Mein Sohn hat ..."})
    assert r.status_code == 403, "nothing a visitor types may reach the others"
    r = await client.patch("/api/auth/me", headers=h, json={"first_name": "x"})
    assert r.status_code == 403

    r = await client.post(f"/api/patients/{p.id}/documents/upload", headers=h,
                          files={"file": ("sample.pdf", SAMPLE, "application/pdf")})
    assert r.status_code == 201
    r = await client.delete(f"/api/documents/{r.json()['id']}", headers=h)
    assert r.status_code == 204, "the upload panel removes the previous sample run"

    _fake_aiservice(monkeypatch, {})
    r = await client.post(f"/api/patients/{p.id}/chat", headers=h, json={"question": "Wann war der letzte Termin?"})
    assert r.status_code == 200 and r.json()["answer"]
    assert (await db.execute(select(func.count()).select_from(ChatMessage))).scalar() == 0, "no visitor's question is kept"
    r = await client.get(f"/api/patients/{p.id}/chat/history", headers=h)
    assert r.json()["messages"] == []
