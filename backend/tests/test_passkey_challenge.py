"""#45: WebAuthn challenges are bound server-side and single-use."""

import pytest
from httpx import AsyncClient

from app.routers.passkey import _consume_challenge, _store_challenge


async def test_store_then_consume_is_single_use():
    challenge = b"\x01\x02\x03unit-test-challenge-bytes"
    await _store_challenge("auth", challenge)
    from webauthn.helpers import bytes_to_base64url
    b64 = bytes_to_base64url(challenge)

    assert await _consume_challenge("auth", b64) is True   # first use works
    assert await _consume_challenge("auth", b64) is False  # replay blocked


async def test_unknown_challenge_never_consumes():
    assert await _consume_challenge("auth", "never-issued-challenge") is False


async def test_complete_rejects_unissued_challenge(client: AsyncClient):
    # An assertion replayed with a challenge the server never issued is rejected
    # before any credential/crypto handling.
    r = await client.post(
        "/api/auth/passkey/authenticate/complete",
        json={"credential": {"id": "x", "rawId": "x", "response": {}}, "expected_challenge": "forged-challenge"},
    )
    assert r.status_code == 401
    assert "challenge" in r.json()["detail"].lower()
