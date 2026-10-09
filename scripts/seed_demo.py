#!/usr/bin/env python3
"""Seed the demo instance with Lena Hoffmann, 7 synthetic documents and her expenses.

Run from the repo root after setting env vars:
  DOCUMENT_ENCRYPTION_KEY=<base64-32-bytes>  (required)
  DATABASE_URL=postgresql+asyncpg://...      (optional, defaults to dev URL)
  DOCUMENT_STORAGE_PATH=/path/to/storage    (optional, defaults to backend/data/documents)

Generate PDFs first if docs/demo/*.pdf are missing:
  python scripts/generate_demo_pdfs.py

Generate real embeddings before deploying the demo (optional but recommended):
  AI_SERVICE_URL=http://localhost:8001 python scripts/generate_demo_embeddings.py

Idempotent — safe to run multiple times. Skips all creation if Lena Hoffmann already exists.
"""

import asyncio
import hashlib
import json
import os
import secrets
import sys
import uuid
from datetime import date as DateType
from datetime import datetime, timezone
from pathlib import Path

# Allow importing from the backend package when run from the repo root.
sys.path.insert(0, str(Path(__file__).parent.parent / "backend"))

os.environ.setdefault(
    "DATABASE_URL",
    "postgresql+asyncpg://openavisio:devpassword123@localhost:5432/vaultdb",
)
os.environ.setdefault(
    "DOCUMENT_STORAGE_PATH",
    str(Path(__file__).parent.parent / "backend" / "data" / "documents"),
)

from sqlalchemy import select  # noqa: E402
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine  # noqa: E402

from app.core.security import hash_password  # noqa: E402
from app.core.encryption import encrypt_document  # noqa: E402
from app.core.patient_keys import ensure_patient_kek  # noqa: E402
from app.core.storage import get_storage  # noqa: E402
from app.services.lab_codes import canonical_code, parse_reference_range  # noqa: E402
from app.models import (  # noqa: E402
    CalendarEvent,
    CareNotes,
    Einstufung,
    EmergencyPlan,
    Condition,
    Correspondent,
    DocumentChunk,
    DocumentReference,
    Expense,
    Incident,
    MedicationStatement,
    Observation,
    Organization,
    Patient,
    PatientAccess,
    Recommendation,
    User,
    UserRole,
)

DOCS_DIR = Path(__file__).parent.parent / "docs" / "demo"
EMBEDDINGS_FILE = Path(__file__).parent / "demo_data" / "embeddings.json"

# ──────────────────────────────────────────────────────────────
# Demo data
# ──────────────────────────────────────────────────────────────

CORRESPONDENTS = [
    "Hausarztpraxis Dr. Schmidt",
    "St. Marien-Kinderklinik",
    "Zentrallabor Nordbaden",
    "Schulärztlicher Dienst Grundschule Am Fluss",
    "Sanitätshaus Berger GmbH",
    "Pflegekasse bei der AOK Baden-Württemberg",
]

# Chunk texts must stay in sync with generate_demo_embeddings.py.
CHUNK_TEXTS: dict[str, list[str]] = {
    "01_gp_referral": [
        (
            "Hausarzt Dr. Klaus Schmidt überweist Lena Hoffmann, geboren am 14. Mai 2019, an die "
            "Abteilung für Neuropädiatrie der St. Marien-Kinderklinik. Lena hatte zwei fragliche "
            "generalisierte tonisch-klonische Anfallsereignisse: das erste am 15. Januar 2024 mit einer "
            "Dauer von circa 2 Minuten, das zweite am 28. Februar 2024. "
            "Im Intervall ist sie altersentsprechend entwickelt."
        ),
        (
            "Keine aktuelle Medikation. Keine Epilepsie in der Familienanamnese. Kein kürzlicher "
            "fieberhafter Infekt. Diagnose: Verdacht auf kindliche Epilepsie. Dr. Schmidt bittet um EEG "
            "und klinisch-neurologische Untersuchung. Um zeitnahe Vergabe eines neuropädiatrischen "
            "Termins wird gebeten."
        ),
    ],
    "02_eeg_report": [
        (
            "EEG bei Lena Hoffmann (geb. 14. Mai 2019) in der Neuropädiatrie der St. Marien-Kinderklinik "
            "am 2. April 2024. Die Ableitung zeigt bilateral synchrone 3-Hz-Spike-Wave-Komplexe im "
            "Wachzustand und im Schlaf, vereinbar mit einer Absence-Epilepsie des Kindesalters (CAE). "
            "Die Grundaktivität ist im Übrigen altersentsprechend unauffällig."
        ),
        (
            "Beurteilung: Pathologisches EEG, vereinbar mit einer Absence-Epilepsie des Kindesalters. "
            "Klinische Empfehlung: Beginn einer antikonvulsiven Therapie mit Valproat als Mittel der "
            "ersten Wahl. Neurologische Verlaufskontrolle in 3 Monaten."
        ),
    ],
    "03_neurology_followup": [
        (
            "Neuropädiatrische Verlaufskontrolle bei Lena Hoffmann am 15. Juli 2024 in der "
            "St. Marien-Kinderklinik. Beginn der Valproat-Therapie mit 300 mg/Tag in zwei Einzeldosen "
            "am 15. April 2024. Seit Therapiebeginn berichtet die Mutter Anna Hoffmann über keine "
            "weiteren Anfallsereignisse. Gewicht: 22.0 kg, Größe: 119 cm."
        ),
        (
            "Lena verträgt Valproat 300 mg/Tag gut, keine Nebenwirkungen berichtet. Aktuelle Dosis "
            "fortführen. Blutentnahme in 6 Monaten empfohlen: Valproat-Serumspiegel, Leberwerte und "
            "Blutbild. Wiedervorstellung in der Ambulanz in 6–12 Monaten."
        ),
    ],
    "04_blood_panel": [
        (
            "Laborbefund für Lena Hoffmann (geb. 14. Mai 2019), Probenentnahme am 20. Januar 2025. "
            "Valproat-Spiegel (Serum): 75.0 mcg/mL (therapeutischer Bereich 50–100 mcg/mL). "
            "ALT (GPT): 18 U/L (normal). AST (GOT): 22 U/L (normal)."
        ),
        (
            "Blutbild: Leukozyten 6.8 × 10⁹/L (normal), Hämoglobin 12.4 g/dL (normal). Alle Werte im "
            "Normbereich. Der Valproat-Spiegel liegt im therapeutischen Bereich; aktuelle Dosis "
            "fortführen. Kontrolle des Laborpanels in 6 Monaten."
        ),
    ],
    "05_school_health_check": [
        (
            "Jährliche Gesundheitsuntersuchung bei Lena Hoffmann (geb. 14. Mai 2019) zur Einschulung in "
            "die 1. Klasse, durchgeführt am 8. September 2025 durch den Schulärztlichen Dienst der "
            "Grundschule Am Fluss. Gewicht: 24.5 kg, Größe: 123 cm, BMI 16.2 kg/m² (normal). "
            "Visus: 6/6 rechts und links. Hörscreening: beidseits bestanden."
        ),
        (
            "Lenas Mutter berichtet, dass Lena unter Valproat bei Absence-Epilepsie des Kindesalters "
            "gut eingestellt ist. Keine Anfälle in den letzten 12 Monaten. Entwicklung "
            "altersentsprechend: Sprache, Feinmotorik, Grobmotorik und soziale Entwicklung unauffällig. "
            "Meilenstein Einschulung dokumentiert (1. Klasse, September 2025). Keine Auffälligkeiten."
        ),
    ],
    "06_hospital_discharge": [
        (
            "Entlassungsbericht für Lena Hoffmann (geb. 14. Mai 2019), stationäre Aufnahme am "
            "12. Februar 2026 nach beobachtetem Durchbruchanfall — generalisiert tonisch-klonisch, "
            "Dauer 3 Minuten, spontan sistierend. Vorgeschichte: Absence-Epilepsie des Kindesalters "
            "unter Valproat 300 mg/Tag seit April 2024."
        ),
        (
            "Valproat-Dosis erhöht auf 400 mg/Tag in zwei Einzeldosen (200 mg morgens, 200 mg abends), "
            "gültig ab 14. Februar 2026. Entlassung am 14. Februar 2026 in gutem Allgemeinzustand. "
            "Ambulante neuropädiatrische Kontrolle vereinbart für den 14. März 2026. Bei erneuten "
            "Anfällen umgehende Kontaktaufnahme mit der Neuropädiatrie."
        ),
    ],
    "07_supplier_invoice": [
        (
            "Rechnung 2026-04-1187 des Sanitätshauses Berger GmbH vom 18. April 2026 an Anna Hoffmann "
            "für Lena Hoffmann. Bettschutzeinlagen, Einmalhandschuhe und Händedesinfektion als "
            "Pflegehilfsmittel zum Verbrauch. Gesamtbetrag 40,00 Euro, zahlbar bis 2. Mai 2026."
        ),
        (
            "Pflegehilfsmittel zum Verbrauch nach § 40 Abs. 2 SGB XI. Ein Antrag auf Kostenübernahme "
            "kann bei der Pflegekasse eingereicht werden."
        ),
    ],
    "08_pflegekasse_decision": [
        (
            "Bescheid der Pflegekasse bei der AOK Baden-Württemberg vom 12. Mai 2026, Aktenzeichen "
            "PK-2026-88431, für Lena Hoffmann, geb. 14.05.2019. Auf den Antrag vom 3. März 2026 auf "
            "Pflegegrad 3 wird ab 1. Juni 2026 Pflegegrad 2 bewilligt, Gesamtpunktzahl 42,5 gewichtete "
            "Punkte. Der beantragte Pflegegrad 3 wird abgelehnt."
        ),
        (
            "Begründung: Mit 42,5 gewichteten Punkten wird die für Pflegegrad 3 erforderliche "
            "Punktzahl von 47,5 nicht erreicht. Eine schwere Beeinträchtigung der Selbständigkeit "
            "im Sinne des § 15 Abs. 3 Nr. 3 SGB XI liegt nach dem Gutachten des Medizinischen "
            "Dienstes vom 28. April 2026 nicht vor."
        ),
        (
            "Rechtsbehelfsbelehrung: Gegen diesen Bescheid kann innerhalb eines Monats nach "
            "Bekanntgabe Widerspruch erhoben werden. Der Widerspruch ist schriftlich oder zur "
            "Niederschrift bei der Pflegekasse bei der AOK Baden-Württemberg einzulegen."
        ),
    ],
}

# Expenses (#218, ADR 040). Spread across a care year so the date filter and the
# CSV export have something to work with, and so every state the overview can show
# is visible without touching anything: fully reimbursed, partly reimbursed, still
# open, and one pipeline PROPOSAL awaiting confirmation.
EXPENSES: list[dict] = [
    {
        "incurred_on": "2025-08-04", "amount": "40.00", "category": "pflegehilfsmittel",
        "note": "Pflegehilfsmittel zum Verbrauch, Monatspauschale",
        "reimbursed_amount": "40.00", "correspondent": "Sanitätshaus Berger GmbH",
    },
    {
        "incurred_on": "2025-09-12", "amount": "10.00", "category": "medication_copay",
        "note": "Zuzahlung Valproat 300 mg", "reimbursed_amount": None,
    },
    {
        "incurred_on": "2025-10-07", "amount": "128.00", "category": "therapy",
        "note": "Ergotherapie, 4 Einheiten", "reimbursed_amount": "96.00",
    },
    {
        "incurred_on": "2025-11-19", "amount": "23.40", "category": "travel",
        "note": "Fahrt zur Neuropädiatrie, 78 km", "reimbursed_amount": None,
    },
    {
        "incurred_on": "2026-01-20", "amount": "10.00", "category": "medication_copay",
        "note": "Zuzahlung Valproat, Rezeptgebühr", "reimbursed_amount": "10.00",
    },
    {
        "incurred_on": "2026-02-14", "amount": "31.20", "category": "travel",
        "note": "Fahrten während des Klinikaufenthalts", "reimbursed_amount": None,
    },
    {
        "incurred_on": "2026-03-05", "amount": "249.00", "category": "aid",
        "note": "Sicherheitsbettgitter, Eigenanteil", "reimbursed_amount": "180.00",
        "correspondent": "Sanitätshaus Berger GmbH",
    },
    # The one the pipeline proposed from 07_supplier_invoice.pdf: unconfirmed, so it
    # stays out of every total until someone checks it against the paper.
    {
        "incurred_on": "2026-04-18", "amount": "40.00", "category": "pflegehilfsmittel",
        "note": "Pflegehilfsmittel zum Verbrauch, Rechnung 2026-04-1187",
        "reimbursed_amount": None, "correspondent": "Sanitätshaus Berger GmbH",
        "status": "proposed", "source": "pipeline", "document": "07_supplier_invoice",
    },
]

# Einstufungen (ADR 042). Two of them, because one is a number and two are a trend:
# the module scores show where the care need moved, which is the reason the history
# exists at all. The 2026 one is the Bescheid in the vault, the 2024 one predates it.
EINSTUFUNGEN: list[dict] = [
    {
        "pflegegrad": 1, "total_points": 22.5, "valid_from": "2024-06-01",
        "authority": "Pflegekasse bei der AOK Baden-Württemberg", "file_reference": "PK-2024-51197",
        "source": "manual",
        "modules": {"mobility": 2.5, "cognitive": 3.75, "behaviour": 1.875,
                    "self_care": 10.0, "therapy_demands": 2.5, "daily_life": 3.75},
    },
    {
        "pflegegrad": 2, "total_points": 42.5, "valid_from": "2026-06-01",
        "authority": "Pflegekasse bei der AOK Baden-Württemberg", "file_reference": "PK-2026-88431",
        "source": "pipeline", "document": "08_pflegekasse_decision",
        "modules": {"mobility": 5.0, "cognitive": 7.5, "behaviour": 3.75,
                    "self_care": 20.0, "therapy_demands": 5.0, "daily_life": 5.0},
    },
]

# Observation categories are "lab" and "measurement", the two values the app filters
# on (routers/observations.py, the Messungen and Laborwerte pages). The seed used to
# write FHIR-flavoured "laboratory"/"vital-signs", which no code path ever read, so
# both pages stood empty on the demo and in the website screenshots.
DOCUMENTS: list[dict] = [
    {
        "key": "01_gp_referral",
        "filename": "01_gp_referral.pdf",
        "type": "referral",
        "issued_date": "2024-03-10",
        "correspondent": "Hausarztpraxis Dr. Schmidt",
        "description": "Hausärztliche Überweisung an die Neuropädiatrie bei fraglichen Anfallsereignissen",
        "document_classification": "referral",
        "detected_provider": "Hausarztpraxis Dr. Schmidt",
        "ocr_confidence": 0.98,
        "extraction_confidence": 0.95,
        "conditions": [
            {
                "code_display": "Verdacht auf kindliche Epilepsie",
                "clinical_status": "active",
                "onset_date_time": "2024-01-15",
            }
        ],
        "medications": [],
        "observations": [],
        "events": [
            {
                "title": "Neuropädiatrischer Termin in der St. Marien-Kinderklinik",
                "start_at": "2024-04-01",
                "all_day": True,
                "source": "pipeline",
                "status": "completed",
            }
        ],
        "recommendations": [
            "Neurologische Abklärung vereinbaren; EEG empfohlen",
        ],
        "incidents": [
            {
                "incident_type": "seizure",
                "incident_type_display": "Generalisierter tonisch-klonischer Anfall",
                "severity": "moderate",
                "occurred_at": "2024-01-15",
                "duration_minutes": 2,
                "status": "resolved",
                "symptoms": "Nicht ansprechbar, generalisierte tonisch-klonische Bewegungen",
                "outcome": "Spontan sistierend; postiktal circa 10 Minuten",
                "reported_to_provider": True,
            },
            {
                "incident_type": "seizure",
                "incident_type_display": "Generalisierter tonisch-klonischer Anfall",
                "severity": "moderate",
                "occurred_at": "2024-02-28",
                "duration_minutes": 2,
                "status": "resolved",
                "symptoms": "Nicht ansprechbar, generalisierte tonisch-klonische Bewegungen",
                "outcome": "Spontan sistierend",
                "reported_to_provider": True,
            },
        ],
    },
    {
        "key": "02_eeg_report",
        "filename": "02_eeg_report.pdf",
        "type": "diagnostic-report",
        "issued_date": "2024-04-02",
        "correspondent": "St. Marien-Kinderklinik",
        "description": "EEG-Befund — pathologisch, vereinbar mit Absence-Epilepsie des Kindesalters",
        "document_classification": "diagnostic-report",
        "detected_provider": "St. Marien-Kinderklinik",
        "ocr_confidence": 0.99,
        "extraction_confidence": 0.96,
        "conditions": [
            {
                "code_display": "Absence-Epilepsie des Kindesalters (CAE)",
                "clinical_status": "active",
                "severity": "moderate",
                "onset_date_time": "2024-01-15",
            }
        ],
        "medications": [],
        "observations": [
            {
                "code_display": "Körpergröße",
                "category": "measurement",
                "effective_date_time": "2024-07-15",
                "value_quantity": 119.0,
                "value_unit": "cm",
            },
        ],
        "events": [],
        "recommendations": [
            "Valproat 300 mg/Tag fortführen — sehr gutes frühes Ansprechen",
            "Blutentnahme in 6 Monaten: Valproat-Spiegel, Leberwerte, Blutbild",
        ],
    },
    {
        "key": "04_blood_panel",
        "filename": "04_blood_panel.pdf",
        "type": "laboratory-report",
        "issued_date": "2025-01-20",
        "correspondent": "Zentrallabor Nordbaden",
        "description": "Laborbefund — Valproat-Spiegel therapeutisch, Leberwerte unauffällig",
        "document_classification": "laboratory-report",
        "detected_provider": "Zentrallabor Nordbaden",
        "ocr_confidence": 0.99,
        "extraction_confidence": 0.97,
        "conditions": [],
        "medications": [],
        "observations": [
            {
                "code_display": "Valproat-Spiegel (Serum)",
                "category": "lab",
                "effective_date_time": "2025-01-20",
                "value_quantity": 75.0,
                "value_unit": "mcg/mL",
                "reference_range": "50–100",
            },
            {
                "code_display": "ALT (GPT)",
                "category": "lab",
                "effective_date_time": "2025-01-20",
                "value_quantity": 18.0,
                "value_unit": "U/L",
                "reference_range": "< 35",
            },
            {
                "code_display": "AST (GOT)",
                "category": "lab",
                "effective_date_time": "2025-01-20",
                "value_quantity": 22.0,
                "value_unit": "U/L",
                "reference_range": "< 50",
            },
            {
                "code_display": "Leukozyten",
                "category": "lab",
                "effective_date_time": "2025-01-20",
                "value_quantity": 6.8,
                "value_unit": "10^9/L",
                "reference_range": "4.5–13.5",
            },
            {
                "code_display": "Hämoglobin",
                "category": "lab",
                "effective_date_time": "2025-01-20",
                "value_quantity": 12.4,
                "value_unit": "g/dL",
                "reference_range": "11.5–15.5",
            },
        ],
        "events": [],
        "recommendations": [
            "Valproat-Spiegel im therapeutischen Bereich (50–100 mcg/mL); aktuelle Dosis fortführen",
            "Laborkontrolle in 6 Monaten",
        ],
    },
    {
        "key": "05_school_health_check",
        "filename": "05_school_health_check.pdf",
        "type": "health-assessment",
        "issued_date": "2025-09-08",
        "correspondent": "Schulärztlicher Dienst Grundschule Am Fluss",
        "description": "Jährliche Schulgesundheitsuntersuchung — Einschulung 1. Klasse",
        "document_classification": "health-assessment",
        "detected_provider": "Schulärztlicher Dienst Grundschule Am Fluss",
        "ocr_confidence": 0.97,
        "extraction_confidence": 0.93,
        "conditions": [],
        "medications": [],
        "observations": [
            {
                "code_display": "Körpergewicht",
                "category": "measurement",
                "effective_date_time": "2025-09-08",
                "value_quantity": 24.5,
                "value_unit": "kg",
            },
            {
                "code_display": "Körpergröße",
                "category": "measurement",
                "effective_date_time": "2025-09-08",
                "value_quantity": 123.0,
                "value_unit": "cm",
            },
            {
                "code_display": "Visus (rechtes Auge)",
                "category": "measurement",
                "effective_date_time": "2025-09-08",
                "value_string": "6/6 (normal)",
            },
            {
                "code_display": "Visus (linkes Auge)",
                "category": "measurement",
                "effective_date_time": "2025-09-08",
                "value_string": "6/6 (normal)",
            },
            {
                "code_display": "Hörscreening (beidseits)",
                "category": "measurement",
                "effective_date_time": "2025-09-08",
                "value_string": "Bestanden",
            },
        ],
        "events": [
            {
                "title": "Einschulung 1. Klasse — Entwicklungs-Meilenstein",
                "start_at": "2025-09-01",
                "all_day": True,
                "source": "pipeline",
                "status": "completed",
                "purpose": "Meilenstein — Einschulung (6 Jahre)",
            }
        ],
        "recommendations": [
            "Keine Auffälligkeiten bei der Einschulung; routinemäßige Verlaufskontrollen fortführen",
        ],
    },
    {
        "key": "06_hospital_discharge",
        "filename": "06_hospital_discharge.pdf",
        "type": "discharge-summary",
        "issued_date": "2026-02-14",
        "correspondent": "St. Marien-Kinderklinik",
        "description": "Entlassungsbericht — Durchbruchanfall, Valproat-Dosis auf 400 mg/Tag erhöht",
        "document_classification": "discharge-summary",
        "detected_provider": "St. Marien-Kinderklinik",
        "ocr_confidence": 0.98,
        "extraction_confidence": 0.95,
        "conditions": [],
        "medications": [
            {
                "medication_display": "Valproat",
                "dosage_text": "400 mg/Tag in zwei Einzeldosen (200 mg morgens, 200 mg abends)",
                "dose_quantity": 400.0,
                "dose_unit": "mg",
                "route": "oral",
                "effective_start": "2026-02-14",
                "status": "active",
                "reason_code": "Absence-Epilepsie des Kindesalters — Durchbruchanfall",
            }
        ],
        "observations": [],
        "incidents": [
            {
                "incident_type": "seizure",
                "incident_type_display": "Generalisierter tonisch-klonischer Durchbruchanfall",
                "severity": "moderate",
                "occurred_at": "2026-02-12",
                "duration_minutes": 3,
                "status": "resolved",
                "symptoms": "Generalisiert tonisch-klonisch, spontan sistierend",
                "actions_taken": "Rettungsdienst alarmiert; stationäre Aufnahme in der St. Marien-Kinderklinik",
                "outcome": "Stationär aufgenommen; Valproat-Dosis auf 400 mg/Tag erhöht; Entlassung am 14. Feb 2026",
                "reported_to_provider": True,
                "reported_to_provider_at": "2026-02-12",
            },
        ],
        "events": [
            {
                "title": "Ambulante neuropädiatrische Kontrolle — nach Durchbruchanfall",
                "start_at": "2026-03-14",
                "all_day": True,
                "source": "pipeline",
                "status": "scheduled",
                "purpose": "Neuropädiatrische Kontrolle nach Entlassung wegen Durchbruchanfall",
            }
        ],
        "recommendations": [
            "Valproat-Dosis auf 400 mg/Tag in zwei Einzeldosen erhöht",
            "Ambulante neuropädiatrische Kontrolle in 4 Wochen (14. März 2026)",
            "Bei erneuten Anfällen vor dem Kontrolltermin umgehende Kontaktaufnahme mit der Neuropädiatrie",
        ],
    },
    {
        # Not a clinical document: the source the proposed Expense points at, so the
        # confirm flow can be walked from the amount back to the paper it came from.
        "key": "07_supplier_invoice",
        "filename": "07_supplier_invoice.pdf",
        "type": "invoice",
        "issued_date": "2026-04-18",
        "correspondent": "Sanitätshaus Berger GmbH",
        "description": "Rechnung über Pflegehilfsmittel zum Verbrauch (April 2026)",
        "document_classification": "invoice",
        "detected_provider": "Sanitätshaus Berger GmbH",
        "ocr_confidence": 0.99,
        "extraction_confidence": 0.94,
        "conditions": [],
        "medications": [],
        "observations": [],
        "events": [],
        "recommendations": [],
    },
    {
        # The Kassenbescheid the Widerspruch deadline is read from (ADR 041). A partial
        # rejection on purpose — Pflegegrad 2 where 3 was applied for prints as an
        # approval, which is why the trigger is the Rechtsbehelfsbelehrung and not a
        # judgement about the outcome. The deadline below is what the backend computes
        # from the decision date: 12 May + 3 days service + 1 month = Monday 15 June.
        "key": "08_pflegekasse_decision",
        "filename": "08_pflegekasse_decision.pdf",
        "type": "insurance_decision",
        "issued_date": "2026-05-12",
        "correspondent": "Pflegekasse bei der AOK Baden-Württemberg",
        "description": "Bescheid über die Einstufung in einen Pflegegrad — Pflegegrad 2 statt beantragtem 3",
        "document_classification": "insurance_decision",
        "detected_provider": "Pflegekasse bei der AOK Baden-Württemberg",
        "ocr_confidence": 0.98,
        "extraction_confidence": 0.92,
        "conditions": [],
        "medications": [],
        "observations": [],
        "events": [
            {
                "title": "Widerspruchsfrist: Pflegegrad 2 statt 3",
                "start_at": "2026-06-15",
                "all_day": True,
                "category": "deadline",
                "provider": "Pflegekasse bei der AOK Baden-Württemberg",
                "description": (
                    "Aktenzeichen: PK-2026-88431\n"
                    "Begründung der Kasse: Mit 42,5 gewichteten Punkten wird die für Pflegegrad 3 "
                    "erforderliche Punktzahl von 47,5 nicht erreicht. Eine schwere Beeinträchtigung "
                    "der Selbständigkeit im Sinne des § 15 Abs. 3 Nr. 3 SGB XI liegt nach dem "
                    "Gutachten nicht vor.\n"
                    "Berechnet aus dem Bescheid vom 2026-05-12 (+3 Tage Bekanntgabe, +1 Monat). "
                    "Ohne Gewähr — das tatsächliche Fristende kann abweichen. Im Zweifel früher "
                    "widersprechen oder beraten lassen."
                ),
            },
        ],
        "recommendations": [
            "Widerspruch gegen die Einstufung bis zum 15. Juni 2026 einlegen",
            "Pflegetagebuch über zwei Wochen führen und dem Widerspruch beilegen",
        ],
    },
]


# ──────────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────────

def _load_embeddings() -> tuple[dict[str, list[list[float]]], bool]:
    """Return (embeddings_dict, is_placeholder).

    embeddings_dict maps doc_key → list of embedding vectors.
    Returns empty dict and is_placeholder=True if the file is missing or is a placeholder.
    """
    if not EMBEDDINGS_FILE.exists():
        return {}, True
    data = json.loads(EMBEDDINGS_FILE.read_text())
    if data.get("placeholder", True):
        return {}, True
    return data.get("embeddings", {}), False


async def _get_or_create_org(db: AsyncSession) -> Organization:
    result = await db.execute(select(Organization))
    org = result.scalars().first()
    if not org:
        org = Organization(name="OpenAvisio")
        db.add(org)
        await db.flush()
    return org


async def _get_or_create_user(
    db: AsyncSession,
    email: str,
    password: str,
    first_name: str,
    last_name: str,
    role: UserRole,
) -> User:
    result = await db.execute(select(User).where(User.email == email))
    user = result.scalar_one_or_none()
    if not user:
        user = User(
            email=email,
            hashed_password=hash_password(password),
            first_name=first_name,
            last_name=last_name,
            role=role,
            is_active=True,
            email_confirmed=True,
        )
        db.add(user)
        await db.flush()
    return user


async def _get_or_create_correspondent(
    db: AsyncSession, name: str, org_id: uuid.UUID
) -> Correspondent:
    result = await db.execute(
        select(Correspondent).where(
            Correspondent.name == name,
            Correspondent.organization_id == org_id,
        )
    )
    corr = result.scalar_one_or_none()
    if not corr:
        corr = Correspondent(name=name, organization_id=org_id)
        db.add(corr)
        await db.flush()
    return corr


def _encrypt_and_store(pdf_path: Path, patient_id: uuid.UUID, doc_id: uuid.UUID, kek: bytes) -> tuple[bytes, bytes, str, int, str]:
    """Encrypt PDF and write to storage. Returns (ciphertext, wrapped_dek, storage_key, size)."""
    data = pdf_path.read_bytes()
    size = len(data)
    file_hash = hashlib.sha256(data).hexdigest()
    ciphertext, wrapped_dek = encrypt_document(data, kek)
    storage_key = f"{patient_id}/{doc_id}.enc"
    get_storage().write(storage_key, ciphertext)
    return ciphertext, wrapped_dek, storage_key, size, file_hash


# ──────────────────────────────────────────────────────────────
# Main
# ──────────────────────────────────────────────────────────────

async def main() -> None:
    database_url = os.environ["DATABASE_URL"]
    engine = create_async_engine(database_url)
    Session = async_sessionmaker(engine, expire_on_commit=False)

    embeddings, is_placeholder = _load_embeddings()
    if is_placeholder:
        print(
            "WARNING: scripts/demo_data/embeddings.json is a placeholder.\n"
            "  The AI Health Assistant will not work semantically on the demo instance.\n"
            "  Run: AI_SERVICE_URL=http://... python scripts/generate_demo_embeddings.py\n"
        )

    # Verify PDFs exist before starting DB work
    missing = [d["filename"] for d in DOCUMENTS if not (DOCS_DIR / d["filename"]).exists()]
    if missing:
        print("ERROR: Missing demo PDFs. Run: python scripts/generate_demo_pdfs.py", file=sys.stderr)
        for f in missing:
            print(f"  {DOCS_DIR / f}", file=sys.stderr)
        sys.exit(1)

    async with Session() as db:
        # Idempotency guard
        existing = await db.execute(
            select(Patient).where(
                Patient.given_name == "Lena",
                Patient.family_name == "Hoffmann",
            )
        )
        if existing.scalar_one_or_none():
            print("Lena Hoffmann already exists — nothing to do.")
            return

        print("Seeding demo data …")

        org = await _get_or_create_org(db)
        print(f"  Organization: {org.name}")

        admin = await _get_or_create_user(
            db,
            email="admin@demo.openavisio.org",
            # never shown to visitors: the operator's own, or a random one nobody knows
            password=os.environ.get("DEMO_ADMIN_PASSWORD") or secrets.token_urlsafe(24),
            first_name="Admin",
            last_name="User",
            role=UserRole.admin,
        )
        caregiver_user = await _get_or_create_user(
            db,
            email="caregiver@demo.openavisio.org",
            password="Demo123!Care",
            first_name="Anna",
            last_name="Hoffmann",
            role=UserRole.user,
        )
        print(f"  Users: {admin.email}, {caregiver_user.email}")

        # Patient
        patient = Patient(
            created_by=admin.id,
            given_name="Lena",
            family_name="Hoffmann",
            birth_date="2019-05-14",
            gender="female",
            active=True,
        )
        db.add(patient)
        await db.flush()
        # per-patient KEK (ADR 031) — documents are encrypted to it
        kek = await ensure_patient_kek(db, patient.id)

        # A face makes the record read as a person's, not a dataset's.
        #
        # demo_data/lena.png is AI-GENERATED (Gemini "nano banana", carries
        # Google's SynthID watermark) and shows no real person. That is
        # deliberate: a photograph of a real child would be personal data, and
        # attaching it to a fictional epilepsy record would put it in a health
        # context no stock licence covers. Stored unmodified, so the watermark
        # and provenance survive.
        #
        # Encrypted exactly like an upload (backend/app/routers/patients.py).
        photo_path = Path(__file__).parent / "demo_data" / "lena.png"
        if photo_path.exists():
            photo_ct, photo_dek = encrypt_document(photo_path.read_bytes(), kek)
            photo_key = f"{patient.id}/photo.enc"
            get_storage().write(photo_key, photo_ct)
            patient.photo_storage_path = photo_key
            patient.photo_dek = photo_dek
            patient.photo_content_type = "image/png"
        else:
            print(f"  ! no avatar at {photo_path} — patient stays without a photo")

        print(f"  Patient: Lena Hoffmann ({patient.id})")

        # The admin ROLE confers no clinical access (ADR 025) — the demo admin
        # needs an explicit grant like anyone else
        db.add(
            PatientAccess(
                patient_id=patient.id,
                user_id=admin.id,
                access_level="admin",
                granted_by_user_id=admin.id,
                granted_at=datetime.now(timezone.utc),
            )
        )

        # Caregiver access
        db.add(
            PatientAccess(
                patient_id=patient.id,
                user_id=caregiver_user.id,
                # the visitors' login: everything a family does, nothing that deletes the patient
                access_level="contribute",
                granted_by_user_id=admin.id,
                granted_at=datetime.now(timezone.utc),
                relationship="mother",
                purpose="Primäre Bezugsperson — Lenas Mutter",
            )
        )

        # Correspondents
        corr_map: dict[str, Correspondent] = {}
        for name in CORRESPONDENTS:
            corr_map[name] = await _get_or_create_correspondent(db, name, org.id)
        print(f"  Correspondents: {len(corr_map)}")

        # Documents
        doc_ids: dict[str, uuid.UUID] = {}
        for doc_def in DOCUMENTS:
            key = doc_def["key"]
            pdf_path = DOCS_DIR / doc_def["filename"]
            doc_id = uuid.uuid4()
            doc_ids[key] = doc_id

            _, wrapped_dek, storage_key, size, file_hash = _encrypt_and_store(
                pdf_path, patient.id, doc_id, kek
            )

            correspondent = corr_map[doc_def["correspondent"]]
            extracted_text = " ".join(CHUNK_TEXTS[key])

            doc = DocumentReference(
                id=doc_id,
                patient_id=patient.id,
                owner_id=admin.id,
                status="current",
                type=doc_def["type"],
                description=doc_def["description"],
                issued_date=DateType.fromisoformat(doc_def["issued_date"]),
                file_name=doc_def["filename"],
                content_type="application/pdf",
                size=size,
                storage_path=storage_key,
                hash=file_hash,
                encrypted_dek=wrapped_dek,
                processing_status="completed",
                verification_status="verified",
                document_classification=doc_def["document_classification"],
                detected_provider=doc_def["detected_provider"],
                ocr_confidence=doc_def["ocr_confidence"],
                extraction_confidence=doc_def["extraction_confidence"],
                extracted_text=extracted_text,
                correspondent_id=correspondent.id,
                extraction_json={
                    "summary": doc_def["description"],
                    "observations": [],
                    "diagnoses": [],
                    "medications": [],
                    "appointments": [],
                    "recommendations": doc_def["recommendations"],
                },
            )
            db.add(doc)
            await db.flush()

            # Clinical data
            for c in doc_def["conditions"]:
                db.add(Condition(
                    patient_id=patient.id,
                    owner_id=admin.id,
                    document_reference_id=doc_id,
                    code_display=c["code_display"],
                    clinical_status=c.get("clinical_status", "active"),
                    severity=c.get("severity"),
                    onset_date_time=c.get("onset_date_time"),
                    recorded_date=doc_def["issued_date"],
                ))

            for m in doc_def["medications"]:
                db.add(MedicationStatement(
                    patient_id=patient.id,
                    owner_id=admin.id,
                    document_reference_id=doc_id,
                    medication_display=m["medication_display"],
                    status=m.get("status", "active"),
                    dosage_text=m.get("dosage_text"),
                    dose_quantity=m.get("dose_quantity"),
                    dose_unit=m.get("dose_unit"),
                    route=m.get("route"),
                    effective_start=m.get("effective_start"),
                    reason_code=m.get("reason_code"),
                    date_asserted=doc_def["issued_date"],
                ))

            for o in doc_def["observations"]:
                db.add(Observation(
                    patient_id=patient.id,
                    owner_id=admin.id,
                    document_reference_id=doc_id,
                    code_display=o["code_display"],
                    # same canonical vocabulary the verify path applies (ADR 029), so a
                    # seeded weight and a hand-entered one land in one series
                    code=canonical_code(o["code_display"]),
                    category=o.get("category"),
                    effective_date_time=o.get("effective_date_time"),
                    value_quantity=o.get("value_quantity"),
                    value_unit=o.get("value_unit"),
                    value_string=o.get("value_string"),
                    reference_range=o.get("reference_range"),
                    # ref_low/ref_high are what the out-of-range flag reads; parsed
                    # from the printed range by the same helper the pipeline uses
                    **dict(zip(("ref_low", "ref_high"), parse_reference_range(o.get("reference_range")))),
                    status="final",
                ))

            for e in doc_def["events"]:
                db.add(CalendarEvent(
                    patient_id=patient.id,
                    owner_id=admin.id,
                    document_reference_id=doc_id,
                    title=e["title"],
                    start_at=e["start_at"],
                    all_day=e.get("all_day", True),
                    source=e.get("source", "pipeline"),
                    status=e.get("status", "scheduled"),
                    purpose=e.get("purpose"),
                    category=e.get("category", "appointment"),
                    description=e.get("description"),
                    provider=e.get("provider"),
                ))

            for rec_text in doc_def["recommendations"]:
                db.add(Recommendation(
                    patient_id=patient.id,
                    owner_id=admin.id,
                    document_reference_id=doc_id,
                    text=rec_text,
                    status="active",
                ))

            for inc in doc_def.get("incidents", []):
                db.add(Incident(
                    patient_id=patient.id,
                    owner_id=admin.id,
                    incident_type=inc["incident_type"],
                    incident_type_display=inc.get("incident_type_display"),
                    severity=inc.get("severity", "mild"),
                    status=inc.get("status", "resolved"),
                    occurred_at=inc["occurred_at"],
                    duration_minutes=inc.get("duration_minutes"),
                    symptoms=inc.get("symptoms"),
                    actions_taken=inc.get("actions_taken"),
                    outcome=inc.get("outcome"),
                    reported_to_provider=inc.get("reported_to_provider", False),
                    reported_to_provider_at=inc.get("reported_to_provider_at"),
                ))

            # Document chunks (embeddings)
            doc_vectors = embeddings.get(key, [])
            for i, chunk_text in enumerate(CHUNK_TEXTS[key]):
                vector = doc_vectors[i] if i < len(doc_vectors) else None
                db.add(DocumentChunk(
                    document_reference_id=doc_id,
                    patient_id=patient.id,
                    chunk_index=i,
                    content=chunk_text,
                    embedding=vector,
                ))

            print(f"  Document: {doc_def['filename']}")

        # Expenses (#218). Amounts are strings in the table above and become
        # Decimal here — never float, a wrong sum ends up in a tax return.
        from decimal import Decimal
        for exp in EXPENSES:
            reimbursed = exp.get("reimbursed_amount")
            db.add(Expense(
                patient_id=patient.id,
                owner_id=admin.id,
                amount=Decimal(exp["amount"]),
                incurred_on=exp["incurred_on"],
                category=exp["category"],
                note=exp.get("note"),
                reimbursed_amount=Decimal(reimbursed) if reimbursed else None,
                status=exp.get("status", "confirmed"),
                source=exp.get("source", "manual"),
                correspondent_id=corr_map[exp["correspondent"]].id if exp.get("correspondent") else None,
                document_reference_id=doc_ids.get(exp["document"]) if exp.get("document") else None,
            ))
        print(f"  Expenses: {len(EXPENSES)}")

        # #297: entered by hand, so no source Document. The allergy feeds the header pill
        # and the Handout (#193); the rescue medication is what the Emergency Plan points at.
        db.add(Condition(
            patient_id=patient.id,
            owner_id=admin.id,
            code_display="Penicillin-Allergie",
            category="allergy",
            note="Exanthem",
            recorded_date="2024-03-10",
        ))
        buccolam = MedicationStatement(
            patient_id=patient.id,
            owner_id=admin.id,
            medication_display="Buccolam (Midazolam)",
            status="active",
            dosage_text="5 mg in die Wangentasche, bei einem Anfall über 5 Minuten",
            dose_quantity=5,
            dose_unit="mg",
            route="bukkal",
            effective_start="2026-02-14",
            date_asserted="2026-02-14",
        )
        db.add(buccolam)
        await db.flush()
        db.add(EmergencyPlan(
            patient_id=patient.id,
            owner_id=admin.id,
            situations=[
                {"trigger": "Anfall länger als 5 Minuten", "steps": [
                    {"text": "Uhrzeit notieren, Lena auf die Seite legen, nichts in den Mund geben"},
                    {"text": "Buccolam in die Wangentasche geben", "medication_id": str(buccolam.id)},
                    {"text": "Endet der Anfall 5 Minuten nach der Gabe nicht: 112 rufen"},
                ]},
                {"trigger": "Mehr als 10 Absencen in einer Stunde", "steps": [
                    {"text": "Absencen mit Uhrzeit im Anfallstagebuch notieren"},
                    {"text": "Am nächsten Werktag die Neuropädiatrie anrufen"},
                ]},
            ],
            # 030 23125 xxx: the Bundesnetzagentur's range reserved for fiction
            contacts=[
                {"name": "Anna Hoffmann", "role": "Mutter", "phone": "030 23125 001"},
                {"name": "St. Marien-Kinderklinik, Neuropädiatrie", "role": "Behandelnde Klinik", "phone": "030 23125 100"},
            ],
            notes="Nach einem Anfall ist Lena ein bis zwei Stunden müde. Das ist normal, sie darf schlafen.",
            document_ids=[str(doc_ids["06_hospital_discharge"])],
        ))
        db.add(CareNotes(
            patient_id=patient.id,
            owner_id=admin.id,
            communication="Spricht in kurzen Sätzen. Braucht etwas länger für eine Antwort, bitte abwarten statt nachfragen.",
            eating_drinking="Isst selbstständig. Trinkt zu wenig, bitte zwischendurch Wasser anbieten.",
            sleep="Mittagsruhe um 13 Uhr. Schlafmangel macht Absencen wahrscheinlicher.",
            aids="Orthopädische Einlagen in beiden Schuhen.",
            what_helps="Ein fester Ablauf und Vorwarnung, bevor etwas Neues kommt. Ihr Kuscheltier, ein Hase.",
            what_overwhelms="Laute, volle Räume und flackerndes Licht.",
        ))
        print("  Emergency Plan, Care Notes, allergy, rescue medication")

        for ein in EINSTUFUNGEN:
            db.add(Einstufung(
                patient_id=patient.id,
                owner_id=admin.id,
                pflegegrad=ein["pflegegrad"],
                total_points=ein["total_points"],
                valid_from=ein["valid_from"],
                valid_until=ein.get("valid_until"),
                authority=ein.get("authority"),
                file_reference=ein.get("file_reference"),
                source=ein.get("source", "manual"),
                document_reference_id=doc_ids.get(ein["document"]) if ein.get("document") else None,
                **{f"module_{k}": v for k, v in ein.get("modules", {}).items()},
            ))
        print(f"  Einstufungen: {len(EINSTUFUNGEN)}")

        await db.commit()

    print("\nDone. Demo credentials:")
    print("  Caregiver: caregiver@demo.openavisio.org / Demo123!Care")
    print("  Admin:     admin@demo.openavisio.org / DEMO_ADMIN_PASSWORD"
          + ("" if os.environ.get("DEMO_ADMIN_PASSWORD") else " (unset: random, not shown)"))
    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
