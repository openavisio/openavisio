# ADR 002: Devcontainer as recommended development setup

**Status:** Accepted

## Context

The project requires Python 3.12 + uv, Node.js 22+, and connection to Postgres 17 (with pgvector) and Redis. On Windows this toolchain is non-trivial to set up correctly, and `pgvector` in particular has no simple native installer.

ADR 001 established a hybrid approach (Docker for infra, local processes for app code) that works well for developers who already have the toolchain. A devcontainer takes this further: the app code also runs in a container, giving every contributor an identical, ready-to-use environment with one VS Code prompt.

## Decision

Add a `.devcontainer` configuration that:
- Uses `mcr.microsoft.com/devcontainers/python:3.12` as the base image
- Installs Node 22 and uv via devcontainer features
- Extends `deploy/docker-compose.infra.yml` (reuses Postgres + Redis, no duplication)
- Connects to Postgres and Redis by service name (`postgres`, `redis`) within the compose network
- Runs `uv sync` + `pnpm install` automatically on container creation

The hybrid approach from ADR 001 remains valid for contributors who prefer native tooling.

## Consequences

**Good:**
- Zero local toolchain requirements beyond VS Code + Docker Desktop
- Works identically on Windows, macOS, Linux, and GitHub Codespaces
- Infra setup is reused from `docker-compose.infra.yml` — single source of truth
- VS Code extensions and settings are provisioned automatically

**Trade-off:**
- First `Reopen in Container` pulls the base image and builds the environment (~1–2 min)
- `DATABASE_URL` uses `postgres` hostname (not `localhost`) — differs from the hybrid `.env` setup; handled via `remoteEnv` in `devcontainer.json` so no manual `.env` change needed inside the container

## Usage

1. Open the repo in VS Code
2. When prompted, click **Reopen in Container** (or run `Dev Containers: Reopen in Container` from the command palette)
3. Wait for `postCreateCommand` to finish (`uv sync` + `pnpm install`)
4. In the integrated terminal:

```bash
# Apply migrations (first time)
cd backend && uv run alembic upgrade head

# Start backend
uv run uvicorn app.main:app --reload

# Start frontend (new terminal)
cd frontend && pnpm dev

# Celery (optional)
cd backend && uv run celery -A app.workers.celery_app worker --loglevel=info
```

Ports 3000, 8000, 8001, and 5555 are forwarded to the host automatically.
