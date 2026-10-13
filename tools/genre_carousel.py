#!/usr/bin/env python3
"""Genre carousel for Instagram: one title image + short video slides (4:5), each slide with its own preview as sound.
Wish in tools/genre_carousel.json: {"genre": "House", "days": 7, "n": 8}. Runs in GitHub Actions; output JSON on stdout."""
import datetime as dt, json, os, re, subprocess, sys, tempfile
sys.path.insert(0, os.path.dirname(__file__))
import numpy as np
from PIL import Image, ImageDraw
import digs
from single_reel import best_cover

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WORK = os.environ.get("REEL_WORK") or tempfile.mkdtemp()
W, H, FPS, SR = 1080, 1350, 30, digs.SR
SEG = 10
BG, FG, MUTED, YEL = (13, 13, 13), (236, 235, 231), (150, 154, 159), (251, 237, 79)

def gmatch(it, genre):
    g = digs.norm(it.get("g") or "")
    return digs.norm(genre) in g

def text_block(d, R):
    """minimal: artist, title, label · shop"""
    x, maxw = 64, W - 128
    digs.txt(d, (x, 1172), R["a"], 44, FG, maxw=maxw)
    digs.txt(d, (x, 1226), R["t"], 34, FG, bold=False, maxw=maxw)
    digs.txt(d, (x, 1286), "  ·  ".join(v for v in [R.get("l"), R["shop_full"]] if v), 26, MUTED, bold=False, maxw=maxw)

def render_slide(R, cov, aud, start, out):
    seg = digs.fade(digs.seg(aud, start, SEG), 0.3, 0.9)
    wav = out + ".f32"
    seg.astype("<f4").tofile(wav)
    side = min(cov.size)
    sq = cov.crop(((cov.width - side) // 2, (cov.height - side) // 2, (cov.width + side) // 2, (cov.height + side) // 2))
    sq = sq.resize((1200, 1200), Image.LANCZOS)
    base = Image.new("RGB", (W, H), BG)
    text_block(ImageDraw.Draw(base), R)
    cmd = ["ffmpeg", "-y", "-v", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", "%dx%d" % (W, H), "-r", str(FPS), "-i", "-",
           "-f", "f32le", "-ar", str(SR), "-ac", "2", "-i", wav,
           "-c:v", "libx264", "-profile:v", "high", "-pix_fmt", "yuv420p", "-b:v", "6M", "-preset", "medium",
           "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", "-shortest", out]
    pr = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    n = SEG * FPS
    for f in range(n):
        z = 1 + 0.03 * f / n                                   # slow push-in, nothing else moves
        s = int(1080 * z)
        c = sq.resize((s, s), Image.BICUBIC)
        o = (s - 1080) // 2
        im = base.copy()
        im.paste(c.crop((o, o, o + 1080, o + 1080)), (0, 0))
        if f == 15:
            im.save(out.replace(".mp4", ".jpg"), quality=90)
        pr.stdin.write(im.tobytes())
    pr.stdin.close()
    if pr.wait() != 0:
        raise RuntimeError("ffmpeg failed")
    os.remove(wav)

def title_image(genre, n, d0, d1, out):
    im = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(im)
    digs.txt(d, (64, 640), genre + ".", 150, YEL, maxw=W - 128)
    digs.txt(d, (64, 720), "%d new records this week" % n, 38, FG, bold=False)
    digs.txt(d, (64, 776), "%s – %s" % (d0.strftime("%-d %b"), d1.strftime("%-d %b %Y")), 30, MUTED, bold=False)
    digs.txt(d, (64, 1286), "swipe. sound on.", 28, MUTED, bold=False)
    im.save(out, quality=92)

def main():
    want = json.load(open(os.path.join(ROOT, "tools", "genre_carousel.json"), encoding="utf-8"))
    genre, days, N = want.get("genre", "House"), int(want.get("days", 7)), int(want.get("n", 8))
    data = json.load(open(os.path.join(ROOT, "releases.json"), encoding="utf-8"))
    fx = data.get("fx", {})
    d1 = dt.date.fromisoformat(data["updated"])
    d0 = d1 - dt.timedelta(days=days - 1)
    G = {}
    for s in data["shops"]:
        for it in s.get("items") or []:
            G.setdefault(digs.gkey(it), []).append(dict(it, shop=s["shop"], cur=s.get("cur", "€"), country=s.get("country", "")))
    cands = []
    for k, arr in G.items():
        first = min(x.get("first_seen") or "9999" for x in arr)
        if not (d0.isoformat() <= first <= d1.isoformat()):
            continue
        if not any(gmatch(x, genre) for x in arr):
            continue
        tracks = digs.playable(arr)
        if not tracks:
            continue
        cands.append((len({x["shop"] for x in arr}), first, k, arr, tracks))
    cands.sort(key=lambda c: (-c[0], c[1]), reverse=False)
    digs.log(len(cands), "candidates", genre, d0, d1)
    slides, used = [], []
    for nshop, first, k, arr, tracks in cands:
        if len(slides) == N:
            break
        feat = next(x for x in arr if (x.get("first_seen") or "9999") == first)
        if any(digs.norm(feat["a"]) == digs.norm(u) for u in used):      # one record per artist
            continue
        try:
            cov = best_cover(arr)
            if cov is None or min(cov.size) < 450:
                digs.log("skip small cover", k)
                continue
            aud = tr = None
            for j, t in enumerate(tracks[:3]):
                try:
                    aud, tr = digs.get_audio(t, False, WORK, 900 + len(slides) * 10 + j), t
                    break
                except Exception as e:
                    digs.log("audio fail", t.get("u"), e)
            if aud is None:
                continue
            c = {"key": k, "arr": arr, "feat": feat, "shop": feat["shop"], "fam": digs.family(feat.get("g")),
                 "strict": True, "tracks": tracks, "score": 0, "track": tr, "cover": cov, "audio": aud}
            R = digs.prepare(c, fx)
            start, _ = digs.pick_start(aud)
            out = os.path.join(WORK, "slide-%02d.mp4" % (len(slides) + 1))
            render_slide(R, cov, aud, max(0.0, start), out)
            slides.append({"video": out, "a": R["a"], "t": R["t"], "l": R["l"], "shop": R["shop_full"], "track": R["tname"]})
            used.append(feat["a"])
            digs.log("slide", len(slides), R["a"], "–", R["t"], "|", R["shop_full"], "| cover", cov.width)
        except Exception as e:
            digs.log("fail", k, e)
    if not slides:
        raise SystemExit("no slides")
    title = os.path.join(WORK, "slide-00.jpg")
    title_image(genre, len(slides), d0, d1, title)
    tag = "#" + re.sub(r"[^a-z0-9]", "", genre.lower())
    lines = ["%s – new this week 👇" % genre, "🔊 Sound on, swipe through.", ""]
    for i, s in enumerate(slides, 1):
        lines.append("%d. %s – %s (%s) · %s" % (i, s["a"], s["t"], s["l"], s["shop"]) if s["l"] else "%d. %s – %s · %s" % (i, s["a"], s["t"], s["shop"]))
    lines += ["", "Previews + price comparison for all of them: monthlyvinyl.net (link in bio)", "",
              "%s %svinyl #newvinyl #vinylrelease #recordshop #vinyldj #nowspinning" % (tag, tag)]
    cap = os.path.join(WORK, "caption.txt")
    open(cap, "w", encoding="utf-8").write("\n".join(lines) + "\n")
    print(json.dumps({"title": title, "slides": slides, "caption": cap, "genre": genre}))

if __name__ == "__main__":
    main()
