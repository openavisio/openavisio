"""Tests for license tier enforcement (issue #1)."""
from __future__ import annotations

import base64
import json
import time
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, patch

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import hash_password
from app.models.access import PatientAccess
from app.models.patient import Patient
from app.models.user import User
from app.services.license import (
    LicenseInfo,
    PERSONAL_PATIENT_LIMIT,
    Tier,
    decode_license,
    evaluate_license,
)


# ---------------------------------------------------------------------------
# Ed25519 key pair helper (generated once per module) — matches license format
# (v1 JSON token, Ed25519 signature over canonical JSON, base64 public key).
# ---------------------------------------------------------------------------

def _generate_ed25519_pair():
    """Return (Ed25519PrivateKey, public_key_b64)."""
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

    private_key = Ed25519PrivateKey.generate()
    public_raw = private_key.public_key().public_bytes(
        serialization.Encoding.Raw, serialization.PublicFormat.Raw
    )
    return private_key, base64.b64encode(public_raw).decode()


def _make_token(private_key, claims: dict) -> str:
    """Build a signed license JSON token (v1, Ed25519 over canonical JSON)."""
    payload = {"v": 1, **claims}
    message = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    sig = base64.b64encode(private_key.sign(message)).decode()
    return json.dumps({**payload, "sig": sig})


_PRIVATE, _PUBLIC_B64 = _generate_ed25519_pair()


def _commercial_claims(exp_offset_seconds: int = 3600, issued_to: str = "test@example.com") -> dict:
    return {
        "tier": "commercial",
        "issued_to": issued_to,
        "exp": int(time.time()) + exp_offset_seconds,
    }


# ---------------------------------------------------------------------------
# Unit tests — decode_license
# ---------------------------------------------------------------------------

def test_decode_license_valid_commercial():
    token = _make_token(_PRIVATE, _commercial_claims())
    info = decode_license(token, _PUBLIC_B64)
    assert info.tier == Tier.commercial
    assert info.has_license is True
    assert info.is_grace_period is False
    assert info.issued_to == "test@example.com"


def test_decode_license_expired_within_grace():
    # Expired 10 days ago (within 30-day grace window)
    claims = _commercial_claims(exp_offset_seconds=-(10 * 86400))
    token = _make_token(_PRIVATE, claims)
    info = decode_license(token, _PUBLIC_B64)
    assert info.tier == Tier.commercial
    assert info.is_grace_period is True


def test_decode_license_expired_beyond_grace():
    # Expired 35 days ago (beyond 30-day grace)
    claims = _commercial_claims(exp_offset_seconds=-(35 * 86400))
    token = _make_token(_PRIVATE, claims)
    info = decode_license(token, _PUBLIC_B64)
    assert info.tier == Tier.personal
    assert info.is_grace_period is False


def test_decode_license_invalid_signature():
    _, other_public = _generate_ed25519_pair()
    token = _make_token(_PRIVATE, _commercial_claims())
    with pytest.raises(ValueError, match="Invalid license signature"):
        decode_license(token, other_public)


def test_decode_license_wrong_tier():
    claims = {"tier": "enterprise", "exp": int(time.time()) + 3600}
    token = _make_token(_PRIVATE, claims)
    with pytest.raises(ValueError, match="tier must be 'commercial'"):
        decode_license(token, _PUBLIC_B64)


def test_decode_license_missing_exp():
    claims = {"tier": "commercial"}
    token = _make_token(_PRIVATE, claims)
    with pytest.raises(ValueError, match="missing expiry"):
        decode_license(token, _PUBLIC_B64)


# ---------------------------------------------------------------------------
# Unit tests — evaluate_license
# ---------------------------------------------------------------------------

def test_evaluate_license_none_token():
    info = evaluate_license(None, _PUBLIC_B64)
    assert info.tier == Tier.personal
    assert info.has_license is False


def test_evaluate_license_garbage_token():
    info = evaluate_license("not.a.valid.jwt", _PUBLIC_B64)
    assert info.tier == Tier.personal
    assert info.has_license is False


def test_evaluate_license_valid_token():
    token = _make_token(_PRIVATE, _commercial_claims())
    info = evaluate_license(token, _PUBLIC_B64)
    assert info.tier == Tier.commercial


# ---------------------------------------------------------------------------
# Shared helpers for integration tests
# ---------------------------------------------------------------------------

async def _create_user(
    db: AsyncSession,
    email: str,
    role: str = "admin",
    password: str = "Password1!",
) -> User:
    user = User(email=email, hashed_password=hash_password(password), role=role, is_active=True)
    db.add(user)
    await db.flush()
    return user


async def _login(client: AsyncClient, email: str, password: str = "Password1!") -> dict:
    r = await client.post("/api/auth/login", json={"email": email, "password": password})
    assert r.status_code == 200, r.text
    return r.json()


def _auth(tokens: dict) -> dict:
    return {"Authorization": f"Bearer {tokens['access_token']}"}


async def _create_patient(db: AsyncSession, owner: User, n: int = 0) -> Patient:
    p = Patient(created_by=owner.id, given_name=f"Patient{n}", family_name="Test")
    db.add(p)
    await db.flush()
    db.add(PatientAccess(patient_id=p.id, user_id=owner.id, access_level="admin",
                         granted_by_user_id=owner.id, granted_at=datetime.now(UTC)))
    await db.commit()
    return p


# ---------------------------------------------------------------------------
# Integration tests — patient limit
# ---------------------------------------------------------------------------

async def test_personal_tier_blocks_patient_at_limit(client: AsyncClient, db: AsyncSession):
    """POST /patients returns 403 when 10 patients already exist on personal tier."""
    owner = await _create_user(db, "limit_owner@test.com", role="admin")
    await db.commit()

    # Create exactly PERSONAL_PATIENT_LIMIT patients
    for i in range(PERSONAL_PATIENT_LIMIT):
        await _create_patient(db, owner, i)
    await db.commit()

    tokens = await _login(client, "limit_owner@test.com")
    r = await client.post(
        "/api/patients",
        json={"given_name": "Extra", "family_name": "Patient"},
        headers=_auth(tokens),
    )
    assert r.status_code == 403
    assert "Personal tier" in r.json()["detail"]


async def test_personal_tier_allows_patient_under_limit(client: AsyncClient, db: AsyncSession):
    """POST /patients returns 201 when under the personal tier limit."""
    owner = await _create_user(db, "under_limit@test.com", role="admin")
    await db.commit()

    for i in range(PERSONAL_PATIENT_LIMIT - 1):
        await _create_patient(db, owner, i)
    await db.commit()

    tokens = await _login(client, "under_limit@test.com")
    r = await client.post(
        "/api/patients",
        json={"given_name": "Ok", "family_name": "Patient"},
        headers=_auth(tokens),
    )
    assert r.status_code == 201


async def test_commercial_tier_bypasses_patient_limit(client: AsyncClient, db: AsyncSession):
    """Commercial license removes the patient limit."""
    commercial_info = LicenseInfo(
        tier=Tier.commercial,
        has_license=True,
        is_grace_period=False,
        issued_to="org@example.com",
        expires_at=datetime.now(UTC) + timedelta(days=365),
        grace_ends_at=datetime.now(UTC) + timedelta(days=395),
    )

    owner = await _create_user(db, "commercial_owner@test.com", role="admin")
    await db.commit()

    for i in range(PERSONAL_PATIENT_LIMIT):
        await _create_patient(db, owner, i)
    await db.commit()

    tokens = await _login(client, "commercial_owner@test.com")

    with patch(
        "app.routers.patients.get_license_info",
        new=AsyncMock(return_value=commercial_info),
    ):
        r = await client.post(
            "/api/patients",
            json={"given_name": "Eleventh", "family_name": "Patient"},
            headers=_auth(tokens),
        )
    assert r.status_code == 201


async def test_invitation_not_limited_on_personal_tier(client: AsyncClient, db: AsyncSession):
    """POST /admin/invitations always succeeds on personal tier — no user cap."""
    admin = await _create_user(db, "inv_admin@test.com", role="admin")
    await db.commit()

    tokens = await _login(client, "inv_admin@test.com")
    r = await client.post(
        "/api/admin/invitations",
        json={"email": "invited@example.com"},
        headers=_auth(tokens),
    )
    assert r.status_code == 201
