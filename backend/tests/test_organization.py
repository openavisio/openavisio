import pytest
from httpx import AsyncClient

INIT_PAYLOAD = {
    "name": "Test Clinic",
    "admin_email": "admin@test.com",
    "admin_password": "Secure123!",
    "admin_first_name": "Admin",
    "admin_last_name": "User",
}


async def test_status_not_initialized(client: AsyncClient):
    r = await client.get("/api/organization/status")
    assert r.status_code == 200
    assert r.json()["initialized"] is False


async def test_init_creates_organization(client: AsyncClient):
    r = await client.post("/api/organization/init", json=INIT_PAYLOAD)
    assert r.status_code == 201
    data = r.json()
    assert data["name"] == "Test Clinic"
    assert "id" in data


async def test_init_with_first_patient(client: AsyncClient):
    payload = {
        **INIT_PAYLOAD,
        "first_patient": {
            "given_name": "Anna",
            "family_name": "Test",
            "birth_date": "1990-01-01",
        },
    }
    r = await client.post("/api/organization/init", json=payload)
    assert r.status_code == 201


async def test_status_after_init(client: AsyncClient):
    await client.post("/api/organization/init", json=INIT_PAYLOAD)
    r = await client.get("/api/organization/status")
    assert r.status_code == 200
    assert r.json()["initialized"] is True


async def test_init_conflict_if_already_initialized(client: AsyncClient):
    await client.post("/api/organization/init", json=INIT_PAYLOAD)
    r = await client.post("/api/organization/init", json=INIT_PAYLOAD)
    assert r.status_code == 409


async def test_init_rejects_missing_required_fields(client: AsyncClient):
    r = await client.post("/api/organization/init", json={"name": "X"})
    assert r.status_code == 422


async def test_init_requires_bootstrap_token_in_production(client: AsyncClient, monkeypatch):
    from app.core.config import settings

    monkeypatch.setattr(settings, "environment", "production")
    monkeypatch.setattr(settings, "bootstrap_token", "s3cret-token")

    # Missing token -> forbidden
    r = await client.post("/api/organization/init", json=INIT_PAYLOAD)
    assert r.status_code == 403
    # Wrong token -> forbidden
    r = await client.post("/api/organization/init", json=INIT_PAYLOAD, headers={"X-Bootstrap-Token": "nope"})
    assert r.status_code == 403
    # Correct token -> created
    r = await client.post("/api/organization/init", json=INIT_PAYLOAD, headers={"X-Bootstrap-Token": "s3cret-token"})
    assert r.status_code == 201


async def test_init_blocked_when_token_unconfigured_in_production(client: AsyncClient, monkeypatch):
    from app.core.config import settings

    monkeypatch.setattr(settings, "environment", "production")
    monkeypatch.setattr(settings, "bootstrap_token", "")

    r = await client.post("/api/organization/init", json=INIT_PAYLOAD, headers={"X-Bootstrap-Token": "anything"})
    assert r.status_code == 503
