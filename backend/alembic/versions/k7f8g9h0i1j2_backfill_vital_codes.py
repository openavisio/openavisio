"""give existing vital signs a canonical code so their series stop splitting

A measurement typed into the form was stored with a code (`body-weight`), one read
out of a document with none — only the German name the letter printed. The list
groups by code and falls back to the name, so the same weight lived in two groups
and each showed half the trend.

The mapping is spelled out here rather than imported from app.services.lab_codes:
a migration has to keep doing what it did the day it ran, whatever the vocabulary
grows into later.
"""

import sqlalchemy as sa
from alembic import op

revision = "k7f8g9h0i1j2"
down_revision = "j6e7f8g9h0i1"
branch_labels = None
depends_on = None

# canonical code -> printed names seen in the wild, lowercased
VITALS = {
    "body-weight": ["gewicht", "körpergewicht", "koerpergewicht", "weight", "body weight"],
    "body-height": ["größe", "grösse", "groesse", "körpergröße", "koerpergroesse",
                    "länge", "laenge", "height", "body height", "body length"],
    "head-circumference": ["kopfumfang", "ku", "head circumference", "ofc"],
    "body-temperature": ["temperatur", "körpertemperatur", "koerpertemperatur",
                         "temperature", "body temperature", "temp"],
    "heart-rate": ["herzfrequenz", "puls", "pulsfrequenz", "heart rate", "hf", "hr"],
    "oxygen-saturation": ["sauerstoffsättigung", "sauerstoffsaettigung", "spo2", "spo₂",
                          "o2-sättigung", "oxygen saturation", "sao2"],
    "blood-pressure-systolic": ["blutdruck systolisch", "systolisch", "systolischer blutdruck",
                                "rr systolisch", "blood pressure systolic", "systolic"],
    "blood-pressure-diastolic": ["blutdruck diastolisch", "diastolisch", "diastolischer blutdruck",
                                 "rr diastolisch", "blood pressure diastolic", "diastolic"],
    "bmi": ["bmi", "body-mass-index", "body mass index", "körpermassenindex"],
}


def upgrade() -> None:
    conn = op.get_bind()
    for code, names in VITALS.items():
        # Only rows that carry no code yet, and only measurements: a lab row's identity
        # is already settled by the analyte vocabulary and must not be touched.
        conn.execute(
            sa.text(
                "UPDATE observations SET code = :code "
                "WHERE code IS NULL AND category = 'measurement' "
                "AND lower(btrim(code_display)) = ANY(:names)"
            ),
            {"code": code, "names": names},
        )


def downgrade() -> None:
    # Clearing the codes again would also clear ones entered through the form, which
    # were never null. Nothing to undo: an added code is additive information.
    pass
