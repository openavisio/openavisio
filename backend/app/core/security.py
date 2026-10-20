import secrets
from datetime import UTC, datetime, timedelta

import bcrypt
import jwt

from app.core.config import settings

ALGORITHM = "HS256"


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def verify_password(plain: str, hashed: str) -> bool:
    return bcrypt.checkpw(plain.encode(), hashed.encode())


def create_access_token(data: dict) -> str:
    expire = datetime.now(UTC) + timedelta(minutes=settings.access_token_expire_minutes)
    return jwt.encode({**data, "exp": expire}, settings.app_secret, algorithm=ALGORITHM)


def create_refresh_token(data: dict) -> str:
    expire = datetime.now(UTC) + timedelta(days=settings.refresh_token_expire_days)
    return jwt.encode({**data, "exp": expire, "type": "refresh"}, settings.app_secret, algorithm=ALGORITHM)


def decode_token(token: str) -> dict | None:
    try:
        return jwt.decode(token, settings.app_secret, algorithms=[ALGORITHM])
    except jwt.PyJWTError:
        return None


# ADR 044: the recovery code is the only way back in when the password and the
# device holding the passkey are both gone. Crockford-style alphabet, so it can
# be read off paper and over the phone without an I/1 or O/0 argument.
_RECOVERY_ALPHABET = "ABCDEFGHJKMNPQRSTUVWXYZ23456789"


def generate_recovery_code() -> str:
    """Four groups of five, ~98 bits. Formatted for a sheet of paper."""
    raw = "".join(secrets.choice(_RECOVERY_ALPHABET) for _ in range(20))
    return "-".join(raw[i : i + 5] for i in range(0, 20, 5))


def normalize_recovery_code(code: str) -> str:
    """Accept it however it was typed: spaces, lowercase, missing dashes."""
    return "".join(c for c in code.upper() if c in _RECOVERY_ALPHABET)
