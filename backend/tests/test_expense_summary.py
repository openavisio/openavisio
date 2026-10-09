"""Pure unit test for the expense money math — no DB, no fixtures.

Guards the rules that matter for a tax/insurance total: proposed amounts never
count, the open remainder is amount - reimbursed, and per-category sums stay exact
(Decimal, not float).
"""

from decimal import Decimal
from types import SimpleNamespace

from app.routers.expenses import summarize


def _e(amount, *, status="confirmed", reimbursed=None, category="other"):
    return SimpleNamespace(
        amount=Decimal(amount),
        reimbursed_amount=None if reimbursed is None else Decimal(reimbursed),
        status=status,
        category=category,
    )


def test_proposed_expenses_are_excluded_from_totals():
    s = summarize([
        _e("40.00", category="pflegehilfsmittel"),
        _e("999.99", status="proposed"),  # extracted, unconfirmed — must not count
    ])
    assert s.total == Decimal("40.00")
    assert s.count == 1
    assert s.proposed_count == 1


def test_open_remainder_and_partial_reimbursement():
    s = summarize([
        _e("100.00", reimbursed="60.00"),   # partially reimbursed
        _e("40.00"),                          # still open
    ])
    assert s.total == Decimal("140.00")
    assert s.total_reimbursed == Decimal("60.00")
    assert s.total_open == Decimal("80.00")   # deductible remainder


def test_by_category_sums_are_exact():
    s = summarize([
        _e("0.10", category="travel"),
        _e("0.20", category="travel"),
        _e("5.00", category="therapy"),
    ])
    assert s.by_category["travel"] == Decimal("0.30")  # would be 0.30000000000000004 as float
    assert s.by_category["therapy"] == Decimal("5.00")


def test_empty():
    s = summarize([])
    assert s.total == Decimal("0.00")
    assert s.total_open == Decimal("0.00")
    assert s.count == 0 and s.proposed_count == 0
