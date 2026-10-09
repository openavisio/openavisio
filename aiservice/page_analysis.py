"""Cheap, model-free page-quality analysis to route OCR (ADR 028, #73).

Pillow-only (no numpy/cv2). Produces the signals that decide whether a rendered
page can go to the fast structured parser (dots.ocr) or must escalate to the
reasoning VLM (Qwen3-VL): sharpness (blur), table-ratio, dark-pixel ratio.
"""
from __future__ import annotations

import io

from PIL import Image, ImageFilter, ImageStat

# Discrete Laplacian; variance of its response is the classic focus/blur measure.
_LAPLACIAN = ImageFilter.Kernel((3, 3), [0, 1, 0, 1, -4, 1, 0, 1, 0], scale=1)

# ponytail: thresholds are calibration knobs — tune on real scans+photos, not sacred.
SHARPNESS_MIN = 40.0   # below → likely blurry → escalate to the reasoning VLM
TABLE_MIN = 0.30       # fraction of text rows with ≥3 column segments → table-like


def _load(image_bytes: bytes) -> Image.Image:
    return Image.open(io.BytesIO(image_bytes))


def sharpness(img: Image.Image) -> float:
    """Variance of the Laplacian response. Low = blurry, high = crisp edges."""
    edges = img.convert("L").filter(_LAPLACIAN)
    return ImageStat.Stat(edges).var[0]


def _binary_rows(img: Image.Image, width: int = 400):
    """Downscale to `width`, return (cols, rows, dark[y][x] bool) with a global threshold."""
    g = img.convert("L")
    h = max(1, round(g.height * width / g.width))
    g = g.resize((width, h))
    px = list(g.getdata())
    # Otsu-lite: threshold at (mean - 0.5*stdev) so light grey shading stays "background".
    stat = ImageStat.Stat(g)
    thr = max(0.0, stat.mean[0] - 20)
    dark = [[px[y * width + x] < thr for x in range(width)] for y in range(h)]
    return width, h, dark


def table_ratio(img: Image.Image) -> float:
    """Fraction of text rows split into ≥3 column segments by clear whitespace gutters.

    A multi-column table (label | value | range | unit) scores high; prose — one wide
    ink band per line — scores low. Works without ruled grid lines.
    """
    cols, rows, dark = _binary_rows(img)
    gutter = max(3, cols // 50)  # a gap this many empty columns wide separates table columns
    text_rows = 0
    multi_col_rows = 0
    for y in range(rows):
        row = dark[y]
        ink = sum(row)
        if ink < cols * 0.02:  # near-empty row, skip
            continue
        text_rows += 1
        segments, run_empty, in_segment = 0, 0, False
        for x in range(cols):
            if row[x]:
                if not in_segment:
                    segments += 1
                    in_segment = True
                run_empty = 0
            else:
                run_empty += 1
                if run_empty >= gutter:
                    in_segment = False
        if segments >= 3:
            multi_col_rows += 1
    return multi_col_rows / text_rows if text_rows else 0.0


def dark_ratio(img: Image.Image) -> float:
    """Share of dark pixels — near-0 means blank/photo-of-nothing, flags empty pages."""
    cols, rows, dark = _binary_rows(img)
    total = cols * rows
    return sum(sum(r) for r in dark) / total if total else 0.0


def analyze_page(image_bytes: bytes) -> dict:
    img = _load(image_bytes)
    s = sharpness(img)
    t = table_ratio(img)
    d = dark_ratio(img)
    return {
        "sharpness": round(s, 1),
        "table_ratio": round(t, 3),
        "dark_ratio": round(d, 4),
        "blurry": s < SHARPNESS_MIN,
        "table_like": t >= TABLE_MIN,
    }


def needs_fallback(metrics: dict, ocr_confidence: float | None = None) -> bool:
    """Escalate to the reasoning VLM when the page is blurry or the parser was unsure."""
    if metrics.get("blurry"):
        return True
    if ocr_confidence is not None and ocr_confidence < 0.5:
        return True
    return False


if __name__ == "__main__":
    from PIL import ImageDraw

    def png(img: Image.Image) -> bytes:
        b = io.BytesIO(); img.save(b, "PNG"); return b.getvalue()

    # Sharp high-frequency pattern vs its blurred copy → sharpness must drop.
    sharp = Image.new("L", (200, 200), 255)
    d = ImageDraw.Draw(sharp)
    for x in range(0, 200, 4):
        d.line([(x, 0), (x, 200)], fill=0)
    blurred = sharp.filter(ImageFilter.GaussianBlur(3))
    assert sharpness(sharp) > sharpness(blurred), "blur must lower sharpness"

    # Multi-column table vs a solid prose block → table_ratio must be higher for the table.
    table = Image.new("L", (400, 300), 255)
    dt = ImageDraw.Draw(table)
    for y in range(10, 290, 20):
        for cx in (20, 160, 260, 340):   # 4 columns
            dt.rectangle([cx, y, cx + 40, y + 8], fill=0)
    prose = Image.new("L", (400, 300), 255)
    dp = ImageDraw.Draw(prose)
    for y in range(10, 290, 20):
        dp.rectangle([20, y, 380, y + 8], fill=0)  # one wide band per line
    assert table_ratio(table) > 0.5, table_ratio(table)
    assert table_ratio(prose) < 0.2, table_ratio(prose)

    # Blank page → almost no dark pixels.
    assert dark_ratio(Image.new("L", (200, 200), 255)) < 0.01
    print("ok")
