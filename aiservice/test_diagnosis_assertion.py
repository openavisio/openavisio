#!/usr/bin/env python3
"""Only the patient's own, present conditions become Diagnoses (#259).

A relative's condition, a ruled-out one, and every question on a form name a
condition without asserting it of the patient. The prompt asks the model to
label each diagnosis; this checks that the label is enforced in code. Run
directly (`python3 aiservice/test_diagnosis_assertion.py`) or under pytest.
"""
import extraction


def _run(diagnoses, document_type="doctor_letter"):
    extraction.call_ollama_text = lambda *a, **k: {
        "diagnoses": [dict(d) for d in diagnoses],
        "medications": [{"name": "Levetiracetam"}],
        "observations": [{"type": "Gewicht", "value": "14.2"}],
        "summary": "Brief",
    }
    extraction.parse_lab_tables = lambda text: []
    return extraction.extract_entities_from_text("irgendein Text", document_type)["entities"]


def test_relative_and_ruled_out_conditions_are_dropped():
    e = _run([
        {"name": "Dup15q-Syndrom", "assertion": "present"},
        {"name": "Epilepsie", "assertion": "family"},
        {"name": "Herzfehler", "assertion": "absent"},
    ])
    assert [d["name"] for d in e["diagnoses"]] == ["Dup15q-Syndrom"], e["diagnoses"]


def test_kept_diagnoses_do_not_carry_the_label():
    e = _run([{"name": "Dup15q-Syndrom", "assertion": "present"}])
    assert "assertion" not in e["diagnoses"][0]


def test_suspected_diagnosis_is_kept_and_marked():
    e = _run([
        {"name": "Epilepsie", "assertion": "suspected"},
        {"name": "Dup15q-Syndrom", "assertion": "present"},
    ])
    by_name = {d["name"]: d for d in e["diagnoses"]}
    assert by_name["Epilepsie"]["verification_status"] == "provisional"
    assert "verification_status" not in by_name["Dup15q-Syndrom"]


def test_unlabelled_diagnosis_is_kept():
    # A model that forgets the field must not wipe a real diagnosis.
    e = _run([{"name": "Dup15q-Syndrom"}])
    assert [d["name"] for d in e["diagnoses"]] == ["Dup15q-Syndrom"]


def test_questionnaire_yields_no_clinical_data():
    e = _run([{"name": "Asthma", "assertion": "present"}], document_type="questionnaire")
    assert e["diagnoses"] == [] and e["medications"] == [] and e["observations"] == [], e
    assert e["summary"] == "Brief"


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            fn()
            print("ok", name)
