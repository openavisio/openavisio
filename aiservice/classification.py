"""
Document classification: detect document type and provider from extracted text.
"""

import json
import logging
import os

from backend import get_backend, get_model, get_num_ctx

logger = logging.getLogger(__name__)

_PROMPT_DIR = os.path.join(os.path.dirname(__file__), "prompts")


def _load_prompt(filename: str) -> str:
    with open(os.path.join(_PROMPT_DIR, filename)) as f:
        return f.read().strip()


CLASSIFICATION_PROMPT = _load_prompt("classification.md")


_LANGUAGE_NAMES: dict[str, str] = {
    "en": "English", "de": "German", "fr": "French", "es": "Spanish", "it": "Italian",
}


def classify_document(text: str, filename: str | None = None, model: str | None = None, language: str = "en") -> dict:
    """Classify a document based on its text content.

    Returns:
        {"document_type": str, "provider": str|None, "confidence": float}
    """
    model = model or get_model("classify")

    lang_name = _LANGUAGE_NAMES.get(language, "English")
    lang_line = f"Respond in {lang_name}. JSON keys must remain in English.\n\n"
    prompt = lang_line + CLASSIFICATION_PROMPT + f"\n\nFilename: {filename or 'unknown'}\n\n--- DOCUMENT TEXT ---\n{text[:4000]}\n--- END ---"

    response = get_backend().chat(model, [{"role": "user", "content": prompt}],
                                  num_ctx=get_num_ctx("classify"), think=False)

    try:
        result = _parse_json_response(response)
        return {
            "document_type": result.get("document_type", "other"),
            "provider": result.get("provider"),
            "confidence": float(result.get("confidence", 0.5)),
        }
    except (json.JSONDecodeError, ValueError) as e:
        logger.warning("Failed to parse classification response: %s", e)
        return {"document_type": "other", "provider": None, "confidence": 0.0}


def _parse_json_response(text: str) -> dict:
    """Parse LLM response, stripping markdown code fences if present."""
    text = text.strip()
    if text.startswith("```"):
        lines = text.split("\n")
        lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        text = "\n".join(lines).strip()
    return json.loads(text)
