"""Tests for GDPR data governance: lawful basis, consent, retention purge (#15/#16)."""

from datetime import UTC, datetime, timedelta

from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import hash_password
from app.models.audit import AuditLog
from app.models.governance import ConsentRecord, DataCategory
from app.models.document import DocumentReference
from app.models.observation import Observation
from app.models.access import PatientAccess
from app.models.patient import Patient
from app.models.system import UserInvitation
from app.models.user import User
from app.services.governance import ensure_categories_seeded, run_retention_purge

BUILTINS = {"observation", "condition", "medication", "document", "incident", "diary", "calendar", "recommendation"}


async def _user(db: AsyncSession, email: str, role: str = "admin") -> User:
    u = User(email=email, hashed_password=hash_password("Pass1!"), role=role, is_active=True)
    db.add(u)
    await db.commit()
    await db.refresh(u)
    return u


async def _auth(client: AsyncClient, email: str) -> dict:
    r = await client.post("/api/auth/login", json={"email": email, "password": "Pass1!"})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


async def _patient(db: AsyncSession, owner: User) -> Patient:
    p = Patient(given_name="Emma", family_name="Test", created_by=owner.id)
    db.add(p)
    await db.commit()
    await db.refresh(p)
    db.add(PatientAccess(patient_id=p.id, user_id=owner.id, access_level="admin",
                         granted_by_user_id=owner.id, granted_at=datetime.now(UTC)))
    await db.commit()
    return p


# --- categories + config -----------------------------------------------------

async def test_categories_seeded_and_listed(client: AsyncClient, db: AsyncSession):
    await _user(db, "adm@t.com")
    h = await _auth(client, "adm@t.com")
    rows = (await client.get("/api/admin/data-categories", headers=h)).json()
    assert BUILTINS <= {r["code"] for r in rows}
    assert all(r["is_builtin"] for r in rows)
    assert all(r["lawful_basis"] is None and r["retention_days"] is None for r in rows)


async def test_update_category_and_validation(client: AsyncClient, db: AsyncSession):
    await _user(db, "adm2@t.com")
    h = await _auth(client, "adm2@t.com")
    await client.get("/api/admin/data-categories", headers=h)  # seed

    r = await client.put("/api/admin/data-categories/observation",
                         json={"lawful_basis": "art9_healthcare", "retention_days": 3650}, headers=h)
    assert r.status_code == 200
    assert r.json()["lawful_basis"] == "art9_healthcare"
    assert r.json()["retention_days"] == 3650

    assert (await client.put("/api/admin/data-categories/observation",
                             json={"lawful_basis": "nonsense"}, headers=h)).status_code == 422
    assert (await client.put("/api/admin/data-categories/observation",
                             json={"retention_days": 0}, headers=h)).status_code == 422
    assert (await client.put("/api/admin/data-categories/nope", json={}, headers=h)).status_code == 404


async def test_requires_admin(client: AsyncClient, db: AsyncSession):
    await _user(db, "plain@t.com", role="user")
    h = await _auth(client, "plain@t.com")
    assert (await client.get("/api/admin/data-categories", headers=h)).status_code == 403


# --- retention purge ---------------------------------------------------------

async def test_retention_purge_soft_deletes_old(client: AsyncClient, db: AsyncSession):
    owner = await _user(db, "owner@t.com", role="user")
    patient = await _patient(db, owner)
    now = datetime.now(UTC)
    old = Observation(patient_id=patient.id, owner_id=owner.id, category="measurement",
                      created_at=now - timedelta(days=60))
    fresh = Observation(patient_id=patient.id, owner_id=owner.id, category="measurement",
                        created_at=now - timedelta(days=1))
    db.add_all([old, fresh])
    await db.commit()

    await ensure_categories_seeded(db)
    cat = (await db.execute(select(DataCategory).where(DataCategory.code == "observation"))).scalar_one()
    cat.retention_days = 30
    await db.commit()

    summary = await run_retention_purge(db)
    assert summary.get("observation") == 1

    await db.refresh(old)
    await db.refresh(fresh)
    assert old.is_deleted is True
    assert fresh.is_deleted is False

    audits = (await db.execute(
        select(AuditLog).where(AuditLog.entity_type == "DataRetention"))).scalars().all()
    assert len(audits) == 1
    assert audits[0].entity_id == "observation"
    assert audits[0].changes["count"] == 1


async def test_retention_off_by_default_no_purge(client: AsyncClient, db: AsyncSession):
    owner = await _user(db, "owner2@t.com", role="user")
    patient = await _patient(db, owner)
    old = Observation(patient_id=patient.id, owner_id=owner.id, category="measurement",
                      created_at=datetime.now(UTC) - timedelta(days=999))
    db.add(old)
    await db.commit()

    await ensure_categories_seeded(db)  # no retention configured
    summary = await run_retention_purge(db)
    assert "observation" not in summary
    await db.refresh(old)
    assert old.is_deleted is False


# --- onboarding consent ------------------------------------------------------

async def test_register_requires_consent_and_records_it(client: AsyncClient, db: AsyncSession):
    admin = await _user(db, "inv_admin@t.com")
    db.add(UserInvitation(email="newbie@t.com", token="tok123",
                          expires_at=datetime.now(UTC) + timedelta(days=7), created_by_user_id=admin.id))
    await db.commit()

    # Without consent → rejected
    r = await client.post("/api/auth/register", json={
        "token": "tok123", "first_name": "N", "last_name": "B", "password": "Passw0rd!", "consent": False})
    assert r.status_code == 422

    # With consent → account + consent record
    r = await client.post("/api/auth/register", json={
        "token": "tok123", "first_name": "N", "last_name": "B", "password": "Passw0rd!", "consent": True})
    assert r.status_code == 201, r.text

    newbie = (await db.execute(select(User).where(User.email == "newbie@t.com"))).scalar_one()
    cr = (await db.execute(select(ConsentRecord).where(ConsentRecord.user_id == newbie.id))).scalar_one_or_none()
    assert cr is not None

# --- domain-date retention (#32) ---------------------------------------------

async def _set_retention(db: AsyncSession, code: str, days: int) -> None:
    await ensure_categories_seeded(db)
    cat = (await db.execute(select(DataCategory).where(DataCategory.code == code))).scalar_one()
    cat.retention_days = days
    await db.commit()


async def test_purge_document_uses_issued_date_with_fallback(client: AsyncClient, db: AsyncSession):
    owner = await _user(db, "dd1@t.com", role="user")
    patient = await _patient(db, owner)
    now = datetime.now(UTC)
    # issued long ago, created recently -> purged (domain date wins)
    old_issued = DocumentReference(patient_id=patient.id, owner_id=owner.id,
                                   issued_date=(now - timedelta(days=60)).date())
    # issued recently, created long ago -> kept (domain date wins)
    recent_issued = DocumentReference(patient_id=patient.id, owner_id=owner.id,
                                      issued_date=now.date(), created_at=now - timedelta(days=60))
    # no issued_date, created long ago -> purged (fallback to created_at)
    no_date_old = DocumentReference(patient_id=patient.id, owner_id=owner.id,
                                    created_at=now - timedelta(days=60))
    db.add_all([old_issued, recent_issued, no_date_old])
    await db.commit()

    await _set_retention(db, "document", 30)
    summary = await run_retention_purge(db)
    assert summary.get("document") == 2

    for obj, deleted in ((old_issued, True), (recent_issued, False), (no_date_old, True)):
        await db.refresh(obj)
        assert obj.is_deleted is deleted


async def test_purge_observation_uses_effective_date(client: AsyncClient, db: AsyncSession):
    owner = await _user(db, "dd2@t.com", role="user")
    patient = await _patient(db, owner)
    now = datetime.now(UTC)
    # old created_at but recent effective date -> kept
    kept = Observation(patient_id=patient.id, owner_id=owner.id, category="measurement",
                       created_at=now - timedelta(days=90),
                       effective_date_time=now.isoformat())
    # recent created_at but old effective date -> purged
    purged = Observation(patient_id=patient.id, owner_id=owner.id, category="measurement",
                         effective_date_time=(now - timedelta(days=90)).isoformat())
    db.add_all([kept, purged])
    await db.commit()

    await _set_retention(db, "observation", 30)
    summary = await run_retention_purge(db)
    assert summary.get("observation") == 1

    await db.refresh(kept)
    await db.refresh(purged)
    assert kept.is_deleted is False
    assert purged.is_deleted is True
