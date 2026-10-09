"""Pre-OCR image cleanup (ADR 028, #73).

De-shade + contrast-normalise a rendered page before the vision model. The
motivating failure: lab reports shade the result column light grey, and
flat-text OCR drops those cells. Knocking the light shading to white while
keeping dark text makes the values legible to any model. Pillow-only.
"""
from __future__ import annotations

import io

from PIL import Image, ImageOps


def deshade(img: Image.Image, black: int = 60, white: int = 170) -> Image.Image:
    """Grayscale + autocontrast + a levels curve that maps light grey → white.

    Text (dark, < black) stays black; shading (light, > white) becomes white; the
    ramp in between preserves anti-aliased digit edges.
    ponytail: black/white are calibration knobs — tune per scanner/photo; no deskew yet.
    """
    g = ImageOps.autocontrast(img.convert("L"), cutoff=1)
    span = max(1, white - black)
    lut = [0 if p < black else 255 if p > white else round((p - black) * 255 / span) for p in range(256)]
    return g.point(lut)


def preprocess_bytes(image_bytes: bytes, fmt: str = "PNG") -> bytes:
    out = io.BytesIO()
    deshade(Image.open(io.BytesIO(image_bytes))).save(out, fmt)
    return out.getvalue()


if __name__ == "__main__":
    import sys
    from PIL import ImageDraw

    # Dark text on a light-grey shaded band: text must survive, shading must go white.
    im = Image.new("L", (120, 40), 255)
    d = ImageDraw.Draw(im)
    d.rectangle([0, 0, 120, 40], fill=210)      # light-grey shading
    d.text((6, 12), "14.1", fill=40)            # dark result value
    out = deshade(im)
    px = list(out.getdata())
    assert max(px) == 255, "shading should reach white"
    assert min(px) == 0, "text should stay black"
    white_frac = sum(1 for p in px if p == 255) / len(px)
    assert white_frac > 0.7, f"most of the band should whiten, got {white_frac:.2f}"
    print("ok")

    # CLI: python image_prep.py in.jpg out.png
    if len(sys.argv) == 3:
        deshade(Image.open(sys.argv[1])).save(sys.argv[2])
        print("wrote", sys.argv[2])
