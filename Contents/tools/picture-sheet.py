#!/usr/bin/env python3
"""Put pictures of the 3D view side by side, each with a title, one line across the top.

    python3 picture-sheet.py --out sheet.png --title "..." "TS=a.png" "CADS=b.png" ...

Made for the rib comparison of 2026-09-20 (one picture per model, the same camera); any set of
pictures the app's __savePicture wrote works. Each picture is scaled to 1000 px; nothing is cropped.
"""
import argparse
from PIL import Image, ImageDraw, ImageFont

def font(size):
    try: return ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", size)
    except Exception: return ImageFont.load_default()

ap = argparse.ArgumentParser()
ap.add_argument("--out", required=True); ap.add_argument("--title", default="")
ap.add_argument("items", nargs="+", help="title=file.png")
a = ap.parse_args()
tiles = []
for it in a.items:
    title, path = it.split("=", 1)
    im = Image.open(path).convert("RGB"); im.thumbnail((1000, 1000))
    tile = Image.new("RGB", (1000, 1060), (30, 30, 30)); tile.paste(im, (0, 60))
    ImageDraw.Draw(tile).text((14, 14), title, fill=(255, 255, 255), font=font(32))
    tiles.append(tile)
gap = 20
sheet = Image.new("RGB", (len(tiles) * 1000 + (len(tiles) - 1) * gap, 1060 + (70 if a.title else 0)), (30, 30, 30))
y0 = 70 if a.title else 0
if a.title: ImageDraw.Draw(sheet).text((14, 18), a.title, fill=(255, 255, 255), font=font(36))
for i, t in enumerate(tiles): sheet.paste(t, (i * (1000 + gap), y0))
sheet.save(a.out); print("wrote", a.out, sheet.size)
