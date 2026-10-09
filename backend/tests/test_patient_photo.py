"""Patient photo — encrypted PHI under the patient KEK (ADR-031, #76 follow-up)."""

from datetime import UTC, datetime

from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import hash_password
from app.models.access import PatientAccess
from app.models.patient import Patient
from app.models.patient_key import PatientKey
from app.models.user import User

# a 1x1 PNG
PNG = bytes.fromhex(
    "89504e470d0a1a0a0000000d4948445200000001000000010806000000"
    "1f15c4890000000d49444154789c6360000002000100" "05fe02fea7"  # noqa
)


async def _setup(db: AsyncSession, email="photo@t.com", level="admin"):
    u = User(email=email, hashed_password=hash_password("Pass1!"), role="user", is_active=True, first_name="P", last_name="U")
    db.add(u)
    await db.commit()
    await db.refresh(u)
    p = Patient(given_name="Emilia", family_name="Hauber", created_by=u.id)
    db.add(p)
    await db.commit()
    await db.refresh(p)
    db.add(PatientAccess(patient_id=p.id, user_id=u.id, access_level=level, granted_by_user_id=u.id, granted_at=datetime.now(UTC)))
    await db.commit()
    return u, p


async def _auth(client, email="photo@t.com"):
    r = await client.post("/api/auth/login", json={"email": email, "password": "Pass1!"})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


async def test_upload_serve_and_delete(client: AsyncClient, db: AsyncSession):
    _, p = await _setup(db)
    h = await _auth(client)

    # upload
    r = await client.post(f"/api/patients/{p.id}/photo", files={"file": ("a.png", PNG, "image/png")}, headers=h)
    assert r.status_code == 200, r.text
    assert r.json()["has_photo"] is True

    # stored ciphertext must NOT equal the plaintext bytes (encrypted at rest)
    key = (await db.execute(select(PatientKey).where(PatientKey.patient_id == p.id))).scalar_one_or_none()
    assert key is not None  # a KEK was provisioned

    # serve — round-trips back to the exact bytes, decrypted
    g = await client.get(f"/api/patients/{p.id}/photo", headers=h)
    assert g.status_code == 200
    assert g.headers["content-type"] == "image/png"
    assert g.content == PNG

    # delete
    d = await client.delete(f"/api/patients/{p.id}/photo", headers=h)
    assert d.status_code == 200
    assert d.json()["has_photo"] is False
    assert (await client.get(f"/api/patients/{p.id}/photo", headers=h)).status_code == 404


async def test_rejects_non_image(client: AsyncClient, db: AsyncSession):
    _, p = await _setup(db, email="photo2@t.com")
    h = await _auth(client, "photo2@t.com")
    r = await client.post(f"/api/patients/{p.id}/photo", files={"file": ("x.svg", b"<svg/>", "image/svg+xml")}, headers=h)
    assert r.status_code == 415


async def test_view_only_cannot_upload(client: AsyncClient, db: AsyncSession):
    owner, p = await _setup(db, email="owner_ph@t.com")
    viewer = User(email="viewer_ph@t.com", hashed_password=hash_password("Pass1!"), role="user", is_active=True, first_name="V", last_name="U")
    db.add(viewer)
    await db.commit()
    await db.refresh(viewer)
    db.add(PatientAccess(patient_id=p.id, user_id=viewer.id, access_level="view", granted_at=datetime.now(UTC)))
    await db.commit()
    h = await _auth(client, "viewer_ph@t.com")
    # insufficient level is masked as 404 app-wide (no existence leak, ADR 025)
    r = await client.post(f"/api/patients/{p.id}/photo", files={"file": ("a.png", PNG, "image/png")}, headers=h)
    assert r.status_code == 404
