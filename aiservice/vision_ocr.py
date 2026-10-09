"""
Vision model OCR fallback: use vision model to extract text from images.
Always uses Ollama backend (vLLM vision support is limited).
"""

import io
import logging

import pypdfium2 as pdfium

from backend import get_vision_backend, get_model, get_num_ctx
from image_prep import deshade
from page_analysis import analyze_page

logger = logging.getLogger(__name__)


VISION_OCR_PROMPT = (
    "Extract ALL text from this medical document image. "
    "Return ONLY the raw text content, preserving structure and formatting. "
    "Do not summarize or interpret — just transcribe exactly what you see."
)

# GLM-OCR's Ollama build expects task-style prompts, not free-form instructions
# (https://ollama.com/library/glm-ocr). Text pages → "Text Recognition:", table pages →
# "Table Recognition:" (emits an HTML <table> with value/reference in separate cells, so
# the extractor can't confuse them — ADR 028). Other vision models get the generic prompt.
_GLM = "glm-ocr"


def _ocr_prompt(model: str, table: bool = False) -> str:
    if _GLM in model.lower():
        return "Table Recognition:" if table else "Text Recognition:"
    return VISION_OCR_PROMPT


def vision_ocr(file_bytes: bytes, content_type: str, model: str | None = None) -> dict:
    """Extract text from file using vision model.

    Returns:
        {"text": str, "confidence": None, "method": "vision"}
    """
    model = model or get_model("vision")
    backend = get_vision_backend()

    if content_type == "application/pdf":
        return _vision_ocr_pdf(file_bytes, backend, model)
    else:
        return _vision_ocr_image(file_bytes, backend, model)


def _vision_ocr_image(image_bytes: bytes, backend, model: str) -> dict:
    """Vision OCR on a single image."""
    from PIL import Image
    buf = io.BytesIO()
    deshade(Image.open(io.BytesIO(image_bytes))).save(buf, format="PNG")  # ADR 028
    img = buf.getvalue()
    table = analyze_page(img)["table_like"]
    text = backend.chat(
        model,
        [{"role": "user", "content": _ocr_prompt(model, table)}],
        images=[img],
        num_ctx=get_num_ctx("vision"),  # else the model loads at its 32k default (#73)
    )
    # No confidence: the model gives us none, and a constant dressed up as a
    # measurement is worse than an honest absence — it was shown to users as
    # "OCR confidence 70%" (#111).
    return {"text": text.strip(), "confidence": None, "method": "vision"}


def _vision_ocr_pdf(file_bytes: bytes, backend, model: str) -> dict:
    """Vision OCR: render each PDF page and extract text via vision model."""
    doc = pdfium.PdfDocument(file_bytes)
    all_text = []
    page_count = len(doc)

    for i, page in enumerate(doc):
        bitmap = page.render(scale=200 / 72)
        pil_image = deshade(bitmap.to_pil())  # ADR 028: recover grey-shaded table columns
        buf = io.BytesIO()
        pil_image.save(buf, format="PNG")
        img_bytes = buf.getvalue()

        table = analyze_page(img_bytes)["table_like"]
        logger.info("Vision OCR on page %d/%d (%s)", i + 1, page_count, "table" if table else "text")
        text = backend.chat(
            model,
            [{"role": "user", "content": _ocr_prompt(model, table)}],
            images=[img_bytes],
            num_ctx=get_num_ctx("vision"),  # else the model loads at its 32k default (#73)
        )
        all_text.append(text.strip())

    doc.close()
    text = "\n\n".join(all_text)
    return {"text": text, "confidence": None, "method": "vision"}
