from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.ratelimit import client_ip, enforce
from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    generate_recovery_code,
    hash_password,
    normalize_recovery_code,
    verify_password,
)
from app.models.user import User
from app.models.system import UserInvitation
from app.deps import get_current_user
from app.schemas.auth import (
    AuthResponse,
    ChangePasswordRequest,
    InviteInfoResponse,
    LoginRequest,
    ProfileResponse,
    ProfileUpdateRequest,
    RecoverRequest,
    RecoverResponse,
    RefreshRequest,
    RegisterRequest,
)

router = APIRouter()


@router.post("/login", response_model=AuthResponse)
async def login(request: Request, body: LoginRequest, db: AsyncSession = Depends(get_db)):
    # Lockout guards one account; this guards the rest — one password sprayed
    # across many accounts never trips a per-account counter.
    ip = client_ip(request)
    await enforce(f"rl:login:ip:{ip}", limit=20, window_seconds=300)
    await enforce(f"rl:login:email:{body.email.lower()}", limit=10, window_seconds=300)

    result = await db.execute(select(User).where(User.email == body.email, User.is_deleted == False))  # noqa: E712
    user = result.scalar_one_or_none()

    now = datetime.now(UTC)
    if not user or not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")

    if user.locked_until and user.locked_until > now:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Account locked")

    # The lockout has been served: forget it. Without this the counter stays at
    # 5 forever, so every later typo re-locks the account — anyone who knows a
    # caregiver's address could keep them out permanently with one wrong
    # password every 15 minutes (#109).
    if user.locked_until and user.locked_until <= now:
        user.failed_login_attempts = 0
        user.locked_until = None

    if not verify_password(body.password, user.hashed_password):
        user.failed_login_attempts += 1
        if user.failed_login_attempts >= 5:
            from datetime import timedelta
            user.locked_until = now + timedelta(minutes=15)
        await db.commit()
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")

    user.failed_login_attempts = 0
    user.locked_until = None
    user.last_login_at = now
    await db.commit()

    data = {"sub": str(user.id), "email": user.email, "role": user.role}
    from datetime import timedelta
    from app.core.config import settings
    expire = now + timedelta(minutes=settings.access_token_expire_minutes)
    return AuthResponse(
        access_token=create_access_token(data),
        refresh_token=create_refresh_token(data),
        expires_at=expire.isoformat(),
        email=user.email,
        role=user.role,
    )


@router.post("/refresh", response_model=AuthResponse)
async def refresh(request: Request, body: RefreshRequest, db: AsyncSession = Depends(get_db)):
    await enforce(f"rl:refresh:ip:{client_ip(request)}", limit=60, window_seconds=300)
    payload = decode_token(body.refresh_token)
    if not payload or payload.get("type") != "refresh":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid refresh token")

    import uuid
    result = await db.execute(select(User).where(User.id == uuid.UUID(payload["sub"]), User.is_deleted == False))  # noqa: E712
    user = result.scalar_one_or_none()
    if not user or not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED)

    from datetime import timedelta
    from app.core.config import settings
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


@router.post("/me/password", status_code=status.HTTP_204_NO_CONTENT)
async def change_password(
    body: ChangePasswordRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if not verify_password(body.current_password, user.hashed_password):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Current password is incorrect")
    user.hashed_password = hash_password(body.new_password)
    await db.commit()


@router.post("/recover", response_model=RecoverResponse)
async def recover(request: Request, body: RecoverRequest, db: AsyncSession = Depends(get_db)):
    """ADR 044: the way back in when the password and the passkey device are both gone."""
    ip = client_ip(request)
    await enforce(f"rl:recover:ip:{ip}", limit=5, window_seconds=900)
    await enforce(f"rl:recover:email:{body.email.lower()}", limit=5, window_seconds=900)

    result = await db.execute(select(User).where(User.email == body.email, User.is_deleted == False))  # noqa: E712
    user = result.scalar_one_or_none()
    code = normalize_recovery_code(body.recovery_code)
    # One answer for a wrong code, an address that has no account, and a User who
    # never wrote a code down: this endpoint tells nobody who is a Customer.
    if (
        not user
        or not user.is_active
        or not user.recovery_code_hash
        or not code
        or not verify_password(code, user.recovery_code_hash)
    ):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid recovery code")

    user.hashed_password = hash_password(body.new_password)
    # Whatever lockout sent them here must not survive the recovery.
    user.failed_login_attempts = 0
    user.locked_until = None
    # Single use. They leave with a fresh code rather than with none.
    fresh = generate_recovery_code()
    user.recovery_code_hash = hash_password(normalize_recovery_code(fresh))
    await db.commit()

    # No token is issued here, deliberately: recovery sets a password, it does not
    # sign anyone in, so it cannot become a way around a second factor (ADR 044).
    return RecoverResponse(recovery_code=fresh)


@router.get("/me", response_model=ProfileResponse)
async def get_me(user: User = Depends(get_current_user)):
    return ProfileResponse(
        id=str(user.id),
        email=user.email,
        first_name=user.first_name,
        last_name=user.last_name,
        role=user.role,
        last_login_at=user.last_login_at.isoformat() if user.last_login_at else None,
    )


@router.patch("/me", status_code=status.HTTP_204_NO_CONTENT)
async def update_me(
    body: ProfileUpdateRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if body.first_name is not None:
        user.first_name = body.first_name or None
    if body.last_name is not None:
        user.last_name = body.last_name or None
    await db.commit()


def _get_valid_invitation(token: str, now: datetime, db_result) -> UserInvitation:
    inv = db_result
    if not inv:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid invitation token")
    if inv.is_used:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Invitation already used")
    if inv.expires_at.replace(tzinfo=UTC) < now:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invitation has expired")
    return inv


@router.get("/invite", response_model=InviteInfoResponse)
async def get_invite_info(token: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(UserInvitation).where(UserInvitation.token == token))
    inv = _get_valid_invitation(token, datetime.now(UTC), result.scalar_one_or_none())
    return InviteInfoResponse(email=inv.email)


@router.post("/register", status_code=status.HTTP_201_CREATED)
async def register(body: RegisterRequest, db: AsyncSession = Depends(get_db)):
    now = datetime.now(UTC)
    result = await db.execute(select(UserInvitation).where(UserInvitation.token == body.token))
    inv = _get_valid_invitation(body.token, now, result.scalar_one_or_none())

    if not body.consent:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Consent is required to create an account.")

    existing = await db.execute(select(User).where(User.email == inv.email, User.is_deleted == False))  # noqa: E712
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="An account with this email already exists")

    user = User(
        email=inv.email,
        first_name=body.first_name,
        last_name=body.last_name,
        hashed_password=hash_password(body.password),
        role="user",
        is_active=True,
    )
    db.add(user)
    await db.flush()

    from app.models.governance import ConsentRecord
    db.add(ConsentRecord(user_id=user.id, consented_at=now))

    inv.is_used = True
    await db.commit()
    return {"email": inv.email}
