"""Abilities, Ability Observations and Test Attempts; milestones become Abilities (ADR 063, #464)"""

import uuid

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

revision = "b4w5x6y7z8a9"
down_revision = "a3v4w5x6y7z8"
branch_labels = None
depends_on = None

DOMAINS = {"speech": "communication", "cognitive": "learning", "motor": "motor", "social": "social"}


def _base() -> list[sa.Column]:
    return [
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("owner_id", UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("patient_id", UUID(as_uuid=True), sa.ForeignKey("patients.id"), nullable=False, index=True),
    ]


def move_milestones(conn) -> None:
    """Every milestone Event becomes one Observation that works; same title, same Ability. Nothing is dropped:
    the description becomes the note, a linked Document stays the source."""
    rows = conn.execute(sa.text(
        "SELECT id, owner_id, patient_id, title, description, start_at, developmental_domain, document_reference_id, created_at "
        "FROM calendar_events WHERE category = 'milestone' AND NOT is_deleted ORDER BY start_at")).mappings().all()
    abilities: dict[tuple, uuid.UUID] = {}
    for r in rows:
        name = " ".join(r["title"].split())[:256] or "?"
        key = (r["patient_id"], name.lower())
        if key not in abilities:
            abilities[key] = uuid.uuid4()
            conn.execute(sa.text(
                "INSERT INTO abilities (id, owner_id, patient_id, name, domain, created_at, updated_at, is_deleted) "
                "VALUES (:id, :owner, :patient, :name, :domain, :at, :at, false)"),
                {"id": abilities[key], "owner": r["owner_id"], "patient": r["patient_id"], "name": name,
                 "domain": DOMAINS.get(r["developmental_domain"] or ""), "at": r["created_at"]})
        conn.execute(sa.text(
            "INSERT INTO ability_observations (id, owner_id, patient_id, ability_id, observed_on, works, with_help, note, "
            "source, document_id, created_at, updated_at, is_deleted) "
            "VALUES (:id, :owner, :patient, :ability, :on, true, false, :note, :source, :doc, :at, :at, false)"),
            {"id": uuid.uuid4(), "owner": r["owner_id"], "patient": r["patient_id"], "ability": abilities[key],
             "on": (r["start_at"] or "")[:10], "note": (r["description"] or "").strip() or None,
             "source": "document" if r["document_reference_id"] else "family", "doc": r["document_reference_id"],
             "at": r["created_at"]})
    conn.execute(sa.text("DELETE FROM calendar_events WHERE category = 'milestone'"))


def upgrade() -> None:
    op.create_table(
        "abilities", *_base(),
        sa.Column("name", sa.String(256), nullable=False),
        sa.Column("domain", sa.String(20)),
    )
    op.create_table(
        "ability_observations", *_base(),
        sa.Column("ability_id", UUID(as_uuid=True), sa.ForeignKey("abilities.id"), nullable=False, index=True),
        sa.Column("observed_on", sa.String(10), nullable=False),
        sa.Column("place", sa.String(20)),
        sa.Column("works", sa.Boolean(), nullable=False),
        sa.Column("with_help", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("note", sa.Text()),
        sa.Column("source", sa.String(20), nullable=False, server_default="family"),
        sa.Column("document_id", UUID(as_uuid=True), sa.ForeignKey("document_references.id")),
    )
    op.create_table(
        "test_attempts", *_base(),
        sa.Column("test_name", sa.String(256), nullable=False),
        sa.Column("attempted_on", sa.String(10), nullable=False),
        sa.Column("correspondent_id", UUID(as_uuid=True), sa.ForeignKey("correspondents.id")),
        sa.Column("setting", sa.String(20)),
        sa.Column("duration_minutes", sa.Integer()),
        sa.Column("outcome", sa.String(20), nullable=False),
        sa.Column("reason", sa.Text()),
        sa.Column("document_id", UUID(as_uuid=True), sa.ForeignKey("document_references.id")),
    )
    move_milestones(op.get_bind())
    op.drop_column("calendar_events", "developmental_domain")


def downgrade() -> None:
    # the Observations are not turned back into milestones
    op.add_column("calendar_events", sa.Column("developmental_domain", sa.String(20)))
    op.drop_table("test_attempts")
    op.drop_table("ability_observations")
    op.drop_table("abilities")
