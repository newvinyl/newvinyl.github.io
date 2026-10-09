#!/usr/bin/env python3
"""Today's Digs + Reel – picks 3 new releases from releases.json for the feed video
("Sorte 2": 3 x 15 s previews with crossfades, 41 s) and one other release for a 20 s Reel
("Sorte 1"), renders both (1080x1920, H.264/AAC) with tools/reelfx.py (full-width cover,
living psychedelic or dreamy background from the cover colours, cover slowly melting into it)
and writes the hidden page /92h6fy/ with both videos and captions.

Rules (from the user):
- 3 releases, each must have a real mp3 preview (music in the video).
- Priority 1: three different shops (the shop where the release is new today).
- Priority 2: different genres. Price is not decisive.
- Never repeat releases that were already featured (history.json / posted.json).
- Layout and caption follow the "Today's Digs 02.10.26" post.

Usage: python3 tools/digs.py [--date YYYY-MM-DD] [--force] [--offline]
Outputs: <WORK>/digs_<yymmdd>.mp4 + poster jpg, 92h6fy/index.html, caption.txt,
history.json. Uploading the video is done by the workflow.
"""
import argparse, datetime as dt, html, io, itertools, json, math, os, re, subprocess, sys, tempfile, urllib.parse, urllib.request
import hashlib
import numpy as np
from PIL import Image, ImageDraw, ImageFont
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import reelfx

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SLUG = "92h6fy"
OUT = os.path.join(ROOT, SLUG)
REPO = "newvinyl/newvinyl.github.io"
RELEASE_TAG = "digs"

W, H, FPS, DUR, SR, SY = 1080, 1920, 30, 21, 44100, 285
BG, ACC, WH, GR, RULE = (15, 15, 15), (255, 214, 10), (255, 255, 255), (154, 154, 154), (46, 46, 46)
UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_5) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0 Safari/537.36"
SHORT = {"Redeye Records": "Redeye", "Juno Records": "Juno", "OYE Records": "OYE"}
CUR = {"€": "EUR", "£": "GBP", "$": "USD", "CHF": "CHF"}
# preferred cover sources (bigger first), preferred named-track sources
COVER_RANK = ["Phonica", "Yoyaku", "Kompakt", "Rush Hour", "Juno Records", "Decks.de", "Redeye Records", "Hardwax", "Clone"]

# ---------------------------------------------------------------- helpers
def log(*a):
    print(*a, file=sys.stderr, flush=True)

def norm(s):
    return (s or "").lower().strip()

def gkey(it):
    return norm(it.get("a")) + "|" + norm(it.get("t"))

def short(shop):
    return SHORT.get(shop, shop)

def family(g):
    g = norm(g)
    if any(x in g for x in ("ambient", "downtempo", "balearic")):
        return "Ambient"
    if any(x in g for x in ("disco", "italo", "edit", "cosmic")):
        return "Disco"
    if any(x in g for x in ("electro", "breakbeat")):
        return "Electro"
    if "techno" in g:
        return "Techno"
    if any(x in g for x in ("house", "minimal")):
        return "House"
    return g.title() or "Electronic"

def genre_label(g):
    g = (g or "").split("·")[0]
    first = g.split("/")[0].strip()
    return (first or "Electronic").upper()

def fetch(url, timeout=40):
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "*/*", "Referer": urllib.parse.urljoin(url, "/")})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read()

def font_path(bold):
    cands = (["/usr/share/texmf/fonts/opentype/public/tex-gyre/texgyreheros-bold.otf",
              "/usr/share/fonts/opentype/tex-gyre/texgyreheros-bold.otf",
              "/usr/share/fonts/opentype/inter/Inter-Bold.otf",
              "/usr/share/fonts/truetype/liberation2/LiberationSans-Bold.ttf",
              "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
              "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"] if bold else
             ["/usr/share/texmf/fonts/opentype/public/tex-gyre/texgyreheros-regular.otf",
              "/usr/share/fonts/opentype/tex-gyre/texgyreheros-regular.otf",
              "/usr/share/fonts/opentype/inter/Inter-Regular.otf",
              "/usr/share/fonts/truetype/liberation2/LiberationSans-Regular.ttf",
              "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
              "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"])
    for p in cands:
        if os.path.exists(p):
            return p
    raise SystemExit("no font found")

FB, FR = font_path(True), font_path(False)
FSYM = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
_fc = {}
def F(size, bold=True, sym=False):
    k = (size, bold, sym)
    if k not in _fc:
        _fc[k] = ImageFont.truetype(FSYM if sym and os.path.exists(FSYM) else (FB if bold else FR), size)
    return _fc[k]

# ---------------------------------------------------------------- selection
def load_seen(skip_day=None):
    seen = set()
    for name in ("history.json", "posted.json"):
        p = os.path.join(OUT, name)
        if os.path.exists(p):
            d = json.load(open(p, encoding="utf-8"))
            for e in d if isinstance(d, list) else d.get("days", []):
                if skip_day and e.get("date") == skip_day:
                    continue
                for k in e.get("keys", []):
                    seen.add(k)
                if e.get("reel"):
                    seen.add(e["reel"].get("key"))
    return seen

def playable(arr):
    """Tracks with a direct mp3, named ones first, one list per release."""
    out, names = [], set()
    for x in arr:
        for t in x.get("tr") or []:
            u = t.get("u")
            if not u:
                continue
            n = (t.get("n") or "").strip()
            out.append({"n": n, "u": u, "shop": x["shop"], "named": bool(n) and n.lower() != "preview"})
    out.sort(key=lambda t: (not t["named"],))
    return out

def candidates(data, day, seen):
    yday = (dt.date.fromisoformat(day) - dt.timedelta(days=1)).isoformat()
    G = {}
    for s in data["shops"]:
        for it in s.get("items") or []:
            x = dict(it, shop=s["shop"], cur=s.get("cur", "€"), country=s.get("country", ""))
            G.setdefault(gkey(it), []).append(x)
    cands = []
    for k, arr in G.items():
        if k in seen:
            continue
        # Gleiche Regel wie «Fresh today» auf der Website: zählt nur, wenn die Platte
        # heute zum ersten Mal in IRGENDEINEM Shop auftaucht (frühestes first_seen)
        first = min((x.get("first_seen") or (x.get("m", "0000-00") + "-01")) for x in arr)
        if first != day:
            continue
        new_here = [x for x in arr if x.get("first_seen") == day]
        if not new_here:
            continue
        tr = playable(arr)
        if not tr:
            continue
        strict = not any(x.get("first_seen") and x["first_seen"] < yday for x in arr)
        shops_with_price = len({x["shop"] for x in arr if x.get("p") is not None})
        for x in new_here:
            score = (2.0 if strict else 0.0) + 0.35 * min(shops_with_price, 4) + (0.4 if tr[0]["named"] else 0)
            score += 0.3 if any(y["shop"] in COVER_RANK[:3] for y in arr) else 0
            cands.append({"key": k, "arr": arr, "feat": x, "shop": x["shop"], "fam": family(x.get("g")),
                          "strict": strict, "tracks": tr, "score": score})
    cands.sort(key=lambda c: -c["score"])
    return cands

# ---------------------------------------------------------------- faces
# Instagram belohnt Gesichter: Covers mit Gesicht zuerst, dann Covers mit Menschen.
_cv = None
def _cvlib():
    global _cv
    if _cv is None:
        try:
            import cv2
            d = cv2.data.haarcascades
            _cv = (cv2, cv2.CascadeClassifier(d + "haarcascade_frontalface_default.xml"),
                   cv2.CascadeClassifier(d + "haarcascade_profileface.xml"),
                   cv2.CascadeClassifier(d + "haarcascade_upperbody.xml"))
            hog = cv2.HOGDescriptor(); hog.setSVMDetector(cv2.HOGDescriptor_getDefaultPeopleDetector())
            _cv = _cv + (hog,)
        except Exception as e:
            log("opencv unavailable, no face check", e)
            _cv = False
    return _cv

def vis_level(im):
    """2 = face, 1 = person, 0 = neither."""
    lib = _cvlib()
    if not lib:
        return 0
    cv2, front, prof, upper, hog = lib
    g = np.array(im.convert("L").resize((400, 400)))
    g = cv2.equalizeHist(g)
    ms = (34, 34)
    if len(front.detectMultiScale(g, 1.1, 7, minSize=ms)) or len(prof.detectMultiScale(g, 1.1, 8, minSize=ms)) \
            or len(prof.detectMultiScale(cv2.flip(g, 1), 1.1, 8, minSize=ms)):
        return 2
    rects, w = hog.detectMultiScale(np.array(im.convert("RGB").resize((400, 400))), winStride=(8, 8), scale=1.05)
    if any(float(x) > 0.8 for x in np.ravel(w)) or len(upper.detectMultiScale(g, 1.1, 6, minSize=(80, 80))):
        return 1
    return 0

def rate_covers(cands, offline, limit=30):
    """Load covers of the best candidates once and mark faces/people (c['vis'])."""
    for n, c in enumerate(cands[:limit]):
        if "vis" in c:
            continue
        try:
            if "cover" not in c:
                c["cover"] = get_cover(c["arr"], offline, 500 + n)
            c["vis"] = 0 if offline else vis_level(c["cover"])
        except Exception as e:
            log("cover check fail", c["key"], e)
            c["vis"] = 0
        if c["vis"]:
            log("cover", "face" if c["vis"] == 2 else "person", c["key"])
    for c in cands:
        c.setdefault("vis", 0)

def choose(cands, banned):
    pool = [c for c in cands if c["key"] not in banned][:45]
    best, bk = None, None
    for combo in itertools.combinations(pool, 3):
        if len({c["key"] for c in combo}) < 3:
            continue
        k = (len({c["fam"] for c in combo}), sum(c.get("vis", 0) for c in combo),
             len({c["shop"] for c in combo}), sum(c["score"] for c in combo))
        if bk is None or k > bk:
            best, bk = combo, k
    return list(best) if best else None

# ---------------------------------------------------------------- media
def cover_urls(arr):
    urls = []
    for shop in COVER_RANK:
        for x in arr:
            u = x.get("cover")
            if x["shop"] != shop or not u:
                continue
            if shop == "Yoyaku":
                urls.append(re.sub(r"-\d+x\d+(\.\w+)$", r"\1", u))
            if shop == "Redeye Records":
                urls.append(re.sub(r"-2\.jpg$", "-1.jpg", u))
            if shop == "Clone":
                urls.append(u.replace("/artwork/small/", "/artwork/large/"))
            urls.append(u)
    return list(dict.fromkeys(urls))

def get_cover(arr, offline, seed):
    if offline:
        rng = np.random.default_rng(seed)
        a = (rng.random((8, 8, 3)) * 255).astype("uint8")
        return Image.fromarray(a).resize((600, 600), Image.NEAREST)
    best = None
    for u in cover_urls(arr):
        try:
            im = Image.open(io.BytesIO(fetch(u))).convert("RGB")
        except Exception as e:
            log("cover fail", u, e)
            continue
        if best is None or im.width > best.width:
            best = im
        if best.width >= 600:
            break
    if best is None:
        raise RuntimeError("no cover")
    s = min(best.size)  # centre-crop square
    l, t = (best.width - s) // 2, (best.height - s) // 2
    return best.crop((l, t, l + s, t + s))

def decode(path):
    raw = subprocess.run(["ffmpeg", "-v", "error", "-i", path, "-f", "f32le", "-ac", "2", "-ar", str(SR), "-"],
                         check=True, capture_output=True).stdout
    return np.frombuffer(raw, dtype="<f4").reshape(-1, 2).copy()

def get_audio(track, offline, work, seed):
    if offline:
        t = np.arange(SR * 60) / SR
        env = np.where(t > 20, 1.0, 0.35)
        x = (np.sin(2 * np.pi * (110 + seed * 40) * t) * 0.3 + np.sin(2 * np.pi * 2 * t) ** 8 * 0.4) * env
        return np.stack([x, x], 1).astype("float32")
    p = os.path.join(work, "a_%d.mp3" % seed)
    open(p, "wb").write(fetch(track["u"], timeout=90))
    a = decode(p)
    if len(a) < SR * 10:
        raise RuntimeError("audio too short")
    return a

def pick_start(a):
    """Start a little before the biggest energy rise (RMS per 0.5 s)."""
    hop = SR // 2
    m = a.mean(1)
    rms = np.array([np.sqrt(np.mean(m[i:i + hop] ** 2)) for i in range(0, len(m) - hop, hop)])
    dur = len(m) / SR
    best, bt = -1, min(30.0, max(0.0, dur - 12))
    for i in range(12, len(rms) - 8):          # t from 6 s
        t = i / 2
        if t > dur - 10:
            break
        rise = rms[i:i + 4].mean() - rms[i - 4:i].mean()
        if rise > best:
            best, bt = rise, t
    return max(0.0, bt - 1.5), rms

def seg(a, start, length):
    i, n = int(start * SR), int(length * SR)
    s = a[i:i + n]
    if len(s) < n:
        s = np.concatenate([s, np.zeros((n - len(s), 2), "float32")])
    r = np.sqrt(np.mean(s ** 2)) + 1e-6
    return s * min(4.0, 0.14 / r)              # loudness match

def fade(s, fin, fout):
    n = len(s)
    g = np.ones(n, "float32")
    a, b = int(fin * SR), int(fout * SR)
    if a: g[:a] = np.linspace(0, 1, a)
    if b: g[n - b:] = np.linspace(1, 0, b)
    return s * g[:, None]

def build_mix(picks):
    mix = np.zeros((SR * DUR, 2), "float32")
    plan = [(0, 9.1, 1.2, 0.15, -3.0), (9, 6.1, 0.1, 0.15, 0.0), (15, 6.0, 0.1, 1.5, 0.0)]
    for p, (at, ln, fi, fo, pre) in zip(picks, plan):
        st = max(0.0, p["start"] + pre)
        s = fade(seg(p["audio"], st, ln), fi, fo)
        i = int(at * SR)
        mix[i:i + len(s)] += s[:len(mix) - i]
    peak = np.abs(mix).max()
    if peak > 0.97:
        mix *= 0.97 / peak
    return mix

# ---------------------------------------------------------------- drawing
def fit(d, text, size, bold, maxw):
    while size > 18 and d.textlength(text, font=F(size, bold)) > maxw:
        size -= 2
    return F(size, bold)

def txt(d, xy, text, size, col, bold=True, anchor="ls", maxw=888):
    f = fit(d, text, size, bold, maxw)
    d.text(xy, text, font=f, fill=col, anchor=anchor)
    return d.textlength(text, font=f)

def paste_cover(img, cov, x, y, s, z=1.0):
    d = int(round(s * z))
    c = cov.resize((d, d), Image.LANCZOS) if z != 1.0 else cov.resize((s, s), Image.LANCZOS)
    off = (d - s) // 2
    img.paste(c.crop((off, off, off + s, off + s)) if d != s else c, (x, y))

def draw_title(img, picks, date_s, t):
    d = ImageDraw.Draw(img)
    y0 = SY
    txt(d, (96, y0 + 230), "Today's Digs", 112, WH)
    txt(d, (96, y0 + 390), date_s, 150, ACC)
    for i, p in enumerate(picks):
        a = min(1, max(0, (t - 0.35 - i * 0.45) / 0.55))
        a = 1 - (1 - a) ** 3
        if a <= 0:
            continue
        layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        ld = ImageDraw.Draw(layer)
        x, y = 96 + i * 299, y0 + 470 + int((1 - a) * 30)
        layer.paste(p["thumb"], (x, y))
        txt(ld, (x, y + 340), p["genre"], 28, ACC, maxw=290)
        txt(ld, (x, y + 382), p["a"], 32, WH, maxw=290)
        txt(ld, (x, y + 420), p["t"], 29, GR, bold=False, maxw=290)
        if a < 1:
            al = layer.getchannel("A").point(lambda v: int(v * a))
            layer.putalpha(al)
        img.paste(layer, (0, 0), layer)
    a = min(1, max(0, (t - 1.6) / 0.5))
    if a > 0:
        col = lambda c: tuple(int(BG[k] + (c[k] - BG[k]) * a) for k in range(3))
        txt(d, (96, y0 + 1200), "Previews & price comparison", 40, col(GR), bold=False)
        txt(d, (96, y0 + 1262), "monthlyvinyl.net", 48, col(ACC))

def draw_slide(img, p, i, date_s, t, lev):
    d = ImageDraw.Draw(img)
    y0 = SY
    txt(d, (96, y0 + 92), p["genre"], 34, ACC, maxw=560)
    txt(d, (984, y0 + 92), "%s  ·  %d / 3" % (date_s, i + 1), 32, GR, anchor="rs")
    paste_cover(img, p["cov700"], 230, y0 + 140, 620, 1 + 0.04 * (t / 6))
    txt(d, (96, y0 + 868), p["a"], 66, WH)
    txt(d, (96, y0 + 936), p["t"], 48, WH, bold=False)
    txt(d, (96, y0 + 990), "  ·  ".join(p["meta"]), 30, GR, bold=False)
    d.rectangle([96, y0 + 1030, 984, y0 + 1031], fill=RULE)
    y = y0 + 1092
    multi = len(p["prices"]) > 1
    for j, (shop, label) in enumerate(p["prices"][:3]):
        ch = multi and j == 0
        col = ACC if ch else WH
        w = txt(d, (96, y), shop, 38, col, bold=ch, maxw=420)
        if ch:
            d.text((96 + w + 18, y), "←", font=F(36, True, sym=True), fill=ACC, anchor="ls")
            txt(d, (96 + w + 62, y), "cheapest", 38, ACC, maxw=300)
        txt(d, (984, y), label, 38, col, bold=ch, anchor="rs")
        y += 54
    d.rectangle([96, y0 + 1252, 984, y0 + 1256], fill=RULE)
    d.rectangle([96, y0 + 1252, 96 + int(888 * min(1, t / 6)), y0 + 1256], fill=ACC)
    by = y0 + 1318
    d.polygon([(98, by - 20), (98, by - 1), (114, by - 10)], fill=WH)
    txt(d, (130, by), p["track"], 30, WH, bold=False, maxw=480)
    for b in range(4):
        ph = math.sin(p["frame"] * 0.45 + b * 1.9) * 0.5 + 0.5
        h = 6 + 30 * lev * (0.4 + 0.6 * ph)
        d.rectangle([632 + b * 13, by + 2 - h, 640 + b * 13, by + 2], fill=ACC)
    txt(d, (984, by), "monthlyvinyl.net", 30, ACC, anchor="rs")

def render_frame(f, picks, date_s, levs):
    t = f / FPS
    base = Image.new("RGB", (W, H), BG)
    layers = []
    xf = 0.25
    if t < 3 + xf:
        im = base.copy(); draw_title(im, picks, date_s, t)
        layers.append((im, 1.0 if t < 3 else 1 - (t - 3) / xf))
    for i in range(3):
        s, e = 3 + i * 6, 9 + i * 6
        if s <= t < e + xf:
            a = (t - s) / xf if t < s + xf else 1.0
            if i < 2 and t > e:
                a = 1 - (t - e) / xf
            if i == 2 and t > DUR - 0.4:
                a = min(a, (DUR - t) / 0.4)
            picks[i]["frame"] = f
            im = base.copy(); draw_slide(im, picks[i], i, date_s, t - s, levs[f])
            layers.append((im, max(0.0, min(1.0, a))))
    out = base
    for im, a in layers:
        out = im if a >= 1 else Image.blend(out, im, a)
    return out

def render_video(picks, date_s, mix, path, poster):
    hop = SR // FPS
    m = mix.mean(1)
    levs = np.array([np.sqrt(np.mean(m[f * hop:(f + 1) * hop] ** 2)) for f in range(DUR * FPS)])
    levs = np.minimum(1, levs / (levs.max() + 1e-9) * 1.15)
    wav = path + ".f32"
    mix.astype("<f4").tofile(wav)
    cmd = ["ffmpeg", "-y", "-v", "error",
           "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", "%dx%d" % (W, H), "-r", str(FPS), "-i", "-",
           "-f", "f32le", "-ar", str(SR), "-ac", "2", "-i", wav,
           "-c:v", "libx264", "-profile:v", "high", "-level", "4.0", "-pix_fmt", "yuv420p",
           "-b:v", "8M", "-maxrate", "10M", "-bufsize", "16M", "-g", "60", "-preset", "medium",
           "-c:a", "aac", "-b:a", "192k", "-ar", str(SR), "-ac", "2",
           "-movflags", "+faststart", "-shortest", path]
    pr = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    for f in range(DUR * FPS):
        im = render_frame(f, picks, date_s, levs)
        if f == int(2.9 * FPS):
            im.convert("RGB").save(poster, quality=88)
        pr.stdin.write(im.tobytes())
    pr.stdin.close()
    if pr.wait() != 0:
        raise RuntimeError("ffmpeg failed")
    os.remove(wav)

# ---------------------------------------------------------------- texts
def price_s(x):
    return "%s%.2f" % (x["cur"], x["p"]) if x.get("p") is not None else None

MONTHS = ["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"]

def parse_d(d, ref):
    """Shop release-date text -> date, or None (week numbers, 'out now' etc.)."""
    d = (d or "").strip().lower()
    if not d:
        return None
    m = re.search(r"(20\d\d)-(\d\d)-(\d\d)", d)
    if m:
        return dt.date(int(m[1]), int(m[2]), int(m[3]))
    m = re.search(r"\b(\d{1,2})\.(\d{1,2})\.(\d{2,4})\b", d)
    if m:
        y = int(m[3]); y = y + 2000 if y < 100 else y
        return dt.date(y, int(m[2]), int(m[1]))
    m = re.search(r"\b([a-z]{3})[a-z]*\.?\s+(\d{1,2})(?:st|nd|rd|th)?,?\s+(20\d\d)", d) or \
        re.search(r"\b(\d{1,2})(?:st|nd|rd|th)?\s+([a-z]{3})[a-z]*\.?(?:\s+(20\d\d))?", d)
    if m:
        g = m.groups()
        if g[0].isdigit():
            day_, mon, yr = int(g[0]), g[1], g[2]
        else:
            mon, day_, yr = g[0], int(g[1]), g[2]
        if mon not in MONTHS:
            return None
        mo = MONTHS.index(mon) + 1
        y = int(yr) if yr else ref.year + (1 if mo < ref.month - 6 else 0)
        try:
            return dt.date(y, mo, day_)
        except ValueError:
            return None
    return None

def release_date(x, arr):
    """Release date for the reel (green line): shop date if readable, else the day it first appeared."""
    ref = dt.date.fromisoformat(x.get("first_seen") or dt.date.today().isoformat())
    for y in [x] + arr:
        r = parse_d(y.get("d"), ref)
        if r:
            break
    else:
        r = ref
    return "%d %s %d" % (r.day, MONTHS[r.month - 1].title(), r.year)

def look_seed(*parts):
    return int(hashlib.md5("|".join(parts).encode("utf-8")).hexdigest()[:8], 16)

def reel_rel(p, cover):
    """data for the reel text layer (website look)"""
    return {"shop": p["shop_full"], "cc": p["cc"], "a": p["a"], "track": p["tname"], "date": p["rdate"],
            "label": " · ".join(v for v in [p["l"], p["cat"]] if v) or p["shop_full"], "cover": cover}

def prepare(c, fx):
    x, arr = c["feat"], c["arr"]
    meta_src = next((y for y in [x] + arr if y.get("l")), x)
    # Phonica shows internal numbers instead of catalog numbers → prefer other shops
    cats = [y.get("cat") for y in [x] + arr if y.get("cat") and not (y["shop"] == "Phonica" and y["cat"].isdigit())]
    cat = cats[0] if cats else ""
    meta = [v for v in [meta_src.get("l"), cat, x.get("f") or meta_src.get("f")] if v]
    rows, seen_shop = [], set()
    for y in arr:
        if y.get("p") is None or y["shop"] in seen_shop:
            continue
        seen_shop.add(y["shop"])
        chf = y["p"] * fx.get(CUR.get(y["cur"], "EUR"), 1)
        rows.append((chf, short(y["shop"]), price_s(y)))
    rows.sort()
    tr = c["track"]
    tname = tr["n"] if tr["named"] else x["t"]
    return {"tname": tname, "cat": cat, "shop_full": x["shop"], "cc": x.get("country") or "",
            "rdate": release_date(x, arr), "key": c["key"], "a": x["a"], "t": x["t"], "l": meta_src.get("l") or "", "genre": genre_label(x.get("g")),
            "gfull": x.get("g") or "", "meta": meta, "prices": [(r[1], r[2]) for r in rows],
            "shop": short(x["shop"]), "shop_price": price_s(x), "url": x.get("url"),
            "track": tname + " (preview)", "strict": c["strict"]}

def tag(s):
    s = re.sub(r"[^a-z0-9]", "", norm(s))
    return "#" + s if 2 < len(s) <= 24 else None

def caption(picks, date_s):
    nums = ["1️⃣", "2️⃣", "3️⃣"]
    lines = ["Today's Digs %s 👇" % date_s, "🔊 Sound on", ""]
    for n, p in zip(nums, picks):
        lab = " (%s)" % p["l"] if p["l"] else ""
        lines.append("%s %s – %s%s" % (n, p["a"], p["t"], lab))
        g = p["genre"].title().replace("Dj", "DJ")
        lines.append("%s · %s at %s" % (g, p["shop_price"], p["shop"]) if p["shop_price"] else "%s · at %s" % (g, p["shop"]))
        lines.append("")
    lines += ["Full price comparison + previews of all three 👉", "monthlyvinyl.net (link in bio)", "",
              "Which one goes in your bag – 1, 2 or 3?", ""]
    tags = ["#newvinyl", "#vinylrelease"]
    for p in picks:
        tags.append(tag(p["genre"]))
    for p in picks:
        tags += [tag(p["a"]), tag(p["l"])]
    tags += ["#vinylcollection", "#recordshop", "#monthlyvinyl"]
    out = []
    for t in tags:
        if t and t not in out:
            out.append(t)
    lines.append(" ".join(out[:16]))
    return "\n".join(lines)


# ---------------------------------------------------------------- reel (one release, 20 s)
RDUR = 20

# Brand colour schemes for the reel (profile picture: neon green + neon pink). Never the same scheme twice in a row.
GRN, PNK, BLK, YEL = (57, 255, 20), (255, 43, 214), (13, 13, 13), (251, 237, 79)
REEL_V = 5   # bump to re-render today's reel after a design change
DIGS_V = 2   # bump to re-render today's digs video after a design change
# One text colour per reel (type, play button, bars, progress all in that colour).
# Pink bg → green type · green bg → yellow type · yellow bg → pink type · black bg → yellow, green or pink (random).
SCHEMES = {
    "BK-Y": dict(bg=BLK, text=YEL, rule=RULE),
    "BK-G": dict(bg=BLK, text=GRN, rule=RULE),
    "BK-P": dict(bg=BLK, text=PNK, rule=RULE),
    "PK":   dict(bg=PNK, text=GRN, rule=GRN),
    "GN":   dict(bg=GRN, text=YEL, rule=YEL),
    "YL":   dict(bg=YEL, text=PNK, rule=PNK),
}

def pick_scheme(last):
    import random
    bgs = ["BK", "PK", "GN", "YL"]
    last_bg = (last or "").split("-")[0] if last in SCHEMES else None
    bg = random.choice([b for b in bgs if b != last_bg])
    return random.choice(["BK-Y", "BK-G", "BK-P"]) if bg == "BK" else bg

def draw_reel(img, p, date_s, t, lev, frame):
    c = SCHEMES[p["scheme"]]
    col, bg = c["text"], c["bg"]
    d = ImageDraw.Draw(img)
    txt(d, (96, 318), p["kicker"], 34, col, maxw=600)
    txt(d, (984, 318), date_s, 32, col, anchor="rs")
    paste_cover(img, p["cov880"], 100, 360, 880, 1 + 0.035 * (t / RDUR))
    txt(d, (96, 1340), p["a"], 76, col)
    txt(d, (96, 1412), p["t"], 56, col, bold=False)
    txt(d, (96, 1470), "  ·  ".join(p["meta"] + ([p["genre"].title()] if p["genre"] else [])), 32, col, bold=False)
    d.rectangle([96, 1538, 984, 1542], fill=c["rule"] if bg == BLK else bg)
    d.rectangle([96, 1539, 984, 1541], fill=c["rule"])
    d.rectangle([96, 1536, 96 + int(888 * min(1, t / RDUR)), 1544], fill=col)
    by = 1612
    d.polygon([(98, by - 22), (98, by - 1), (116, by - 11)], fill=col)
    tw = txt(d, (134, by), p["track"], 32, col, bold=False, maxw=640)
    bx = 134 + int(tw) + 26
    for b in range(5):
        ph = math.sin(frame * 0.45 + b * 1.7) * 0.5 + 0.5
        h = 6 + 32 * lev * (0.4 + 0.6 * ph)
        d.rectangle([bx + b * 14, by + 2 - h, bx + 8 + b * 14, by + 2], fill=col)
    txt(d, (96, 1680), p["shops_line"], 34, col, maxw=560)
    txt(d, (984, 1680), "monthlyvinyl.net", 34, col, anchor="rs")

def render_reel(p, date_s, aud, path, poster):
    n = RDUR * FPS
    hop = SR // FPS
    m = aud.mean(1)
    levs = np.array([np.sqrt(np.mean(m[f * hop:(f + 1) * hop] ** 2)) for f in range(n)])
    levs = np.minimum(1, levs / (levs.max() + 1e-9) * 1.15)
    wav = path + ".f32"
    aud.astype("<f4").tofile(wav)
    cmd = ["ffmpeg", "-y", "-v", "error",
           "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", "%dx%d" % (W, H), "-r", str(FPS), "-i", "-",
           "-f", "f32le", "-ar", str(SR), "-ac", "2", "-i", wav,
           "-c:v", "libx264", "-profile:v", "high", "-level", "4.0", "-pix_fmt", "yuv420p",
           "-b:v", "8M", "-maxrate", "10M", "-bufsize", "16M", "-g", "60", "-preset", "medium",
           "-c:a", "aac", "-b:a", "192k", "-ar", str(SR), "-ac", "2",
           "-movflags", "+faststart", "-shortest", path]
    pr = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    black = Image.new("RGB", (W, H), (0, 0, 0))
    for f in range(n):
        t = f / FPS
        im = Image.new("RGB", (W, H), SCHEMES[p["scheme"]]["bg"])
        draw_reel(im, p, date_s, t, levs[f], f)
        if f == int(1.5 * FPS):
            im.save(poster, quality=88)
        a = min(1.0, t / 0.6, (RDUR - t) / 1.0)
        if a < 1:
            im = Image.blend(black, im, max(0.0, a))
        pr.stdin.write(im.tobytes())
    pr.stdin.close()
    if pr.wait() != 0:
        raise RuntimeError("ffmpeg failed")
    os.remove(wav)

def reel_mix(audio, start):
    s = fade(seg(audio, start, RDUR), 0.6, 2.0)
    peak = np.abs(s).max()
    return s * (0.97 / peak) if peak > 0.97 else s

def pick_reel(cands, digs_keys, digs_fams, offline, work):
    """Best remaining release with a real preview and a big cover; a different genre family than the digs if possible."""
    pool = [c for c in cands if c["key"] not in digs_keys]
    pool.sort(key=lambda c: (-c.get("vis", 0), c["fam"] in digs_fams, -(c["score"] + (0.5 if c["tracks"][0]["named"] else 0))))
    fallback = None
    for n, c in enumerate(pool[:12]):
        try:
            cov = c.get("cover") or get_cover(c["arr"], offline, 90 + n)
            aud = tr = None
            for ti, t in enumerate(c["tracks"][:3]):
                try:
                    aud, tr = get_audio(t, offline, work, 900 + n * 10 + ti), t
                    break
                except Exception as e:
                    log("reel audio fail", c["key"], e)
            if aud is None:
                continue
        except Exception as e:
            log("reel drop", c["key"], e)
            continue
        c = dict(c, cover=cov, audio=aud, track=tr)
        if cov.width >= 500:
            return c
        fallback = fallback or c
    return fallback

def tracklist(arr):
    out, seen = [], set()
    for x in arr:
        for t in x.get("tr") or []:
            n = (t.get("n") or "").strip()
            if not n or n.lower() in ("preview", "whole ep on youtube") or n.lower() in seen:
                continue
            seen.add(n.lower())
            out.append(("%s %s" % (t.get("s") or "", n)).strip())
    return out[:10]

def reel_caption(p, arr):
    cat = [v for v in p["meta"][1:2]]
    head = "%s – %s" % (p["a"], p["t"])
    inside = ", ".join(v for v in [p["l"]] + cat if v)
    lines = [head + (" (%s)" % inside if inside else ""),
             "%s 🔊 Sound on: \"%s\"" % ("New in the shops" if p["strict"] else "Fresh in the shops", p["track"].replace(" (preview)", "")), ""]
    tl = tracklist(arr)
    if len(tl) > 1:
        lines += tl + [""]
    fmt = p["meta"][-1] if p["meta"] else "Vinyl"
    if len(p["prices"]) > 1:
        lines.append("💿 %s – %d shops compared:" % (fmt, len(p["prices"])))
        for j, (shop, pr) in enumerate(p["prices"][:5]):
            lines.append("%s %s%s" % (shop, pr, "  ← cheapest" if j == 0 else ""))
    elif p["shop_price"]:
        lines.append("💿 %s – %s at %s" % (fmt, p["shop_price"], p["shop"]))
    else:
        lines.append("💿 %s – at %s" % (fmt, p["shop"]))
    lines += ["", "Listen to all previews + compare prices 👉", "monthlyvinyl.net (link in bio)", "", "Cop or drop?", ""]
    tags = ["#newvinyl", "#vinylrelease", tag(p["genre"]), tag(p["a"]), tag(p["l"]), "#vinyldj", "#vinylcollection", "#recordshop", "#nowspinning", "#monthlyvinyl"]
    out = []
    for t in tags:
        if t and t not in out:
            out.append(t)
    lines.append(" ".join(out))
    return "\n".join(lines)

# ---------------------------------------------------------------- page
PAGE = """<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="robots" content="noindex,nofollow,noarchive">
<meta name="referrer" content="no-referrer">
<title>Today's Digs + Reel</title>
<link rel="icon" href="/favicon-32.png">
<style>
:root{--bg:#0f0f0f;--fg:#fff;--mut:#9a9a9a;--acc:#ffd60a;--line:#2e2e2e}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--fg);font:16px/1.45 "Helvetica Neue",Helvetica,Arial,sans-serif}
main{max-width:980px;margin:0 auto;padding:28px 16px 60px}
h1{font-size:30px;margin:0}h1 span{color:var(--acc)}.sub{color:var(--mut);margin:4px 0 8px}
nav.jump{display:flex;gap:10px;margin:0 0 8px;flex-wrap:wrap}nav.jump a{color:var(--fg);border:1px solid var(--line);border-radius:999px;padding:6px 14px;text-decoration:none;font-size:14px}
section{border-top:4px solid var(--acc);margin-top:30px;padding-top:16px}
section h2.t{font-size:24px;margin:0 0 4px;color:var(--fg);text-transform:none;letter-spacing:0}
.grid{display:grid;grid-template-columns:minmax(0,360px) 1fr;gap:28px;margin-top:14px}@media(max-width:760px){.grid{grid-template-columns:1fr}}
video{width:100%;border-radius:10px;background:#000;display:block}
.btn{display:inline-block;background:var(--acc);color:#000;font-weight:700;padding:12px 18px;border-radius:9px;text-decoration:none;border:0;font-size:15px;cursor:pointer;margin:12px 8px 0 0}
textarea{width:100%;min-height:380px;background:#161616;color:var(--fg);border:1px solid var(--line);border-radius:9px;padding:12px;font:14px/1.5 ui-monospace,Menlo,monospace}
ol{padding-left:20px}li{margin:6px 0}a{color:var(--acc)}.m{color:var(--mut);font-size:14px}
h2{font-size:15px;text-transform:uppercase;letter-spacing:.06em;color:var(--mut);margin:26px 0 8px}
.ok{color:var(--acc);font-size:14px;margin-left:6px}
</style></head><body><main>
<h1>Instagram <span>__DATE__</span></h1>
<p class="sub">Generated __GEN__ · not published · both 1080×1920</p>
<nav class="jump"><a href="#digs">Today's Digs · post video</a><a href="#reel">Reel · one release</a></nav>
__SECTIONS__
<h2>Previous days</h2>
<ul class="m">__ARCHIVE__</ul>
</main>
<script>
document.querySelectorAll('[data-copy]').forEach(b=>b.onclick=async()=>{const t=document.getElementById(b.dataset.copy),ok=b.nextElementSibling;
try{await navigator.clipboard.writeText(t.value)}catch(e){t.select();document.execCommand('copy')}
ok.textContent='copied ✓';setTimeout(()=>ok.textContent='',2000)});
</script></body></html>
"""

SECTION = """<section id="__ID__">
<h2 class="t">__TITLE__</h2><p class="m">__SUB__</p>
<div class="grid">
<div>
<video controls playsinline preload="metadata" poster="__POSTER__" src="__VIDEO__"></video>
<a class="btn" href="__VIDEO__" download="__FILE__">⬇ Download video</a>
</div>
<div>
<textarea id="cap-__ID__" readonly>__CAPTION__</textarea>
<button class="btn" data-copy="cap-__ID__">Copy caption</button><span class="ok"></span>
<h2>Release__S__</h2>
<ol>__LIST__</ol>
__NOTE__
</div></div></section>"""

def rel_li(p):
    pr = " · ".join("%s %s" % (s_, v) for s_, v in p["prices"]) or "no price"
    return '<li><b>%s – %s</b> <span class="m">(%s · new at %s)</span><br><span class="m">%s · ▶ %s</span>%s</li>' % (
        html.escape(p["a"]), html.escape(p["t"]), html.escape(p["genre"].title()), html.escape(p["shop"]),
        html.escape(pr), html.escape(p["track"]),
        ' · <a href="%s" target="_blank" rel="noopener">shop</a>' % html.escape(p["url"]) if p.get("url") else "")

def section(sid, title, sub, video, poster, fname, cap, items, note):
    rep = {"__ID__": sid, "__TITLE__": title, "__SUB__": sub, "__VIDEO__": html.escape(video), "__POSTER__": html.escape(poster),
           "__FILE__": fname, "__CAPTION__": html.escape(cap), "__LIST__": "".join(rel_li(p) for p in items),
           "__S__": "s" if len(items) > 1 else "", "__NOTE__": '<p class="m">%s</p>' % html.escape(note) if note else ""}
    out = SECTION
    for k, v in rep.items():
        out = out.replace(k, v)
    return out

def write_page(date_s, sections, history, caps):
    arch = []
    for e in history[1:8]:
        r = e.get("reel") or {}
        arch.append('<li>%s – digs: %s · <a href="%s">video</a>%s</li>' % (
            html.escape(e["date"]), html.escape(" / ".join(e.get("titles", []))), html.escape(e.get("video", "")),
            ' · reel: %s · <a href="%s">video</a>' % (html.escape(r.get("title", "")), html.escape(r.get("video", ""))) if r else ""))
    gen = dt.datetime.now(dt.timezone(dt.timedelta(hours=2))).strftime("%d.%m.%Y %H:%M")
    page = PAGE.replace("__DATE__", date_s).replace("__GEN__", gen).replace("__SECTIONS__", "\n".join(sections)) \
               .replace("__ARCHIVE__", "".join(arch) or "<li>–</li>")
    os.makedirs(OUT, exist_ok=True)
    open(os.path.join(OUT, "index.html"), "w", encoding="utf-8").write(page)
    open(os.path.join(OUT, "caption.txt"), "w", encoding="utf-8").write(caps[0] + "\n")
    if len(caps) > 1:
        open(os.path.join(OUT, "caption_reel.txt"), "w", encoding="utf-8").write(caps[1] + "\n")

def make_reel(a, cands, fx, digs_keys, digs_fams, history, date_s, ymd, base):
    rc = pick_reel(cands, digs_keys, digs_fams, a.offline, a.work)
    if not rc:
        log("no reel candidate")
        return None
    import random
    R = prepare(rc, fx)
    start, _ = pick_start(rc["audio"])
    aud = reel_mix(rc["audio"], max(0.0, start - 1.0))
    rname = "reel-%s.mp4" % ymd
    rpath = os.path.join(a.work, rname)
    rposter = os.path.join(a.work, "reel-%s.jpg" % ymd)
    look = reelfx.reel_single(reel_rel(R, rc["cover"]), aud, look_seed(ymd, R["key"], "reel"), rpath, rposter)
    rcap = reel_caption(R, rc["arr"])
    sec = section("reel", "Reel · one release", "20 s · post as a Reel · look: %s" % look, base + rname,
                  base + os.path.basename(rposter), rname, rcap, [R],
                  "" if R["strict"] else "Note: already listed in another shop before yesterday.")
    log("reel", R["shop"], "|", R["a"], "–", R["t"], "|", R["genre"], "|", look)
    return {"files": [rpath, rposter], "cap": rcap, "section": sec,
            "entry": {"key": R["key"], "title": "%s – %s" % (R["a"], R["t"]), "video": base + rname, "look": look, "v": REEL_V}}

def reel_only(a, data, day, date_s, ymd, history, keep, cands, fx, hist_p):
    base = "https://github.com/%s/releases/download/%s/" % (REPO, RELEASE_TAG)
    cap_p = os.path.join(OUT, "caption.txt")
    cap = open(cap_p, encoding="utf-8").read().rstrip("\n") if os.path.exists(cap_p) else ""
    fams = set()
    G = {}
    for s_ in data["shops"]:
        for it in s_.get("items") or []:
            G.setdefault(gkey(it), it)
    for k in keep.get("keys", []):
        if k in G: fams.add(family(G[k].get("g")))
    rel = make_reel(a, cands, fx, set(keep.get("keys", [])), fams, history, date_s, ymd, base)
    video = keep.get("video", "")
    fname = video.rsplit("/", 1)[-1]
    items = "".join("<li><b>%s</b> <span class=\"m\">(%s)</span></li>" % (html.escape(t), html.escape(s_))
                    for t, s_ in zip(keep.get("titles", []), keep.get("shops", [])))
    digs_sec = section("digs", "Today's Digs · post video", "3 releases · 3 × 15 s · post in the feed", video,
                       video.replace(".mp4", ".jpg"), fname, cap, [], "").replace("<ol></ol>", "<ol>%s</ol>" % items).replace("<h2>Release</h2>", "<h2>Releases</h2>")
    sections, caps, files = [digs_sec], [cap], []
    if rel:
        sections.insert(0, rel["section"]); caps.append(rel["cap"]); files = rel["files"]; keep["reel"] = rel["entry"]
    else:
        keep["reel"] = {"key": "", "title": "(none)", "video": ""}
    history.insert(0, keep)
    write_page(date_s, sections, history, caps)
    json.dump(history[:60], open(hist_p, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(json.dumps({"skip": not files, "video": files[0] if files else "", "poster": files[1] if files else "", "files": files, "date": day}))

# ---------------------------------------------------------------- main
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--date")
    ap.add_argument("--force", action="store_true")
    ap.add_argument("--offline", action="store_true", help="synthetic media, for layout tests")
    ap.add_argument("--work", default=os.environ.get("DIGS_WORK") or tempfile.mkdtemp())
    a = ap.parse_args()
    data = json.load(open(os.path.join(ROOT, "releases.json"), encoding="utf-8"))
    day = a.date or data["updated"]
    date_s = dt.date.fromisoformat(day).strftime("%d.%m.%y")
    ymd = day.replace("-", "")[2:]
    hist_p = os.path.join(OUT, "history.json")
    history = json.load(open(hist_p, encoding="utf-8")) if os.path.exists(hist_p) else []
    if not a.force and history and history[0]["date"] == day and (history[0].get("reel") or {}).get("v") == REEL_V \
            and history[0].get("dv") == DIGS_V:
        log("digs + reel for", day, "already done")
        print(json.dumps({"skip": True}))
        return
    keep = None
    if not a.force and history and history[0]["date"] == day and history[0].get("dv") == DIGS_V \
            and (history[0].get("reel") or {}).get("v") != REEL_V:
        keep = history[0]          # digs done earlier today: keep exactly that video, add the reel only
    history = [e for e in history if e["date"] != day]
    seen = load_seen(skip_day=day)
    fx = data.get("fx", {})
    cands = candidates(data, day, seen)
    log(len(cands), "candidates for", day)
    rate_covers(cands, a.offline)
    banned, picks = set(), None
    if keep:
        return reel_only(a, data, day, date_s, ymd, history, keep, cands, fx, hist_p)
    while True:
        combo = choose(cands, banned)
        if not combo:
            raise SystemExit("not enough releases with previews for %s" % day)
        ok = []
        for n, c in enumerate(combo):
            if "audio" not in c:
                try:
                    for ti, tr in enumerate(c["tracks"][:3]):
                        try:
                            c["audio"] = get_audio(tr, a.offline, a.work, n * 10 + ti)
                            c["track"] = tr
                            break
                        except Exception as e:
                            log("audio fail", c["key"], e)
                    if "audio" not in c:
                        raise RuntimeError("no audio")
                    if "cover" not in c:
                        c["cover"] = get_cover(c["arr"], a.offline, n)
                except Exception as e:
                    log("drop", c["key"], e)
                    banned.add(c["key"])
                    break
            ok.append(c)
        if len(ok) == 3:
            picks = ok
            break
    P = []
    for c in picks:
        p = prepare(c, fx)
        p["audio"] = c["audio"]
        p["start"], _ = pick_start(c["audio"])
        p["cover"] = c["cover"]
        P.append(p)
        log("pick", p["shop"], "|", p["a"], "–", p["t"], "|", p["genre"], "| start %.1fs" % p["start"], "| strict" if p["strict"] else "| newly listed at shop")
    fname = "todays-digs-%s.mp4" % ymd
    vpath = os.path.join(a.work, fname)
    poster = os.path.join(a.work, "todays-digs-%s.jpg" % ymd)
    seeds = [look_seed(ymd, p["key"], "digs") for p in P]
    import random
    rnd = random.Random(seeds[0])
    cmodes = rnd.sample(reelfx.CoverFX.MODES, 3)          # three different cover characters
    offs = [max(0.0, min(p["start"] - 1.0, len(p["audio"]) / SR - 15.5)) for p in P]
    looks, _ = reelfx.reel_triple([reel_rel(p, p["cover"]) for p in P], [p["audio"] for p in P], offs, seeds,
                                  vpath, poster, cmodes=cmodes)
    base = "https://github.com/%s/releases/download/%s/" % (REPO, RELEASE_TAG)
    cap = caption(P, date_s)
    nonstrict = [p for p in P if not p["strict"]]
    note = ("Note: %s was already listed in another shop before yesterday (new at %s today)." %
            (", ".join("%s – %s" % (p["a"], p["t"]) for p in nonstrict), ", ".join(p["shop"] for p in nonstrict))) if nonstrict else ""
    entry = {"date": day, "keys": [p["key"] for p in P], "titles": ["%s – %s" % (p["a"], p["t"]) for p in P],
             "shops": [p["shop"] for p in P], "video": base + fname, "looks": looks, "dv": DIGS_V}
    files = [vpath, poster]
    sections = [section("digs", "Today's Digs · post video", "3 releases · 3 × 15 s · post in the feed", base + fname,
                        base + os.path.basename(poster), fname, cap, P, note)]
    caps = [cap]
    # Reel: one other release, 20 s
    rel = make_reel(a, cands, fx, {p["key"] for p in P}, {c["fam"] for c in picks}, history, date_s, ymd, base)
    if rel:
        files += rel["files"]; caps.append(rel["cap"]); sections.insert(0, rel["section"]); entry["reel"] = rel["entry"]
    else:
        entry["reel"] = {"key": "", "title": "(none)", "video": ""}
    history.insert(0, entry)
    write_page(date_s, sections, history, caps)
    json.dump(history[:60], open(hist_p, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(json.dumps({"skip": False, "video": vpath, "poster": poster, "files": files, "date": day}))

if __name__ == "__main__":
    main()
