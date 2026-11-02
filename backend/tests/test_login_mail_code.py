"""#338: a password sign-in from a new device needs a code by mail; a passed device, a
recovery or a Deployment without mail does not."""

from app.core.security import generate_recovery_code, hash_password, normalize_recovery_code
from app.models.user import User
from app.routers import auth as auth_router

SMTP = {"host": "smtp.test", "port": 587, "user": "u", "password": "p", "from_address": "a@test"}


async def _user(db, email):
    db.add(User(email=email, hashed_password=hash_password("Pass1!word"), role="user", is_active=True))
    await db.commit()


def _mail(monkeypatch):
    sent = []

    async def send(db, cfg, to, code):
        sent.append((to, code))

    async def smtp(db):
        return SMTP
    monkeypatch.setattr(auth_router, "_get_smtp_config", smtp)
    monkeypatch.setattr(auth_router, "send_login_code", send)
    return sent


async def test_new_device_needs_the_mail_code_then_is_remembered(client, db, monkeypatch):
    await _user(db, "mfa@t.com")
    sent = _mail(monkeypatch)
    creds = {"email": "mfa@t.com", "password": "Pass1!word"}

    r = await client.post("/api/auth/login", json=creds)
    assert r.status_code == 401 and r.json()["detail"] == "Code required"
    assert sent[0][0] == "mfa@t.com" and len(sent[0][1]) == 6

    bad = await client.post("/api/auth/login", json={**creds, "code": "000000" if sent[0][1] != "000000" else "111111"})
    assert bad.status_code == 401 and bad.json()["detail"] == "Invalid code"

    ok = await client.post("/api/auth/login", json={**creds, "code": sent[0][1]})
    assert ok.status_code == 200 and ok.json()["access_token"] and ok.json()["device"]
    # the code is spent
    again = await client.post("/api/auth/login", json={**creds, "code": sent[0][1]})
    assert again.status_code == 401

    known = await client.post("/api/auth/login", json={**creds, "device": ok.json()["device"]})
    assert known.status_code == 200 and known.json()["device"] is None
    assert len(sent) == 1  # a spent code mails nothing new, a known device needs none


async def test_a_device_token_of_another_user_does_not_count(client, db, monkeypatch):
    await _user(db, "a@t.com")
    await _user(db, "b@t.com")
    sent = _mail(monkeypatch)
    await client.post("/api/auth/login", json={"email": "a@t.com", "password": "Pass1!word"})
    a_dev = (await client.post("/api/auth/login", json={"email": "a@t.com", "password": "Pass1!word",
                                                       "code": sent[-1][1]})).json()["device"]
    r = await client.post("/api/auth/login", json={"email": "b@t.com", "password": "Pass1!word", "device": a_dev})
    assert r.json()["detail"] == "Code required"


async def test_without_mail_there_is_no_code(client, db):
    await _user(db, "nomail@t.com")
    r = await client.post("/api/auth/login", json={"email": "nomail@t.com", "password": "Pass1!word"})
    assert r.status_code == 200 and r.json()["device"] is None


async def test_recovery_remembers_the_device_instead_of_a_mail_code(client, db, monkeypatch):
    code = generate_recovery_code()
    db.add(User(email="rec@t.com", hashed_password=hash_password("Old1!word"), role="user", is_active=True,
                recovery_code_hash=hash_password(normalize_recovery_code(code))))
    await db.commit()
    _mail(monkeypatch)
    r = await client.post("/api/auth/recover", json={"email": "rec@t.com", "recovery_code": code,
                                                    "new_password": "New1!word"})
    assert r.status_code == 200 and "access_token" not in r.json()
    device = r.cookies.get("oa_device")
    assert device
    ok = await client.post("/api/auth/login", json={"email": "rec@t.com", "password": "New1!word", "device": device})
    assert ok.status_code == 200, ok.text


async def test_a_device_token_is_no_session(client, db, monkeypatch):
    await _user(db, "dev@t.com")
    sent = _mail(monkeypatch)
    creds = {"email": "dev@t.com", "password": "Pass1!word"}
    await client.post("/api/auth/login", json=creds)
    ok = (await client.post("/api/auth/login", json={**creds, "code": sent[-1][1]})).json()
    assert (await client.get("/api/auth/me", headers={"Authorization": f"Bearer {ok['access_token']}"})).status_code == 200
    r = await client.get("/api/auth/me", headers={"Authorization": f"Bearer {ok['device']}"})
    assert r.status_code == 401
