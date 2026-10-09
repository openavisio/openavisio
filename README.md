# OpenAvisio

**A privacy-first personal health record for families.** Upload doctors' letters, lab
reports and discharge summaries — OpenAvisio reads them and turns them into a
structured record: diagnoses with their source documents, medications with their
periods, lab values with reference ranges, appointments on a timeline.

Built by a father managing his daughter's rare-disease paperwork. Everything runs on
**your own server** — including the AI. Nothing leaves your house.

## Try it

**https://demo.openavisio.org** — no signup needed:

| Login | Password | Role |
|---|---|---|
| `caregiver@demo.openavisio.org` | `Demo123!Care` | Caregiver |

Synthetic data (one fictional patient, six documents), resets every night. The AI
assistant answers with a real language model, so please type nothing personal into it.

![Patient overview](docs/screenshots/overview.png)

![Documents with extracted insights](docs/screenshots/documents.png)

![Diagnoses with their source documents](docs/screenshots/conditions.png)

## Why

- **Your server, your data.** AGPL-3.0, self-hosted, per-patient envelope encryption;
  erasing a patient destroys their key — crypto-shredding that reaches the backups.
- **Local AI or none.** OCR, classification and extraction run against your own
  Ollama/vLLM. No cloud egress unless you deliberately switch it on.
- **The paperwork is included.** DPIA, RoPA, GDPR checklist, breach-response runbook
  and an AVV template ship in `docs/` — the documents a family, a Verein or a care
  home actually needs to run this legally.
- **Not a medical device — deliberately.** The software transcribes documents; it
  does not diagnose, grade or predict. See `docs/regulatory-positioning.md`.

---

## What OpenAvisio does

**Document upload & AI Processing Pipeline**
Upload any medical PDF, image, or scan. The Processing Pipeline automatically runs OCR, classifies the document, and extracts structured clinical data — Diagnoses, Medications, Measurements, Lab Results — directly into the patient record. It also generates a human-readable Summary, Recommendations (e.g. "return in three months"), and proposes Events (appointments, follow-ups) for the caregiver to accept onto the health timeline.

**Clinical data**
Each Patient record tracks:
- **Diagnoses** — medical conditions attributed to the patient
- **Medications** — current and historical drugs with dosage and period
- **Measurements** — weight, blood pressure, temperature, oxygen saturation, etc.
- **Lab Results** — outcomes from blood tests, biopsies, and other clinical tests
- **Incidents** — adverse events (seizures, falls, allergic reactions) with suspected triggers
- **Events** — health timeline entries: appointments, hospital stays, therapy sessions
- **Health Log** — patient self-reported daily record: mood, pain, sleep, medication compliance

**AI Health Assistant**
Conversational interface that searches across all clinical data and documents to answer questions about a patient's health record.

**Expenses**
Care costs money, and getting it back means paperwork. Upload an invoice and the Processing Pipeline proposes an Expense — amount, date, category — which the caregiver confirms before it counts; nothing extracted from a scan enters a total unchecked. Cash payments and mileage can be entered by hand. The overview totals what was paid, what an insurer reimbursed, and what is still open (the part that may be tax-deductible), and exports as CSV for a Krankenkasse/Pflegekasse application or the tax return. OpenAvisio prepares the overview; it does not transmit anything to an insurer (ADR 040).

**Data sharing**
A Coordinator can open a Sharing Purpose (e.g. an epilepsy study collecting EEG files) that asks every caregiver for a kind of data. Caregivers choose which documents to share and consent per file — identified or anonymously. Consented files can then be collected and forwarded to the study; consent is recorded, freezes once a file is shared, and can be revoked at any time.

**Access model**
- **Coordinator** — onboards new Patients, assigns access to other Users
- **Caregiver** — manages a specific Patient's day-to-day care; covers family members, nurses, legal guardians, and anyone in the care circle
- **Group** — named set of Patients for bulk access management (useful in care homes and clinics)

**Tiers**
| Tier | License required | Patients | Users |
|---|---|---|---|
| Personal (default) | None — AGPL | up to 10 | up to 3 |
| Commercial | Valid License file | Unlimited | Unlimited |

A Commercial License that expires enters a 30-day grace period before falling back to Personal limits.

## Stack

| Layer | Technology |
|---|---|
| Backend | FastAPI + uv (Python 3.12) |
| ORM | SQLAlchemy 2.0 async + asyncpg + Alembic |
| Auth | passlib/bcrypt + python-jose JWT + py_webauthn (passkeys) + next-auth v5 |
| Background jobs | Celery + Redis |
| Frontend | Next.js 16 App Router + Tailwind CSS + shadcn/ui + @simplewebauthn/browser |
| i18n | next-intl (en, de, fr, es, it) |
| DB | PostgreSQL 17 + pgvector (768-dim HNSW embeddings) |
| AI | Separate FastAPI microservice (Ollama / vLLM / hosted OpenAI-compatible endpoint / mock) |
| Reverse proxy | Caddy (HTTP routing, production) |

## Quick Start (dev)

### Prerequisites
- Docker + Docker Compose
- Node.js 22+ (for frontend dev outside Docker)
- Python 3.12 + [uv](https://docs.astral.sh/uv/) (for backend dev outside Docker)

### 1. Configure environment

```bash
cp .env.example .env
# Edit .env — set APP_SECRET, POSTGRES_PASSWORD, etc.
# AI is optional: leave OLLAMA_URL empty to disable, or set AI_BACKEND=mock for canned responses
```

**Passkey (WebAuthn) settings** — required for passkey sign-in to work:

| Variable | Default | Description |
|---|---|---|
| `WEBAUTHN_RP_ID` | `localhost` | Registerable domain suffix (no port) — must match the browser origin |
| `WEBAUTHN_RP_NAME` | `OpenAvisio` | Human-readable site name shown in the OS passkey dialog |
| `WEBAUTHN_ORIGIN` | `http://localhost:3000` | Full origin of the frontend, e.g. `https://health.example.com` |

**Licensing** — required for Commercial tier enforcement:

| Variable | Default | Description |
|---|---|---|
| `LICENSE_PUBLIC_KEY` | _(embedded production key)_ | Ed25519 public key (raw 32 bytes, base64) used to verify Commercial License files. Leave unset in production. Set to the dev public key for local license testing — see `docs/license-format.md`. |

See [docs/license-format.md](docs/license-format.md) for the license file format and how to generate test licenses.

`setup.sh` sets these automatically from your domain. In dev you only need them if you change the default ports.

### 2. Start all services

```bash
docker compose -f deploy/docker-compose.dev.yml up
```

Services:
- **Backend API**: http://localhost:8000 (FastAPI docs at `/docs`)
- **Frontend**: http://localhost:3000
- **Flower** (Celery monitor): http://localhost:5555
- **PostgreSQL**: localhost:5432
- **Redis**: localhost:6379

### 3. Seed dev data

```bash
curl -X POST http://localhost:8000/api/dev/seed
# Admin: admin@openavisio.dev / Admin123!Admin
```

### 4. First-time setup (fresh DB)

Visit http://localhost:3000 → you'll be redirected to `/setup` to create the organization + admin account.

## Development (devcontainer — recommended)

Requires: VS Code + Docker Desktop. No local Python/Node install needed.

### 1. Open in container

Open the repo in VS Code, then either:
- Click the **Reopen in Container** popup in the bottom-right, or
- `Ctrl+Shift+P` → **Dev Containers: Reopen in Container**

VS Code will build the image and start Postgres + Redis automatically. This takes a few minutes the first time.

### 2. Wait for setup to finish

Watch the **Terminal** panel at the bottom — `postCreateCommand` runs automatically:
- `uv sync` — installs Python dependencies into `.venv`
- `pnpm install` — installs frontend dependencies

The terminal prompt returns when it's done.

### 3. Open split terminals

Use `` Ctrl+Shift+` `` to open a new terminal. You'll need two (or three for Celery).  
All commands run from inside the container — no local Python or Node needed.

**Terminal 1 — backend:**
```bash
cd backend
uv run alembic upgrade head   # first time only — applies DB migrations
uv run uvicorn app.main:app --reload
```

**Terminal 2 — frontend:**
```bash
cd frontend
pnpm dev
```

**Terminal 3 — Celery (optional, only needed for document processing):**
```bash
cd backend
uv run celery -A app.workers.celery_app worker --loglevel=info
```

### 4. Open in browser

Ports are forwarded to your host automatically — open these in your normal browser:

| Service | URL |
|---|---|
| Frontend | http://localhost:3000 |
| Backend API + docs | http://localhost:8000/docs |
| Flower (Celery monitor) | http://localhost:5555 |

### 5. Seed dev data (first time)

In any terminal:
```bash
curl -X POST http://localhost:8000/api/dev/seed
# Login: admin@openavisio.dev / Admin123!Admin
```

See [docs/adr/002-devcontainer.md](docs/adr/002-devcontainer.md) for rationale.

## Development (hybrid — recommended)

Run infra in Docker, app code locally. Best DX: native hot reload + debugger, no rebuilds.

### 1. Start infra

```bash
docker compose -f deploy/docker-compose.infra.yml up -d
```

### 2. Configure `.env`

Uncomment and set the direct `DATABASE_URL`:

```env
DATABASE_URL=postgresql+asyncpg://openavisio:devpassword123@localhost:5432/vaultdb
```

### 3. Run backend

```bash
cd backend
uv sync
uv run alembic upgrade head
uv run uvicorn app.main:app --reload
# → http://localhost:8000/docs
```

### 4. Run frontend

```bash
cd frontend
pnpm install
pnpm dev
# → http://localhost:3000
```

### 5. Celery (optional — only for background job testing)

```bash
cd backend
uv run celery -A app.workers.celery_app worker --loglevel=info
```

See [docs/adr/001-hybrid-local-dev.md](docs/adr/001-hybrid-local-dev.md) for rationale.

## Development (without Docker)

### Backend

```bash
cd backend
uv sync
uv run alembic upgrade head
uv run uvicorn app.main:app --reload
# → http://localhost:8000/docs
```

### Frontend

```bash
cd frontend
pnpm install
pnpm dev
# → http://localhost:3000
```

### Celery workers

```bash
cd backend
uv run celery -A app.workers.celery_app worker --loglevel=info
uv run celery -A app.workers.celery_app beat --loglevel=info
```

### Tests

Tests use a separate `vaultdb_test` database. Create it once:

```bash
# From the repo root (infra must be running)
docker compose -f deploy/docker-compose.infra.yml exec postgres \
  psql -U openavisio -d vaultdb -c "CREATE DATABASE vaultdb_test;"
docker compose -f deploy/docker-compose.infra.yml exec postgres \
  psql -U openavisio -d vaultdb_test -c "CREATE EXTENSION IF NOT EXISTS vector;"
```

Run tests locally (with infra running):

```bash
cd backend
TEST_DATABASE_URL=postgresql+asyncpg://openavisio:devpassword123@localhost:5432/vaultdb_test \
  uv run pytest -v
```

Run tests in the production Docker stack (no separate infra needed):

```bash
docker compose exec backend bash -c "cd /app && uv run pytest -v"
# The default TEST_DATABASE_URL points to postgres:5432/vaultdb_test inside Docker
```

## Architecture

```
openavisio-py/
├── backend/          # FastAPI + SQLAlchemy + Celery
│   └── app/
│       ├── core/     # config, database, security, audit
│       ├── models/   # SQLAlchemy ORM (25 models)
│       ├── schemas/  # Pydantic DTOs
│       ├── routers/  # 15 router files (58 endpoints)
│       ├── auth/     # RBAC — PatientAccessService
│       ├── workers/  # Celery pipeline + scheduler
│       └── deps.py   # DI: get_db, get_current_user, patient access
├── frontend/         # Next.js 16 App Router
│   └── src/
│       ├── app/      # 20 pages (patients, family, admin, auth)
│       ├── components/
│       ├── lib/      # api.ts (58 typed wrappers), utils.ts
│       └── messages/ # i18n JSON (en, de, fr, es, it)
├── aiservice/        # Python FastAPI — OCR, classify, extract, embed, chat
└── deploy/
    ├── docker-compose.dev.yml
    ├── docker-compose.prod.yml
    └── Caddyfile
```

### Document processing pipeline

Upload → encrypt (AES-256-GCM) → Celery chain:
1. **OCR** — Tesseract/OCRmyPDF + vision LLM fallback
2. **Classification** — document type + provider
3. **Extraction** — entities via LLM → stored as JSONB
4. **Embedding** — pgvector chunks for RAG

Caregiver reviews extracted data → confirms → real FHIR entities created.

### RBAC

Three system roles: **Admin**, **Coordinator** (onboard Patients, manage access), **User** (view assigned Patients only).  
Row-level patient access: ownership → Group membership → Caregiver grant (legal relationships recorded as attributes on the grant, not a separate path).

### AI

Set `AI_BACKEND` in `.env`:
- `ollama` — local Ollama instance (`OLLAMA_URL` required)
- `vllm` — vLLM server, or **any OpenAI-compatible endpoint** (`VLLM_URL` required, `VLLM_API_KEY` if the endpoint asks for one). Patient data goes wherever `VLLM_URL` points; a hosted provider needs a data-processing agreement.
- `mock` — canned responses, full pipeline without GPU (dev/CI)
- _(empty)_ — AI disabled, uploads saved with `status=skipped`

## API

Full REST API documented at http://localhost:8000/docs (58 endpoints).

Key endpoint groups:
- `POST /api/auth/login` + `/api/auth/refresh`
- `GET/POST /api/auth/passkey/*` — WebAuthn registration + authentication ceremonies; passkey CRUD
- `GET/POST /api/patients` + sub-resources (documents, diagnoses, medications, measurements, lab-results, incidents, events, health-log, chat, export)
- `GET/POST /api/groups` + members + invite flow
- `GET/POST /api/patients/{id}/caregivers` + invite/revoke
- `GET /api/admin/*` — users, groups, invitations, audit, AI settings, license
- `POST /api/dev/seed` + `/api/dev/reset` (development only)

## Production deployment

Clone, configure, start — that's it.

```bash
cd /opt
git clone https://codeberg.org/openavisio/openavisio.git
cd openavisio
./setup.sh
docker compose up -d
```

`setup.sh` checks prerequisites, generates all secrets, and asks a handful of questions. The first visit to your domain or IP redirects to `/setup` to create the organization and admin account.

---

### Requirements

| | |
|---|---|
| OS | Ubuntu 22.04 / 24.04 or Debian 12 |
| CPU | 2 cores minimum |
| RAM | 4 GB minimum (8 GB recommended if running Ollama locally) |
| Disk | 20 GB minimum |
| Docker | 24+ with Compose plugin |
| Proxmox LXC | Container must be **privileged** — enable via Proxmox web UI: Container → Options → Features → check **nesting** and **keyctl** |

### 1. Get a Docker-ready machine

**Option A — Proxmox LXC (recommended for homelab):**
Run the [Proxmox community scripts](https://community-scripts.org/scripts/docker) from the Proxmox shell. This creates a privileged Ubuntu LXC with Docker already installed — skip to step 2.

**Option B — existing Ubuntu / Debian server:**

```bash
apt update && apt install -y ca-certificates curl git
install -m 0755 -d /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/$(. /etc/os-release && echo "$ID")/gpg \
  -o /etc/apt/keyrings/docker.asc
echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] \
  https://download.docker.com/linux/$(. /etc/os-release && echo "$ID") \
  $(. /etc/os-release && echo "$VERSION_CODENAME") stable" \
  > /etc/apt/sources.list.d/docker.list
apt update && apt install -y docker-ce docker-ce-cli containerd.io docker-compose-plugin
```

### 2. Clone and run setup

```bash
cd /opt
git clone https://codeberg.org/openavisio/openavisio.git
cd openavisio
./setup.sh --start
```

`setup.sh` will ask for:
- **Domain or IP** — used to set `NEXTAUTH_URL` and CORS origins
- **AI backend** — choose `ollama` (local), `vllm` (own server or a hosted endpoint), or `mock` (no GPU, for testing)
- **Ollama URL** — if using Ollama, the endpoint it's reachable at

Everything else (secrets, database password, CORS) is generated or derived automatically.

**TLS / HTTPS:** Caddy handles HTTP routing on port 80 only. For HTTPS, choose one of:

- **External reverse proxy (default)** — put [Nginx Proxy Manager](https://nginxproxymanager.com/) or any other proxy in front and point it at `http://<host>:80`.
- **Caddy automatic HTTPS (Let's Encrypt)** — change `http://{$DOMAIN}` to `{$DOMAIN}` in `deploy/Caddyfile`, expose ports 443/443-udp in `deploy/docker-compose.prod.yml`, and make sure port 443 is reachable from the internet (no upstream proxy intercepting TLS).

### 3. Ollama (local AI)

Ollama runs **outside** the Docker Compose stack so it can access the GPU directly.

**Proxmox: run Ollama on the host**, not the LXC:

```bash
# On the Proxmox host:
curl -fsSL https://ollama.com/install.sh | sh

# Allow LXC containers to connect:
mkdir -p /etc/systemd/system/ollama.service.d
cat > /etc/systemd/system/ollama.service.d/override.conf <<EOF
[Service]
Environment="OLLAMA_HOST=0.0.0.0:11434"
EOF
systemctl daemon-reload && systemctl restart ollama
```

Set `OLLAMA_URL` to the Proxmox host IP when `setup.sh` asks (e.g. `http://192.168.1.10:11434`).

Pull models before configuring them in the admin UI:

```bash
ollama pull qwen3.6:27b-mtp-q4_K_M   # extraction + classification + chat (one model, ~18 GB)
ollama pull glm-ocr:Q8_0             # vision OCR (image-only PDFs, ~1.6 GB)
ollama pull qwen3-embedding:4b       # embeddings (required for AI Health Assistant, ~2.5 GB)
```

After first login, go to **Admin → Ollama / AI Backend** to assign each model to its task.

### Updating

```bash
git pull
docker compose pull
docker compose up -d --build
```

Migrations run automatically on backend startup.
