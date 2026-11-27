#!/usr/bin/env python3
"""Static link preview image per genre page: og/genre-<slug>.jpg (1200x630), same look as og/new-*.jpg.
Creates only missing images (python3 tools/og_genre.py --force renders all again). build_static.py uses
the image when it exists, otherwise og-image-v2.png. No network needed."""
import os, re, sys
sys.path.insert(0, os.path.dirname(__file__))
from PIL import Image, ImageDraw, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
FONTS = {True: os.path.join(HERE, "fonts", "texgyreheros-bold.otf"), False: os.path.join(HERE, "fonts", "texgyreheros-regular.otf")}
class digs:  # gleiche Schrift wie og_image.py, ohne dessen schwere Abhängigkeiten
    @staticmethod
    def F(size, bold=True):
        return ImageFont.truetype(FONTS[bold], size)

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
W, H = 1200, 630
BG, YEL, FG, MUTED = (13, 13, 13), (251, 237, 79), (236, 235, 231), (160, 164, 169)

def fit(d, text, maxw, size):
    while size > 40 and d.textlength(text, font=digs.F(size, True)) > maxw:
        size -= 4
    return digs.F(size, True)

def render(name, path):
    img = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(img)
    d.rectangle([0, 0, W, 10], fill=YEL)
    d.text((72, 150), "NEW", font=digs.F(40, True), fill=MUTED, anchor="ls")
    f = fit(d, name.upper(), W - 144, 150)
    d.text((72, 330), name.upper(), font=f, fill=FG, anchor="ls", stroke_width=1, stroke_fill=FG)
    d.text((72, 400), "vinyl releases from independent record shops", font=digs.F(34, False), fill=FG, anchor="ls")
    d.rectangle([0, 500, W, 503], fill=YEL)
    d.text((72, 580), "MONTHLY VINYL", font=digs.F(56, True), fill=YEL, anchor="ls", stroke_width=2, stroke_fill=YEL)
    d.text((W - 72, 572), "Listen. Compare. Buy at the shop.", font=digs.F(26, False), fill=MUTED, anchor="rs")
    img.save(path, quality=88, optimize=True, progressive=True)

def main():
    os.makedirs(os.path.join(ROOT, "og"), exist_ok=True)
    n = 0
    for d in sorted(os.listdir(ROOT)):
        f = os.path.join(ROOT, d, "index.html")
        if not os.path.isfile(f): continue
        m = re.search(r'"@type": "CollectionPage", "name": "New (.+?) vinyl releases"', open(f, encoding="utf-8").read(3000))
        if not m: continue
        out = os.path.join(ROOT, "og", f"genre-{d}.jpg")
        if os.path.exists(out) and "--force" not in sys.argv: continue
        render(m.group(1), out); n += 1
    print(f"og_genre: {n} images")

if __name__ == "__main__":
    main()
