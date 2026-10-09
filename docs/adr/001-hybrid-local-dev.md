# ADR 001: Hybrid local development setup

**Status:** Accepted — superseded by [ADR 002](002-devcontainer.md) for new contributors; remains valid for developers with an existing local toolchain

## Context

The project provides a full `docker-compose.dev.yml` that runs all services (Postgres, Redis, backend, frontend, Celery, AI service) in containers. While this guarantees environment parity, it creates friction during active development:

- Code changes require Docker rebuilds
- Debuggers and profilers don't attach easily inside containers
- Hot reload is slower through volume mounts than native

Stateful services (Postgres + Redis) have no hot-reload benefit and are painful to run natively because they require system-level installation plus the `pgvector` extension.

## Decision

Run stateful infrastructure (Postgres + Redis) in Docker via `deploy/docker-compose.infra.yml`, and run application code (backend, frontend, Celery) as local processes.

## Consequences

**Good:**
- Native hot reload for backend (`uvicorn --reload`) and frontend (`next dev`)
- Debugger / profiler attach directly to local processes
- No rebuilds on code changes
- Postgres + Redis stay isolated, reproducible, and version-pinned

**Trade-off:**
- Local Python/Node versions must match project requirements (uv handles Python; Node 22+ required for frontend)
- `DATABASE_URL` in `.env` must point to `localhost:5432`, not the Docker internal hostname

## Usage

```bash
# Start infra
docker compose -f deploy/docker-compose.infra.yml up -d

# Backend
cd backend
uv sync
uv run alembic upgrade head
uv run uvicorn app.main:app --reload

# Frontend
cd frontend
npm run dev

# Celery (only needed when testing background jobs)
cd backend
uv run celery -A app.workers.celery_app worker --loglevel=info
```

Full Docker dev remains available via `docker compose -f deploy/docker-compose.dev.yml up`.
