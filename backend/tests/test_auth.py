from datetime import UTC, datetime, timedelta

from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

import secrets

from app.core.security import (
    create_refresh_token,
    generate_recovery_code,
    hash_password,
    normalize_recovery_code,
)
from app.models.user import User
from app.models.system import UserInvitation

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

async def _create_user(
    db: AsyncSession,
    email: str = "user@test.com",
    password: str = "Password1!",
    role: str = "user",
    is_active: bool = True,
) -> User:
    user = User(
        email=email,
        hashed_password=hash_password(password),
        role=role,
        is_active=is_active,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user


async def _login(client: AsyncClient, email: str, password: str) -> dict:
    r = await client.post(
        "/api/auth/login", json={"email": email, "password": password}
    )
    assert r.status_code == 200
    return r.json()


# ---------------------------------------------------------------------------
# Login
# ---------------------------------------------------------------------------

async def test_login_success(client: AsyncClient, db: AsyncSession):
    await _create_user(db, email="login@test.com", password="Secret99!")
    r = await client.post(
        "/api/auth/login", json={"email": "login@test.com", "password": "Secret99!"}
    )
    assert r.status_code == 200
    data = r.json()
    assert "access_token" in data
    assert "refresh_token" in data
    assert data["email"] == "login@test.com"


async def test_login_wrong_password(client: AsyncClient, db: AsyncSession):
    await _create_user(db, email="wp@test.com", password="Correct1!")
    r = await client.post(
        "/api/auth/login", json={"email": "wp@test.com", "password": "Wrong1!"}
    )
    assert r.status_code == 401


async def test_login_unknown_email(client: AsyncClient):
    r = await client.post(
        "/api/auth/login", json={"email": "nobody@test.com", "password": "anything"}
    )
    assert r.status_code == 401


async def test_login_inactive_user(client: AsyncClient, db: AsyncSession):
    await _create_user(db, email="inactive@test.com", password="Pass1!", is_active=False)
    r = await client.post(
        "/api/auth/login", json={"email": "inactive@test.com", "password": "Pass1!"}
    )
    assert r.status_code == 401


async def test_login_locked_account(client: AsyncClient, db: AsyncSession):
    user = await _create_user(db, email="locked@test.com", password="Pass1!")
    user.locked_until = datetime.now(UTC) + timedelta(minutes=15)
    await db.commit()
    r = await client.post(
        "/api/auth/login", json={"email": "locked@test.com", "password": "Pass1!"}
    )
    assert r.status_code == 401
    assert "locked" in r.json()["detail"].lower()


async def test_login_increments_failed_attempts(client: AsyncClient, db: AsyncSession):
    await _create_user(db, email="attempts@test.com", password="Correct1!")
    await client.post(
        "/api/auth/login", json={"email": "attempts@test.com", "password": "wrong"}
    )
    from sqlalchemy import select
    result = await db.execute(
        select(User).where(User.email == "attempts@test.com")
    )
    user = result.scalar_one()
    assert user.failed_login_attempts == 1


async def test_login_resets_failed_attempts_on_success(client: AsyncClient, db: AsyncSession):
    from sqlalchemy import select
    user = await _create_user(db, email="reset@test.com", password="Correct1!")
    user.failed_login_attempts = 3
    await db.commit()
    await client.post(
        "/api/auth/login", json={"email": "reset@test.com", "password": "Correct1!"}
    )
    result = await db.execute(select(User).where(User.email == "reset@test.com"))
    u = result.scalar_one()
    assert u.failed_login_attempts == 0


# ---------------------------------------------------------------------------
# Refresh
# ---------------------------------------------------------------------------

async def test_refresh_token(client: AsyncClient, db: AsyncSession):
    await _create_user(db, email="refresh@test.com", password="Pass1!")
    tokens = await _login(client, "refresh@test.com", "Pass1!")
    r = await client.post(
        "/api/auth/refresh", json={"refresh_token": tokens["refresh_token"]}
    )
    assert r.status_code == 200
    data = r.json()
    assert "access_token" in data
    assert "refresh_token" in data


async def test_refresh_rejects_access_token(client: AsyncClient, db: AsyncSession):
    await _create_user(db, email="badrefresh@test.com", password="Pass1!")
    tokens = await _login(client, "badrefresh@test.com", "Pass1!")
    r = await client.post(
        "/api/auth/refresh", json={"refresh_token": tokens["access_token"]}
    )
    assert r.status_code == 401


async def test_refresh_rejects_garbage(client: AsyncClient):
    r = await client.post("/api/auth/refresh", json={"refresh_token": "notavalidtoken"})
    assert r.status_code == 401


async def test_refresh_rejects_inactive_user(client: AsyncClient, db: AsyncSession):
    user = await _create_user(db, email="inactref@test.com", password="Pass1!")
    token = create_refresh_token({"sub": str(user.id), "email": user.email, "role": user.role})
    user.is_active = False
    await db.commit()
    r = await client.post("/api/auth/refresh", json={"refresh_token": token})
    assert r.status_code == 401


# ---------------------------------------------------------------------------
# Change password  (/api/auth/me/password)
# ---------------------------------------------------------------------------

async def test_change_password_success(client: AsyncClient, db: AsyncSession):
    await _create_user(db, email="chpw@test.com", password="OldPass1!")
    tokens = await _login(client, "chpw@test.com", "OldPass1!")
    r = await client.post(
        "/api/auth/me/password",
        json={"current_password": "OldPass1!", "new_password": "NewPass1!"},
        headers={"Authorization": f"Bearer {tokens['access_token']}"},
    )
    assert r.status_code == 204
    # Old password no longer works
    assert (await client.post("/api/auth/login", json={"email": "chpw@test.com", "password": "OldPass1!"})).status_code == 401
    # New password works
    assert (await client.post("/api/auth/login", json={"email": "chpw@test.com", "password": "NewPass1!"})).status_code == 200


async def test_change_password_wrong_current(client: AsyncClient, db: AsyncSession):
    await _create_user(db, email="wpchpw@test.com", password="OldPass1!")
    tokens = await _login(client, "wpchpw@test.com", "OldPass1!")
    r = await client.post(
        "/api/auth/me/password",
        json={"current_password": "WrongPass1!", "new_password": "NewPass1!"},
        headers={"Authorization": f"Bearer {tokens['access_token']}"},
    )
    assert r.status_code == 400
    assert "incorrect" in r.json()["detail"].lower()


async def test_change_password_requires_auth(client: AsyncClient):
    r = await client.post(
        "/api/auth/me/password",
        json={"current_password": "x", "new_password": "y"},
    )
    assert r.status_code in (401, 403)


# ---------------------------------------------------------------------------
# Profile  (GET/PATCH /api/auth/me)
# ---------------------------------------------------------------------------

async def test_get_me(client: AsyncClient, db: AsyncSession):
    user = await _create_user(db, email="me@test.com", password="Pass1!")
    user.first_name = "Ada"
    user.last_name = "Lovelace"
    await db.commit()
    tokens = await _login(client, "me@test.com", "Pass1!")
    r = await client.get(
        "/api/auth/me",
        headers={"Authorization": f"Bearer {tokens['access_token']}"},
    )
    assert r.status_code == 200
    data = r.json()
    assert data["email"] == "me@test.com"
    assert data["first_name"] == "Ada"
    assert data["last_name"] == "Lovelace"


async def test_get_me_requires_auth(client: AsyncClient):
    r = await client.get("/api/auth/me")
    assert r.status_code in (401, 403)


async def test_update_profile(client: AsyncClient, db: AsyncSession):
    from sqlalchemy import select
    await _create_user(db, email="profile@test.com", password="Pass1!")
    tokens = await _login(client, "profile@test.com", "Pass1!")
    r = await client.patch(
        "/api/auth/me",
        json={"first_name": "Grace", "last_name": "Hopper"},
        headers={"Authorization": f"Bearer {tokens['access_token']}"},
    )
    assert r.status_code == 204
    result = await db.execute(select(User).where(User.email == "profile@test.com"))
    user = result.scalar_one()
    assert user.first_name == "Grace"
    assert user.last_name == "Hopper"


async def test_update_profile_partial(client: AsyncClient, db: AsyncSession):
    from sqlalchemy import select
    user = await _create_user(db, email="partial@test.com", password="Pass1!")
    user.first_name = "Original"
    user.last_name = "Name"
    await db.commit()
    tokens = await _login(client, "partial@test.com", "Pass1!")
    # Only update first_name
    r = await client.patch(
        "/api/auth/me",
        json={"first_name": "Updated"},
        headers={"Authorization": f"Bearer {tokens['access_token']}"},
    )
    assert r.status_code == 204
    result = await db.execute(select(User).where(User.email == "partial@test.com"))
    u = result.scalar_one()
    assert u.first_name == "Updated"
    assert u.last_name == "Name"  # unchanged


async def test_update_profile_requires_auth(client: AsyncClient):
    r = await client.patch("/api/auth/me", json={"first_name": "X"})
    assert r.status_code in (401, 403)


# ---------------------------------------------------------------------------
# Registration  (GET /api/auth/invite  +  POST /api/auth/register)
# ---------------------------------------------------------------------------

async def _create_invitation(
    db: AsyncSession,
    email: str = "invited@test.com",
    days: int = 7,
    is_used: bool = False,
) -> UserInvitation:
    inv = UserInvitation(
        email=email,
        token=secrets.token_urlsafe(32),
        expires_at=datetime.now(UTC) + timedelta(days=days),
        is_used=is_used,
    )
    db.add(inv)
    await db.commit()
    await db.refresh(inv)
    return inv


async def test_invite_info_valid(client: AsyncClient, db: AsyncSession):
    inv = await _create_invitation(db, email="info@test.com")
    r = await client.get(f"/api/auth/invite?token={inv.token}")
    assert r.status_code == 200
    assert r.json()["email"] == "info@test.com"


async def test_invite_info_invalid_token(client: AsyncClient):
    r = await client.get("/api/auth/invite?token=notarealtoken")
    assert r.status_code == 400


async def test_invite_info_expired(client: AsyncClient, db: AsyncSession):
    inv = await _create_invitation(db, days=-1)
    r = await client.get(f"/api/auth/invite?token={inv.token}")
    assert r.status_code == 400
    assert "expired" in r.json()["detail"].lower()


async def test_invite_info_already_used(client: AsyncClient, db: AsyncSession):
    inv = await _create_invitation(db, is_used=True)
    r = await client.get(f"/api/auth/invite?token={inv.token}")
    assert r.status_code == 409


async def test_register_success(client: AsyncClient, db: AsyncSession):
    from sqlalchemy import select
    inv = await _create_invitation(db, email="newuser@test.com")
    r = await client.post("/api/auth/register", json={
        "token": inv.token,
        "first_name": "New",
        "last_name": "User",
        "password": "SecurePass1!",
        "consent": True,
    })
    assert r.status_code == 201
    assert r.json()["email"] == "newuser@test.com"

    # User was created
    result = await db.execute(select(User).where(User.email == "newuser@test.com"))
    user = result.scalar_one()
    assert user.first_name == "New"
    assert user.last_name == "User"
    assert user.is_active is True

    # Invitation marked used
    await db.refresh(inv)
    assert inv.is_used is True

    # Can now log in
    login = await client.post("/api/auth/login", json={"email": "newuser@test.com", "password": "SecurePass1!"})
    assert login.status_code == 200


async def test_register_invalid_token(client: AsyncClient):
    r = await client.post("/api/auth/register", json={
        "token": "badtoken",
        "first_name": "X",
        "last_name": "Y",
        "password": "Password1!",
    })
    assert r.status_code == 400


async def test_register_expired_token(client: AsyncClient, db: AsyncSession):
    inv = await _create_invitation(db, days=-1)
    r = await client.post("/api/auth/register", json={
        "token": inv.token,
        "first_name": "X",
        "last_name": "Y",
        "password": "Password1!",
    })
    assert r.status_code == 400
    assert "expired" in r.json()["detail"].lower()


async def test_register_already_used(client: AsyncClient, db: AsyncSession):
    inv = await _create_invitation(db, is_used=True)
    r = await client.post("/api/auth/register", json={
        "token": inv.token,
        "first_name": "X",
        "last_name": "Y",
        "password": "Password1!",
    })
    assert r.status_code == 409


async def test_register_duplicate_email(client: AsyncClient, db: AsyncSession):
    await _create_user(db, email="dup@test.com", password="Pass1!")
    inv = await _create_invitation(db, email="dup@test.com")
    r = await client.post("/api/auth/register", json={
        "token": inv.token,
        "first_name": "X",
        "last_name": "Y",
        "password": "Password1!",
        "consent": True,
    })
    assert r.status_code == 409


async def test_expired_lockout_clears_the_counter(client: AsyncClient, db: AsyncSession):
    """A served lockout must be forgotten.

    Regression for #109: failed_login_attempts was only ever reset on a
    *successful* login. Once an account had reached 5, the counter stayed at 5
    forever — so every later typo pushed it to 6 and re-locked the account for
    another 15 minutes. Anyone who knew a caregiver's e-mail could keep them
    locked out indefinitely with one wrong password every quarter of an hour.
    """

    user = await _create_user(db, email="expired@test.com", password="Correct1!")
    user.failed_login_attempts = 5
    user.locked_until = datetime.now(UTC) - timedelta(minutes=1)  # lockout is over
    await db.commit()

    # a single wrong password must NOT re-lock: the old lockout was served
    r = await client.post(
        "/api/auth/login", json={"email": "expired@test.com", "password": "wrong"}
    )
    assert r.status_code == 401
    await db.refresh(user)
    assert user.failed_login_attempts == 1, "counter should restart, not resume at 5"
    assert user.locked_until is None, "one typo after a served lockout must not re-lock"

    # and the correct password still gets in
    r = await client.post(
        "/api/auth/login", json={"email": "expired@test.com", "password": "Correct1!"}
    )
    assert r.status_code == 200


# ---------------------------------------------------------------------------
# Recovery code (ADR 044)
# ---------------------------------------------------------------------------

async def _create_user_with_code(db: AsyncSession, email: str, code: str) -> User:
    user = await _create_user(db, email=email, password="Password1!")
    user.recovery_code_hash = hash_password(normalize_recovery_code(code))
    await db.commit()
    return user


async def test_recover_sets_new_password_and_spends_the_code(client: AsyncClient, db: AsyncSession):
    code = generate_recovery_code()
    await _create_user_with_code(db, "recover@test.com", code)

    r = await client.post(
        "/api/auth/recover",
        json={"email": "recover@test.com", "recovery_code": code, "new_password": "BrandNew9!"},
    )
    assert r.status_code == 200
    fresh = r.json()["recovery_code"]
    assert fresh != code

    await _login(client, "recover@test.com", "BrandNew9!")

    # The used code is spent, the fresh one works in its place.
    again = await client.post(
        "/api/auth/recover",
        json={"email": "recover@test.com", "recovery_code": code, "new_password": "Another9!"},
    )
    assert again.status_code == 400
    ok = await client.post(
        "/api/auth/recover",
        json={"email": "recover@test.com", "recovery_code": fresh, "new_password": "Another9!"},
    )
    assert ok.status_code == 200


async def test_recover_accepts_the_code_however_it_was_typed(client: AsyncClient, db: AsyncSession):
    code = generate_recovery_code()
    await _create_user_with_code(db, "sloppy@test.com", code)

    r = await client.post(
        "/api/auth/recover",
        json={
            "email": "sloppy@test.com",
            "recovery_code": code.lower().replace("-", " "),
            "new_password": "BrandNew9!",
        },
    )
    assert r.status_code == 200


async def test_recover_answers_the_same_for_a_wrong_code_and_an_unknown_address(
    client: AsyncClient, db: AsyncSession
):
    code = generate_recovery_code()
    await _create_user_with_code(db, "known@test.com", code)

    wrong = await client.post(
        "/api/auth/recover",
        json={"email": "known@test.com", "recovery_code": generate_recovery_code(), "new_password": "BrandNew9!"},
    )
    unknown = await client.post(
        "/api/auth/recover",
        json={"email": "nobody@test.com", "recovery_code": code, "new_password": "BrandNew9!"},
    )
    assert wrong.status_code == unknown.status_code == 400
    assert wrong.json() == unknown.json()


async def test_recover_issues_no_session(client: AsyncClient, db: AsyncSession):
    """Recovery sets a password. It must never be a way around a second factor."""
    code = generate_recovery_code()
    await _create_user_with_code(db, "nosession@test.com", code)

    r = await client.post(
        "/api/auth/recover",
        json={"email": "nosession@test.com", "recovery_code": code, "new_password": "BrandNew9!"},
    )
    assert r.status_code == 200
    assert "access_token" not in r.json()
    assert "refresh_token" not in r.json()


async def test_recover_clears_a_lockout(client: AsyncClient, db: AsyncSession):
    code = generate_recovery_code()
    user = await _create_user_with_code(db, "locked@test.com", code)
    user.failed_login_attempts = 5
    user.locked_until = datetime.now(UTC) + timedelta(minutes=15)
    await db.commit()

    r = await client.post(
        "/api/auth/recover",
        json={"email": "locked@test.com", "recovery_code": code, "new_password": "BrandNew9!"},
    )
    assert r.status_code == 200
    await _login(client, "locked@test.com", "BrandNew9!")
