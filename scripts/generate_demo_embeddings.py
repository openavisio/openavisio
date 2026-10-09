#!/usr/bin/env python3
"""Generate real embedding vectors for the demo seed and write to scripts/demo_data/embeddings.json.

Requires the AI service to be running. Run from the repo root:
  AI_SERVICE_URL=http://localhost:8001 python scripts/generate_demo_embeddings.py

The output file (scripts/demo_data/embeddings.json) should be committed so that
seed_demo.py can run without an AI service at deploy time. See ADR 019.
"""

import json
import os
import sys
import urllib.request
import urllib.error
from pathlib import Path

AI_SERVICE_URL = os.environ.get("AI_SERVICE_URL", "http://localhost:8001")
OUTPUT_FILE = Path(__file__).parent / "demo_data" / "embeddings.json"

# The chunk texts must stay in sync with seed_demo.py.
CHUNKS: dict[str, list[str]] = {
    "01_gp_referral": [
        (
            "GP Dr. Klaus Schmidt refers Lena Hoffmann, date of birth 14 May 2019, to St. Mary's Hospital "
            "Neurology Department. Lena has experienced two suspected generalised tonic-clonic seizure "
            "episodes: first on 15 January 2024 lasting approximately 2 minutes, second on 28 February 2024. "
            "She is developmentally normal between episodes."
        ),
        (
            "No current medications. No family history of epilepsy. No recent febrile illness. "
            "Diagnosis: suspected childhood epilepsy. Dr. Schmidt requests EEG and clinical neurological "
            "assessment. Please schedule a neurology appointment at earliest convenience."
        ),
    ],
    "02_eeg_report": [
        (
            "EEG performed on Lena Hoffmann (DOB 14 May 2019) at St. Mary's Hospital Neurology on 2 April "
            "2024. The recording shows bilateral synchronous 3 Hz spike-and-wave discharges during "
            "wakefulness and sleep, consistent with childhood absence epilepsy (CAE). Background activity "
            "is otherwise normal for age."
        ),
        (
            "Impression: Abnormal EEG consistent with childhood absence epilepsy. Clinical "
            "recommendation: initiate sodium valproate as first-line antiepileptic therapy. "
            "Follow-up neurological assessment in 3 months."
        ),
    ],
    "03_neurology_followup": [
        (
            "Neurology follow-up for Lena Hoffmann on 15 July 2024 at St. Mary's Hospital. Lena was "
            "started on sodium valproate 300 mg/day in two divided doses on 15 April 2024. Since "
            "initiation, no further seizure episodes reported by her mother Anna Hoffmann. "
            "Weight: 22.0 kg, Height: 119 cm."
        ),
        (
            "Lena is tolerating sodium valproate 300 mg/day well with no reported side effects. "
            "Continue current dose. Blood test recommended in 6 months: sodium valproate serum level, "
            "liver function tests, and full blood count. Return to clinic in 6–12 months."
        ),
    ],
    "04_blood_panel": [
        (
            "Laboratory report for Lena Hoffmann (DOB 14 May 2019), sample collected 20 January 2025. "
            "Sodium valproate serum level: 75.0 mcg/mL (therapeutic range 50–100 mcg/mL). "
            "ALT: 18 U/L (normal). AST: 22 U/L (normal)."
        ),
        (
            "Full blood count: WBC 6.8 × 10⁹/L (normal), haemoglobin 12.4 g/dL (normal). All results "
            "within normal limits. Sodium valproate level is within the therapeutic range; continue "
            "current dose. Repeat blood panel in 6 months."
        ),
    ],
    "05_school_health_check": [
        (
            "Annual health assessment for Lena Hoffmann (DOB 14 May 2019) at school Year 1 entry, "
            "conducted 8 September 2025 by Riverside Primary School Health Service. "
            "Weight: 24.5 kg, Height: 123 cm, BMI 16.2 kg/m² (normal). "
            "Visual acuity: 6/6 right and left. Hearing: pass bilateral."
        ),
        (
            "Lena's mother reports she is well-controlled on sodium valproate for childhood absence "
            "epilepsy. No seizures in the past 12 months. Development appropriate for age: speech, fine "
            "motor, gross motor, and social development all on track. School entry milestone recorded "
            "(Year 1, September 2025). No concerns identified."
        ),
    ],
    "06_hospital_discharge": [
        (
            "Discharge summary for Lena Hoffmann (DOB 14 May 2019), admitted 12 February 2026 following "
            "a witnessed breakthrough seizure — generalised tonic-clonic, duration 3 minutes, "
            "self-terminating. Background: childhood absence epilepsy on sodium valproate 300 mg/day "
            "since April 2024."
        ),
        (
            "Sodium valproate dose increased to 400 mg/day in two divided doses (200 mg morning, "
            "200 mg evening) effective 14 February 2026. Discharged 14 February 2026 in good condition. "
            "Outpatient neurology review booked for 14 March 2026. Contact neurology immediately if "
            "further seizures occur."
        ),
    ],
    "07_supplier_invoice": [
        (
            "Invoice 2026-04-1187 from Sanitaetshaus Berger GmbH dated 18 April 2026, issued to Anna "
            "Hoffmann for Lena Hoffmann. Washable bed pads, disposable gloves and hand sanitiser as "
            "consumable care aids. Total amount 40.00 euro, payable by 2 May 2026."
        ),
        (
            "Consumable care aids under section 40(2) SGB XI. A reimbursement claim may be submitted "
            "to the long-term care insurance fund."
        ),
    ],
}


def embed(texts: list[str]) -> list[list[float]]:
    payload = json.dumps({"texts": texts}).encode()
    req = urllib.request.Request(
        f"{AI_SERVICE_URL}/embed",
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            data = json.loads(resp.read())
            return data["embeddings"]
    except urllib.error.URLError as e:
        print(f"ERROR: Could not reach AI service at {AI_SERVICE_URL}: {e}", file=sys.stderr)
        print("Set AI_SERVICE_URL to a running instance.", file=sys.stderr)
        sys.exit(1)


def main() -> None:
    print(f"Generating embeddings via {AI_SERVICE_URL} …")

    all_texts = [text for chunks in CHUNKS.values() for text in chunks]
    print(f"  Embedding {len(all_texts)} chunks …")
    all_vectors = embed(all_texts)

    embeddings: dict[str, list[list[float]]] = {}
    idx = 0
    for doc_key, chunks in CHUNKS.items():
        embeddings[doc_key] = all_vectors[idx : idx + len(chunks)]
        idx += len(chunks)

    dim = len(all_vectors[0]) if all_vectors else 0
    result = {
        "placeholder": False,
        "dimension": dim,
        "embeddings": embeddings,
    }

    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_FILE.write_text(json.dumps(result, indent=2))
    print(f"  Written to {OUTPUT_FILE}")
    print(f"  Dimension: {dim}, docs: {len(embeddings)}, total chunks: {len(all_texts)}")
    print("Commit scripts/demo_data/embeddings.json and re-run seed_demo.py.")


if __name__ == "__main__":
    main()
