"""Intake Form: read a form's questions, answer them from given entries (ADR 047).

The prompts ask; the code guarantees. Whatever the model returns, a judgement
question leaves here unanswered and a fact answer leaves here only with a
source that was actually offered to it.
"""

import json
import logging

from backend import get_backend, get_model, get_num_ctx
from extraction import _LANGUAGE_NAMES, _load_prompt, _parse_llm_response

logger = logging.getLogger(__name__)

QUESTIONS_PROMPT = _load_prompt("intake_questions.md")
ANSWER_PROMPT = _load_prompt("intake_answer.md")

AGINGS = {"lasting", "changeable", "visit_only"}
RELATED_LIMIT = 5


def _ask(prompt: str, model: str | None) -> dict:
    """One JSON call, one retry on bad JSON, like extraction."""
    model = model or get_model("extract")
    messages = [{"role": "user", "content": prompt}]
    for attempt in (1, 2):
        response = get_backend().chat(model, messages, num_ctx=get_num_ctx("extract"), think=False)
        try:
            parsed = _parse_llm_response(response)
            return parsed if isinstance(parsed, dict) else {}
        except (json.JSONDecodeError, ValueError):
            if attempt == 2:
                raise
            logger.warning("Intake call returned invalid JSON, retrying once")


def read_questions(text: str, model: str | None = None, language: str = "en") -> list[dict]:
    lang = _LANGUAGE_NAMES.get(language, "English")
    prompt = (f"JSON keys and the values of kind and aging stay in English; the question text stays in the "
              f"form's language (the family reads {lang}).\n\n{QUESTIONS_PROMPT}\n\n"
              f"--- FORM TEXT ---\n{text}\n--- END ---")
    out = []
    for q in _ask(prompt, model).get("questions") or []:
        if not isinstance(q, dict) or not str(q.get("text") or "").strip():
            continue
        out.append({
            "text": str(q["text"]).strip(),
            "section": (str(q.get("section") or "").strip() or None),
            # in doubt a judgement (GLOSSARY, Intake Form)
            "kind": "fact" if q.get("kind") == "fact" else "judgement",
            "aging": q.get("aging") if q.get("aging") in AGINGS else "changeable",
        })
    return out


def answer_questions(questions: list[dict], context: list[dict], model: str | None = None,
                     language: str = "en") -> list[dict]:
    """questions: [{text, kind}], context: [{id, text}]. One result per question, same order."""
    ids = {c["id"] for c in context}
    record = "\n".join(f"[{c['id']}] {c['text']}" for c in context)
    numbered = "\n".join(f"{i}. ({'FACT' if q.get('kind') == 'fact' else 'JUDGEMENT'}) {q['text']}"
                         for i, q in enumerate(questions, 1))
    lang = _LANGUAGE_NAMES.get(language, "English")
    prompt = (f"Write answers in the language of the question; if unsure, in {lang}. JSON keys stay in English."
              f"\n\n{ANSWER_PROMPT}\n\n--- RECORD ---\n{record}\n--- END RECORD ---\n\n"
              f"--- QUESTIONS ---\n{numbered}\n--- END QUESTIONS ---")
    by_q = {}
    for a in _ask(prompt, model).get("answers") or []:
        if isinstance(a, dict) and isinstance(a.get("q"), int):
            by_q[a["q"]] = a

    out = []
    for i, q in enumerate(questions, 1):
        a = by_q.get(i, {})
        sources = [s for s in a.get("sources") or [] if s in ids]
        answer = str(a.get("answer") or "").strip() or None
        if q.get("kind") != "fact":
            related = [s for s in a.get("related") or [] if s in ids][:RELATED_LIMIT]
            out.append({"answer": None, "sources": [], "related": related})
        elif answer and sources:
            out.append({"answer": answer, "sources": sources, "related": []})
        else:
            out.append({"answer": None, "sources": [], "related": []})
    return out
