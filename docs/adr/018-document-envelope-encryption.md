# ADR 018: Document envelope encryption with per-document DEKs

**Status:** Accepted — refined by ADR-022

> ADR-022 (encryption-at-rest strategy) refines this ADR: it sets the overall threat model, brings the database into scope (infra-level encryption), and **supersedes the one-time Alembic data migration below** (thrown away pre-production — wipe & re-upload). It also adds `kek_version`, removes `is_encrypted`, and hardens rotation ordering. The core scheme here (envelope, dedicated KEK, DEK-in-`BYTEA`, script-only rotation) still stands.

## Context

Documents were encrypted at rest using a single AES-GCM key derived from `app_secret` via PBKDF2 with a hardcoded salt (`b"openavisio-salt"`). Two weaknesses:

1. **Hardcoded salt** — negates most of PBKDF2's value; anyone who knows `app_secret` derives the key instantly without needing the salt.
2. **Single key for all documents** — rotating `app_secret` breaks decryption of all existing documents; there is no key rotation path.

The threat model: an attacker who obtains a copy of storage files and/or a DB dump, but does not have the encryption key. Encryption does not protect against an attacker who also has the key.

## Decisions

### Envelope encryption

Each document is encrypted with a randomly generated 32-byte DEK (Document Encryption Key). The DEK is then wrapped (encrypted) with a KEK (Key Encryption Key) and stored in the `DocumentReference` row. The storage file remains a pure ciphertext blob (`[12-byte nonce][ciphertext]`).

**Key rotation** means re-wrapping DEKs under a new KEK — storage files are never touched.

### Dedicated `DOCUMENT_ENCRYPTION_KEY` env var

The KEK is derived from a dedicated `DOCUMENT_ENCRYPTION_KEY` environment variable, separate from `app_secret`. `app_secret` is used exclusively for JWT signing. The two can rotate independently.

**Rejected:** deriving the KEK from `app_secret` (double duty — JWT rotation and document key rotation become coupled).

### DEK stored as `encrypted_dek BYTEA` on `DocumentReference`

The wrapped DEK lives in the database alongside the document record. The storage file carries no key material.

**Rejected:** prepending the wrapped DEK to the ciphertext blob (splits key material across DB and storage, complicates migration and rotation).

### One-time Alembic data migration

A data migration re-encrypts all existing documents at deploy time: decrypt with old scheme (PBKDF2 + hardcoded salt), generate fresh DEK, re-encrypt, store wrapped DEK. Old code path is deleted immediately after.

**Rejected:** lazy migration on first read (old vulnerable code path lives indefinitely; impossible to confirm full migration).

### Key rotation via management script only

Re-wrapping DEKs under a new KEK is done via `python -m app.scripts.rotate_deks`, run over SSH. Key material is never posted to an HTTP endpoint.

**Rejected:** admin API endpoint (`POST /admin/rotate-encryption-key`) — key material in HTTP request body appears in access logs even over HTTPS.

## Consequences

- `DocumentReference` gains an `encrypted_dek` column (nullable during migration; non-null for all new documents).
- Documents with `encrypted_dek IS NULL` are legacy (old scheme). The migration script eliminates these at deploy time.
- Operators must set `DOCUMENT_ENCRYPTION_KEY` in `.env`. The migration script prints a freshly generated key to stdout if the var is absent, so the operator can copy it in.
- `app_secret` rotation (JWT) and `DOCUMENT_ENCRYPTION_KEY` rotation are now independent operations.
