import json
import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from webauthn import (
    generate_authentication_options,
    generate_registration_options,
    verify_authentication_response,
    verify_registration_response,
)
from webauthn.helpers import base64url_to_bytes, bytes_to_base64url
from webauthn.helpers.options_to_json import options_to_json
from webauthn.helpers.structs import (
    AttestationConveyancePreference,
    AuthenticatorAssertionResponse,
    AuthenticatorAttestationResponse,
    AuthenticatorSelectionCriteria,
    AuthenticationCredential,
    PublicKeyCredentialDescriptor,
    RegistrationCredential,
    ResidentKeyRequirement,
    UserVerificationRequirement,
)

from app.core.config import settings
from app.core.database import get_db
from app.core.security import create_access_token, create_refresh_token
from app.deps import get_current_user
from app.models.passkey import PasskeyCredential
from app.models.user import User
from app.schemas.auth import AuthResponse
from app.schemas.passkey import (
    PasskeyAuthenticateCompleteRequest,
    PasskeyCredentialResponse,
    PasskeyRegisterCompleteRequest,
    PasskeyRenameRequest,
)

router = APIRouter()

# Server-side challenge binding (#45): a challenge is stored at /begin and
# consumed once at /complete, so a captured assertion cannot be replayed with a
# caller-supplied challenge. Short TTL matches the frontend cookie maxAge.
_CHALLENGE_TTL = 300


def _redis():
    import redis.asyncio as aioredis
    return aioredis.Redis.from_url(settings.redis_url, decode_responses=True)


async def _store_challenge(kind: str, challenge: bytes) -> None:
    r = _redis()
    try:
        await r.set(f"passkey:chal:{kind}:{bytes_to_base64url(challenge)}", "1", ex=_CHALLENGE_TTL)
    finally:
        await r.aclose()


async def _consume_challenge(kind: str, challenge_b64: str) -> bool:
    """Atomically delete the challenge; returns True only if it existed (single-use)."""
    r = _redis()
    try:
        return bool(await r.delete(f"passkey:chal:{kind}:{challenge_b64}"))
    finally:
        await r.aclose()


def _passkey_to_response(p: PasskeyCredential) -> PasskeyCredentialResponse:
    return PasskeyCredentialResponse(
        id=str(p.id),
        label=p.label,
        aaguid=p.aaguid,
        created_at=p.created_at.isoformat(),
        last_used_at=p.last_used_at.isoformat() if p.last_used_at else None,
    )


@router.post("/passkey/register/begin")
async def passkey_register_begin(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(PasskeyCredential).where(PasskeyCredential.user_id == user.id)
    )
    existing = result.scalars().all()

    options = generate_registration_options(
        rp_id=settings.webauthn_rp_id,
        rp_name=settings.webauthn_rp_name,
        user_id=user.id.bytes,
        user_name=user.email,
        user_display_name=(
            f"{user.first_name or ''} {user.last_name or ''}".strip() or user.email
        ),
        authenticator_selection=AuthenticatorSelectionCriteria(
            resident_key=ResidentKeyRequirement.REQUIRED,
            user_verification=UserVerificationRequirement.REQUIRED,
        ),
        attestation=AttestationConveyancePreference.NONE,
        exclude_credentials=[
            PublicKeyCredentialDescriptor(id=c.credential_id)
            for c in existing
        ],
    )
    await _store_challenge("reg", options.challenge)
    return json.loads(options_to_json(options))


@router.post("/passkey/register/complete", response_model=PasskeyCredentialResponse, status_code=201)
async def passkey_register_complete(
    body: PasskeyRegisterCompleteRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if not await _consume_challenge("reg", body.expected_challenge):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Unknown or expired challenge")
    try:
        cred_data = body.credential
        response_data = cred_data.get("response", {})
        credential = RegistrationCredential(
            id=cred_data["id"],
            raw_id=base64url_to_bytes(cred_data["rawId"]),
            response=AuthenticatorAttestationResponse(
                client_data_json=base64url_to_bytes(response_data["clientDataJSON"]),
                attestation_object=base64url_to_bytes(response_data["attestationObject"]),
                transports=response_data.get("transports"),
            ),
            type=cred_data.get("type", "public-key"),
        )
        verified = verify_registration_response(
            credential=credential,
            expected_challenge=base64url_to_bytes(body.expected_challenge),
            expected_rp_id=settings.webauthn_rp_id,
            expected_origin=settings.webauthn_origin,
            require_user_verification=True,
        )
    except Exception:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Registration verification failed")

    transports = response_data.get("transports")
    passkey = PasskeyCredential(
        user_id=user.id,
        credential_id=verified.credential_id,
        public_key=verified.credential_public_key,
        sign_count=verified.sign_count,
        aaguid=str(verified.aaguid) if verified.aaguid else None,
        transports=json.dumps(transports) if transports else None,
        label=body.label or "Passkey",
    )
    db.add(passkey)
    await db.commit()
    await db.refresh(passkey)
    return _passkey_to_response(passkey)


@router.get("/passkey/authenticate/begin")
async def passkey_authenticate_begin():
    options = generate_authentication_options(
        rp_id=settings.webauthn_rp_id,
        user_verification=UserVerificationRequirement.REQUIRED,
    )
    await _store_challenge("auth", options.challenge)
    return json.loads(options_to_json(options))


@router.post("/passkey/authenticate/complete", response_model=AuthResponse)
async def passkey_authenticate_complete(
    body: PasskeyAuthenticateCompleteRequest,
    db: AsyncSession = Depends(get_db),
):
    if not await _consume_challenge("auth", body.expected_challenge):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Unknown or expired challenge")

    cred_data = body.credential
    response_data = cred_data.get("response", {})

    # Look up credential by id
    try:
        credential_id_bytes = base64url_to_bytes(cred_data["id"])
    except Exception:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid credential id")

    result = await db.execute(
        select(PasskeyCredential).where(PasskeyCredential.credential_id == credential_id_bytes)
    )
    passkey = result.scalar_one_or_none()
    if not passkey:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Unknown credential")

    # Load the user
    user = await db.get(User, passkey.user_id)
    if not user or not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Account not found or inactive")

    try:
        user_handle_raw = response_data.get("userHandle")
        credential = AuthenticationCredential(
            id=cred_data["id"],
            raw_id=base64url_to_bytes(cred_data["rawId"]),
            response=AuthenticatorAssertionResponse(
                client_data_json=base64url_to_bytes(response_data["clientDataJSON"]),
                authenticator_data=base64url_to_bytes(response_data["authenticatorData"]),
                signature=base64url_to_bytes(response_data["signature"]),
                user_handle=base64url_to_bytes(user_handle_raw) if user_handle_raw else None,
            ),
            type=cred_data.get("type", "public-key"),
        )
        verified = verify_authentication_response(
            credential=credential,
            expected_challenge=base64url_to_bytes(body.expected_challenge),
            expected_rp_id=settings.webauthn_rp_id,
            expected_origin=settings.webauthn_origin,
            credential_public_key=passkey.public_key,
            credential_current_sign_count=passkey.sign_count,
            require_user_verification=True,
        )
    except Exception:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication verification failed")

    # Update sign count and last_used_at
    passkey.sign_count = verified.new_sign_count
    passkey.last_used_at = datetime.now(UTC)
    user.last_login_at = datetime.now(UTC)
    await db.commit()

    from datetime import timedelta
    now = datetime.now(UTC)
    data = {"sub": str(user.id), "email": user.email, "role": user.role}
    expire = now + timedelta(minutes=settings.access_token_expire_minutes)
    return AuthResponse(
        access_token=create_access_token(data),
        refresh_token=create_refresh_token(data),
        expires_at=expire.isoformat(),
        email=user.email,
        role=user.role,
    )


@router.get("/passkey", response_model=list[PasskeyCredentialResponse])
async def list_passkeys(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(PasskeyCredential).where(PasskeyCredential.user_id == user.id)
    )
    return [_passkey_to_response(p) for p in result.scalars().all()]


@router.patch("/passkey/{passkey_id}", status_code=status.HTTP_204_NO_CONTENT)
async def rename_passkey(
    passkey_id: uuid.UUID,
    body: PasskeyRenameRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(PasskeyCredential).where(
            PasskeyCredential.id == passkey_id,
            PasskeyCredential.user_id == user.id,
        )
    )
    passkey = result.scalar_one_or_none()
    if not passkey:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    passkey.label = body.label.strip() or "Passkey"
    await db.commit()


@router.delete("/passkey/{passkey_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_passkey(
    passkey_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(PasskeyCredential).where(
            PasskeyCredential.id == passkey_id,
            PasskeyCredential.user_id == user.id,
        )
    )
    passkey = result.scalar_one_or_none()
    if not passkey:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    await db.delete(passkey)
    await db.commit()
