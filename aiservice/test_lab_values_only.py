#!/usr/bin/env python3
"""A laboratory report yields values, never diagnoses (#208 family, 2026-07-27).

The prompt asks for this; this checks the guarantee that does not depend on a
model complying. Run directly (`python3 aiservice/test_lab_values_only.py`) or
under pytest — no fixtures, no model, no network.
"""
import extraction

FABRICATED = {
    "diagnoses": [{"name": "Hyperkaliämie"}, {"name": "Anisozytose"}, {"name": "Folsäuremangel"}],
    "medications": [{"name": "Valproinsäure"}, {"name": "Lamotrigin"}],
    "observations": [{"type": "Kalium", "value": "6.1"}],
    "appointments": [{"date": "2026-05-07"}],
    "recommendations": ["Kontrolle der Elektrolyte"],
    "summary": "Laborbefund vom 12.03.2026",
}


def _run(document_type, monkeypatched=FABRICATED):
    extraction.call_ollama_text = lambda *a, **k: dict(monkeypatched)
    extraction.parse_lab_tables = lambda text: []
    return extraction.extract_entities_from_text("irgendein Text", document_type)["entities"]


def test_lab_report_keeps_no_diagnoses_or_medications():
    e = _run("lab_report")
    assert e["diagnoses"] == [], e["diagnoses"]
    assert e["medications"] == [], e["medications"]


def test_lab_report_keeps_everything_else():
    """The guard must not turn into 'lab reports yield nothing'. Appointments and
    recommendations are written sentences, not inferences, and stay."""
    e = _run("lab_report")
    assert e["appointments"] and e["recommendations"] and e["summary"]


def test_other_document_types_are_untouched():
    """A doctor's letter is exactly where a real diagnosis is written down."""
    e = _run("doctor_letter")
    assert len(e["diagnoses"]) == 3
    assert len(e["medications"]) == 2


def test_no_document_type_is_untouched():
    """Classification can fail or be skipped; that must not silently strip a
    letter's diagnoses."""
    e = _run(None)
    assert len(e["diagnoses"]) == 3


def test_lab_report_survives_a_model_returning_nothing():
    extraction.call_ollama_text = lambda *a, **k: None
    extraction.parse_lab_tables = lambda text: []
    e = extraction.extract_entities_from_text("x", "lab_report")["entities"]
    assert e["diagnoses"] == [] and e["medications"] == []


if __name__ == "__main__":
    original = (extraction.call_ollama_text, extraction.parse_lab_tables)
    for name, fn in sorted(globals().items()):
        if name.startswith("test_"):
            extraction.call_ollama_text, extraction.parse_lab_tables = original
            fn()
            print("ok", name)
