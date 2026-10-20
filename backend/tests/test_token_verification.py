"""Session tokens after the switch from python-jose to PyJWT (#379)."""

import base64
import hashlib
import hmac
import json
import warnings
from datetime import UTC, datetime, timedelta

import jwt

from app.core.config import settings
from app.core.security import create_access_token, decode_token


def _b64(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode()


def _sign(header: dict, payload: dict, key: bytes) -> str:
    signing_input = f"{_b64(json.dumps(header).encode())}.{_b64(json.dumps(payload).encode())}"
    sig = hmac.new(key, signing_input.encode(), hashlib.sha256).digest()
    return f"{signing_input}.{_b64(sig)}"


def _exp(minutes: int) -> int:
    return int((datetime.now(UTC) + timedelta(minutes=minutes)).timestamp())


def test_round_trip():
    token = create_access_token({"sub": "u1", "role": "user"})
    assert decode_token(token)["sub"] == "u1"


def test_a_token_signed_before_the_switch_stays_valid():
    # what python-jose wrote: plain HS256 with the app secret
    token = _sign({"alg": "HS256", "typ": "JWT"}, {"sub": "u1", "exp": _exp(5)}, settings.app_secret.encode())
    assert decode_token(token)["sub"] == "u1"


def test_rejected():
    secret = settings.app_secret.encode()
    expired = _sign({"alg": "HS256", "typ": "JWT"}, {"sub": "u1", "exp": _exp(-1)}, secret)
    wrong_key = _sign({"alg": "HS256", "typ": "JWT"}, {"sub": "u1", "exp": _exp(5)}, b"x" * 32)
    claims = _b64(json.dumps({"sub": "u1", "exp": _exp(5)}).encode())
    unsigned = f"{_b64(json.dumps({'alg': 'none'}).encode())}.{claims}."
    with warnings.catch_warnings():  # the secret is short for HS512; this token only has to exist
        warnings.simplefilter("ignore")
        other_alg = jwt.encode({"sub": "u1", "exp": _exp(5)}, settings.app_secret, algorithm="HS512")
    head, body, sig = create_access_token({"sub": "u1"}).split(".")
    tampered = f"{head}.{_b64(json.dumps({'sub': 'admin', 'exp': _exp(5)}).encode())}.{sig}"
    for token in (expired, wrong_key, unsigned, other_alg, tampered, "garbage"):
        assert decode_token(token) is None, token
