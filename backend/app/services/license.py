"""License verification and tier enforcement for the licensing system."""
from __future__ import annotations

import base64
import enum
import json
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

_GRACE_PERIOD_DAYS = 30

# Production Ed25519 public key (raw 32 bytes, base64-encoded).
# Private key is kept offline — see avisiohub for license issuance.
# For local dev/testing generate your own key pair and set LICENSE_PUBLIC_KEY:
#   openssl genpkey -algorithm ed25519 -out /tmp/dev-license.pem
#   openssl pkey -in /tmp/dev-license.pem -pubout -outform DER | tail -c 32 | base64
# (a dev private key used to be committed under docs/ — it is gone, see #116)
_DEFAULT_PUBLIC_KEY_B64 = "OnGVcsU2yy0nw/d2WiJYCC3SRdUfkG/Qq5eEebnzsPA="

PERSONAL_PATIENT_LIMIT = 10
PERSONAL_USER_LIMIT = 3


class Tier(str, enum.Enum):
    personal = "personal"
    commercial = "commercial"


@dataclass
class LicenseInfo:
    tier: Tier
    has_license: bool
    is_grace_period: bool
    issued_to: str | None
    expires_at: datetime | None
    grace_ends_at: datetime | None


_PERSONAL_NO_LICENSE = LicenseInfo(
    tier=Tier.personal,
    has_license=False,
    is_grace_period=False,
    issued_to=None,
    expires_at=None,
    grace_ends_at=None,
)


def decode_license(token: str, public_key_b64: str) -> LicenseInfo:
    """Verify and decode a license file. Raises ValueError on any problem.

    License format (JSON):
      { "v": 1, "tier": "commercial", "issued_to": "...", "iat": <unix>, "exp": <unix>, "sig": "<base64>" }

    The signature covers the canonical JSON of all fields except "sig"
    (json.dumps with sort_keys=True, no extra whitespace).
    """
    try:
        data = json.loads(token)
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid license format: {exc}") from exc

    if data.get("v") != 1:
        raise ValueError("Unsupported license version")

    sig_b64 = data.get("sig")
    if not sig_b64:
        raise ValueError("License is missing signature")

    try:
        sig_bytes = base64.b64decode(sig_b64)
    except Exception as exc:
        raise ValueError(f"Invalid license signature encoding: {exc}") from exc

    payload = {k: v for k, v in data.items() if k != "sig"}
    message = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()

    try:
        pub_key = Ed25519PublicKey.from_public_bytes(base64.b64decode(public_key_b64))
        pub_key.verify(sig_bytes, message)
    except InvalidSignature as exc:
        raise ValueError("Invalid license signature") from exc
    except Exception as exc:
        raise ValueError(f"License verification error: {exc}") from exc

    if data.get("tier") != "commercial":
        raise ValueError("License tier must be 'commercial'")

    exp = data.get("exp")
    if exp is None:
        raise ValueError("License is missing expiry")

    issued_to: str | None = data.get("issued_to")
    expires_at = datetime.fromtimestamp(exp, tz=UTC)
    grace_ends_at = expires_at + timedelta(days=_GRACE_PERIOD_DAYS)
    now = datetime.now(UTC)

    if now <= expires_at:
        effective_tier = Tier.commercial
        in_grace = False
    elif now <= grace_ends_at:
        effective_tier = Tier.commercial
        in_grace = True
    else:
        effective_tier = Tier.personal
        in_grace = False

    return LicenseInfo(
        tier=effective_tier,
        has_license=True,
        is_grace_period=in_grace,
        issued_to=issued_to,
        expires_at=expires_at,
        grace_ends_at=grace_ends_at,
    )


def evaluate_license(license_token: str | None, public_key_b64: str) -> LicenseInfo:
    """Return effective LicenseInfo. Falls back to personal on missing or invalid license."""
    if not license_token:
        return _PERSONAL_NO_LICENSE
    key = public_key_b64.strip() or _DEFAULT_PUBLIC_KEY_B64
    try:
        return decode_license(license_token, key)
    except ValueError:
        return _PERSONAL_NO_LICENSE


async def get_license_info(db: AsyncSession, public_key_b64: str) -> LicenseInfo:
    from app.models.organization import Organization

    result = await db.execute(select(Organization))
    org = result.scalar_one_or_none()
    if org is None:
        return _PERSONAL_NO_LICENSE
    return evaluate_license(org.license_token, public_key_b64)
