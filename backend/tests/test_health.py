"""/health must actually check something (#115).

It used to return a static {"status": "ok"} — so when Postgres died the
healthcheck still passed, Docker kept the container running, and nobody was
told. A health endpoint that cannot fail is decoration.
"""

from httpx import AsyncClient


async def test_health_reports_its_dependencies(client: AsyncClient):
    r = await client.get("/health")
    body = r.json()

    # the point of the endpoint: it names what it checked
    assert body["checks"]["database"] == "ok"
    assert "redis" in body["checks"]

    # Whether Redis is up depends on where the suite runs; what must hold is that
    # the endpoint AGREES WITH ITSELF — green only when everything it probed is.
    everything_ok = all(v == "ok" for v in body["checks"].values())
    assert (r.status_code == 200) is everything_ok
    assert body["status"] == ("ok" if everything_ok else "degraded")


async def test_health_goes_degraded_when_a_dependency_is_down(client: AsyncClient, monkeypatch):
    """A dead database must turn the endpoint red, not leave it green."""
    from app.core import database

    class DeadEngine:
        def connect(self):
            raise OSError("connection refused")

    monkeypatch.setattr(database, "engine", DeadEngine())
    monkeypatch.setattr("app.main.engine", DeadEngine())

    r = await client.get("/health")
    assert r.status_code == 503
    assert r.json()["status"] == "degraded"
    assert "error" in r.json()["checks"]["database"]


async def test_alive_stays_dumb(client: AsyncClient):
    """Liveness must not depend on anything — it answers "the process runs"."""
    r = await client.get("/alive")
    assert r.status_code == 200
    assert r.json() == {"status": "alive"}
