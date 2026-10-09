"""
OCR module: Tesseract/OCRmyPDF-based text extraction from PDFs and images.
"""

import io
import logging
import subprocess
import tempfile
from pathlib import Path

logger = logging.getLogger(__name__)


def ocr_pdf(file_bytes: bytes) -> dict:
    """Run OCRmyPDF on a PDF, return extracted text + confidence.

    Returns:
        {"text": str, "confidence": float, "method": "tesseract"}
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        input_path = Path(tmpdir) / "input.pdf"
        output_path = Path(tmpdir) / "output.pdf"
        sidecar_path = Path(tmpdir) / "sidecar.txt"

        input_path.write_bytes(file_bytes)

        try:
            subprocess.run(
                [
                    "ocrmypdf",
                    "--force-ocr",
                    "--sidecar", str(sidecar_path),
                    "-l", "deu+eng",
                    "--tesseract-timeout", "120",
                    str(input_path),
                    str(output_path),
                ],
                capture_output=True,
                text=True,
                timeout=180,
                check=True,
            )
        except subprocess.CalledProcessError as e:
            logger.warning("OCRmyPDF failed: %s", e.stderr)
            # Fallback: try without --force-ocr (already has text layer)
            try:
                subprocess.run(
                    [
                        "ocrmypdf",
                        "--skip-text",
                        "--sidecar", str(sidecar_path),
                        "-l", "deu+eng",
                        str(input_path),
                        str(output_path),
                    ],
                    capture_output=True,
                    text=True,
                    timeout=180,
                    check=True,
                )
            except subprocess.CalledProcessError as e2:
                logger.error("OCRmyPDF fallback also failed: %s", e2.stderr)
                return {"text": "", "confidence": 0.0, "method": "tesseract"}

        text = sidecar_path.read_text(encoding="utf-8").strip() if sidecar_path.exists() else ""
        confidence = _get_tesseract_confidence_pdf(file_bytes)

        return {"text": text, "confidence": confidence, "method": "tesseract"}


def ocr_image(file_bytes: bytes) -> dict:
    """Run pytesseract on an image, return extracted text + confidence.

    Returns:
        {"text": str, "confidence": float, "method": "tesseract"}
    """
    import pytesseract
    from PIL import Image

    image = Image.open(io.BytesIO(file_bytes))
    text = pytesseract.image_to_string(image, lang="deu+eng")

    # Get word-level confidence
    data = pytesseract.image_to_data(image, lang="deu+eng", output_type=pytesseract.Output.DICT)
    confidences = [int(c) for c in data["conf"] if int(c) > 0]
    avg_confidence = (sum(confidences) / len(confidences) / 100.0) if confidences else 0.0

    return {"text": text.strip(), "confidence": avg_confidence, "method": "tesseract"}


def _get_tesseract_confidence_pdf(file_bytes: bytes) -> float:
    """Extract average word confidence from first page of PDF via pytesseract."""
    try:
        import pypdfium2 as pdfium
        import pytesseract

        doc = pdfium.PdfDocument(file_bytes)
        if len(doc) == 0:
            return 0.0

        # Render first page
        bitmap = doc[0].render(scale=200 / 72)
        img = bitmap.to_pil()
        doc.close()

        data = pytesseract.image_to_data(img, lang="deu+eng", output_type=pytesseract.Output.DICT)
        confidences = [int(c) for c in data["conf"] if int(c) > 0]
        return (sum(confidences) / len(confidences) / 100.0) if confidences else 0.0
    except Exception as e:
        logger.warning("Could not compute PDF OCR confidence: %s", e)
        return 0.5  # Unknown confidence
