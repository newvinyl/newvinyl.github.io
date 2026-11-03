#!/usr/bin/env python3
"""Artist-photo slide for an Instagram carousel (TEST since 3.11.26, not part of the daily automation).
Same look as the fresh carousel slides (4:5, dark, yellow type). The photo is only cropped/scaled, never altered.
Only use photos with a clear permission (press kit "free for promotional use", or sent by artist/label);
the credit line is mandatory.

  python3 tools/photo_slide.py PHOTO.jpg "Artist name" "Photo: Name" OUT.jpg [--sub "short line"] [--focus 0.35]

--focus: vertical crop position 0..1 (0 = top, default 0.3 so faces in portraits stay in frame)."""
import argparse, os, sys
sys.path.insert(0, os.path.dirname(__file__))
from PIL import Image, ImageDraw, ImageOps
import digs

W, H = 1080, 1350
BG, INK = (13, 13, 13), (251, 237, 79)
FAINT = tuple(int(b + (c - b) * .25) for b, c in zip(BG, INK))
PW, PH = 880, 1000            # photo area (portrait), same left edge as the cover slides

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("photo"); ap.add_argument("name"); ap.add_argument("credit"); ap.add_argument("out")
    ap.add_argument("--sub", default="")
    ap.add_argument("--focus", type=float, default=0.3)
    a = ap.parse_args()
    if not a.credit.strip():
        raise SystemExit("credit is mandatory")
    ph = ImageOps.exif_transpose(Image.open(a.photo)).convert("RGB")
    if min(ph.size) < 500:
        print("warning: small photo %dx%d" % ph.size, file=sys.stderr)
    r = max(PW / ph.width, PH / ph.height)
    ph = ph.resize((round(ph.width * r), round(ph.height * r)), Image.LANCZOS)
    x0 = (ph.width - PW) // 2
    y0 = int((ph.height - PH) * min(1, max(0, a.focus)))
    ph = ph.crop((x0, y0, x0 + PW, y0 + PH))
    im = Image.new("RGB", (W, H), BG)
    im.paste(ph, (100, 60))
    d = ImageDraw.Draw(im)
    d.rectangle([100, 1086, 980, 1088], fill=FAINT)
    digs.txt(d, (100, 1160), a.name, 64, INK, maxw=880)
    if a.sub:
        digs.txt(d, (102, 1214), a.sub, 34, INK, bold=False, maxw=880)
    digs.txt(d, (102, 1262), a.credit, 26, INK, bold=False, maxw=880)
    digs.txt(d, (980, 1302), "monthlyvinyl.net", 34, INK, anchor="rs", maxw=400)
    im.save(a.out, quality=92)
    print(a.out)

if __name__ == "__main__":
    main()
