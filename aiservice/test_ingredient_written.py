#!/usr/bin/env python3
"""The ingredient comes from the letter, never from the model's knowledge (#209)."""
import extraction


def _run(text, meds):
    extraction.call_ollama_text = lambda *a, **k: {"medications": meds}
    extraction.parse_lab_tables = lambda t: []
    return extraction.extract_entities_from_text(text, "doctor_letter")["entities"]["medications"]


def test_ingredient_the_letter_names_stays():
    m = _run("Medikation: Ergenyl (Valproinsäure) 300 mg 1-0-1", [{"name": "Ergenyl", "ingredient": "Valproinsäure"}])
    assert m[0]["ingredient"] == "Valproinsäure"


def test_ingredient_from_general_knowledge_is_dropped():
    m = _run("Medikation: Ergenyl 300 mg 1-0-1", [{"name": "Ergenyl", "ingredient": "Valproinsäure"}])
    assert m[0]["ingredient"] is None and m[0]["name"] == "Ergenyl"


if __name__ == "__main__":
    test_ingredient_the_letter_names_stays()
    test_ingredient_from_general_knowledge_is_dropped()
    print("ok")
