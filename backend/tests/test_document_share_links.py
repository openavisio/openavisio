"""Tests for external document share links — see docs/adr/021-external-document-share-links.md."""

import hashlib
from datetime import UTC, datetime, timedelta

from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.encryption import encrypt_document
from app.core.security import hash_password
from app.core.storage import get_storage
from app.models.access import PatientAccess
from app.models.audit import AuditLog
from app.models.document import DocumentReference
from app.models.patient import Patient
from app.models.share_link import DocumentShareLink, DocumentShareLinkItem
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
    p = Patient(given_name="Emma", family_name="Test", birth_date="2015-04-02", created_by=owner.id)
    db.add(p)
    await db.commit()
    await db.refresh(p)
    db.add(PatientAccess(patient_id=p.id, user_id=owner.id, access_level="admin",
                         granted_by_user_id=owner.id, granted_at=datetime.now(UTC)))
    await db.commit()
    return p


async def _document(db: AsyncSession, patient: Patient, owner: User, name: str = "befund.pdf") -> DocumentReference:
    from app.core.patient_keys import ensure_patient_kek
    await ensure_patient_kek(db, patient.id)  # every real document's patient has a KEK (ADR-031)
    d = DocumentReference(patient_id=patient.id, owner_id=owner.id, file_name=name, type="lab_report",
                          content_type="application/pdf",
                          extraction_json={"diagnoses": [{"name": "Epilepsy"}]})
    db.add(d)
    await db.commit()
    await db.refresh(d)
    return d


async def _grant(db: AsyncSession, patient: Patient, user: User, level: str = "view") -> None:
    db.add(PatientAccess(patient_id=patient.id, user_id=user.id, access_level=level,
                         granted_at=datetime.now(UTC)))
    await db.commit()


async def _representation(db: AsyncSession, patient: Patient, user: User) -> None:
    # legal representation is now a flag on the access grant (ADR 027)
    existing = (await db.execute(select(PatientAccess).where(
        PatientAccess.patient_id == patient.id, PatientAccess.user_id == user.id,
        PatientAccess.revoked_at == None,  # noqa: E711
    ))).scalars().first()
    if existing:
        existing.is_legal_representative = True
    else:
        db.add(PatientAccess(patient_id=patient.id, user_id=user.id, access_level="full",
                             granted_at=datetime.now(UTC), is_legal_representative=True))
    await db.commit()


async def _auth(client: AsyncClient, email: str) -> dict:
    r = await client.post("/api/auth/login", json={"email": email, "password": "Pass1!"})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def _token_of(url: str) -> str:
    return url.rsplit("/", 1)[1]


# --- creation authorization (Regel X + owner/rep exception) ------------------

async def test_owner_user_can_create_staff_cannot(client: AsyncClient, db: AsyncSession):
    owner = await _user(db, "owner@t.com", role="user")
    await _user(db, "admin@t.com", role="admin")
    patient = await _patient(db, owner)
    doc = await _document(db, patient, owner)

    owner_h = await _auth(client, "owner@t.com")
    admin_h = await _auth(client, "admin@t.com")
    body = {"document_ids": [str(doc.id)], "expiry_days": 30}

    # Staff admin has no patient access at all since ADR 025 → 404 (no existence leak)
    assert (await client.post(f"/api/patients/{patient.id}/share-links", json=body, headers=admin_h)).status_code == 404
    # Owner (role=user) → allowed
    r = await client.post(f"/api/patients/{patient.id}/share-links", json=body, headers=owner_h)
    assert r.status_code == 201, r.text
    assert r.json()["created_legal"] is False


async def test_owner_admin_exception_allowed(client: AsyncClient, db: AsyncSession):
    # A parent who is also the deployment admin shares via their legal representation (ADR 026).
    admin = await _user(db, "adminowner@t.com", role="admin")
    patient = await _patient(db, admin)
    doc = await _document(db, patient, admin)
    await _representation(db, patient, admin)
    h = await _auth(client, "adminowner@t.com")
    r = await client.post(f"/api/patients/{patient.id}/share-links",
                          json={"document_ids": [str(doc.id)], "expiry_days": 7}, headers=h)
    assert r.status_code == 201, r.text


async def test_active_rep_allowed_and_flagged(client: AsyncClient, db: AsyncSession):
    owner = await _user(db, "owner_r@t.com", role="user")
    rep = await _user(db, "rep@t.com", role="user")
    patient = await _patient(db, owner)
    doc = await _document(db, patient, owner)
    await _representation(db, patient, rep)
    h = await _auth(client, "rep@t.com")
    r = await client.post(f"/api/patients/{patient.id}/share-links",
                          json={"document_ids": [str(doc.id)], "expiry_days": 30}, headers=h)
    assert r.status_code == 201, r.text
    assert r.json()["created_legal"] is True


async def test_manager_with_grant_still_forbidden(client: AsyncClient, db: AsyncSession):
    owner = await _user(db, "owner_m@t.com", role="user")
    mgr = await _user(db, "mgr@t.com", role="manager")
    patient = await _patient(db, owner)
    doc = await _document(db, patient, owner)
    await _grant(db, patient, mgr, "full")  # concrete access, but still staff
    h = await _auth(client, "mgr@t.com")
    r = await client.post(f"/api/patients/{patient.id}/share-links",
                          json={"document_ids": [str(doc.id)], "expiry_days": 30}, headers=h)
    assert r.status_code == 403, r.text


async def test_plain_user_with_grant_allowed(client: AsyncClient, db: AsyncSession):
    owner = await _user(db, "owner_g@t.com", role="user")
    helper = await _user(db, "helper@t.com", role="user")
    patient = await _patient(db, owner)
    doc = await _document(db, patient, owner)
    await _grant(db, patient, helper, "contribute")
    h = await _auth(client, "helper@t.com")
    r = await client.post(f"/api/patients/{patient.id}/share-links",
                          json={"document_ids": [str(doc.id)], "expiry_days": 30}, headers=h)
    assert r.status_code == 201, r.text


# --- validation --------------------------------------------------------------

async def test_invalid_expiry_and_empty_docs(client: AsyncClient, db: AsyncSession):
    owner = await _user(db, "owner_v@t.com", role="user")
    patient = await _patient(db, owner)
    doc = await _document(db, patient, owner)
    h = await _auth(client, "owner_v@t.com")

    assert (await client.post(f"/api/patients/{patient.id}/share-links",
                              json={"document_ids": [str(doc.id)], "expiry_days": 14}, headers=h)).status_code == 422
    assert (await client.post(f"/api/patients/{patient.id}/share-links",
                              json={"document_ids": [], "expiry_days": 30}, headers=h)).status_code == 400


# --- token: only the hash is stored ------------------------------------------

async def test_only_hash_stored(client: AsyncClient, db: AsyncSession):
    owner = await _user(db, "owner_h@t.com", role="user")
    patient = await _patient(db, owner)
    doc = await _document(db, patient, owner)
    h = await _auth(client, "owner_h@t.com")
    url = (await client.post(f"/api/patients/{patient.id}/share-links",
                             json={"document_ids": [str(doc.id)], "expiry_days": 30}, headers=h)).json()["url"]
    token = _token_of(url)

    link = (await db.execute(select(DocumentShareLink).where(DocumentShareLink.patient_id == patient.id))).scalar_one()
    assert link.token_hash == hashlib.sha256(token.encode()).hexdigest()
    assert token not in link.token_hash


# --- public view + status codes ----------------------------------------------

async def test_public_view_and_error_codes(client: AsyncClient, db: AsyncSession):
    owner = await _user(db, "owner_p@t.com", role="user")
    patient = await _patient(db, owner)
    doc = await _document(db, patient, owner)
    h = await _auth(client, "owner_p@t.com")
    url = (await client.post(f"/api/patients/{patient.id}/share-links",
                             json={"document_ids": [str(doc.id)], "expiry_days": 30}, headers=h)).json()["url"]
    token = _token_of(url)

    r = await client.get(f"/api/public/document-shares/{token}")
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["patient"]["given_name"] == "Emma"
    assert body["patient"]["birth_date"] == "2015-04-02"
    assert len(body["documents"]) == 1
    assert body["documents"][0]["extraction"]["diagnoses"][0]["name"] == "Epilepsy"
    assert r.headers.get("referrer-policy") == "no-referrer"
    assert "noindex" in r.headers.get("x-robots-tag", "")

    # Unknown token → 404
    assert (await client.get("/api/public/document-shares/deadbeef")).status_code == 404


async def test_expired_and_revoked_return_410(client: AsyncClient, db: AsyncSession):
    owner = await _user(db, "owner_e@t.com", role="user")
    patient = await _patient(db, owner)
    doc = await _document(db, patient, owner)
    h = await _auth(client, "owner_e@t.com")

    # Expired
    url = (await client.post(f"/api/patients/{patient.id}/share-links",
                             json={"document_ids": [str(doc.id)], "expiry_days": 7}, headers=h)).json()["url"]
    token = _token_of(url)
    link = (await db.execute(select(DocumentShareLink).where(DocumentShareLink.patient_id == patient.id))).scalar_one()
    link.expires_at = datetime.now(UTC) - timedelta(days=1)
    await db.commit()
    assert (await client.get(f"/api/public/document-shares/{token}")).status_code == 410

    # Revoked
    doc2 = await _document(db, patient, owner, "x.pdf")
    resp = (await client.post(f"/api/patients/{patient.id}/share-links",
                              json={"document_ids": [str(doc2.id)], "expiry_days": 30}, headers=h)).json()
    token2 = _token_of(resp["url"])
    await client.post(f"/api/patients/{patient.id}/share-links/{resp['id']}/revoke", headers=h)
    assert (await client.get(f"/api/public/document-shares/{token2}")).status_code == 410


# --- append: snapshot stays, expiry unchanged --------------------------------

async def test_append_keeps_snapshot_and_expiry(client: AsyncClient, db: AsyncSession):
    owner = await _user(db, "owner_a@t.com", role="user")
    patient = await _patient(db, owner)
    d1 = await _document(db, patient, owner, "one.pdf")
    d2 = await _document(db, patient, owner, "two.pdf")
    h = await _auth(client, "owner_a@t.com")

    created = (await client.post(f"/api/patients/{patient.id}/share-links",
                                 json={"document_ids": [str(d1.id)], "expiry_days": 30}, headers=h)).json()
    link_id, expires_at = created["id"], created["expires_at"]
    assert len(created["documents"]) == 1

    added = (await client.post(f"/api/patients/{patient.id}/share-links/{link_id}/documents",
                               json={"document_ids": [str(d2.id)]}, headers=h)).json()
    assert len(added["documents"]) == 2
    assert added["expires_at"] == expires_at  # append does not extend expiry


async def test_append_to_revoked_conflict(client: AsyncClient, db: AsyncSession):
    owner = await _user(db, "owner_ar@t.com", role="user")
    patient = await _patient(db, owner)
    d1 = await _document(db, patient, owner, "one.pdf")
    d2 = await _document(db, patient, owner, "two.pdf")
    h = await _auth(client, "owner_ar@t.com")
    created = (await client.post(f"/api/patients/{patient.id}/share-links",
                                 json={"document_ids": [str(d1.id)], "expiry_days": 30}, headers=h)).json()
    await client.post(f"/api/patients/{patient.id}/share-links/{created['id']}/revoke", headers=h)
    r = await client.post(f"/api/patients/{patient.id}/share-links/{created['id']}/documents",
                          json={"document_ids": [str(d2.id)]}, headers=h)
    assert r.status_code == 409


# --- access audit: anonymous, debounced --------------------------------------

async def test_access_is_audited_and_debounced(client: AsyncClient, db: AsyncSession):
    owner = await _user(db, "owner_au@t.com", role="user")
    patient = await _patient(db, owner)
    doc = await _document(db, patient, owner)
    h = await _auth(client, "owner_au@t.com")
    token = _token_of((await client.post(f"/api/patients/{patient.id}/share-links",
                                         json={"document_ids": [str(doc.id)], "expiry_days": 30}, headers=h)).json()["url"])

    hdrs = {"X-Forwarded-For": "203.0.113.9", "User-Agent": "DrBrowser/1.0"}
    await client.get(f"/api/public/document-shares/{token}", headers=hdrs)
    await client.get(f"/api/public/document-shares/{token}", headers=hdrs)  # within debounce window

    rows = (await db.execute(select(AuditLog).where(
        AuditLog.entity_type == "DocumentShareLink", AuditLog.action == "accessed"))).scalars().all()
    assert len(rows) == 1  # second view debounced
    e = rows[0]
    assert e.user_id is None
    assert e.user_name == "External via share link"
    assert e.ip_address == "203.0.113.9"
    assert e.user_agent == "DrBrowser/1.0"
    assert e.changes["event"] == "open"


# --- deleted documents drop out ----------------------------------------------

async def test_deleted_document_drops_and_empty_link_410(client: AsyncClient, db: AsyncSession):
    owner = await _user(db, "owner_d@t.com", role="user")
    patient = await _patient(db, owner)
    d1 = await _document(db, patient, owner, "a.pdf")
    d2 = await _document(db, patient, owner, "b.pdf")
    h = await _auth(client, "owner_d@t.com")
    token = _token_of((await client.post(f"/api/patients/{patient.id}/share-links",
                                         json={"document_ids": [str(d1.id), str(d2.id)], "expiry_days": 30},
                                         headers=h)).json()["url"])

    d1.is_deleted = True
    await db.commit()
    body = (await client.get(f"/api/public/document-shares/{token}")).json()
    assert len(body["documents"]) == 1

    d2.is_deleted = True
    await db.commit()
    assert (await client.get(f"/api/public/document-shares/{token}")).status_code == 410


# --- file download -----------------------------------------------------------

async def test_file_download_and_wrong_doc(client: AsyncClient, db: AsyncSession):
    owner = await _user(db, "owner_f@t.com", role="user")
    patient = await _patient(db, owner)
    doc = await _document(db, patient, owner)
    other = await _document(db, patient, owner, "other.pdf")  # not in the link
    h = await _auth(client, "owner_f@t.com")
    token = _token_of((await client.post(f"/api/patients/{patient.id}/share-links",
                                         json={"document_ids": [str(doc.id)], "expiry_days": 30}, headers=h)).json()["url"])

    payload = b"%PDF-1.4 hello"
    key = f"test-shares/{doc.id}.bin"
    storage = get_storage()
    from app.core.patient_keys import get_patient_kek
    blob, wrapped_dek = encrypt_document(payload, await get_patient_kek(db, patient.id))
    storage.write(key, blob)
    doc.storage_path = key
    doc.encrypted_dek = wrapped_dek
    await db.commit()
    try:
        r = await client.get(f"/api/public/document-shares/{token}/documents/{doc.id}/file")
        assert r.status_code == 200
        assert r.content == payload
        assert "inline" in r.headers.get("content-disposition", "")

        rd = await client.get(f"/api/public/document-shares/{token}/documents/{doc.id}/file?download=true")
        assert "attachment" in rd.headers.get("content-disposition", "")

        # Document not part of the link → 404
        assert (await client.get(
            f"/api/public/document-shares/{token}/documents/{other.id}/file")).status_code == 404
    finally:
        storage.delete(key)


# --- erasure cascade ---------------------------------------------------------

async def test_patient_erasure_deletes_links_items_and_access_logs(client: AsyncClient, db: AsyncSession):
    owner = await _user(db, "owner_er@t.com", role="user")
    actor = await _user(db, "actor@t.com", role="admin")
    patient = await _patient(db, owner)
    doc = await _document(db, patient, owner)
    h = await _auth(client, "owner_er@t.com")
    token = _token_of((await client.post(f"/api/patients/{patient.id}/share-links",
                                         json={"document_ids": [str(doc.id)], "expiry_days": 30}, headers=h)).json()["url"])
    await client.get(f"/api/public/document-shares/{token}")  # produce an access log

    pid = patient.id
    await erase_patient(pid, actor, db)

    assert (await db.execute(select(DocumentShareLink).where(DocumentShareLink.patient_id == pid))).first() is None
    assert (await db.execute(select(DocumentShareLinkItem).where(DocumentShareLinkItem.patient_id == pid))).first() is None
    accessed = (await db.execute(select(AuditLog).where(
        AuditLog.entity_type == "DocumentShareLink", AuditLog.action == "accessed"))).scalars().all()
    assert accessed == []
