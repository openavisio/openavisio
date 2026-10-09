"""Widerspruchsfrist arithmetic (ADR 041).

The one piece of non-trivial logic in the deadline feature: the date is never
printed on the letter, and getting it wrong late cannot be undone.
"""

from datetime import date

from app.services.deadlines import parse_iso_date, widerspruch_deadline


def test_plain_month():
    # 3 Jul + 3 days service = 6 Jul, + 1 month = 6 Aug, a Thursday.
    assert widerspruch_deadline(date(2026, 7, 3)) == date(2026, 8, 6)


def test_rolls_off_a_weekend():
    # 2 Jun + 3 days = 5 Jun, + 1 month = 5 Jul, a Sunday -> Monday.
    assert widerspruch_deadline(date(2026, 6, 2)) == date(2026, 7, 6)


def test_clamps_to_the_end_of_a_short_month_then_rolls():
    # 28 Jan + 3 days = 31 Jan; February has no 31st, so 28 Feb, a Saturday -> Monday.
    assert widerspruch_deadline(date(2026, 1, 28)) == date(2026, 3, 2)


def test_crosses_the_year():
    assert widerspruch_deadline(date(2026, 12, 30)) == date(2027, 2, 2)


def test_longer_period():
    # A Rechtsbehelfsbelehrung stating a different period is honoured.
    assert widerspruch_deadline(date(2026, 7, 3), months=3) == date(2026, 10, 6)


def test_never_lands_on_a_weekend():
    start = date(2026, 1, 1)
    for offset in range(400):
        assert widerspruch_deadline(date.fromordinal(start.toordinal() + offset)).weekday() < 5


def test_parse_iso_date_is_lenient_but_not_credulous():
    assert parse_iso_date("2026-07-03") == date(2026, 7, 3)
    assert parse_iso_date("2026-07-03T00:00:00") == date(2026, 7, 3)
    assert parse_iso_date("03.07.2026") is None
    assert parse_iso_date(None) is None
    assert parse_iso_date(42) is None
