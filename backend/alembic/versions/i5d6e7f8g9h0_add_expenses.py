"""expense tracking for insurance/tax overviews (#218)"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

revision = "i5d6e7f8g9h0"
down_revision = "h4c5d6e7f8g9"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "expenses",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("owner_id", UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("patient_id", UUID(as_uuid=True), sa.ForeignKey("patients.id"), nullable=False, index=True),
        sa.Column("amount", sa.Numeric(10, 2), nullable=False),
        sa.Column("incurred_on", sa.String(50), nullable=True),
        sa.Column("category", sa.String(50), server_default="other"),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("reimbursed_amount", sa.Numeric(10, 2), nullable=True),
        sa.Column("status", sa.String(20), server_default="confirmed"),
        sa.Column("source", sa.String(20), server_default="manual"),
        sa.Column("correspondent_id", UUID(as_uuid=True), sa.ForeignKey("correspondents.id"), nullable=True),
        sa.Column("document_reference_id", UUID(as_uuid=True), sa.ForeignKey("document_references.id"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("is_deleted", sa.Boolean(), server_default=sa.false()),
    )


def downgrade() -> None:
    op.drop_table("expenses")
