"""An unhandled error answers with an id and mails the operator once an hour (ADR 053)."""

import asyncio

import redis.asyncio as aioredis
from httpx import ASGITransport, AsyncClient

import app.core.error_report as er
import app.services.email as email
from app.main import app


class _Redis:
    keys: set = set()

    async def set(self, key, value, nx=False, ex=None):
        if nx and key in self.keys:
            return None
        self.keys.add(key)
        return True

    async def aclose(self):
        pass


async def test_an_unhandled_error_gets_an_id_and_one_mail(monkeypatch):
    async def boom():
        raise RuntimeError("Emma Test, Epilepsie")  # the kind of text that must not leave the box
    app.add_api_route("/api/test-boom", boom)
    sent = []
    _Redis.keys = set()
    monkeypatch.setattr(er.settings, "ops_alert_email", "ops@t.com")
    monkeypatch.setattr(aioredis, "from_url", lambda url: _Redis())
    async def smtp(db):
        return {"from_address": "x@t.com"}
    monkeypatch.setattr(email, "_get_smtp_config", smtp)
    monkeypatch.setattr(email, "_send_smtp", lambda cfg, to, subject, html, text: sent.append((to, subject, text)))
    try:
        async with AsyncClient(transport=ASGITransport(app=app, raise_app_exceptions=False), base_url="http://test") as c:
            r1 = await c.get("/api/test-boom")
            r2 = await c.get("/api/test-boom")
            for _ in range(50):
                if not er._tasks:
                    break
                await asyncio.sleep(0.02)
    finally:
        app.router.routes[:] = [r for r in app.router.routes if getattr(r, "path", "") != "/api/test-boom"]

    assert r1.status_code == 500 and len(r1.json()["error_id"]) == 8
    assert "Emma" not in r1.text
    assert len(sent) == 1, sent
    to, subject, text = sent[0]
    assert to == "ops@t.com" and r1.json()["error_id"] in subject
    assert "RuntimeError" in text and "/api/test-boom" in text and "Emma" not in text
    assert r2.json()["error_id"] != r1.json()["error_id"]
