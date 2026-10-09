#!/usr/bin/env python3
"""Regenerate frontend/public/icon-{192,512}.png from frontend/public/logo.png.

Run after changing the logo: python3 scripts/generate-pwa-icons.py
Requires Pillow.
"""
from pathlib import Path

from PIL import Image

public = Path(__file__).resolve().parent.parent / "frontend" / "public"
img = Image.open(public / "logo.png")
img = img.crop(img.getbbox())  # trim transparent border
side = int(max(img.size) * 1.2)  # 10% margin each side
canvas = Image.new("RGBA", (side, side), (0, 0, 0, 0))
canvas.paste(img, ((side - img.width) // 2, (side - img.height) // 2), img)
for s in (192, 512):
    canvas.resize((s, s), Image.LANCZOS).save(public / f"icon-{s}.png")
    print(f"wrote icon-{s}.png")
