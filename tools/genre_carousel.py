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

# ---------------------------------------------------------------- fresh mode (since 31.10.26)
# {"mode": "fresh", "date": "YYYY-MM-DD", "n": 4, "seg": 30}: n slides of records that are «Fresh today»
# (not the three in Today's Digs), each one record, 4:5, yellow type like the digs video.
INK = (251, 237, 79)
FAINT = tuple(int(b + (c - b) * .25) for b, c in zip(BG, INK))
MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]

def fresh_slide(R, cov, aud, start, seg_s, date_s, out):
    import math
    import digs_oneview as ov
    seg = digs.fade(digs.seg(aud, start, seg_s), 0.3, 1.2)
    m = seg.mean(1); hop = SR // FPS; n = int(seg_s * FPS)
    levs = np.array([np.sqrt(np.mean(m[f * hop:(f + 1) * hop] ** 2)) if f * hop < len(m) else 0 for f in range(n)])
    levs = np.minimum(1, levs / (levs.max() + 1e-9) * 1.15)
    wav = out + ".f32"
    seg.astype("<f4").tofile(wav)
    side = min(cov.size)
    sq = cov.convert("RGB").crop(((cov.width - side) // 2, (cov.height - side) // 2, (cov.width + side) // 2, (cov.height + side) // 2))
    sq = sq.resize((960, 960), Image.LANCZOS)
    title = ov.clean_title(R["t"])
    meta = " · ".join(v for v in [R.get("l"), date_s, R.get("fmt"), R.get("genre")] if v)
    base = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(base)
    digs.txt(d, (100, 1048), R["a"], 64, INK, maxw=880)
    digs.txt(d, (102, 1105), title, 46, INK, bold=False, maxw=880)
    digs.txt(d, (102, 1148), meta, 28, INK, bold=False, maxw=880)
    digs.txt(d, (100, 1302), R["shop_full"], 34, INK, maxw=560)
    digs.txt(d, (980, 1302), "monthlyvinyl.net", 34, INK, anchor="rs", maxw=400)
    d.polygon([(100, 1212), (100, 1236), (121, 1224)], fill=INK)
    ftr = digs.fit(d, R["tname"], 32, False, 700)
    d.text((137, 1240), R["tname"], font=ftr, fill=INK, anchor="ls")
    bx = 137 + int(d.textlength(R["tname"], font=ftr)) + 22
    d.rectangle([100, 1171, 980, 1173], fill=FAINT)
    cmd = ["ffmpeg", "-y", "-v", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", "%dx%d" % (W, H), "-r", str(FPS), "-i", "-",
           "-f", "f32le", "-ar", str(SR), "-ac", "2", "-i", wav,
           "-c:v", "libx264", "-profile:v", "high", "-level", "4.0", "-pix_fmt", "yuv420p", "-b:v", "6M", "-maxrate", "8M", "-bufsize", "12M",
           "-g", "60", "-preset", "medium", "-c:a", "aac", "-b:a", "192k", "-ar", str(SR), "-ac", "2", "-movflags", "+faststart", "-shortest", out]
    pr = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    for f in range(n):
        z = 1 + 0.04 * f / n                                   # slow push-in inside the frame
        s_ = int(880 * z); o = (s_ - 880) // 2
        im = base.copy()
        im.paste(sq.resize((s_, s_), Image.BICUBIC).crop((o, o, o + 880, o + 880)), (100, 60))
        dd = ImageDraw.Draw(im)
        dd.rectangle([100, 1169, 100 + 880 * (f + 1) / n, 1175], fill=INK)
        for k in range(5):
            ph = math.sin(f * 0.45 + k * 1.7) * 0.5 + 0.5
            h = 6 + 22 * levs[f] * (0.4 + 0.6 * ph)
            dd.rectangle([bx + k * 13, 1238 - h, bx + 8 + k * 13, 1238], fill=INK)
        if f == 15:
            im.save(out.replace(".mp4", ".jpg"), quality=90)
        g = (n - f) / FPS
        if g < 0.6:
            im = Image.blend(Image.new("RGB", (W, H), BG), im, max(0.0, g / 0.6))
        pr.stdin.write(im.tobytes())
    pr.stdin.close()
    if pr.wait() != 0:
        raise RuntimeError("ffmpeg failed")
    os.remove(wav)

def main_fresh(want):
    data = json.load(open(os.path.join(ROOT, "releases.json"), encoding="utf-8"))
    fx = data.get("fx", {})
    day = want.get("date") or data["updated"]
    N, seg_s = int(want.get("n", 4)), int(want.get("seg", 30))
    d_ = dt.date.fromisoformat(day)
    date_s = "%d %s %d" % (d_.day, MONTHS[d_.month - 1], d_.year)
    hist = json.load(open(os.path.join(ROOT, "92h6fy", "history.json"), encoding="utf-8"))
    digs_keys = set(next((e.get("keys", []) for e in hist if e.get("date") == day), []))
    seen = set()
    for e in hist:
        if e.get("date") != day:
            seen.update(e.get("keys", []))
    cands = [c for c in digs.candidates(data, day, seen) if c["key"] not in digs_keys]
    cands.sort(key=lambda c: (-c["score"], -len({x["shop"] for x in c["arr"]})))
    digs.log(len(cands), "fresh candidates for", day)
    slides, used_a, used_shop, used_fam = [], set(), {}, {}
    for rnd in range(2):                                   # 1st round: spread shops and genres, 2nd: fill up
        for c in cands:
            if len(slides) == N:
                break
            x = c["feat"]
            if digs.norm(x["a"]) in used_a or c["key"] in {s["key"] for s in slides}:
                continue
            if rnd == 0 and (used_shop.get(c["shop"], 0) >= 1 or used_fam.get(c["fam"], 0) >= 2):
                continue
            try:
                cov = best_cover(c["arr"])
                if cov is None or min(cov.size) < 450:
                    continue
                aud = tr = None
                for j, t in enumerate(c["tracks"][:3]):
                    try:
                        aud, tr = digs.get_audio(t, False, WORK, 900 + len(slides) * 10 + j), t
                        break
                    except Exception as e:
                        digs.log("audio fail", t.get("u"), e)
                if aud is None:
                    continue
                c = dict(c, track=tr, cover=cov, audio=aud)
                R = digs.prepare(c, fx)
                start, _ = digs.pick_start(aud)
                start = max(0.0, min(start, len(aud) / SR - seg_s - 0.5))
                out = os.path.join(WORK, "slide-%02d.mp4" % (len(slides) + 1))
                fresh_slide(R, cov, aud, start, seg_s, date_s, out)
                slides.append({"key": c["key"], "video": out, "a": R["a"], "t": R["t"], "l": R["l"], "shop": R["shop_full"],
                               "track": R["tname"], "pre": R["pre"], "genre": R["genre"]})
                used_a.add(digs.norm(x["a"])); used_shop[c["shop"]] = used_shop.get(c["shop"], 0) + 1
                used_fam[c["fam"]] = used_fam.get(c["fam"], 0) + 1
                digs.log("slide", len(slides), R["a"], "–", R["t"], "|", R["shop_full"], "| cover", cov.width)
            except Exception as e:
                digs.log("fail", c["key"], e)
    if not slides:
        raise SystemExit("no slides")
    from shutil import copyfile
    copyfile(slides[0]["video"].replace(".mp4", ".jpg"), os.path.join(WORK, "slide-00.jpg"))
    lines = []
    for i, s in enumerate(slides, 1):
        lab = " (%s)" % s["l"] if s["l"] else ""
        lines.append("%d. %s – %s%s · %s" % (i, s["a"], s["t"], lab, s["shop"]))
    cap = os.path.join(WORK, "caption.txt")
    open(cap, "w", encoding="utf-8").write("\n".join(lines) + "\n")
    print(json.dumps({"title": os.path.join(WORK, "slide-00.jpg"), "slides": slides, "caption": cap, "genre": "fresh-" + day}))

def main():
    want = json.load(open(os.path.join(ROOT, "tools", "genre_carousel.json"), encoding="utf-8"))
    if want.get("mode") == "fresh":
        return main_fresh(want)
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
