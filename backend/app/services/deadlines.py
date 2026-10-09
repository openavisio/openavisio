"""Widerspruchsfrist arithmetic for a Kassenbescheid (ADR 041).

Deliberately not done by the model: the end date is never printed on the letter,
it follows from the decision date and the period stated in the Rechtsbehelfs-
belehrung, and a wrong one cannot be re-opened. Date arithmetic is a known weak
spot of language models; this is six testable lines instead.
"""

from calendar import monthrange
from datetime import date, timedelta

# § 37 Abs. 2 SGB X: a posted decision counts as served on the third day after posting.
# We can only assume the printed decision date is the posting date; the letter never
# says. That assumption is why the result is labelled as a calculation everywhere it
# is shown, and why the reminders run well ahead of it.
SERVICE_ASSUMPTION_DAYS = 3


def _add_months(d: date, months: int) -> date:
    """Calendar-month addition, clamped to the end of the target month.

    Matches § 188 Abs. 2/3 BGB: the period ends on the day bearing the same number
    as the day of service, or on the last day of the month if there is no such day
    (31 Jan + 1 month -> 28/29 Feb).
    """
    total = d.month - 1 + months
    year = d.year + total // 12
    month = total % 12 + 1
    return date(year, month, min(d.day, monthrange(year, month)[1]))


def widerspruch_deadline(decision_date: date, months: int = 1) -> date:
    """Last day on which a Widerspruch can be raised against a decision.

    Decision date, plus the service assumption, plus the stated period, rolled off
    a weekend onto the next working day (§ 26 Abs. 3 SGB X).
    """
    served = decision_date + timedelta(days=SERVICE_ASSUMPTION_DAYS)
    end = _add_months(served, months)
    # ponytail: weekends only, public holidays are Bundesland-dependent and we do not
    # know the Patient's state. Not rolling off a holiday only ever makes our date
    # earlier than the real one, which is the safe direction; the reminders absorb it.
    while end.weekday() >= 5:
        end += timedelta(days=1)
    return end


def parse_iso_date(value: object) -> date | None:
    """Lenient ISO date parse for model output: accepts a date or a datetime string."""
    if not isinstance(value, str) or len(value) < 10:
        return None
    try:
        return date.fromisoformat(value[:10])
    except ValueError:
        return None
