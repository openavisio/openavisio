"""On a hosted Deployment the customer's admin cannot reach what only the operator runs:
the AI settings, the license, the system page and the logs. Self-hosted admins keep them."""

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.security import hash_password
from app.models.user import User

OPERATOR_ROUTES = [
    ("GET", "/api/admin/ollama"),
    ("PUT", "/api/admin/ollama/models"),
    ("POST", "/api/admin/ollama/test"),
    ("POST", "/api/admin/ollama/pull"),
    ("GET", "/api/admin/system"),
    ("GET", "/api/admin/license"),
    ("POST", "/api/admin/license"),
    ("DELETE", "/api/admin/license"),
    ("GET", "/api/admin/logs/tasks"),
    ("GET", "/api/admin/data-categories"),
]


async def _admin(client: AsyncClient, db: AsyncSession) -> dict:
    db.add(User(email="a@t.com", hashed_password=hash_password("Pass1!"), role="admin",
                is_active=True, first_name="A", last_name="Dmin"))
    await db.commit()
    r = await client.post("/api/auth/login", json={"email": "a@t.com", "password": "Pass1!"})
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


@pytest.mark.parametrize("method,path", OPERATOR_ROUTES)
async def test_hosted_admin_is_refused(client: AsyncClient, db: AsyncSession, monkeypatch, method, path):
    h = await _admin(client, db)
    monkeypatch.setattr(settings, "hosted", True)
    r = await client.request(method, path, headers=h, json={})
    assert r.status_code == 403, f"{method} {path} reachable by a hosted customer"


async def test_hosted_admin_keeps_invitations_and_audit(client: AsyncClient, db: AsyncSession, monkeypatch):
    h = await _admin(client, db)
    monkeypatch.setattr(settings, "hosted", True)
    for path in ("/api/admin/invitations", "/api/admin/audit"):
        assert (await client.get(path, headers=h)).status_code == 200


async def test_self_hosted_admin_is_not_affected(client: AsyncClient, db: AsyncSession):
    h = await _admin(client, db)
    assert (await client.get("/api/admin/license", headers=h)).status_code != 403
