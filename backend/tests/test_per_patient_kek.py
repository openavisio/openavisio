"""Per-patient KEK keystore + crypto-shredding (ADR-031, #76)."""

import pytest
from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.encryption import decrypt_document, decrypt_str, encrypt_document, encrypt_str
from app.core.patient_keys import ensure_patient_kek, get_patient_kek, invalidate
from app.core.security import hash_password
from app.models.patient import Patient
from app.models.patient_key import PatientKey
from app.models.user import User


async def _patient(db: AsyncSession) -> Patient:
    user = User(email="kek@t.com", hashed_password=hash_password("Pass1!"), role="user",
                is_active=True, first_name="K", last_name="U")
    db.add(user)
    await db.commit()
    await db.refresh(user)
    p = Patient(given_name="Key", family_name="Test", created_by=user.id)
    db.add(p)
    await db.commit()
    await db.refresh(p)
    return p


async def test_ensure_is_idempotent_and_get_matches(db: AsyncSession):
    p = await _patient(db)
    k1 = await ensure_patient_kek(db, p.id)
    k2 = await ensure_patient_kek(db, p.id)  # second call must not mint a new key
    assert k1 == k2
    invalidate(p.id)  # force a DB round-trip, not the cache
    assert await get_patient_kek(db, p.id) == k1
    rows = (await db.execute(delete(PatientKey).where(PatientKey.patient_id == p.id).returning(PatientKey.id))).all()
    assert len(rows) == 1  # exactly one key row existed


async def test_document_roundtrip_under_patient_kek(db: AsyncSession):
    p = await _patient(db)
    kek = await ensure_patient_kek(db, p.id)
    blob, wrapped = encrypt_document(b"lab pdf bytes", kek)
    assert decrypt_document(blob, wrapped, kek) == b"lab pdf bytes"
    enc = encrypt_str("Kreatinin 1.2 mg/dl", kek)
    assert decrypt_str(enc, kek) == "Kreatinin 1.2 mg/dl"


async def test_crypto_shred_makes_key_unavailable(db: AsyncSession):
    p = await _patient(db)
    await ensure_patient_kek(db, p.id)
    # erasure deletes the key row + invalidates the cache
    await db.execute(delete(PatientKey).where(PatientKey.patient_id == p.id))
    invalidate(p.id)
    with pytest.raises(KeyError):
        await get_patient_kek(db, p.id)
