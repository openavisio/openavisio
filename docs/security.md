# Security

Operator reference for running OpenAvisio securely. Covers secrets, document encryption, authentication, audit logging, GDPR operations, breach response, and backups.

---

## Security model

OpenAvisio stores special-category health data (GDPR Article 9). The core threat model is:

**Protected against:** An attacker who obtains a copy of the database or storage files without the encryption key — e.g. a stolen disk, a misconfigured storage bucket, or a database dump.

**Not protected against:** An attacker who also has the `DOCUMENT_ENCRYPTION_KEY` and `app_secret` — full key compromise requires credential rotation (see [Key rotation](#key-rotation)) and a breach notification (see [Breach response](#breach-response)).

What is encrypted at rest:
- **Document files** (PDFs, images, scans) and patient photos: AES-GCM with a random per-document key (DEK) wrapped under the KEK. See [ADR 018](adr/018-document-envelope-encryption.md).
- **Free text** under the per-patient key: extracted document text and extraction results, the chunks the AI Health Assistant searches, chat messages, Health Log entries. See [ADR 031](adr/031-per-patient-kek-crypto-shredding.md).

What is NOT encrypted at rest (stored in plaintext in the database):
- The structured clinical tables (Diagnoses, Medications, Measurements, Lab Results, Incidents, Events, Expenses, Einstufungen), because they must stay filterable and sortable ([ADR 022](adr/022-encryption-at-rest-strategy.md)), and audit log entries. The database itself must be protected at the infrastructure level (firewall, no public exposure).

### No side doors to the database

**Never connect anything but OpenAvisio itself to a production database**: no BI or analytics tool (Metabase, Superset, Grafana), no web admin (pgAdmin, Adminer), no reporting replica. Anything with a read connection sees the plaintext tables above, and such tools are the easiest thing on a host to leave reachable. In September 2026 a German DiGA provider lost questionnaire answers and diary entries exactly this way: an open-source BI tool attached to its database was reachable from the internet, and an unpatched vulnerability let attackers create their own accounts in it. For a one-off query, use `psql` inside the postgres container over SSH and close it afterwards.

---

## Secrets and environment variables

All secrets live in `/opt/openavisio/.env`. Never commit this file.

| Variable | Purpose | When to rotate |
|---|---|---|
| `app_secret` | JWT signing key. Rotating it immediately invalidates all active sessions. | If compromised |
| `DOCUMENT_ENCRYPTION_KEY` | KEK that wraps per-document encryption keys. Rotating requires running the `rotate_deks` script first. | If compromised |
| `minio_secret_key` | MinIO access (if using MinIO storage backend) | If compromised |
| `database_url` | PostgreSQL credentials | If compromised |

### Generating a new DOCUMENT_ENCRYPTION_KEY

```bash
python -c "import os,base64; print(base64.b64encode(os.urandom(32)).decode())"
```

This must be set before running database migrations for the first time. If it is absent, the backend will refuse to encrypt or decrypt any document.

---

## Document encryption

Documents are encrypted with envelope encryption (ADR 018):

1. A random 32-byte DEK is generated per document at upload time.
2. The DEK is wrapped (encrypted) under the KEK (`DOCUMENT_ENCRYPTION_KEY`) and stored in the `encrypted_dek` column of `document_references`.
3. The document file in storage contains only ciphertext.

### Verifying encryption is active

```bash
# Check that uploaded documents have a non-null encrypted_dek
ssh root@YOUR_SERVER_IP
docker exec openavisio-postgres-1 psql -U openavisio vaultdb \
  -c "SELECT COUNT(*) FROM document_references WHERE is_encrypted AND encrypted_dek IS NULL;"
# Should return 0
```

### Key rotation

Use the `rotate_deks` script when you need to change `DOCUMENT_ENCRYPTION_KEY`. This re-wraps all DEKs under the new key without touching the storage files.

```bash
# 1. Generate a new key
NEW_KEY=$(python -c "import os,base64; print(base64.b64encode(os.urandom(32)).decode())")
echo $NEW_KEY  # save this — you will need it in step 4

# 2. Run the rotation script (uses the current DOCUMENT_ENCRYPTION_KEY from .env)
ssh root@YOUR_SERVER_IP
docker exec openavisio-backend-1 python -m app.scripts.rotate_deks --new-key "$NEW_KEY"

# 3. Confirm output: "Rotated N DEK(s) successfully."

# 4. Update .env
nano /opt/openavisio/.env
# Set: DOCUMENT_ENCRYPTION_KEY=<new key from step 1>

# 5. Restart services
cd /opt/openavisio && docker compose up -d --build backend celery-worker celery-beat
```

If the script fails (any DEK cannot be re-wrapped), it aborts without committing. The old key remains active. Investigate and retry before updating `.env`.

---

## AI data flows

The Processing Pipeline sends patient document content to the AI service for OCR, classification, extraction, and embedding. Where that data goes depends on the configured backend (`AI_BACKEND` env var):

| Backend | Where patient data goes | GDPR implication |
|---|---|---|
| `ollama` (default) | Local Ollama instance at `OLLAMA_URL` — stays on your infrastructure | No third-party processor |
| `vllm` | Wherever `VLLM_URL` points: your own vLLM keeps it on your infrastructure, a hosted provider receives it | Hosted provider: Art. 28 DPA required (see below) |
| `mock` | No data sent anywhere — canned responses only | Dev/testing only |

**Embeddings and vision OCR** go where their own URLs point (`OLLAMA_EMBED_URL` / `VLLM_EMBED_URL`, `OLLAMA_VISION_URL` / `VLLM_VISION_URL`), which may differ from the text backend. Document chunks and page images reach whichever host serves those roles.

### Using a hosted provider

Where any role points at a provider's endpoint, OpenAvisio does not check where that is; the operator does:

1. Execute the provider's Data Processor Agreement before processing real patient data.
2. Check where the provider processes the data (Art. 44 if outside the EU/EEA).
3. Record the provider as a data processor in your RoPA (see issue #19).

---

## Authentication

### Passkeys (recommended)

Users can register passkeys from their profile settings after signing in with a password. Passkeys are phishing-resistant and faster for day-to-day use. See [ADR 014](adr/014-passkey-authentication.md).

### Passwords

Every user has a password set during invitation acceptance. Passwords are bcrypt-hashed; the hash is never logged.

### Session tokens

- Access token: 15-minute JWT, signed with `app_secret`
- Refresh token: 7-day JWT

Rotating `app_secret` immediately invalidates all sessions — all users must log in again.

---

## Audit log

All create, update, and delete operations on patient data are written to the `audit_log` table. The admin log viewer is at `/admin/logs`.

Log retention: entries older than **30 days** are pruned automatically by the log handler scheduler.

Sensitive fields excluded from audit log diffs: `hashed_password`, `failed_login_attempts`, `locked_until`.

On Patient Erasure, all prior audit log entries for that patient's data are hard-deleted and replaced with a single tombstone entry (no PII). See [ADR 017](adr/017-patient-erasure-cascade-hard-delete.md).

---

## External document share links

Caregivers can generate a time-limited, read-only, anonymous link for an external specialist to view a chosen set of a Patient's Documents (see [ADR 021](adr/021-external-document-share-links.md)). This is the app's highest-sensitivity surface — an anonymous URL to an identified Patient's health data — and is hardened accordingly:

- **Token:** 256-bit (`secrets.token_urlsafe(32)`). Only its SHA-256 hash is stored in `document_share_links.token_hash`; the plaintext token exists solely in the URL and is shown **once** at creation. A database leak yields no usable links.
- **Access endpoints are public** (`/api/public/document-shares/{token}` and `.../documents/{id}/file`) — unauthenticated, token-only. Unknown/malformed token → `404`; expired or revoked → `410`. Lookups are by hash with a constant response, so the endpoint never reveals which links exist.
- **Expiry is mandatory:** 7, 30, or 90 days (max 90) — there is no "never". Caregivers can revoke at any time.
- **Creation is restricted** to the Patient's own caregivers (owner / active legal representative / non-staff with access). A `manager`/`admin` acting only on blanket staff access is refused (403).
- **Every external access is audit-logged** (`action = accessed`, `user_id = null`) with the recipient's IP and user-agent, debounced per link+document to avoid viewer-driven log floods. Patient Erasure cascades the links, their items, and these access logs.
- **Response headers:** `Referrer-Policy: no-referrer`, `X-Robots-Tag: noindex, nofollow`, `Cache-Control: no-store` on all public share responses and the public page.
- **Delivery is copy-link only** in v1 (no app-sent email). App-level rate limiting is out of scope for v1 — rely on the reverse proxy.

---

## GDPR operations

### Patient erasure (GDPR Art. 17)

Triggered by a Coordinator or the patient's owning User from the patient settings page, or via the API:

```
POST /patients/{patient_id}/erase
```

This cascade hard-deletes all clinical data, documents (including storage files), access records, and prior audit log entries for that patient. A tombstone audit entry is written. **Irreversible.**

### User erasure (GDPR Art. 17)

Triggered by an admin or the user themselves. Anonymises PII fields, hard-deletes credentials and access grants. Blocked if the user still owns any patients — erase or transfer those first.

```
POST /users/{user_id}/erase
```

### Subject access request (GDPR Art. 15 / 20)

Export a patient's full record in FHIR R4 format:

```
GET /patients/{patient_id}/export/fhir
```

This produces a FHIR Bundle including Patient demographics, Observations, Conditions, Medications, Incidents, Events, Health Log entries, Recommendations, and Document metadata.

---

## Breach response

If you suspect a data breach (unauthorised access to patient data, credentials, or storage):

### Immediate steps

1. **Isolate** — if the backend is reachable from the internet, take it offline immediately:
   ```bash
   ssh root@YOUR_SERVER_IP
   cd /opt/openavisio && docker compose stop backend celery-worker celery-beat
   ```

2. **Assess scope** — check audit logs and system logs for signs of unauthorised access:
   ```bash
   docker logs openavisio-backend-1 --since 24h | grep -i "error\|unauthori\|403\|401"
   ```

3. **Rotate compromised credentials** — see [Secrets and environment variables](#secrets-and-environment-variables) above.

4. **Notify the supervisory authority within 72 hours** (GDPR Art. 33):
   - LfDI Baden-Württemberg: https://www.baden-wuerttemberg.datenschutz.de/meldung-einer-datenpanne/
   - Required fields: nature of breach, categories and approximate number of affected persons, likely consequences, measures taken.

5. **Notify affected patients/users** if the breach is likely to result in high risk to them (GDPR Art. 34). Health data breaches are high-risk by default.

6. **Document** the incident, the timeline, and all actions taken. Keep records for at least 3 years.

---

## Backups

Three things must be backed up together to enable a full restore:

| What | Where | How |
|---|---|---|
| Database | PostgreSQL in `openavisio-postgres-1` | `pg_dump` or volume snapshot |
| Document storage | `/opt/openavisio/data/documents/` (local) or MinIO bucket | rsync / bucket replication |
| Environment file | `/opt/openavisio/.env` | Encrypted offsite copy |

**Without `.env`, encrypted documents cannot be decrypted.** Store it separately from the server — if the server is compromised or lost, you need the key to restore documents.

### Example database backup

```bash
ssh root@YOUR_SERVER_IP
docker exec openavisio-postgres-1 pg_dump -U openavisio vaultdb | gzip > /tmp/vaultdb-$(date +%Y%m%d).sql.gz
```
