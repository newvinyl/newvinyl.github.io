#!/usr/bin/env python3
"""Wochenrückblick (Reel, Sonntag 16:00, seit 8.11.26): eine Platte pro Wochentag.
Reduziert und klar anders als Today's Digs: gelber Hintergrund, schwarze Typo,
Wochentag gross, Cover unverändert, Artist und Titel. Je Platte ein Ausschnitt der Hörprobe.

Wunsch in tools/weekly_recap.json:
  {"week": "WEEK 45", "range": "2–8 NOV 2026", "seg": 6,
   "picks": [{"day": "MONDAY", "artist": "...", "title": "...", "track": "(optional)"}, ...]}
Läuft in GitHub Actions (Shops sind nur von dort erreichbar). Ausgabe JSON auf stdout.
--offline: synthetische Cover und Töne, nur für Layout-Tests."""
import argparse, json, os, re, subprocess, sys, tempfile
import numpy as np
from PIL import Image, ImageDraw
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import digs

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
W, H, FPS, SR = 1080, 1920, 30, digs.SR
YEL, INK = (251, 237, 79), (13, 13, 13)
X0, CW = 96, 888               # margin, content width (same grid as the site)
XF = 0.3                       # audio crossfade between records

def F(s, bold=True):
    return digs.F(s, bold)

def fit(text, maxw, start, bold=True, minsize=30):
    s = start
    while s > minsize and F(s, bold).getlength(text) > maxw:
        s -= 2
    return F(s, bold)

def wrap(text, f, maxw, maxlines=2):
    lines, cur = [], ""
    for w in text.split():
        t = (cur + " " + w).strip()
        if f.getlength(t) <= maxw or not cur:
            cur = t
        else:
            lines.append(cur); cur = w
    lines.append(cur)
    if len(lines) > maxlines:
        lines = lines[:maxlines]
        while f.getlength(lines[-1] + "…") > maxw and " " in lines[-1]:
            lines[-1] = lines[-1].rsplit(" ", 1)[0]
        lines[-1] += "…"
    return lines

def clean_title(t):
    t = re.sub(r"\s*\((reissue|repress|remastered[^)]*)\)\s*$", "", t, flags=re.I)
    return t.strip()

def best_cover(arr, offline, seed):
    """real artwork first (coverlife.artwork_score), then the biggest file; hi-res variants of every shop"""
    if offline:
        return digs.get_cover(arr, True, seed)
    import io, coverlife, single_reel
    best, bk = None, None
    for x in arr:
        if not x.get("cover"):
            continue
        for u in dict.fromkeys([single_reel.hires(x["cover"])] + digs.cover_urls([x]) + [x["cover"]]):
            try:
                im = Image.open(io.BytesIO(digs.fetch(u))).convert("RGB")
            except Exception as e:
                digs.log("cover fail", u, e); continue
            im = coverlife.autocrop(im)
            s = min(im.size)
            l, t = (im.width - s) // 2, (im.height - s) // 2
            im = im.crop((l, t, l + s, t + s))
            art, why = coverlife.artwork_score(im)
            k = (art, min(im.width, 1200))
            digs.log("cover", u, im.width, art, why)
            if bk is None or k > bk:
                best, bk = im, k
                best.info.update(art=art, src=u)
    if best is None:
        raise RuntimeError("no cover")
    return best

def find(G, want):
    wa, wt = digs.norm(want["artist"]), digs.norm(want["title"])
    for k, arr in G.items():
        if any(wa in digs.norm(x["a"]) and wt in digs.norm(x["t"]) for x in arr):
            return k, arr
    raise SystemExit("release not found: %s – %s" % (want["artist"], want["title"]))

def base_frame(day, artist, title):
    """static layer: weekday, artist, title, site – cover goes in at y COV_Y"""
    img = Image.new("RGB", (W, H), YEL)
    d = ImageDraw.Draw(img)
    d.text((X0, 420), day, font=fit("WEDNESDAY", CW, 170), fill=INK, anchor="ls")   # same size every day
    fa = fit(artist, CW, 60, True, 40)
    y = COV_Y + CW + 82
    for ln in wrap(artist, fa, CW, 2):
        d.text((X0, y), ln, font=fa, fill=INK, anchor="ls"); y += int(fa.size * 1.12)
    ft = F(48, False)
    for ln in wrap(title, ft, CW, 2):
        d.text((X0, y + 4), ln, font=ft, fill=INK, anchor="ls"); y += int(ft.size * 1.15)
    d.text((X0 + CW, 1650), "monthlyvinyl.net", font=F(30), fill=INK, anchor="rs")
    return img

COV_Y = 470

def title_frame(recs, want):
    """title card: RECAP + week, then all covers fanned top to bottom – upright, each one showing a strip,
    the last one complete; weekday next to every strip"""
    img = Image.new("RGB", (W, H), YEL)
    d = ImageDraw.Draw(img)
    d.text((X0, 330), want.get("kicker", "WEEKLY"), font=F(46), fill=INK, anchor="ls")
    d.text((X0, 470), want.get("headline", "RECAP"), font=fit("WEDNESDAY", CW, 170), fill=INK, anchor="ls")
    d.text((X0, 540), "%s  ·  %s" % (want.get("week", ""), want.get("range", "")), font=F(40, False), fill=INK, anchor="ls")
    n = len(recs)
    cs, top, bottom = 600, 610, 1640
    step = (bottom - top - cs) / max(1, n - 1)
    for i, r in enumerate(recs):
        y = int(top + i * step)
        cov = r["cover"].convert("RGB").resize((cs, cs), Image.LANCZOS)
        sh = Image.new("RGB", (cs, 6), tuple(int(c * 0.82) for c in YEL))
        img.paste(sh, (X0, y - 6))                     # hairline shadow: the strips read as separate sleeves
        img.paste(cov, (X0, y))
        d.text((X0 + cs + 28, y + min(step, 120) / 2 + 14), r["day"][:3], font=F(42), fill=INK, anchor="ls")
    return img

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--offline", action="store_true")
    ap.add_argument("--config", default=os.path.join(ROOT, "tools", "weekly_recap.json"))
    a = ap.parse_args()
    work = os.environ.get("RECAP_WORK") or tempfile.mkdtemp()
    want = json.load(open(a.config, encoding="utf-8"))
    seg_s = float(want.get("seg") or 6)
    data = json.load(open(os.path.join(ROOT, "releases.json"), encoding="utf-8"))
    G = {}
    for s in data["shops"]:
        for it in s.get("items") or []:
            G.setdefault(digs.gkey(it), []).append(dict(it, shop=s["shop"]))
    recs, mixes = [], []
    for i, p in enumerate(want["picks"]):
        k, arr = find(G, p)
        feat = arr[0]
        tracks = digs.playable(arr) or ([{"u": "", "n": ""}] if a.offline else [])
        pref = [t for t in tracks if p.get("track") and digs.norm(p["track"]) in digs.norm(t["n"])] + tracks
        aud = None
        for j, t in enumerate(pref[:4]):
            try:
                aud = digs.get_audio(t, a.offline, work, 900 + i * 10 + j); break
            except Exception as e:
                digs.log("audio fail", t.get("u"), e)
        if aud is None:
            raise SystemExit("no audio: %s – %s" % (p["artist"], p["title"]))
        cov = best_cover(arr, a.offline, 50 + i)
        start, _ = digs.pick_start(aud)
        L = seg_s + (XF if i < len(want["picks"]) - 1 else 0)
        mixes.append(digs.fade(digs.seg(aud, max(0.0, start), L), 0.15, XF if i < len(want["picks"]) - 1 else 0.8))
        artist = p.get("show_artist") or feat["a"]
        title = clean_title(p.get("show_title") or feat["t"])
        recs.append(dict(day=p["day"].upper(), artist=artist, title=title, cover=cov, key=k,
                         src=cov.info.get("src", ""), cover_px=cov.width))
        digs.log("pick", p["day"], artist, "–", title, "| cover", cov.width, cov.info.get("src", ""))
    # audio: overlap XF between records
    n = len(recs)
    total = n * seg_s
    out_a = np.zeros((int((total + 1) * SR), 2), "float32")
    for i, m in enumerate(mixes):
        o = int(i * seg_s * SR)
        out_a[o:o + len(m)] += m[:len(out_a) - o]
    out_a = out_a[:int(total * SR)]
    wav = os.path.join(work, "recap.wav")
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "f32le", "-ar", str(SR), "-ac", "2", "-i", "-", wav],
                   input=np.clip(out_a, -1, 1).astype("<f4").tobytes(), check=True)
    slug = re.sub(r"[^a-z0-9]+", "-", want.get("week", "week").lower()).strip("-")
    out = os.path.join(work, "weekly-recap-%s.mp4" % slug)
    poster = out.replace(".mp4", ".jpg")
    enc = subprocess.Popen(["ffmpeg", "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", "%dx%d" % (W, H),
                            "-r", str(FPS), "-i", "-", "-i", wav, "-map", "0:v", "-map", "1:a", "-c:v", "libx264", "-crf", "18",
                            "-preset", "medium", "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "192k", "-shortest",
                            "-movflags", "+faststart", out], stdin=subprocess.PIPE)
    title = title_frame(recs, want)
    title_p = out.replace(".mp4", "-title.jpg")
    title.save(title_p, quality=93)
    poster_i = int(want.get("poster_index", 0))
    for i, r in enumerate(recs):
        base = base_frame(r["day"], r["artist"], r["title"])
        cov = r["cover"].convert("RGB").resize((CW, CW), Image.LANCZOS)
        nf = int(round(seg_s * FPS))
        for f in range(nf):
            t = f / FPS
            z = 0.965 + 0.035 * min(1.0, t / 0.45) ** 0.5 if t < 0.45 else 1.0   # cover settles in, never altered
            img = base.copy()
            if z < 1.0:
                s = int(CW * z)
                img.paste(cov.resize((s, s), Image.BILINEAR), (X0 + (CW - s) // 2, COV_Y + (CW - s) // 2))
            else:
                img.paste(cov, (X0, COV_Y))
            enc.stdin.write(img.tobytes())
            if i == poster_i and f == nf // 2:
                img.save(poster, quality=92)
    enc.stdin.close(); enc.wait()
    cap = os.path.join(work, "weekly-recap-%s.txt" % slug)
    if want.get("caption"):
        open(cap, "w", encoding="utf-8").write(want["caption"].rstrip() + "\n")
    print(json.dumps({"video": out, "poster": poster, "title": title_p, "caption": cap if want.get("caption") else None, "dur": total,
                      "records": [{k: v for k, v in r.items() if k != "cover"} for r in recs]}, ensure_ascii=False))

if __name__ == "__main__":
    main()
