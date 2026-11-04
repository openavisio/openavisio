"""Cheap, model-free table detection to route OCR (ADR 028, #73). Pillow-only."""
from __future__ import annotations

import io

from PIL import Image, ImageStat

# ponytail: threshold is a calibration knob, tune on real scans+photos.
TABLE_MIN = 0.30       # fraction of text rows with ≥3 column segments → table-like


def _binary_rows(img: Image.Image, width: int = 400):
    """Downscale to `width`, return (cols, rows, dark[y][x] bool) with a global threshold."""
    g = img.convert("L")
    h = max(1, round(g.height * width / g.width))
    g = g.resize((width, h))
    px = list(g.get_flattened_data())
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


def is_table_like(image_bytes: bytes) -> bool:
    return table_ratio(Image.open(io.BytesIO(image_bytes))) >= TABLE_MIN


if __name__ == "__main__":
    from PIL import ImageDraw

    def png(img: Image.Image) -> bytes:
        b = io.BytesIO()
        img.save(b, "PNG")
        return b.getvalue()

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
    assert is_table_like(png(table)) and not is_table_like(png(prose))
    print("ok")
