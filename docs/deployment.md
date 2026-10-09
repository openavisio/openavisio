# Deployment

## Stack overview

Docker Compose stack defined in `deploy/docker-compose.prod.yml` (included via `compose.yml` at repo root).

Services: `postgres`, `redis`, `aiservice`, `backend`, `celery-worker`, `celery-beat`, `frontend`, `caddy`.

Traffic path: Browser → Nginx Proxy Manager (HTTPS termination) → Caddy (HTTP :80, internal router) → Next.js `frontend:3000`. The backend is internal-only at `backend:8000`.

`DOMAIN` in `.env` is a bare domain (e.g. `DOMAIN=nordstern.openavisio.app`). The Caddyfile hardcodes the `http://` scheme, so Caddy never attempts ACME/auto-HTTPS — TLS is NPM's job. Serving TLS from Caddy directly would be an architecture change (edit the Caddyfile), not a config flag.

## How code gets into containers

**All application services bake source code into the Docker image at build time.** There are no code volume mounts. A `docker compose restart` reloads the process but does not pick up file changes — a `--build` is always required.

| What changed | Command |
|---|---|
| Backend Python (`backend/`) | `docker compose up -d --build backend celery-worker celery-beat` |
| Frontend TypeScript (`frontend/`) | `docker compose up -d --build frontend` |
| AI service Python (`aiservice/`) | `docker compose up -d --build aiservice` |
| Caddyfile (`deploy/Caddyfile`) | `docker compose restart caddy` (volume-mounted, no rebuild needed) |
| AI prompts (`aiservice/prompts/`) | `docker compose up -d --build aiservice` — they are read at request time, but from the copy baked into the image (`COPY . .`), so an edited file on the host changes nothing until a rebuild. For a quick test only, `docker cp` the file into the running container; the next request picks it up |

## Test server

- **Host:** `YOUR_SERVER_IP` (Debian LXC inside Proxmox)
- **SSH:** `ssh root@YOUR_SERVER_IP`
- **URL:** `https://openavisio.org`
- **Stack location:** `/opt/openavisio/`
- **Env file:** `/opt/openavisio/.env`

### The AI runs on two separate Ollama hosts, not on the app server

The app server holds no model. It talks to **two** Ollama hosts, and losing either
one takes out a different half of the product, which is why they are worth naming
separately. Both are configured in `/opt/openavisio/.env`:

| Env var | Host | Stage | Models it must hold |
|---|---|---|---|
| `OLLAMA_URL` | text host | chat, extraction, classification | the model named by `ai.model.chat` / `.extract` / `.classify` (one 27B, ~16 GB) |
| `OLLAMA_VISION_URL` | small host | vision OCR | `glm-ocr:Q8_0` (~1.5 GB) |
| `OLLAMA_EMBED_URL` | small host | embeddings | `qwen3-embedding:4b` (~2.4 GB) |

The split follows the hardware: one 24 GB card carries the 27B alone, and OCR plus
embeddings share a small card. **Only one 27B fits on the big card**, so chat,
extraction and classification should all point at the *same* tag. A mixed setting
swaps models twice per document, which costs more than any model difference gains
(`docs/research-extraction-model.md`).

Failure modes worth recognising:

- **Text host down:** chat returns 503 and nothing is stored (by design). Uploads
  still OCR and still get embedded, they just do not get their entities extracted.
- **Small host down:** documents stop being processed, and chat still answers from
  structured records but finds no document chunks.
- **Model tags are not backed up.** Rebuilding an Ollama container loses every
  pulled model. The stage settings in the database keep pointing at tags that no
  longer exist, and every call fails until the tags are pulled again. Check with
  `curl -s http://<host>:11434/api/tags`.

Which model each stage uses is a database setting, not an env var, and is changed
in the admin UI (ADR 005). `ai.model.*` in `system_settings`.

Note that `EMBEDDING_SCHEDULER_CRON` (default `*/15 * * * *`) sends work at the
embedding host on a timer, so a freshly rebuilt host gets traffic before anyone
asks for it. Stop the stack while rebuilding if that is in the way.

### Deploying a release

To ship a tagged release to a box, use the deploy script — it streams the tag's
tree over SSH, rebuilds, and waits for the backend to report healthy:

```bash
./deploy/deploy.sh root@YOUR_SERVER_IP v0.1.0
```

It deploys only a pushed annotated tag (see `docs/releasing.md`), never touches
the box's `.env`/`data`/`backups` (they are untracked, so absent from
`git archive`), and lets the backend's own start-up run `alembic upgrade head`.

### Iterating a single file (test server)

For a quick one-file change while developing, skip the tag dance and copy
directly. Always run `docker compose` from `/opt/openavisio/`, not from
`deploy/` — running from `deploy/` creates a separate `deploy-*` project that is
not the live stack.

```bash
# 1. Copy changed files to the server
scp backend/app/routers/documents.py root@YOUR_SERVER_IP:/opt/openavisio/backend/app/routers/documents.py

# 2. Rebuild and restart the affected service(s)
ssh root@YOUR_SERVER_IP "cd /opt/openavisio && docker compose up -d --build backend celery-worker celery-beat"
```

For the Caddyfile (no rebuild needed):
```bash
scp deploy/Caddyfile root@YOUR_SERVER_IP:/opt/openavisio/deploy/Caddyfile
ssh root@YOUR_SERVER_IP "cd /opt/openavisio && docker compose restart caddy"
```

### Viewing logs

```bash
# Backend (FastAPI)
ssh root@YOUR_SERVER_IP "docker logs openavisio-backend-1 --tail 100"

# Celery worker
ssh root@YOUR_SERVER_IP "docker logs openavisio-celery-worker-1 --tail 100"

# All services, live
ssh root@YOUR_SERVER_IP "cd /opt/openavisio && docker compose logs -f --tail 50"
```

## Demo instance

The public demo (`demo.openavisio.org`) is its **own** host, separate from the
test server above — a different box with a different `.env`. It uses the same
deploy layout (stack in `/opt/openavisio/`, compose run from there), so the
"Deploying a change" and "Viewing logs" steps apply unchanged; only the target
host differs.

Visitors log in as the caregiver; the admin account's password comes from
`DEMO_ADMIN_PASSWORD` (random if unset) and is never shown, because an admin
can change the AI models, roles and users of the whole instance.

Because it shares one account with every visitor, uploads must be locked
to the bundled sample — otherwise the box is an anonymous file drop under our
domain, and we own whatever gets uploaded. This takes **two** env vars that must
be set together:

- `DEMO_MODE=true` — frontend. Replaces the upload dropzone with a "replay the
  bundled sample" button.
- `DEMO_LOCKED_UPLOAD_SHA256=<sha256 of frontend/public/demo-sample.pdf>` —
  backend. Returns 403 for any file whose hash differs from the sample.

`DEMO_MODE` alone is a silent hole: the UI looks locked but the API stays open,
so a direct POST (or the frontend proxy) still stores any file. Both, or neither.

```bash
# the value to set — recompute if demo-sample.pdf ever changes
sha256sum frontend/public/demo-sample.pdf
```

## One-off: the embedding model changed (July 2026)

The default embedding model moved from `nomic-embed-text` to `qwen3-embedding:4b`
(`docs/research-embedding-model.md`). **A box that deploys this without acting will not throw
an error**, because both produce 768-dimensional vectors: questions get embedded by the new
model and compared against chunks embedded by the old one, and the chat quietly retrieves
nonsense. There is nothing in the logs to see.

On every box that already holds documents, after deploying:

```bash
# 1. the model has to exist on the Ollama host named by OLLAMA_EMBED_URL
ollama pull qwen3-embedding:4b

# 2. re-embed everything; no Alembic revision is involved, the chunks are rebuilt in place
docker compose exec backend python -c "
import asyncio
from sqlalchemy import text
from app.core.database import AsyncSessionLocal
from app.workers.pipeline import embedding_stage
async def main():
    async with AsyncSessionLocal() as db:
        ids = [str(r[0]) for r in (await db.execute(text(
            'select distinct document_reference_id from document_chunks '
            'where document_reference_id is not null'))).fetchall()]
    for i in ids: embedding_stage.delay(i)
    print('enqueued', len(ids))
asyncio.run(main())"
```

Roughly a minute per ten chunks on a 3090. Verify by counting: every row in `document_chunks`
should have a `created_at` from after the run.

## Backups

Two layers, per ADR-022:

- **ZFS native encryption** on the Postgres data volume — covers a stolen/decommissioned disk.
- **age-encrypted `pg_dump`** of `vaultdb`, with the age key held **out-of-band** (never inside the backup) — covers backup exfiltration. Keep the `DOCUMENT_ENCRYPTION_KEY` (master KEK) backed up out-of-band too; losing it means permanent loss of all documents.

### Keystore is a SEPARATE, short-retention stream (ADR-031)

Per-patient KEKs live in the **`patient_keys`** table. Crypto-shredding (erasing one
patient deletes their KEK, rendering their encrypted documents/text unrecoverable)
only reaches **backups** if the KEK is not restorable from a backup. So `patient_keys`
must be backed up **apart from the rest of `vaultdb`, with short retention** (days),
while the clinical data keeps its normal long retention.

Practical recipe — two dump streams instead of one:

```bash
# 1. Main clinical dump, EXCLUDING the keystore — long retention (e.g. 90 days)
pg_dump -U openavisio --exclude-table=patient_keys vaultdb \
  | age -r "$AGE_PUBKEY" > clinical-$(date +%F).sql.age

# 2. Keystore-only dump — SHORT retention (e.g. 7 days), pruned aggressively
pg_dump -U openavisio --table=patient_keys vaultdb \
  | age -r "$AGE_PUBKEY" > keystore-$(date +%F).sql.age
```

After a patient is erased, their KEK is gone from live data immediately and drops out
of every keystore backup once the 7-day window rolls — at which point the clinical
backups still holding their ciphertext become permanently undecryptable. **A restore
needs both streams for the same date** to bring documents back online.

If you skip the split (one combined dump), crypto-shredding still isolates blast radius
and shreds **live** data, but no longer reaches old backups — it degrades cleanly to the
ADR-022 guarantee. Nothing breaks; the erasure claim just narrows.
