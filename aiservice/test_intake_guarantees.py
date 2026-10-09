#!/usr/bin/env python3
"""Intake Form answers (ADR 047): what the code guarantees whatever the model says.

A judgement question leaves unanswered, a fact answer leaves only with a source
that was offered. Run directly (`python3 aiservice/test_intake_guarantees.py`)
or under pytest.
"""
import intake

CONTEXT = [{"id": "E1", "text": "Medication | 2024-03-01 | Levetiracetam | 250 mg twice daily"},
           {"id": "E2", "text": "Diagnosis | 2020-01-01 | Dup15q syndrome"}]


def _answers(model_answers, questions):
    intake._ask = lambda prompt, model: {"answers": model_answers}
    return intake.answer_questions(questions, CONTEXT)


def test_judgement_is_never_answered():
    out = _answers([{"q": 1, "answer": "Yes, age-appropriate", "sources": ["E2"], "related": ["E2", "E9"]}],
                   [{"text": "Is the development age-appropriate?", "kind": "judgement"}])
    assert out == [{"answer": None, "sources": [], "related": ["E2"]}], out


def test_fact_without_an_offered_source_is_dropped():
    out = _answers([{"q": 1, "answer": "None", "sources": []},
                    {"q": 2, "answer": "Valproate", "sources": ["E7"]},
                    {"q": 3, "answer": "Levetiracetam 250 mg twice daily", "sources": ["E1"]}],
                   [{"text": "Allergies?", "kind": "fact"}, {"text": "Medication?", "kind": "fact"},
                    {"text": "Current medication?", "kind": "fact"}])
    assert [a["answer"] for a in out] == [None, None, "Levetiracetam 250 mg twice daily"], out


def test_unknown_kind_counts_as_judgement_and_unknown_aging_as_changeable():
    intake._ask = lambda prompt, model: {"questions": [
        {"text": "How does your child sleep?", "kind": "opinion", "aging": "forever"}, {"text": " "}]}
    assert intake.read_questions("form") == [
        {"text": "How does your child sleep?", "section": None, "kind": "judgement", "aging": "changeable"}]


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            fn()
    print("intake guarantees OK")
