"""Per-patient KEK keystore and in-process cache (ADR-031).

Each patient has one random KEK, stored wrapped under the master KEK in the
`patient_keys` table — a SEPARATE, short-retention backup stream so that
deleting the row crypto-shreds that patient's encrypted PHI in backups too.

The unwrapped KEK is cached per process with a short TTL to avoid a master-KEK
AES-GCM on every document op. The cache is never persisted and is invalidated
on erasure/rotation.
"""

import os
import time
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.encryption import _get_kek, wrap_dek, unwrap_dek
from app.models.patient_key import PatientKey

_TTL_SECONDS = 300  # 5 min
_cache: dict[str, tuple[bytes, float]] = {}  # patient_id -> (unwrapped_kek, expires_at)


def invalidate(patient_id: uuid.UUID | str) -> None:
    _cache.pop(str(patient_id), None)


async def get_patient_kek(db: AsyncSession, patient_id: uuid.UUID) -> bytes:
    """Return the unwrapped patient KEK. Raises KeyError if the patient has no
    key row (never provisioned, or crypto-shredded by erasure)."""
    pid = str(patient_id)
    hit = _cache.get(pid)
    if hit and hit[1] > time.monotonic():
        return hit[0]
    row = (await db.execute(select(PatientKey).where(PatientKey.patient_id == patient_id))).scalar_one_or_none()
    if row is None:
        raise KeyError(f"no patient KEK for {pid} (unprovisioned or erased)")
    kek = unwrap_dek(row.wrapped_kek, _get_kek())
    _cache[pid] = (kek, time.monotonic() + _TTL_SECONDS)
    return kek


async def ensure_patient_kek(db: AsyncSession, patient_id: uuid.UUID) -> bytes:
    """Return the patient KEK, creating and persisting one on first use."""
    row = (await db.execute(select(PatientKey).where(PatientKey.patient_id == patient_id))).scalar_one_or_none()
    if row is not None:
        return await get_patient_kek(db, patient_id)
    kek = os.urandom(32)
    db.add(PatientKey(patient_id=patient_id, wrapped_kek=wrap_dek(kek, _get_kek()), kek_version=1))
    await db.flush()
    _cache[str(patient_id)] = (kek, time.monotonic() + _TTL_SECONDS)
    return kek
