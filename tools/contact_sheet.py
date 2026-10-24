"""Tile unit preview strips into one review sheet.  python3 tools/contact_sheet.py [frame] [out]"""
import json
import os
import sys

from PIL import Image, ImageDraw, ImageFont

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PREV = os.path.join(ROOT, "docs", "renders", "units")
frame = int(sys.argv[1]) if len(sys.argv) > 1 else 0
out = sys.argv[2] if len(sys.argv) > 2 else os.path.join(ROOT, "docs", "renders", "roster.png")
order = ["cat", "dog", "ham", "hare", "rat"]
files = sorted(f for f in os.listdir(PREV) if f.endswith(".png"))
files.sort(key=lambda f: (order.index(f.split("_")[0]), f))
meta = {}
mp = os.path.join(ROOT, "assets", "animal_kingdoms", "units", "units.json")
if os.path.exists(mp):
    meta = json.load(open(mp))
cells = []
for f in files:
    im = Image.open(os.path.join(PREV, f))
    n = max(1, round(im.width / (im.height * 600 / 720)))
    w = im.width // n
    crop = im.crop((w * frame, 60, w * (frame + 1), im.height - 60)).resize((300, 300))
    cells.append((f[:-4], crop))
cols = 6
rows = (len(cells) + cols - 1) // cols
sheet = Image.new("RGB", (cols * 300, rows * 330), (24, 26, 30))
d = ImageDraw.Draw(sheet)
try:
    font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 14)
except OSError:
    font = ImageFont.load_default()
for i, (uid, im) in enumerate(cells):
    x, y = (i % cols) * 300, (i // cols) * 330
    sheet.paste(im, (x, y))
    label = meta.get(uid, {}).get("name", uid)
    d.text((x + 8, y + 306), label, fill=(235, 230, 215), font=font)
sheet.save(out)
print(out, len(cells))
