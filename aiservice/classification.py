"""
Document classification: detect document type and provider from extracted text.
"""

import json
import logging

from backend import get_backend, get_model, get_num_ctx
from extraction import _LANGUAGE_NAMES, _load_prompt, _parse_llm_response

logger = logging.getLogger(__name__)

CLASSIFICATION_PROMPT = _load_prompt("classification.md")


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
        result = _parse_llm_response(response)
        return {
            "document_type": result.get("document_type", "other"),
            "provider": result.get("provider"),
            "confidence": float(result.get("confidence", 0.5)),
        }
    except (json.JSONDecodeError, ValueError) as e:
        logger.warning("Failed to parse classification response: %s", e)
        return {"document_type": "other", "provider": None, "confidence": 0.0}

