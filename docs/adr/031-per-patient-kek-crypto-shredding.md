# ADR 031: Per-patient KEK — crypto-shredding that reaches backups

**Status:** Accepted

**Refines:** ADR-022 (encryption-at-rest strategy), ADR-018 (document envelope encryption), ADR-017 (patient erasure cascade). ADR-022 deferred this ("Future option, noted not decided: per-Patient KEK … revisit only if erasure must reach backups becomes a hard requirement"). It is now a requirement: GDPR Art. 17 erasure must be provable even against retained backups.

## Context

ADR-022 established a two-layer at-rest model: app-level envelope encryption for storage blobs, infrastructure-level encryption (ZFS + age-encrypted `pg_dump`) for the database. Erasure stayed a **hard delete** (ADR-017); crypto-shredding was rejected because the DEK lived in the same DB row — and therefore the same backups — as the ciphertext, so destroying the live key shredded nothing in a backup.

Two things push us past that:

1. **Blast-radius isolation.** A single KEK wraps every document's DEK. Unwrapping one DEK requires the KEK, which then decrypts *all* patients. A per-patient key confines exposure to one patient.
2. **Erasure reaching backups.** For a multi-patient instance (a care home), "delete this one patient, provably, including from old backups" is a real GDPR ask that hard-delete + backup retention does not answer within a bounded window.

The central constraint, which killed the naive version: **crypto-shredding only reaches a backup if the decrypting key is not recoverable from that backup.** A per-patient KEK stored as a column on the patient row lands in the DB backup — destroying it live leaves old DB backups fully recoverable with the (persistent) master KEK. So the KEK's *placement* is the whole game.

## Decisions

### Key hierarchy

```
blob + extracted_text + extraction_json   (ciphertext, in DB / storage)
        ▲ AES-GCM, per-document DEK
document DEK                               (encrypted_dek, on document row)
        ▲ AES-GCM, per-patient KEK
patient KEK                                (wrapped, in the KEYSTORE)
        ▲ AES-GCM, master KEK
master KEK                                 (DOCUMENT_ENCRYPTION_KEY env, out-of-band)
```

The document DEK wraps **all** of a document's PHI — the storage blob *and* its plaintext derivatives `extracted_text` and `extraction_json`. Only the small DEK is wrapped under the patient KEK, so KEK rotation re-wraps DEKs, never re-encrypts blobs or text.

### Scope: documents + free text, not structured columns

Encrypted under the chain: storage blobs, `extracted_text`, `extraction_json`. **Not** encrypted: the structured/coded clinical rows (`observation`, `condition`, `medication`, `diary`, `calendar`, …) — they must stay queryable (trends, filters, calendar, range checks). ADR-022's rejection of column-encrypting those still stands.

Consequence: **literal SQL search over `extracted_text` is dropped**; document-content search runs on embeddings (semantic, pgvector). Embedding vectors stay plaintext and are hard-deleted on erasure (they are a lossy derivative, not a readable copy).

Honest erasure claim: *encrypted PHI (documents + their text) is cryptographically shredded across live data and, within the keystore retention window, all backups; structured clinical rows are hard-deleted per ADR-017.*

### Keystore: a separate backup stream

Wrapped patient KEKs live in a dedicated `patient_key` table that the **backup tooling treats separately** from the main DB: short retention (days), so a destroyed KEK rolls out of every backup quickly, while clinical backups keep their normal long retention. This is what makes crypto-shredding actually reach backups. The separation is an **ops requirement**, documented for deployment; the app only guarantees the row is deleted and caches invalidated.

**Rejected — KEK as a column on the patient row:** simplest, gives instant live shred + isolation, but old DB backups stay recoverable with the master KEK. Does not deliver the "reaches backups" goal.

**Rejected (for now) — external KMS/HSM:** strongest (backups never held usable key material) but contradicts ADR-022's "env now, KMS-able later" and needs infra we don't run. The `_get_kek()` seam already abstracts master-KEK holding; KMS slots in later without touching the hierarchy.

### Master KEK holding

Unchanged from ADR-022: master KEK from `DOCUMENT_ENCRYPTION_KEY` env, held out-of-band, never in a DB/storage backup. Retrieval stays behind `_get_kek()` so a future KMS is a one-function change.

### Caching

Unwrapping the patient KEK on every document op means a master-KEK AES-GCM per request. An in-memory LRU keyed by `patient_id` caches the **unwrapped** KEK with a short TTL (default 5 min). Erasure and rotation invalidate the entry immediately. Cache is per-process, never persisted.

### Erasure (extends ADR-017)

Erasing a patient now:
1. **Delete the `patient_key` row** → crypto-shreds every blob, `extracted_text`, `extraction_json` for that patient, live and (as the keystore stream rolls) in backups.
2. **Hard-delete** structured clinical rows, storage files, and embeddings (ADR-017, unchanged).
3. **Invalidate** the patient's KEK cache entry.

Belt-and-suspenders: even though (1) renders documents unreadable, (2) still physically removes rows — we do not leave undecryptable ciphertext lying around.

### Rotation

Two independent rotations, both offline, both re-wrap keys only:
- **Master KEK:** re-wrap every `patient_key.wrapped_kek`, bump `patient_key.kek_version`.
- **Patient KEK:** generate a new patient KEK, re-wrap that patient's document DEKs, bump the document `kek_version`.

`kek_version` (ADR-022) already exists on the document row; `patient_key` carries its own.

### Migration: big-bang, pre-production

Project is still pre-production (disposable data), so a one-shot script: per patient, generate a KEK, unwrap each document DEK under the master KEK and re-wrap under the patient KEK, encrypt `extracted_text` + `extraction_json` under the document DEK. No lazy dual-read path (ADR-022's crash-safety reasoning: a lazy path that half-migrates is worse than a windowed offline run on disposable data).

## Consequences

- New table `patient_key (patient_id PK/FK, wrapped_kek bytea, kek_version smallint, created_at)`, provisioned into a **separate, short-retention backup stream** by deployment.
- `encrypted_dek` on documents is now wrapped under the patient KEK, not the master KEK. `extracted_text` / `extraction_json` become ciphertext at rest; all reads route through decrypt.
- **Literal `extracted_text` search removed**; content search is embeddings-only. Any feature relying on SQL text match over document bodies must move to semantic search.
- A patient with no `patient_key` row can decrypt nothing — the row's existence is the invariant, its deletion is erasure.
- Operators must configure the keystore's separate/short backup retention; without it, crypto-shredding still isolates and shreds live data but does **not** reach old backups (degrades to ADR-022's guarantee, not a correctness bug).
- Host compromise remains out of scope (master KEK + DB + keystore all on the running host) — unchanged from ADR-022.
