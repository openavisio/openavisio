"""An Incident records what happened, nothing around it (ADR 062, #434)"""

import sqlalchemy as sa
from alembic import op

revision = "a3v4w5x6y7z8"
down_revision = "z2u3v4w5x6y7"
branch_labels = None
depends_on = None

TEXT = ["location", "suspected_trigger", "symptoms", "outcome"]
DROPPED = [("severity", sa.String(50)), ("status", sa.String(50)), ("resolved_at", sa.String(50)),
           ("location", sa.String(512)), ("geo_location", sa.String(256)), ("weather_condition", sa.String(100)),
           ("temperature", sa.Float()), ("humidity", sa.Float()), ("pollen_level", sa.String(50)),
           ("air_quality_index", sa.Integer()), ("activity_at_time", sa.String(256)),
           ("hours_since_last_meal", sa.Float()), ("sleep_hours_previous_night", sa.Float()),
           ("suspected_trigger", sa.Text()), ("symptoms", sa.Text()), ("outcome", sa.Text()),
           ("reported_to_provider", sa.Boolean()), ("reported_to_provider_at", sa.String(50))]


def upgrade() -> None:
    # free text a family wrote moves into the note instead of being dropped
    op.execute("UPDATE incidents SET note = NULLIF(concat_ws(E'\\n', " + ", ".join(f"NULLIF({c}, '')" for c in ["note", *TEXT]) + "), '')")
    op.execute("UPDATE incidents SET incident_type_display = COALESCE(incident_type_display, incident_type), "
               "incident_type = 'other' WHERE incident_type NOT IN ('seizure', 'fall', 'allergic_reaction', 'other')")
    for name, _ in DROPPED:
        op.drop_column("incidents", name)


def downgrade() -> None:
    for name, type_ in DROPPED:
        op.add_column("incidents", sa.Column(name, type_, nullable=True))
    op.execute("UPDATE incidents SET severity = 'mild', status = 'resolved', reported_to_provider = false")
