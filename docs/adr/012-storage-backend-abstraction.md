# ADR 012: StorageBackend abstraction — local filesystem and MinIO

## Context

Document files are encrypted at upload time and need to be retrieved by the Processing Pipeline for OCR. The initial implementation wrote encrypted bytes directly to a local filesystem path and stored that path in `DocumentReference.storage_path`.

For AvisioHub (multi-tenant, Proxmox LXC per org), local storage inside an LXC has three problems:

- **Disk resize pain** — documents are the fastest-growing data. Resizing an LXC disk (especially ZFS) per-org as storage grows is operational burden.
- **Heavy LXC migration** — live-migrating an LXC with tens of GB of documents is slow. A lightweight LXC (Postgres + app only) is fast to move between nodes.
- **Backup doesn't scale** — N Proxmox LXC snapshots vs. one MinIO backup of a dedicated storage LXC.

## Decision

Introduce a `StorageBackend` interface in `app/core/storage.py` with `write`, `read`, and `delete` methods. Two implementations ship:

- **`LocalFileBackend`** — wraps `Path.write_bytes` / `read_bytes` / `unlink`. Default for single-install deployments. Base path is `settings.document_storage_path`.
- **`MinioBackend`** — uses the `minio` Python client to PUT/GET/DELETE objects in an S3-compatible bucket. Selected when `STORAGE_BACKEND=minio`.

`get_storage()` is a `@lru_cache(maxsize=1)` singleton — the backend is constructed once per process.

### Key format

New uploads use **relative keys**: `{patient_id}/{doc_id}.enc`

- `LocalFileBackend` resolves these as `base_path / key`. Legacy rows that stored absolute paths (e.g. `/data/documents/patient-uuid/doc-uuid.enc`) continue to work because `Path(absolute_base) / absolute_key == absolute_key` in Python.
- `MinioBackend` uses the relative key directly as the S3 object key.

### Configuration

| Env var | Default | Purpose |
|---|---|---|
| `STORAGE_BACKEND` | `local` | `local` or `minio` |
| `MINIO_ENDPOINT` | _(empty)_ | MinIO host:port, e.g. `minio.internal:9000` |
| `MINIO_BUCKET` | `openavisio` | Bucket name (created automatically if absent) |
| `MINIO_ACCESS_KEY` | _(empty)_ | Per-org access key |
| `MINIO_SECRET_KEY` | _(empty)_ | Per-org secret key |
| `MINIO_SECURE` | `true` | TLS; set `false` for plain HTTP on a private LAN |

Encryption and decryption remain in the calling code — they are not a storage concern.

## AvisioHub deployment topology

```
Proxmox node(s)
├── LXC: org-A  (postgres, redis, backend, celery, frontend, caddy)
│     STORAGE_BACKEND=minio, MINIO_BUCKET=org-a, MINIO_ACCESS_KEY=...
├── LXC: org-B  (postgres, redis, backend, celery, frontend, caddy)
│     STORAGE_BACKEND=minio, MINIO_BUCKET=org-b, MINIO_ACCESS_KEY=...
└── LXC: minio  (shared MinIO on the largest/fastest disk pool)
      one bucket + one access key pair per org — isolation enforced by MinIO policy
```

Each org LXC only stores transient data (Postgres WAL, Redis RDB). Snapshots are fast. Document data lives entirely in the MinIO LXC, backed up independently.

## Consequences

- `minio>=7.0.0` is a hard dependency (small, pure Python). It is only instantiated when `STORAGE_BACKEND=minio`.
- `LocalFileBackend.write` creates parent directories automatically — no external `mkdir` needed.
- Existing single-install deployments: no config change required; `STORAGE_BACKEND` defaults to `local`.
- Migrating an existing install to MinIO: upload files to MinIO, rewrite `storage_path` values to relative keys, set env vars.

## Rejected alternatives

**Async interface.** Making `write`/`read` async would require wrapping Celery sync tasks in another event loop layer and complicates testing. The existing pattern (sync I/O in async FastAPI endpoints) is already established by `_encrypt`/`_decrypt`. Revisit if large uploads cause event-loop blocking in practice.

**Encrypt inside the backend.** The backend would need the app secret, making it stateful and harder to test in isolation. Encryption is a separate concern.

**SeaweedFS.** More operational complexity (master + volume servers), no standard S3 API. MinIO covers the same use cases with a simpler single-binary deploy and S3 compatibility that opens a future migration path to AWS S3 or Cloudflare R2.
