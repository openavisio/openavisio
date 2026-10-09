"""merge share-links + milestones migration heads

Two feature branches (document share links, milestone events) each added a
migration descending from o5j6k7l8m9n0, producing two Alembic heads on master.
This no-op merge migration unifies them into a single head.

Revision ID: s9n0o1p2q3r4
Revises: p6k7l8m9n0o1, q7l8m9n0o1p2
Create Date: 2026-07-02

"""

revision = "s9n0o1p2q3r4"
down_revision = ("p6k7l8m9n0o1", "q7l8m9n0o1p2")
branch_labels = None
depends_on = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
