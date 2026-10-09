"""operator legal details for the Impressum (§5 DDG) and the privacy policy (#112)

OpenAvisio is self-hosted: the operator of the instance is the one with the
legal duty, not the project. So these live in the database, per instance —
never hardcoded in an AGPL repository.
"""

import sqlalchemy as sa
from alembic import op

revision = "d0y1z2a3b4c5"
down_revision = "c9x0y1z2a3b4"
branch_labels = None
depends_on = None

_COLUMNS = [
    ("legal_name", sa.String(256)),        # "Martin Riedel" or "Verein XY e.V."
    ("legal_street", sa.String(256)),
    ("legal_postcode", sa.String(32)),
    ("legal_city", sa.String(128)),
    ("legal_country", sa.String(128)),
    ("legal_email", sa.String(256)),       # §5 DDG: an address you actually read
    ("legal_phone", sa.String(64)),
    ("legal_responsible", sa.String(256)), # V.i.S.d.P., if content is published
    ("legal_vat_id", sa.String(64)),       # only if one exists — never invent one
    ("legal_register", sa.String(256)),    # Registergericht + Nummer, e.g. a Verein
    ("dpo_contact", sa.Text()),            # data protection officer, if appointed
]


def upgrade() -> None:
    for name, type_ in _COLUMNS:
        op.add_column("organization", sa.Column(name, type_, nullable=True))


def downgrade() -> None:
    for name, _ in reversed(_COLUMNS):
        op.drop_column("organization", name)
