#!/usr/bin/env python3
"""Link preview image (Facebook, WhatsApp, iMessage …) with the newest records: a strip of real covers + the wordmark.
Writes og/new-<yymmdd>.jpg (1200×630), points the og:image / twitter:image tags of index.html and all/index.html
to it and keeps only the last 3 images. Runs in GitHub Actions after each daily update."""
import datetime as dt, glob, json, os, re, sys
sys.path.insert(0, os.path.dirname(__file__))
from PIL import Image, ImageDraw
import digs

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SITE = "https://monthlyvinyl.net"
W, H = 1200, 630
COLS, ROWS, S = 5, 2, 240                      # 5 × 2 covers of 240 px = 1200 × 480, band of 150 px below
BG, YEL, FG, MUTED = (13, 13, 13), (251, 237, 79), (236, 235, 231), (160, 164, 169)

def picks(data, n=COLS * ROWS):
    G = {}
    for s in data["shops"]:
        for it in s.get("items") or []:
            G.setdefault(digs.gkey(it), []).append(dict(it, shop=s["shop"]))
    recs = []
    for k, arr in G.items():
        first = min((x.get("first_seen") or "0000") for x in arr)
        recs.append((first, len({x["shop"] for x in arr}), k, arr))
    recs.sort(key=lambda r: (r[0], r[1]), reverse=True)          # newest day first, records in several shops first
    out, labels, artists = [], set(), set()
    for first, nshop, k, arr in recs[:160]:
        a = digs.norm(arr[0]["a"])
        lab = digs.norm(arr[0].get("l") or "")
        if a in artists or (lab and lab in labels):              # variety: one record per artist and label
            continue
        try:
            im = digs.get_cover(arr, False, 0)
        except Exception as e:
            digs.log("no cover", k, e)
            continue
        if im.info.get("art", 0) < 1 or min(im.size) < 300:      # real artwork only (no label photos, blank sleeves)
            continue
        out.append(im.resize((S, S), Image.LANCZOS))
        artists.add(a); labels.add(lab)
        digs.log("cover", first, arr[0]["a"], "–", arr[0]["t"], im.info.get("art"))
        if len(out) == n:
            break
    return out

def render(covers, path):
    img = Image.new("RGB", (W, H), BG)
    for i, c in enumerate(covers):
        img.paste(c, ((i % COLS) * S, (i // COLS) * S))
    d = ImageDraw.Draw(img)
    y = ROWS * S
    d.rectangle([0, y, W, H], fill=BG)
    d.rectangle([0, y, W, y + 3], fill=YEL)
    f = digs.F(64, True)
    d.text((48, y + 92), "MONTHLY VINYL", font=f, fill=YEL, anchor="ls", stroke_width=2, stroke_fill=YEL)
    d.text((W - 48, y + 66), "New vinyl from independent record shops", font=digs.F(26, False), fill=FG, anchor="rs")
    d.text((W - 48, y + 104), "Listen. Compare. Buy at the shop.", font=digs.F(26, False), fill=MUTED, anchor="rs")
    img.save(path, quality=86, optimize=True, progressive=True)

def point_tags(url):
    for rel in ("index.html", "all/index.html"):
        p = os.path.join(ROOT, rel)
        s = open(p, encoding="utf-8").read()
        s2 = re.sub(r'(<meta property="og:image" content=")[^"]*(")', r"\g<1>%s\2" % url, s)
        s2 = re.sub(r'(<meta name="twitter:image" content=")[^"]*(")', r"\g<1>%s\2" % url, s2)
        if 'property="og:image:type"' not in s2:
            s2 = s2.replace('<meta property="og:image:width"', '<meta property="og:image:type" content="image/jpeg">\n<meta property="og:image:width"', 1)
        if s2 != s:
            open(p, "w", encoding="utf-8").write(s2)

def main():
    data = json.load(open(os.path.join(ROOT, "releases.json"), encoding="utf-8"))
    ymd = data["updated"].replace("-", "")[2:]
    os.makedirs(os.path.join(ROOT, "og"), exist_ok=True)
    name = "new-%s.jpg" % ymd
    path = os.path.join(ROOT, "og", name)
    if os.path.exists(path) and "--force" not in sys.argv:
        digs.log("already done", name)
    else:
        covers = picks(data)
        if len(covers) < COLS * ROWS:
            raise SystemExit("only %d usable covers" % len(covers))
        render(covers, path)
    point_tags("%s/og/%s" % (SITE, name))
    for old in sorted(glob.glob(os.path.join(ROOT, "og", "new-*.jpg")))[:-3]:
        os.remove(old)
    print(json.dumps({"image": "og/" + name}))

if __name__ == "__main__":
    main()
