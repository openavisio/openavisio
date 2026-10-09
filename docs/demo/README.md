# Demo data

## Patient: Lena Hoffmann

Female, DOB 14 May 2019 (age 7). Childhood absence epilepsy (CAE) on sodium valproate.

| # | File | Date | Correspondent | What it exercises |
|---|------|------|---------------|-------------------|
| 1 | `01_gp_referral.pdf` | 2024-03-10 | Dr. Schmidt Family Practice | Diagnosis (suspected epilepsy), 2 Incidents (seizures), proposed Event |
| 2 | `02_eeg_report.pdf` | 2024-04-02 | St. Mary's Hospital | Lab Result (EEG), confirmed Diagnosis, Recommendations |
| 3 | `03_neurology_followup.pdf` | 2024-07-15 | St. Mary's Hospital | Medication (valproate 300 mg), Measurements (weight/height) |
| 4 | `04_blood_panel.pdf` | 2025-01-20 | Central Medical Laboratory | Lab Results (valproate level, LFTs, FBC) |
| 5 | `05_school_health_check.pdf` | 2025-09-08 | Riverside Primary School Health Service | Measurements, milestone Event (school entry) |
| 6 | `06_hospital_discharge.pdf` | 2026-02-14 | St. Mary's Hospital | Medication change (400 mg), Incident (breakthrough seizure), future Event |
| 7 | `07_supplier_invoice.pdf` | 2026-04-18 | Sanitätshaus Berger GmbH | Invoice: the source of the proposed Expense (#218) |

## Expenses

Eight Expenses across a care year, so the overview shows every state it can without
anyone touching it: fully reimbursed, partly reimbursed, still open, and one
**proposed** entry the pipeline read off `07_supplier_invoice.pdf` that is waiting to
be confirmed. Categories cover care aids, medication co-payments, therapy, travel and
one assistive device.

Confirmed total 491.60 €, of which 326.00 € reimbursed, leaving 165.60 € open — the
part that may be tax-deductible. The proposal (40.00 €) counts toward none of those
until someone confirms it, which is the behaviour ADR 040 exists for.

## User accounts (demo instance)

| Email | Password | Role |
|-------|----------|------|
| `caregiver@demo.openavisio.org` | `Demo123!Care` | Caregiver (Anna Hoffmann, Lena's mother) |
| `admin@demo.openavisio.org` | `DEMO_ADMIN_PASSWORD` from `.env`, random if unset | Admin, the operator's only |

## Workflows

### Local development — upload manually

The PDFs in `docs/demo/` are committed to the repo. Upload them through the normal UI to
exercise the full Processing Pipeline locally:

1. Log in as the dev admin (`admin@openavisio.dev` / `Admin123!Admin` after running `/api/dev/seed`)
2. Create a Patient, then upload each PDF from `docs/demo/`
3. The pipeline runs, extracts clinical data, and generates embeddings

### Demo instance — seed script

Run once after deploy (from the repo root):

```
cd backend
pip install -e .
cd ..

# Required env vars
export DATABASE_URL="postgresql+asyncpg://user:pass@host/db"
export DOCUMENT_ENCRYPTION_KEY="<base64-32-bytes>"
export DOCUMENT_STORAGE_PATH="/path/to/document/storage"

python scripts/seed_demo.py
```

The script is idempotent — re-running it when Lena Hoffmann already exists is a no-op.

### Regenerating PDFs

If the document content changes, regenerate the PDFs and commit them:

```
cd backend && pip install -e . && cd ..
python scripts/generate_demo_pdfs.py
```

### Regenerating embeddings

If the embedding model or document text changes, regenerate and commit the embeddings file:

```
AI_SERVICE_URL=http://localhost:8001 python scripts/generate_demo_embeddings.py
```

Then commit `scripts/demo_data/embeddings.json` and re-run `seed_demo.py`.

---

## What must be updated when things change

| Change | Files to update |
|--------|----------------|
| Embedding model changes (new model or dimension ≠ 768) | Regenerate `scripts/demo_data/embeddings.json`; update dimension note in ADR 019 |
| Demo document text changes | `scripts/generate_demo_pdfs.py`, chunk texts in `scripts/seed_demo.py`, then regenerate PDF and embeddings |
| `DocumentChunk` schema changes | `scripts/seed_demo.py` |
| `DocumentReference` field added/renamed | `scripts/seed_demo.py` |
| Pipeline extraction format changes (new entity type, renamed field) | `scripts/seed_demo.py` — the hardcoded clinical data records mirror what the pipeline would have produced |
| Clinical data models change (`Condition`, `MedicationStatement`, `Observation`, `Incident`, `CalendarEvent`, `Recommendation`) | `scripts/seed_demo.py` |
| New Correspondent needed | `scripts/seed_demo.py` (add to `CORRESPONDENTS` constant) |

## Embeddings note

The pre-generated embeddings in `scripts/demo_data/embeddings.json` still pair with
the original English chunk texts. With the demo's mock AI backend that is invisible;
if semantic search on a demo instance ever matters, re-run
`generate_demo_embeddings.py` against a real backend after the German rewrite.
