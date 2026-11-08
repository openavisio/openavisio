#!/usr/bin/env python3
"""Development from a therapy report (ADR 063, #465): what the code guarantees whatever the model says.

Run directly (`python3 aiservice/test_development.py`) or under pytest.
"""
import development

REPORT = """Ergotherapeutischer Bericht. Anamnese: Lena lief mit 18 Monaten frei.
Aktueller Stand: Lena isst inzwischen selbstständig mit dem Löffel. Socken zieht sie nur mit Hilfe an.
Der SON-R 2-8 wurde nach 20 Minuten abgebrochen, ein IQ war nicht bestimmbar. Im Bayley erreichte sie einen Wert von 62."""


def _read(raw):
    development._ask = lambda prompt, model: raw
    return development.read_development(REPORT, abilities=["Mit dem Löffel essen"])


def test_an_ability_needs_a_quote_that_stands_in_the_report():
    out = _read({"abilities": [
        {"name": "Mit dem Löffel essen", "works": True, "with_help": False, "place": "therapy", "domain": "daily_living",
         "quote": "Lena isst inzwischen  selbstständig mit dem Löffel."},
        {"name": "Frei laufen", "works": True, "quote": "Lena läuft frei."},
        {"name": "Socken anziehen", "works": "yes", "quote": "Socken zieht sie nur mit Hilfe an."},
        {"name": "Socken anziehen", "works": True, "with_help": True, "place": "garden", "domain": "x",
         "quote": "Socken zieht sie nur mit Hilfe an."},
    ]})["abilities"]
    assert [(a["name"], a["place"], a["domain"]) for a in out] == [
        ("Mit dem Löffel essen", "therapy", "daily_living"), ("Socken anziehen", None, None)], out
    assert out[0]["quote"] == "Lena isst inzwischen selbstständig mit dem Löffel."


def test_no_score_leaves_with_a_test_attempt():
    out = _read({"test_attempts": [
        {"test_name": "SON-R 2-8", "outcome": "stopped", "date": "2025-07", "reason": "nach 20 Minuten, IQ nicht bestimmbar",
         "quote": "Der SON-R 2-8 wurde nach 20 Minuten abgebrochen, ein IQ war nicht bestimmbar.", "iq": 57},
        {"test_name": "Bayley", "outcome": "completed", "date": "irgendwann", "reason": None,
         "quote": "Im Bayley erreichte sie einen Wert von 62."},
        {"test_name": "WPPSI", "outcome": "passed", "quote": "Im Bayley erreichte sie einen Wert von 62."},
    ]})["test_attempts"]
    assert out == [
        {"test_name": "SON-R 2-8", "outcome": "stopped", "date": "2025-07", "reason": None},
        {"test_name": "Bayley", "outcome": "completed", "date": None, "reason": None},
    ], out


def test_an_ability_quote_with_a_score_is_dropped():
    out = _read({"abilities": [{"name": "Bayley", "works": True, "quote": "Im Bayley erreichte sie einen Wert von 62."}]})
    assert out["abilities"] == [], out


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            fn()
    print("development guarantees OK")
