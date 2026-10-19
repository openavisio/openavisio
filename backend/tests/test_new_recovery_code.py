"""The operator's fresh recovery code opens the normal recovery and nothing else (ADR 044)."""

import contextlib

from app.core.security import hash_password
from app.models.user import User
from app.scripts import new_recovery_code


async def test_the_new_code_lets_the_member_set_a_password(client, db, monkeypatch):
    db.add(User(email="lost@t.com", hashed_password=hash_password("Old1!pass"), role="user", is_active=True,
                failed_login_attempts=9))
    await db.commit()

    @contextlib.asynccontextmanager
    async def session():
        yield db
    monkeypatch.setattr(new_recovery_code, "AsyncSessionLocal", session)
    code = await new_recovery_code.main("LOST@t.com")

    r = await client.post("/api/auth/recover", json={"email": "lost@t.com", "recovery_code": code,
                                                    "new_password": "New1!pass"})
    assert r.status_code == 200, r.text
    assert "access_token" not in r.json()
    assert (await client.post("/api/auth/login", json={"email": "lost@t.com", "password": "New1!pass"})).status_code == 200
