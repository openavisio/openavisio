"""turn values stored as text back into numbers where they are purely numeric

A value printed as "13,9" failed float() on the way in and was kept as text. It
still showed in the list, so nothing looked broken, but it carried no unit and
dropped out of the trend chart, which filters on value_quantity.

Only purely numeric text is converted. "< 5", "negativ" and "12-15" are values in
their own right and stay exactly as they are.
"""

import re

import sqlalchemy as sa
from alembic import op

revision = "l8g9h0i1j2k3"
down_revision = "k7f8g9h0i1j2"
branch_labels = None
depends_on = None

_NUMERIC = re.compile(r"[+-]?[\d.,]*\d")


def _as_number(s: str) -> float | None:
    """Same rule as app.services.lab_codes.parse_number, frozen at this revision:
    with both separators the last one is the decimal point, a lone comma is a
    decimal separator."""
    s = (s or "").strip()
    if not _NUMERIC.fullmatch(s):
        return None
    if "," in s and "." in s:
        dec, thou = (",", ".") if s.rindex(",") > s.rindex(".") else (".", ",")
        s = s.replace(thou, "").replace(dec, ".")
    elif "," in s:
        s = s.replace(",", ".")
    try:
        return float(s)
    except ValueError:
        return None


def upgrade() -> None:
    conn = op.get_bind()
    rows = conn.execute(sa.text(
        "SELECT id, value_string FROM observations "
        "WHERE value_quantity IS NULL AND value_string IS NOT NULL AND is_deleted = false"
    )).fetchall()
    for row_id, text in rows:
        number = _as_number(text)
        if number is None:
            continue
        # value_string is cleared: the number is now the value, and leaving both would
        # give the UI two sources of truth for one reading.
        conn.execute(
            sa.text("UPDATE observations SET value_quantity = :n, value_string = NULL WHERE id = :id"),
            {"n": number, "id": row_id},
        )


def downgrade() -> None:
    # The original text is gone by design. Rendering the number back would invent a
    # formatting that was never printed, so this is deliberately not reversible.
    pass
