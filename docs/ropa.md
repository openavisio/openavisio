# Records of Processing Activities (RoPA) — Operator Template

> **This is a template.** The organisation that operates an OpenAvisio installation is the data
> controller and must maintain their own RoPA. Fill in all fields marked with square brackets `[…]`
> and keep the document up to date as processing activities change.
>
> The OpenAvisio project (software author) is not a data controller and does not require its own RoPA.

Required under GDPR Article 30. Maintained by the data controller operating this OpenAvisio installation.

**Controller:** [ORGANISATION NAME], [ADDRESS], [CONTACT EMAIL]
**Last updated:** [DATE OF COMPLETION]

---

## 1. User account management

| Field | Detail |
|---|---|
| **Purpose** | Authentication, authorisation, and invitation of staff/caregivers |
| **Legal basis** | Art. 6(1)(b) — necessary for the performance of a contract (access to the system) |
| **Data subjects** | Users (staff, caregivers, administrators) |
| **Personal data** | First name, last name, email address, hashed password, passkey credentials, role, login timestamps |
| **Recipients** | Internal only. Email delivery via configured SMTP provider (see processor list below). |
| **International transfers** | None, unless SMTP provider is outside EU/EEA |
| **Retention** | Active until User Erasure is triggered. Anonymised shell retained for audit log referential integrity. |
| **Security measures** | Passwords bcrypt-hashed. Passkeys stored as public-key credentials only. Short-lived JWT sessions (15 min). |

---

## 2. Patient record management

| Field | Detail |
|---|---|
| **Purpose** | Storage and management of health records for care, treatment, or personal health tracking |
| **Legal basis** | Art. 9(2)(h) — necessary for health care purposes under professional responsibility; or Art. 9(2)(a) — explicit consent (homelab/personal deployments) |
| **Data subjects** | Patients |
| **Personal data** | Name, date of birth, gender, and all clinical data: Diagnoses, Medications, Measurements, Lab Results, Incidents, Events, Health Logs, Recommendations |
| **Recipients** | Users with Caregiver or Coordinator access granted by the owning User |
| **International transfers** | None |
| **Retention** | Until Patient Erasure is triggered. Irreversible hard-delete with tombstone audit entry. |
| **Security measures** | Role-based and patient-level access control. All data in PostgreSQL with infrastructure-level access controls. |

---

## 3. Document upload and AI Processing Pipeline

| Field | Detail |
|---|---|
| **Purpose** | Processing uploaded medical documents (PDFs, images) to extract structured clinical data |
| **Legal basis** | Same as patient record management (Art. 9(2)(h) or Art. 9(2)(a)) |
| **Data subjects** | Patients |
| **Personal data** | Document files, extracted text, clinical entities (Diagnoses, Medications, Measurements, Recommendations) |
| **Recipients** | Internal AI service (self-hosted Ollama or vLLM, by default). If the AI runs at a hosted provider (`AI_BACKEND=vllm` with `VLLM_URL` pointing at the provider), that provider receives the plaintext document content and a DPA is required. Where the hosted endpoint also serves vision OCR (`VLLM_VISION_URL`) or embeddings (`VLLM_EMBED_URL`), it receives the page images and the text chunks as well. Which provider is a per-installation configuration: IONOS Cloud GmbH (AI Model Hub, processed in Germany) on the instances the project operates. |
| **International transfers** | None when the AI runs on your own infrastructure. IONOS is domestic (Germany) and needs no Art. 44 mechanism. A provider outside the EU/EEA would, and is not in use. |
| **Retention** | Until Patient Erasure. Storage files hard-deleted; extracted text and entities hard-deleted. |
| **Security measures** | Documents encrypted at rest with AES-GCM envelope encryption (ADR 018). Transmitted to AI service over internal Docker network only. |

---

## 4. AI Health Assistant (RAG chat)

| Field | Detail |
|---|---|
| **Purpose** | Answering user questions about a patient's health records using AI |
| **Legal basis** | Same as patient record management |
| **Data subjects** | Patients (whose data is retrieved), Users (who ask questions) |
| **Personal data** | Patient document chunks (embeddings and text), conversation messages (question and AI answer) |
| **Recipients** | Internal AI service (same as Processing Pipeline above) |
| **International transfers** | Same as Processing Pipeline |
| **Retention** | Chat messages retained until Patient Erasure. Document embeddings deleted with patient. |
| **Security measures** | Embeddings stored in pgvector (PostgreSQL). Chat messages stored in DB. Patient-level access control on all retrieval. |

---

## 5. Caregiver access management

| Field | Detail |
|---|---|
| **Purpose** | Managing who has access to each Patient's data |
| **Legal basis** | Art. 6(1)(b) — necessary for providing the service |
| **Data subjects** | Users (caregivers), Patients |
| **Personal data** | User–Patient access grants, relationship type, legal representation attributes, invite tokens |
| **Recipients** | Internal only. Invite emails via SMTP provider. |
| **International transfers** | None, unless SMTP provider is outside EU/EEA |
| **Retention** | Until Patient Erasure (grants deleted) or User Erasure (grants deleted). |
| **Security measures** | Access grants enforced on every API request via `auth/access.py`. |

---

## 6. Audit logging

| Field | Detail |
|---|---|
| **Purpose** | Accountability — recording who changed what and when (GDPR Art. 5(2)) |
| **Legal basis** | Art. 6(1)(c) — legal obligation (GDPR accountability principle) |
| **Data subjects** | Users (actor), Patients (subject of the action) |
| **Personal data** | User ID, user name, entity type, entity ID, action, before/after field values (excluding passwords) |
| **Recipients** | Admins via admin log viewer |
| **International transfers** | None |
| **Retention** | 30 days for application logs. Audit log DB entries: purged on Patient Erasure (for that patient's entries); user_name scrubbed on User Erasure. Tombstone entries retained indefinitely. |
| **Security measures** | Admin-only access. Sensitive fields (hashed_password, failed_login_attempts) excluded from diffs. |

---

## 7. Email delivery

| Field | Detail |
|---|---|
| **Purpose** | Sending invitation emails to new Users |
| **Legal basis** | Art. 6(1)(b) — necessary for providing the service |
| **Data subjects** | Users (invited) |
| **Personal data** | Email address, invite link |
| **Recipients** | Configured SMTP provider |
| **International transfers** | Depends on SMTP provider. Operator must verify. |
| **Retention** | Invite tokens expire on acceptance. Email not stored by OpenAvisio. |
| **Security measures** | Invite tokens are single-use and time-limited. |

---

## 8. Data sharing for studies / external purposes

| Field | Detail |
|---|---|
| **Purpose** | Collecting specific Patient files (e.g. EEG recordings) for a defined Sharing Purpose such as a research study or registry submission |
| **Legal basis** | Art. 9(2)(a) — explicit consent of the Patient or their representative, given per file and per Sharing Purpose |
| **Data subjects** | Patients |
| **Personal data** | Selected Document files and their contents; consent records (who consented, when, whether under a legal-representation relationship) |
| **Recipients** | The Coordinator/admin tier (Purpose Managers) collect the shared files and forward them externally to the study. The external study/registry is a recipient **outside** OpenAvisio — the operator must document it and put any required data-sharing agreement in place. |
| **International transfers** | Depends on the external study's location. Operator must assess per Sharing Purpose. |
| **Retention** | Each Share lasts until a caregiver revokes it, the Document is deleted, or Patient Erasure (which hard-deletes all Shares and decline markers). Files already downloaded and forwarded externally are outside OpenAvisio's control. |
| **Security measures** | Creation restricted to Coordinator/admin. Access is file-scoped — a Purpose Manager sees only files explicitly shared to a purpose, never the full record. Consent terms freeze once the first file is shared. Optional anonymous mode shows a stable pseudonym instead of the name (metadata only — file contents are unchanged). Every consent, decline, revoke, and purpose close is audit-logged. |

---

## 9. External document share links

| Field | Detail |
|---|---|
| **Purpose** | Letting a caregiver give an external specialist (e.g. a new doctor or therapist, without an account) read-only access to a chosen set of a Patient's Documents via a time-limited link (see ADR-021) |
| **Legal basis** | Art. 9(2)(a) — explicit consent of the Patient or their representative; the caregiver who creates the link selects the Documents and the recipient channel |
| **Data subjects** | Patients (shared Documents); the external recipient (their IP address and user-agent, captured for access accountability) |
| **Personal data** | The shared Document files and their contents, the Patient's name and date of birth (shown to the recipient); per-access audit records (link, document, timestamp, recipient IP + user-agent) |
| **Recipients** | The external specialist who holds the link URL. They are a recipient **outside** OpenAvisio; the operator should ensure caregivers understand that anyone holding the link can view the Documents until it expires. |
| **International transfers** | Depends on the recipient's location; not controlled by OpenAvisio. Operators should advise short expiry and private delivery. |
| **Retention** | A link lasts until its expiry (7/30/90 days, max 90) or caregiver revocation. Patient Erasure hard-deletes links, their items, and their access logs. Files the recipient already downloaded are outside OpenAvisio's control. |
| **Security measures** | Read-only, snapshot-scoped. Creation restricted to the Patient's own caregivers (owner / legal representative / non-staff with access); staff-only admins/managers refused. 256-bit token, only its hash stored, shown once. Mandatory expiry + revocation. Every external access audit-logged (IP + user-agent). Public pages set `no-referrer`, `noindex`, `no-store`. Copy-link delivery only (no app-sent email in v1). |

---

## Data processors

| Processor | Purpose | Location | DPA |
|---|---|---|---|
| Hosting infrastructure (Proxmox/server provider) | Runs the Docker stack and storage | [FILL IN] | [FILL IN] |
| SMTP provider | Sends invitation emails | [FILL IN] | [FILL IN] |
| IONOS Cloud GmbH | LLM inference, vision OCR and embeddings (if `VLLM_URL` points at their AI Model Hub) | Germany (`de-txl`) | Part of the Cloud terms, no separate signature — **not** the IONOS SE DPA, which is a different party |
| *(any other hosted AI endpoint)* | LLM inference | [FILL IN] | Required — a `VLLM_URL` at a provider is a third party |
