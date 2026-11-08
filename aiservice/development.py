"""Abilities and Test Attempts from a therapy report (ADR 063, #465).

The prompt asks; the code guarantees. Whatever the model returns, an entry leaves
here only with a quote that stands in the report, and never with a score.
"""

import re

from extraction import _LANGUAGE_NAMES, _load_prompt
from intake import _ask

PROMPT = _load_prompt("development.md")
DOMAINS = {"communication", "daily_living", "social", "motor", "learning"}
PLACES = {"home", "kita_school", "therapy", "out"}
OUTCOMES = {"completed", "stopped", "refused", "not_attempted"}
# a test number in any wording; a reason or a quote that carries one is not kept
SCORE = re.compile(r"\b(IQ|Punkt\w*|Prozentrang|PR\s*\d|T-Wert\w*|Standardwert\w*|SW\s*\d|Score\w*|Quotient\w*|"
                   r"Rohwert\w*|Entwicklungsalter|Perzentil\w*|percentile\w*|standard score|Wert\w*\s+(von\s+)?\d)", re.I)
DATE = re.compile(r"^\d{4}-(0[1-9]|1[0-2])(-(0[1-9]|[12]\d|3[01]))?$")


def _norm(text: str) -> str:
    return " ".join(text.split()).casefold()


def _quote(item: dict, text: str) -> str | None:
    q = " ".join(str(item.get("quote") or "").split())
    return q if q and _norm(q) in text else None


def read_development(text: str, model: str | None = None, language: str = "en",
                     abilities: list[str] = ()) -> dict:
    lang = _LANGUAGE_NAMES.get(language, "English")
    prompt = (f"JSON keys and the values of place, domain and outcome stay in English; names, reasons and quotes stay in "
              f"the report's language (the family reads {lang}).\n\n{PROMPT}\n\n"
              f"--- KNOWN ABILITIES ---\n{chr(10).join(abilities) or '(none)'}\n--- END ---\n\n"
              f"--- REPORT ---\n{text}\n--- END ---")
    raw = _ask(prompt, model)
    plain = _norm(text)
    found = []
    for a in raw.get("abilities") or []:
        name = " ".join(str(a.get("name") or "").split())[:256] if isinstance(a, dict) else ""
        quote = _quote(a, plain) if name else None
        # the quote is kept as the Observation's citation, so it must not carry a test number
        if quote and not SCORE.search(quote) and isinstance(a.get("works"), bool):
            found.append({"name": name, "works": a["works"], "with_help": a.get("with_help") is True,
                          "place": a.get("place") if a.get("place") in PLACES else None,
                          "domain": a.get("domain") if a.get("domain") in DOMAINS else None, "quote": quote})
    tests = []
    for t in raw.get("test_attempts") or []:
        name = " ".join(str(t.get("test_name") or "").split())[:256] if isinstance(t, dict) else ""
        if not (name and t.get("outcome") in OUTCOMES and _quote(t, plain)):  # checked, never stored
            continue
        reason = " ".join(str(t.get("reason") or "").split()) or None
        date = str(t.get("date") or "")
        tests.append({"test_name": name, "outcome": t["outcome"], "date": date if DATE.match(date) else None,
                      "reason": None if reason and SCORE.search(reason) else reason})
    return {"abilities": found, "test_attempts": tests}
