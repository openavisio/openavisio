# ADR 022: Encryption-at-rest strategy — app-level files, infra-level database

**Status:** Accepted

**Refines:** ADR-018 (document envelope encryption). The envelope scheme, dedicated `DOCUMENT_ENCRYPTION_KEY`, DEK-in-`BYTEA`, and script-only rotation from ADR-018 still stand. This ADR sets the overall threat model, brings the database into scope, and supersedes ADR-018's one-time data migration.

## Context

ADR-018 introduced per-document envelope encryption for storage files but only reasoned about the storage layer. It left a hole: the same medical content that lives in an encrypted storage blob is **also stored as plaintext in Postgres** in several places:

- `DocumentReference.extracted_text`, `extraction_json`, `description` (OCR + extracted clinical data)
- `DocumentChunk.content` — the RAG chunk text (needed in plaintext for embedding and retrieval)
- `ChatMessage.content` — the AI Health Assistant conversation
- the structured clinical tables — `condition`, `medication`, `observation`, `diary`, `incident`, `calendar`, `recommendation` (diagnoses, drugs, values as plaintext columns)

So a threat model that includes "attacker obtains a DB dump" (as ADR-018 stated) is **not actually satisfied** by encrypting storage files alone — the attacker just reads `document_chunks` or `conditions` instead.

App-level column encryption of these fields was considered and **rejected**: encrypted chunks cannot be embedded or retrieved (RAG breaks), and encrypted clinical columns cannot be filtered, sorted, or range-queried (core product features break).

The project is **pre-production** — the only deployment is a single test server with disposable data — so this is the right moment to fix the strategy coherently rather than accrete half-measures.

## Decisions

### Threat model (explicit)

Encryption at rest protects against an attacker who obtains a **copy** — a stolen or discarded disk, or an exfiltrated backup — of the storage bucket and/or the database, **without** the encryption keys.

It does **not** protect against host compromise: whoever controls the running host has the KEK (from `.env`), the DB, and the ciphertext together. This is an accepted, documented limitation for a self-hostable product.

### Two layers, matched to the two data stores

| Data store | Mechanism | Protects against |
|---|---|---|
| Storage files (blobs) | App-level envelope encryption (ADR-018) | Storage/bucket exfiltration |
| Database | **Infrastructure-level** at-rest encryption | Stolen disk / exfiltrated DB backup |

Both defend the same "someone grabbed a copy" vector; they are symmetric.

### Database confidentiality is infrastructure, not application

> **Superseded in part by ADR-031.** This section says free-text medical content stays
> in plaintext Postgres columns and rejects app-level column encryption. That is no
> longer what the code does: `extracted_text`, `extraction_json` and `DocumentChunk.content`
> are encrypted under the per-patient KEK (`enc:v1:` prefix, see `pipeline.py` and
> `app/core/encryption.py`), which is what makes crypto-shredding in ADR-031 reach them.
> The *structured* clinical tables — `condition`, `medication`, `observation`, and the
> rest — are still plaintext, and the reasoning below still holds for them: they must
> stay filterable and sortable. Anything reading these columns outside the app gets
> ciphertext and must decrypt through `decrypt_str` with the patient's KEK.

Plaintext medical content stays in Postgres columns (RAG and query features depend on it). DB confidentiality is delivered below the application:

1. **ZFS native encryption** on the Postgres data volume (the host is Proxmox/ZFS) — covers a stolen or decommissioned disk.
2. **age-encrypted `pg_dump` backups**, with the age key held **out-of-band** (never inside the backup) — covers backup exfiltration, the most realistic leak vector.

**Rejected:** Postgres TDE (pg_tde / Percona / Cybertec) — not in vanilla `pgvector/pg17`, heavyweight for the protection gained.

**Rejected:** app-level column encryption of `extracted_text` / `document_chunks` / clinical tables — breaks RAG, search, filtering; and would be incomplete anyway.

### Supersedes ADR-018's one-time data migration

ADR-018's Alembic data migration re-encrypted legacy documents **in place** (decrypt legacy → re-encrypt envelope → overwrite the storage file → update the row). A crash between the storage overwrite and the DB update leaves a document as envelope-ciphertext with no DEK — **unrecoverable**, with no original backup.

Because the project is pre-production with disposable data, the migration is **thrown away** entirely:

- Delete the `..._migrate_document_encryption` migration.
- Delete the legacy PBKDF2 / hardcoded-salt decrypt path.
- Wipe the test server's documents and re-upload; new uploads are envelope-encrypted from the start.

The `..._add_encrypted_dek` schema migration (adds the column) is kept.

### `kek_version` column added now

`DocumentReference` gains `kek_version smallint NOT NULL DEFAULT 1`, recording which KEK generation wrapped each DEK. It is not exercised yet (single KEK), but it is cheap to add pre-production and unlocks future zero-downtime rotation without a schema change under load.

### Offline key rotation with hardened ordering

`rotate_deks.py` re-wraps all DEKs under a new KEK and bumps `kek_version`. Rotation is **offline**: the documented and enforced order is *stop backend + celery → rotate → update `.env` → start*. The script must not leave the system in a state where a running backend holds the old KEK against newly re-wrapped DEKs (which would silently fail every document read).

**Rejected:** online dual-KEK rotation (`DOCUMENT_ENCRYPTION_KEY` + `..._PREVIOUS`, unwrap by `kek_version`) — more code and a second env var for a rare, maintenance-windowable operation. YAGNI pre-production; `kek_version` keeps the door open.

### Encryption is mandatory — `is_encrypted` flag removed

Every storage file is ciphertext; there is no plaintext path. The `DocumentReference.is_encrypted` boolean (a relic of mixed states) is **removed** — a "may be unencrypted" flag only invites inconsistency bugs. `encrypted_dek IS NOT NULL` is the factual invariant.

### Erasure is unchanged; crypto-shredding deferred

Encryption does **not** change Patient Erasure semantics (ADR-017): erasure remains a **hard delete** of documents, storage files, and embeddings.

Crypto-shredding (destroy the DEK to render ciphertext unreadable) is explicitly **not** used for erasure, because the DEK lives in the DB row and therefore lands in the *same* backups as the ciphertext — destroying the live key does not shred backed-up copies. Backup residue is handled by backup retention/rotation.

**Future option (noted, not decided):** per-Patient KEK, so that destroying one patient's key crypto-shreds *all* copies (including backups). Revisit only if "erasure must reach backups" becomes a hard requirement.

## Consequences

- `DocumentReference`: `encrypted_dek` becomes effectively non-null for all documents; `is_encrypted` column dropped; `kek_version smallint NOT NULL DEFAULT 1` added.
- The document read/write path encrypts/decrypts unconditionally; no legacy decrypt path remains.
- Operators must: set `DOCUMENT_ENCRYPTION_KEY` in `.env`; back the KEK up **out-of-band, separate from storage/DB backups** (KEK loss = permanent loss of all documents; KEK stored inside the backup it protects makes that backup's encryption worthless).
- Deployment must provision **ZFS-encrypted** Postgres storage and **age-encrypted** `pg_dump` backups. (The full Proxmox/AvisioHub deployment is a separate design pass.)
- ADR-018's migration and lazy-migration reasoning are historical; this ADR is the current source of truth for the migration approach.
