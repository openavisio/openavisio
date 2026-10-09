"""Data-governance service: built-in categories, lawful-basis vocabulary,
and the retention purge (#15/#16)."""

from datetime import UTC, datetime, timedelta

from sqlalchemy import Date, and_, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.audit import AuditLog
from app.models.calendar import CalendarEvent
from app.models.condition import Condition
from app.models.diary import DiaryEntry
from app.models.document import DocumentReference
from app.models.governance import DataCategory
from app.models.incident import Incident
from app.models.medication import MedicationStatement
from app.models.observation import Observation
from app.models.recommendation import Recommendation

# Built-in categories (code, label). Seeded on startup; 1:1 with a clinical table.
BUILTIN_CATEGORIES: list[tuple[str, str]] = [
    ("observation", "Measurements & Lab Results"),
    ("condition", "Diagnoses"),
    ("medication", "Medications"),
    ("document", "Documents"),
    ("incident", "Incidents"),
    ("diary", "Health Log (Diary)"),
    ("calendar", "Calendar Events"),
    ("recommendation", "Recommendations"),
]

# Purge targets — built-in code -> model. Custom categories are documentation-only.
CATEGORY_MODELS = {
    "observation": Observation,
    "condition": Condition,
    "medication": MedicationStatement,
    "document": DocumentReference,
    "incident": Incident,
    "diary": DiaryEntry,
    "calendar": CalendarEvent,
    "recommendation": Recommendation,
}

# Clinically relevant date per category (#32) — retention is measured against
# this column when set on a record, falling back to created_at. Columns are
# either Date or ISO-8601 strings; both compare correctly against an ISO date
# string at day granularity.
DOMAIN_DATE_FIELDS = {
    "document": "issued_date",          # Date, nullable
    "diary": "entry_date",              # "YYYY-MM-DD" string
    "observation": "effective_date_time",  # ISO datetime string, nullable
}

# GDPR Art. 6 / 9 lawful bases the controller can assign per category.
LAWFUL_BASES = [
    "art9_healthcare",     # Art. 9(2)(h) — health care under professional responsibility
    "consent",             # Art. 6(1)(a) / 9(2)(a) — explicit consent
    "legitimate_interest",  # Art. 6(1)(f)
    "legal_obligation",    # Art. 6(1)(c)
    "vital_interest",      # Art. 6(1)(d) / 9(2)(c)
    "contract",            # Art. 6(1)(b)
    "public_task",         # Art. 6(1)(e)
]


async def ensure_categories_seeded(db: AsyncSession) -> None:
    """Insert any missing built-in categories (idempotent)."""
    existing = {c for (c,) in (await db.execute(select(DataCategory.code))).all()}
    added = False
    for code, label in BUILTIN_CATEGORIES:
        if code not in existing:
            db.add(DataCategory(code=code, label=label, is_builtin=True))
            added = True
    if added:
        await db.commit()


async def run_retention_purge(db: AsyncSession) -> dict[str, int]:
    """Soft-delete records past their category retention window.

    Only built-in categories with a positive ``retention_days`` are purged.
    Writes one summary audit entry per category that purged anything.
    Returns {code: count}.
    """
    now = datetime.now(UTC)
    summary: dict[str, int] = {}

    result = await db.execute(
        select(DataCategory).where(
            DataCategory.is_builtin == True,  # noqa: E712
            DataCategory.retention_days.isnot(None),
        )
    )
    for cat in result.scalars().all():
        if not cat.retention_days or cat.retention_days <= 0:
            continue
        model = CATEGORY_MODELS.get(cat.code)
        if model is None:
            continue
        cutoff = now - timedelta(days=cat.retention_days)
        age_clause = model.created_at < cutoff
        field = DOMAIN_DATE_FIELDS.get(cat.code)
        if field:
            col = getattr(model, field)
            domain_cutoff = cutoff.date() if isinstance(col.type, Date) else cutoff.date().isoformat()
            age_clause = or_(
                and_(col.isnot(None), col < domain_cutoff),
                and_(col.is_(None), age_clause),
            )
        res = await db.execute(
            update(model)
            .where(model.is_deleted == False, age_clause)  # noqa: E712
            .values(is_deleted=True)
        )
        count = res.rowcount or 0
        if count:
            summary[cat.code] = count
            db.add(AuditLog(
                timestamp=now,
                user_id=None,
                user_name="Retention policy",
                entity_type="DataRetention",
                entity_id=cat.code,
                action="purged",
                changes={"count": count, "retention_days": cat.retention_days, "cutoff": cutoff.isoformat()},
            ))
    await db.commit()
    return summary


async def next_purge_run_hint() -> str:
    """Human hint for the admin UI — the purge runs daily."""
    return "daily"
