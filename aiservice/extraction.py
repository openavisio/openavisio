"""
Medical document extraction using AI inference backends.
Handles PDF text extraction, image extraction, and LLM-based structured summarization.
"""

import io
import json
import logging
import os
from typing import Optional

import pypdfium2 as pdfium

from backend import get_backend, get_vision_backend, get_model, get_num_ctx
from lab_table import parse_lab_tables

logger = logging.getLogger(__name__)

_PROMPT_DIR = os.path.join(os.path.dirname(__file__), "prompts")


def _load_prompt(filename: str) -> str:
    with open(os.path.join(_PROMPT_DIR, filename)) as f:
        return f.read().strip()


EXTRACTION_PROMPT = _load_prompt("extraction.md")

_LANGUAGE_NAMES: dict[str, str] = {
    "en": "English", "de": "German", "fr": "French", "es": "Spanish", "it": "Italian",
}


def extract_text_from_pdf(file_bytes: bytes) -> tuple[str, list[bytes]]:
    """Extract text and page images from a PDF using pypdfium2.

    Returns:
        Tuple of (extracted_text, list_of_page_images_as_png_bytes)
    """
    doc = pdfium.PdfDocument(file_bytes)
    text_parts = []
    images = []

    for page in doc:
        textpage = page.get_textpage()
        text_parts.append(textpage.get_text_range())
        textpage.close()

        # Render page as image for vision model fallback
        bitmap = page.render(scale=200 / 72)
        pil_image = bitmap.to_pil()
        buf = io.BytesIO()
        pil_image.save(buf, format="PNG")
        images.append(buf.getvalue())

    doc.close()
    return "\n".join(text_parts).strip(), images


def _parse_llm_response(response_text: str) -> dict:
    """Parse LLM response, handling markdown code blocks."""
    text = response_text.strip()
    # Strip markdown code fences if present
    if text.startswith("```"):
        lines = text.split("\n")
        # Remove first and last lines (fences)
        lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        text = "\n".join(lines).strip()

    return json.loads(text)


def _lang_line(language: str) -> str:
    lang_name = _LANGUAGE_NAMES.get(language, "English")
    return f"Respond in {lang_name}. Free-text values (summary, recommendations) must be written in {lang_name}. JSON keys must remain in English.\n\n"


def call_ollama_text(text: str, model: str, language: str = "en") -> dict:
    """Send extracted text to backend for structured extraction. Retries once on bad JSON."""
    prompt = f"{_lang_line(language)}{EXTRACTION_PROMPT}\n\n--- DOCUMENT TEXT ---\n{text}\n--- END ---"
    messages = [{"role": "user", "content": prompt}]
    nctx = get_num_ctx("extract")
    # think=False: a reasoning model otherwise spends the context window
    # reasoning and never reaches the JSON. On a long document that returns
    # done_reason=length with an empty answer, which then burns the one retry
    # below on an identical failure. There is nothing to reason about here —
    # the task is to transcribe what the document says into fields.
    response = get_backend().chat(model, messages, num_ctx=nctx, think=False)
    try:
        return _parse_llm_response(response)
    except (json.JSONDecodeError, ValueError):
        logger.warning("Extraction returned invalid JSON, retrying once")
        response = get_backend().chat(model, messages, num_ctx=nctx, think=False)
        return _parse_llm_response(response)


def call_ollama_vision(image_bytes: bytes, model: str, language: str = "en") -> dict:
    """Send an image to vision backend for structured extraction. Retries once on bad JSON."""
    prompt = f"{_lang_line(language)}{EXTRACTION_PROMPT}"
    messages = [{"role": "user", "content": prompt}]
    nctx = get_num_ctx("vision")
    response = get_vision_backend().chat(model, messages, images=[image_bytes], num_ctx=nctx)
    try:
        return _parse_llm_response(response)
    except (json.JSONDecodeError, ValueError):
        logger.warning("Vision extraction returned invalid JSON, retrying once")
        response = get_vision_backend().chat(model, messages, images=[image_bytes], num_ctx=nctx)
        return _parse_llm_response(response)


def extract_document(
    file_bytes: bytes,
    content_type: str,
    model: Optional[str] = None,
    language: str = "en",
) -> dict:
    """Main extraction entry point. Routes to text or vision model based on content.

    Returns dict with keys: extracted_text, entities
    """
    model = model or get_model("extract")

    extracted_text = ""
    entities = {}

    if content_type == "application/pdf":
        text, images = extract_text_from_pdf(file_bytes)
        extracted_text = text

        # If substantial text found, use text model; otherwise vision
        if len(text.strip()) > 100:
            logger.info("PDF has substantial text (%d chars), using text model", len(text))
            entities = call_ollama_text(text, model, language)
        elif images:
            logger.info("PDF has little text, using vision model on first page")
            entities = call_ollama_vision(images[0], model, language)
        else:
            return {"extracted_text": "", "entities": {}}
    elif content_type in ("image/png", "image/jpeg", "image/jpg"):
        logger.info("Image file, using vision model")
        entities = call_ollama_vision(file_bytes, model, language)
    else:
        raise ValueError(f"Unsupported content type: {content_type}")

    if isinstance(entities, dict):
        entities["diagnoses"] = _patients_own(entities.get("diagnoses") or [])
    return {
        "extracted_text": extracted_text,
        "entities": entities,
    }


# A laboratory report states measurements. The diagnosis is made afterwards, by a
# clinician, in a different document — so a diagnosis extracted from one of these
# can only ever be the model's own inference. Same reasoning as ADR 028, which
# took the lab values themselves away from the model for being unreliable there.
_VALUES_ONLY_TYPES = {"lab_report"}

# A form to be filled in is a list of conditions phrased as questions
# ("Epilepsie? ja / nein"). Whatever is ticked on it, it asserts nothing a
# clinician stated, so it yields no clinical data at all (#259, ADR 047).
_NO_CLINICAL_TYPES = {"questionnaire"}

# A diagnosis names a condition; only "present" asserts it of the patient.
# "family" is a relative's, "absent" is ruled out or answered no (#259).
# "suspected" is kept but marked, FHIR's verificationStatus "provisional" (#271).
_NOT_THE_PATIENTS = {"family", "absent"}


def extract_entities_from_text(
    text: str,
    document_type: Optional[str] = None,
    model: Optional[str] = None,
    language: str = "en",
) -> dict:
    """Extract structured entities from already-OCR'd text.

    Used by the new pipeline (Step 3: extraction stage) where OCR and
    classification have already happened.

    Returns dict with key: entities
    """
    model = model or get_model("extract")

    extra = ""
    if document_type:
        extra = f"\nThis document has been classified as: {document_type}\n"

    # Lab tables are parsed deterministically from the OCR HTML (exact, no LLM
    # guessing, no timeout, ADR 028). Tell the model to skip observations so its
    # output stays small and fast; we inject the parsed rows afterwards.
    lab_obs = parse_lab_tables(text)
    if lab_obs:
        extra += (
            "\nThe lab result tables are already captured separately. Return an empty "
            '"observations" array and focus on summary and appointments.\n'
        )
    if document_type in _VALUES_ONLY_TYPES:
        extra += (
            "\nThis is a laboratory report. It reports measurements; it does not make "
            'diagnoses. Return empty "diagnoses" and "medications" arrays even if values '
            "lie outside their reference ranges, even if the report names a finding such "
            "as Anisozytose, and even if it prints a legend or a conditional sentence "
            "about what a value might mean.\n"
        )

    if document_type in _NO_CLINICAL_TYPES:
        extra += (
            "\nThis is a form to be filled in. Its questions name conditions without "
            'stating that the patient has them. Return empty "diagnoses", "medications" '
            'and "observations" arrays, whatever is ticked or written in.\n'
        )

    entities = call_ollama_text(extra + text, model, language)
    # The deterministic lab values must not depend on the LLM producing valid JSON —
    # some models return null/invalid here; still surface the parsed observations.
    if not isinstance(entities, dict):
        entities = {}
    if lab_obs:
        entities["observations"] = lab_obs
    if document_type in _VALUES_ONLY_TYPES:
        # The instruction above is a request; this is the guarantee. Every
        # fabricated diagnosis found on 2026-07-27 came off a laboratory report,
        # in three different ways: derived from a value alone (Hyperkaliämie),
        # promoted from a lab remark that names a finding (Anisozytose), and read
        # off a legend the laboratory itself printed ("10 - 20 ug/l : Mangel"
        # beside a vitamin D of 14). A prompt rule catches the first only, and
        # models ignored it in 1 run out of 5 anyway. A report of measurements
        # cannot be a source of diagnoses, so nothing here has to be trusted.
        _drop(entities, ("diagnoses", "medications"), "lab report")
    if document_type in _NO_CLINICAL_TYPES:
        _drop(entities, ("diagnoses", "medications", "observations"), "questionnaire")
    entities["diagnoses"] = _patients_own(entities.get("diagnoses") or [])
    # No confidence score: the model gives us none. The 0.85 that used to sit here
    # was invented, and the threshold that read it was never wired up — a fake
    # number is worse than an honest absence (#111).
    return {"entities": entities}


# Counts only: condition names are health data, and log entries are stored in
# plaintext and streamed to the admin UI.
def _drop(entities: dict, fields: tuple, reason: str) -> None:
    for field in fields:
        dropped = entities.get(field) or []
        if dropped:
            logger.info("%s: dropped %d %s from extraction", reason, len(dropped), field)
        entities[field] = []


def _patients_own(diagnoses: list) -> list:
    """Keep diagnoses asserted of the patient; an unlabelled one is kept."""
    kept = [d for d in diagnoses
            if not (isinstance(d, dict) and d.get("assertion") in _NOT_THE_PATIENTS)]
    if len(kept) < len(diagnoses):
        logger.info("dropped %d diagnoses not asserted of the patient", len(diagnoses) - len(kept))
    for d in kept:
        if isinstance(d, dict) and d.pop("assertion", None) == "suspected":
            d["verification_status"] = "provisional"
    return kept
