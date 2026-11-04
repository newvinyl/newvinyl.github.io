#!/usr/bin/env python3
"""Instagram Stories of the day (since 4.11.26): one 9:16 story per record of Today's Digs and of the
«Fresh today» carousel. Reduced and strong: big cover, artist bold, title, monthlyvinyl.net, yellow on black;
@handles (shop, label, artist) as typewriter stickers (white on a black box, slightly tilted) on an edge of
the cover, somewhere else in every story. Audio: the record's preview (digs 10 s, carousel 15 s).

Works from the published release assets only (digs video, carousel slides), no shop access needed:
  python3 tools/stories.py --date 2026-11-04 --work /tmp/st --out stories/261104
Writes story-01.mp4 … and stories.json (file, handles per story) for posting (see tools/instagram_post.md §6)."""
import argparse, json, math, os, random, re, subprocess, sys, urllib.request
from PIL import Image, ImageDraw, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
import coverlife, digs_oneview

REL = "https://github.com/newvinyl/newvinyl.github.io/releases/download/"
FB = os.path.join(HERE, "fonts", "texgyreheros-bold.otf"); FR = os.path.join(HERE, "fonts", "texgyreheros-regular.otf")
TWF = [p for p in ("/usr/share/fonts/truetype/liberation/LiberationMono-Bold.ttf",
                   "/usr/share/fonts/truetype/dejavu/DejaVuSansMono-Bold.ttf") if os.path.exists(p)][0]
Y, BG = (251, 237, 79), (13, 13, 13)
X0, Y0, S = 60, 420, 960            # cover; type below it; everything inside the story safe zone (y 290..1700)
MONTHS = "JAN FEB MAR APR MAY JUN JUL AUG SEP OCT NOV DEC".split()

def get(url, path):
    if not os.path.exists(path):
        urllib.request.urlretrieve(url, path)
    return path

def ff(*a):
    subprocess.run(["ffmpeg", "-v", "error", "-y", *a], check=True)

def fit(t, maxw, size, f):
    while ImageFont.truetype(f, size).getlength(t) > maxw and size > 30:
        size -= 2
    return ImageFont.truetype(f, size)

def sticker(h, ang):
    f = ImageFont.truetype(TWF, 40); t = "@" + h; w = int(f.getlength(t))
    im = Image.new("RGBA", (w + 28, 58), (0, 0, 0, 255))
    ImageDraw.Draw(im).text((14, 30), t, font=f, fill=(255, 255, 255, 255), anchor="lm")
    return im.rotate(ang, expand=True, resample=Image.BICUBIC)

def handles(artist, label, shop):
    """verified handles only: shops from shop_instagram.json, artists / labels / remixers from artist_instagram.json"""
    shops = json.load(open(os.path.join(HERE, "shop_instagram.json"), encoding="utf-8"))
    arts = json.load(open(os.path.join(HERE, "artist_instagram.json"), encoding="utf-8"))
    out = []
    names = [label] + [x.strip() for x in re.split(r" / |, | & | x | vs\.? | feat\.? ", artist, flags=re.I)]
    for n in names:
        e = arts.get((n or "").lower())
        if isinstance(e, dict) and e.get("handle"):
            out.append(e["handle"])
    if shops.get(shop):
        out.append(shops[shop])
    return list(dict.fromkeys(out))

def records(day, work):
    ymd = day[2:].replace("-", "")
    hist = json.load(open(os.path.join(ROOT, "92h6fy", "history.json"), encoding="utf-8"))
    e = next(x for x in hist if x["date"] == day)
    data = json.load(open(os.path.join(ROOT, "releases.json"), encoding="utf-8"))
    by = {}
    for s in data["shops"]:
        for it in s["items"]:
            by.setdefault((it["a"] + "|" + it["t"]).lower(), []).append(dict(it, shop=s["shop"]))
    recs = []
    vid = get(REL + "digs/todays-digs-%s.mp4" % ymd, os.path.join(work, "digs.mp4"))
    dur = float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", vid],
                               capture_output=True, text=True).stdout)
    n = len(e["keys"]); seg = dur / n
    digs_oneview.layout(n)
    for i, (k, t) in enumerate(zip(e["keys"], e["titles"])):
        x, y, s = digs_oneview.slots(i, n)[i]
        fr = os.path.join(work, "f%d.png" % i)
        ff("-ss", "%.2f" % (i * seg + seg * .6), "-i", vid, "-frames:v", "1", fr)
        cov = coverlife.trim_frame(Image.open(fr).convert("RGB").crop((x, y, x + s, y + s)))
        it = (by.get(k) or [{}])[0]
        shop = next((x["shop"] for x in by.get(k, []) if x["shop"].startswith(e["shops"][i].split()[0])), it.get("shop", ""))
        a, ti = t.split(" – ", 1)
        recs.append(dict(kick="TODAY'S DIGS", a=a, t=ti, cover=cov, src=vid, ss=i * seg + .9, dur=min(10, seg - 1),
                         tags=handles(a, it.get("l", ""), shop)))
    try:
        c = json.load(open(get(REL + "carousel/carousel.json", os.path.join(work, "carousel.json"))))
    except Exception:
        c = {}
    if c.get("date") == day:
        for j, s in enumerate(c["slides"]):
            mp4 = get(REL + "carousel/" + s["video"], os.path.join(work, s["video"]))
            jpg = get(REL + "carousel/" + s["video"].replace(".mp4", ".jpg"), os.path.join(work, s["video"].replace(".mp4", ".jpg")))
            cov = Image.open(jpg).convert("RGB").crop((100, 60, 980, 940))      # cover position in genre_carousel slides
            recs.append(dict(kick="FRESH TODAY", a=s["a"], t=s["t"], cover=cov, src=mp4, ss=0, dur=15,
                             tags=handles(s["a"], s.get("l", ""), s["shop"])))
    return recs

def render(recs, day, out):
    d_ = [int(v) for v in day.split("-")]; date_s = "%d %s" % (d_[2], MONTHS[d_[1] - 1])
    prev, meta = [], []
    for k, r in enumerate(recs, 1):
        im = Image.new("RGB", (1080, 1920), BG); d = ImageDraw.Draw(im)
        cov = r["cover"]; s = min(cov.size)
        cov = cov.crop(((cov.width - s) // 2, (cov.height - s) // 2, (cov.width + s) // 2, (cov.height + s) // 2))
        im.paste(cov.resize((S, S), Image.LANCZOS), (X0, Y0))
        d.text((X0, 290), r["kick"] + "  ·  " + date_s, font=ImageFont.truetype(FB, 34), fill=Y, anchor="ls")
        a = r["a"]; fa = fit(a, S, 84, FB); yb = Y0 + S + 100
        if fa.size < 56 and " / " in a:                       # many artists: two lines instead of tiny type
            parts = a.split(" / "); m = (len(parts) + 1) // 2
            lines = [" / ".join(parts[:m]) + " /", " / ".join(parts[m:])]
            fa = fit(max(lines, key=len), S, 64, FB)
            d.text((X0, yb - 4), lines[0], font=fa, fill=Y, anchor="ls"); d.text((X0, yb + 64), lines[1], font=fa, fill=Y, anchor="ls")
            yb += 64
        else:
            d.text((X0, yb), a, font=fa, fill=Y, anchor="ls")
        d.text((X0, yb + 68), r["t"], font=fit(r["t"], S, 54, FR), fill=Y, anchor="ls")
        d.text((X0, 1680), "monthlyvinyl.net", font=ImageFont.truetype(FB, 34), fill=Y, anchor="ls")
        rng = random.Random(day + str(k)); boxes, cs = [], []
        for h in r["tags"]:
            best = None
            for _ in range(1500):
                ang = rng.choice([-1, 1]) * rng.uniform(6, 22); L = sticker(h, ang); w, hh = L.size
                cx, cy = rng.uniform(X0, X0 + S), rng.uniform(Y0 - 40, Y0 + S + 20)
                x, y = int(cx - w / 2), int(cy - hh / 2)
                x = max(20, min(1060 - w, x)); cx = x + w / 2
                if y < 305 or y + hh > Y0 + S + 35:
                    continue                                    # never over the type
                if any(not (x + w + 16 < bx or bx + bw + 16 < x or y + hh + 16 < by or by + bh + 16 < y) for bx, by, bw, bh in boxes):
                    continue
                edge = min(cx - X0, X0 + S - cx, cy - Y0, Y0 + S - cy)                 # on an edge of the cover
                near = min([math.hypot(cx - px, cy - py) for px, py in prev] or [999])  # elsewhere than last story
                sc = rng.random() + min(near, 500) / 250 - abs(edge) / 120
                if best is None or sc > best[0]:
                    best = (sc, x, y, L, cx, cy)
            if best:
                _, x, y, L, cx, cy = best
                im.paste(L, (x, y), L); boxes.append((x, y, L.width, L.height)); cs.append((cx, cy))
        prev = cs
        png = os.path.join(out, "story-%02d.png" % k); mp4 = png[:-4] + ".mp4"
        im.save(png)
        dur = r["dur"]
        ff("-loop", "1", "-framerate", "30", "-i", png, "-ss", "%.2f" % r["ss"], "-t", str(dur), "-i", r["src"],
           "-map", "0:v", "-map", "1:a", "-af", "afade=t=in:d=0.3,afade=t=out:st=%.2f:d=0.8" % (dur - .8), "-t", str(dur),
           "-c:v", "libx264", "-tune", "stillimage", "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "192k",
           "-movflags", "+faststart", mp4)
        meta.append({"file": os.path.basename(mp4), "a": r["a"], "t": r["t"], "tags": r["tags"]})
    json.dump(meta, open(os.path.join(out, "stories.json"), "w"), indent=1, ensure_ascii=False)
    return meta

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--date", required=True); ap.add_argument("--work", required=True); ap.add_argument("--out", required=True)
    ap.add_argument("--max", type=int, default=5)       # max. 5 stories per day (user, 4.11.26)
    a = ap.parse_args()
    os.makedirs(a.work, exist_ok=True); os.makedirs(a.out, exist_ok=True)
    recs = records(a.date, a.work)
    # the 5 with the most verified handles (reach), digs first on a tie; then back in the original order
    keep = sorted(sorted(range(len(recs)), key=lambda i: (-len(recs[i]["tags"]), i))[:a.max])
    for m in render([recs[i] for i in keep], a.date, a.out):
        print(m["file"], m["a"], "–", m["t"], m["tags"])
