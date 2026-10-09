"""Reading a printed measurement value as a number.

The bug this closes: "13,9" off a German report failed float(), was stored as text,
and silently vanished from the trend chart while still showing in the list.
"""

import pytest

from app.services.lab_codes import parse_number


@pytest.mark.parametrize("raw,expected", [
    ("13,9", 13.9),      # the German decimal comma, the whole point
    ("13.9", 13.9),
    ("12", 12.0),
    ("-0,5", -0.5),
    ("+12", 12.0),
    ("1.234,5", 1234.5),  # German thousands dot
    ("1,234.5", 1234.5),  # English thousands comma
    (" 13,9 ", 13.9),
    (13.9, 13.9),
    (12, 12.0),
])
def test_numbers_are_read_as_numbers(raw, expected):
    assert parse_number(raw) == pytest.approx(expected)


@pytest.mark.parametrize("raw", [
    "< 5",            # a censored lab result is not a number
    "> 10",
    "negativ",
    "unauffällig",
    "13,9 kg",        # the unit lives in its own column
    "",
    None,
    "n/a",
    "12-15",          # a range, not a value
])
def test_anything_that_is_not_purely_a_number_stays_text(raw):
    assert parse_number(raw) is None


def test_a_bool_is_not_a_measurement():
    """bool is an int in Python, and True would otherwise become 1.0."""
    assert parse_number(True) is None
    assert parse_number(False) is None
