# Data Protection Impact Assessment (DPIA) — Operator Template

> **This is a template.** OpenAvisio is self-hosted software. The organisation that operates an
> OpenAvisio installation is the data controller and must complete their own DPIA before processing
> real patient data. Fill in all fields marked with square brackets `[…]` and have the completed
> document reviewed by a data protection professional.
>
> The OpenAvisio project (software author) is not a data controller and does not require its own DPIA.

Required under GDPR Article 35 for systematic processing of special-category data (health data, Art. 9).

**Controller:** [ORGANISATION NAME], [ADDRESS], [CONTACT EMAIL]
**System:** OpenAvisio health data vault
**Version assessed:** current codebase (master branch)
**Date:** [DATE OF COMPLETION]
**Status:** Template — must be completed and reviewed before first production use with real patient data

---

## 1. Description of the processing

### What OpenAvisio does

OpenAvisio is a self-hosted health data vault. It stores, processes, and provides access to personal health records for one Organisation (a care home, clinic, household, or individual).

### Processing operations

1. **User authentication** — email/password and passkey login; short-lived JWT sessions.
2. **Patient record management** — creation, editing, and viewing of clinical data (Diagnoses, Medications, Measurements, Lab Results, Incidents, Events, Health Logs, Recommendations).
3. **Document processing** — upload of medical PDFs and images; AI-powered OCR, classification, and entity extraction via the Processing Pipeline.
4. **AI Health Assistant** — conversational interface answering questions about a patient's records using retrieval-augmented generation (RAG).
5. **Access management** — Coordinators grant Caregiver access to Users; access is patient-scoped.
6. **Audit logging** — all create/update/delete operations on patient data are logged.
7. **Data export** — FHIR R4 bundle export of the full patient record.
8. **Data erasure** — GDPR Art. 17 cascade hard-delete of all patient or user data on request.

### Data subjects

- **Patients** — the persons whose health data is stored. May or may not be Users themselves.
- **Users** — persons with a system login who manage patient records.

### Special-category data

All clinical data stored in OpenAvisio (Diagnoses, Medications, Measurements, Lab Results, Incidents, Health Logs, document contents) is health data within the meaning of GDPR Art. 9(1) and Art. 4(15).

---

## 2. Necessity and proportionality

### Purposes and legal basis

| Processing operation | Legal basis |
|---|---|
| Patient record management, document processing, AI Health Assistant | Art. 9(2)(h) — health care purposes under professional responsibility (organisational deployments); or Art. 9(2)(a) — explicit consent (homelab/personal use) |
| User account management, access control, audit logging | Art. 6(1)(b) — contractual necessity; Art. 6(1)(c) — legal obligation (GDPR accountability) |
| Email delivery (invitations) | Art. 6(1)(b) — contractual necessity |

### Data minimisation

- Only data the user explicitly enters or uploads is stored.
- The Processing Pipeline extracts only clinical entities relevant to care (Diagnoses, Medications, Measurements, Lab Results, Recommendations). Raw document text is stored for search but not displayed beyond the document view.
- Audit logs exclude sensitive credential fields (`hashed_password`, `failed_login_attempts`).
- Health Log (DiaryEntry) fields are all optional — the user records only what is relevant.

### Storage limitation

- **Documents and clinical data**: retained until Patient Erasure is triggered. No automatic expiry — health records may be needed indefinitely for care continuity.
- **Audit log entries**: 30-day retention for application logs; DB audit entries purged on Patient Erasure.
- **Sessions**: access tokens expire after 15 minutes; refresh tokens after 7 days.
- **Invite tokens**: single-use, expire on acceptance.

---

## 3. Risk assessment

### Risk 1 — Unauthorised access to health data

**Likelihood:** Low (access controls, authentication, encrypted transport)
**Severity:** High (health data is special-category; disclosure could harm patients)
**Residual risk:** Low after controls

**Controls in place:**
- Patient-level access control enforced on every API endpoint (`auth/access.py`)
- Role-based access: admin > coordinator > caregiver
- Short-lived JWT sessions; passkey (phishing-resistant) authentication available
- HTTPS enforced (Nginx Proxy Manager → Caddy)
- Backend not exposed to the internet — only reachable via the frontend proxy

### Risk 2 — Data breach via storage or database access

**Likelihood:** Low (infrastructure-level controls)
**Severity:** High

**Controls in place:**
- Document files encrypted at rest with AES-GCM envelope encryption; random per-document DEK wrapped under dedicated `DOCUMENT_ENCRYPTION_KEY` (ADR 018)
- Database not exposed outside the Docker network
- `DOCUMENT_ENCRYPTION_KEY` stored separately from database

**Residual risk:** Low. An attacker with DB dump alone cannot decrypt document content without the KEK.

### Risk 3 — Accidental erasure or data loss

**Likelihood:** Low
**Severity:** High (health records are irreplaceable)

**Controls in place:**
- Soft-delete (`is_deleted`) as default for all clinical entities — recoverable by admin
- Patient Erasure is a separate, explicit endpoint (`POST /patients/{id}/erase`), separate from soft-delete
- Erasure requires Coordinator or owning User role
- Backup procedure documented in `docs/security.md`

**Residual risk:** Low with regular backups. Without backups, loss from hard-delete is irreversible by design.

### Risk 4 — AI processing sending health data to third parties

**Likelihood:** Low for self-hosted deployments (default backend is Ollama). Certain for the deployments the project hosts, which run all three AI roles at IONOS by design.
**Severity:** High if it occurs

**Controls in place:**
- Default `AI_BACKEND=ollama` keeps all inference on-premises
- Whether `VLLM_URL` (and the vision and embedding URLs) point at the operator's own infrastructure or at a provider is the operator's decision; OpenAvisio does not infer it, since a key protects an on-premise vLLM as often as a hosted one (ADR 050)
- Each role can be kept local independently: `OLLAMA_VISION_URL` and `OLLAMA_EMBED_URL` take precedence over their hosted counterparts

**Scope of a hosted deployment, stated plainly:** with `VLLM_VISION_URL` and `VLLM_EMBED_URL` pointed at the provider, all three roles run there, and the provider receives the **page images** (vision OCR), the document text (extraction and chat) and the text chunks (embeddings). This is not a residual detail: the images are the widest disclosure of the three, and an earlier version of this document claimed both roles were always local.

**Residual risk:** Low for default deployments. Medium for any hosted-AI deployment without a DPA — the operator must execute one before use, with whichever provider the endpoint belongs to (IONOS Cloud GmbH on the instances the project operates, whose DPA is part of the Cloud terms and is not the IONOS SE one).

### Risk 5 — Rights of data subjects not fulfilled

**Likelihood:** Low
**Severity:** Medium

**Controls in place:**
- Art. 17 (erasure): implemented — cascade hard-delete for both Patient and User, with tombstone audit entry
- Art. 20 (portability): implemented — FHIR R4 bundle export covering all entity types
- Art. 15 (access): users can view all their data via the UI; full export available via FHIR endpoint
- Art. 16 (rectification): all clinical data is editable by authorised users

**Gap (open):** No formal Subject Access Request workflow for situations where a data subject requests their data directly (e.g. via email). Operator must handle manually.

### Risk 6 — Health data shared externally for studies beyond the original consent

**Likelihood:** Low–Medium (depends on how actively Sharing Purposes are used)
**Severity:** High (data leaves the care circle to an external study/registry)

**Controls in place:**
- Sharing is opt-in per file — a caregiver explicitly selects Documents and consents; nothing is shared automatically
- Only Coordinators/admins can create a Sharing Purpose; ordinary caregivers can only respond to requests
- Purpose Managers get file-scoped access — only the files shared to that purpose, never the rest of the record
- Consent terms (requested data + identification mode) freeze once the first file is shared, so the basis a caregiver agreed to cannot be changed afterwards
- Revocation, Document deletion, and Patient Erasure all end in-system access; every consent/decline/revoke/close is audit-logged
- Optional anonymous mode replaces the patient name with a stable pseudonym in the collection view

**Residual risk:** Medium. Once a Purpose Manager downloads a file and forwards it to the external study, OpenAvisio cannot recall it. The operator must put an appropriate agreement in place with the study and ensure caregivers understand this before consenting.

---

### Risk 7 — Health data disclosed externally via anonymous document share links

**Likelihood:** Low–Medium (depends on how often caregivers share with external specialists)
**Severity:** High (an identified Patient's Documents reach an external party; anyone holding the link URL can read them)

**Controls in place:**
- Links are read-only, scoped to an explicitly chosen snapshot of Documents, and never expose the wider Patient record
- Creation is a data-subject act — restricted to the Patient's own Caregivers (owner / active legal representative / non-staff with access); staff acting only in an admin/manager capacity are refused (see ADR-021)
- 256-bit token; only its SHA-256 hash is stored, so a database leak yields no usable links; the full link is shown once at creation
- Mandatory expiry (7/30/90 days, max 90 — no "never") and caregiver revocation; expired/revoked links return a clear error
- Every external access (view + download) is audit-logged with the recipient's IP and user-agent; Patient Erasure cascades links, items, and these logs
- Public pages carry `no-referrer`, `noindex`, and `no-store`; app-level delivery is copy-link only (no app-sent email in v1)

**Residual risk:** Medium. The link is anonymous by design — anyone who obtains the URL (e.g. via a forwarded email) can view the Documents until it expires or is revoked. The recipient's IP/user-agent are themselves personal data of the specialist and are processed for accountability (logged in the audit trail). Operators should keep expiry short and advise caregivers to share links over private channels.

---

## 4. Measures to address risks

| Risk | Additional measure needed |
|---|---|
| Unauthorised access | Multi-factor authentication (passkeys are available but not mandated). Consider requiring passkeys for admin accounts. |
| Data breach | Maintain encrypted backups of `.env` (contains `DOCUMENT_ENCRYPTION_KEY`). Follow breach response runbook (`docs/breach-response.md`). |
| Data loss | Regular automated backups of PostgreSQL and document storage. Test restore procedure quarterly. |
| AI data flows | Mandate DPA execution before pointing any AI role at a hosted endpoint (a `VLLM_URL`, `VLLM_VISION_URL` or `VLLM_EMBED_URL` at a provider). Name the actual provider in the RoPA sub-processor table. |
| Data subject rights | Document SAR response procedure. Nominally: export via FHIR endpoint, erasure via admin UI. |

---

## 5. Consultation

For organisational deployments (care homes, clinics), consult with:
- A qualified data protection officer (DPO) or external data protection advisor
- Legal counsel familiar with German healthcare data protection law (BDSG, GDPR, potentially KHZG)

For personal/homelab deployments, formal consultation is not required.

---

## 6. Review schedule

This DPIA must be reviewed when:
- A new processing operation is added (new entity type, new AI provider, new external service)
- A security incident occurs
- Applicable law changes
- At minimum annually

---

## Sign-off

| Role | Name | Date | Signature |
|---|---|---|---|
| Controller representative | | | |
| Data protection advisor (if applicable) | | | |
