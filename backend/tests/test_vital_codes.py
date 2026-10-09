"""Vital signs get a canonical code, so a hand-typed weight and an extracted one
land in the same series (follow-up to the split "Weight"/"Gewicht" groups).

The trap this guards: giving a vital a *panel* would turn it into a lab result,
because that is how documents.py decides the category.
"""

import pytest

from app.services.lab_codes import canonical_code, resolve_panel


@pytest.mark.parametrize("printed,expected", [
    ("Gewicht", "body-weight"),
    ("Körpergewicht", "body-weight"),
    ("Weight", "body-weight"),
    ("Länge", "body-height"),
    ("Körpergröße", "body-height"),
    ("Height", "body-height"),
    ("Kopfumfang", "head-circumference"),
    ("Temperatur", "body-temperature"),
    ("Herzfrequenz", "heart-rate"),
    ("Puls", "heart-rate"),
    ("SpO₂", "oxygen-saturation"),
    ("Sauerstoffsättigung", "oxygen-saturation"),
    ("BMI", "bmi"),
])
def test_vitals_resolve_to_the_form_s_own_codes(printed, expected):
    assert canonical_code(printed) == expected


@pytest.mark.parametrize("printed", ["Gewicht", "Kopfumfang", "Herzfrequenz", "BMI"])
def test_a_vital_never_gets_a_panel(printed):
    """A panel is what makes a value a lab result; a weight is not one."""
    assert resolve_panel(canonical_code(printed), None) is None


def test_lab_analytes_are_untouched():
    assert canonical_code("Hämoglobin") == "hemoglobin"
    assert resolve_panel(canonical_code("Hämoglobin"), None) == "Blutbild"


def test_an_unknown_name_still_resolves_to_nothing():
    assert canonical_code("Schuhgröße links") is None
