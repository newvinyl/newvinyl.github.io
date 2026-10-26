#!/usr/bin/env python3
"""Today's Digs in ONE view (since 26.10.26): all three covers always visible, the playing one large,
the two others small in a grid column that swaps sides with every track. Black background, yellow type
(Helvetica, as on the site). Reads top to bottom like a card on the site:
TODAY'S DIGS / date · artist · title · covers · label · format · ▶ track + equalizer · progress · shop / site."""
import math, os, re, subprocess
import numpy as np
from PIL import Image, ImageDraw

import digs
W, H, FPS, SR = digs.W, digs.H, digs.FPS, digs.SR
BG, INK = (13, 13, 13), (251, 237, 79)

# Grid: margin 96, gutter 24, width 888 = big + gutter + small, big = 2 small + gutter
G, X0, Y0 = 24, 96, 600
SS = (888 - 2 * G) // 3          # 280
BS = 2 * SS + G                  # 584

def F(size, bold):
    return digs.F(size, bold)

def fit(text, maxw, start, bold):
    s = start
    while s > 24 and F(s, bold).getlength(text) > maxw:
        s -= 2
    return F(s, bold)

def wrap(text, f, maxw):
    lines, cur = [], ""
    for w_ in text.split():
        t = (cur + " " + w_).strip()
        if f.getlength(t) <= maxw or not cur:
            cur = t
        else:
            lines.append(cur); cur = w_
    lines.append(cur)
    while len(lines) > 1 and f.getlength(lines[-1]) < maxw / 3 and len(lines[-2].split()) > 1:   # no orphans
        a, b = lines[-2].rsplit(" ", 1)
        if f.getlength(b + " " + lines[-1]) > maxw:
            break
        lines[-2], lines[-1] = a, b + " " + lines[-1]
    return lines

def ease(x):
    x = max(0.0, min(1.0, x)); return x * x * (3 - 2 * x)

def slots(active, n):
    others = [(active + k) % n for k in range(1, n)]
    left = active % 2 == 0
    bx = X0 if left else X0 + SS + G
    sx = X0 + BS + G if left else X0
    r = {active: (bx, Y0, BS)}
    for k, i in enumerate(others):
        r[i] = (sx, Y0 + k * (SS + G), SS)
    return r

def lerp(a, b, m):
    return tuple(x + (y - x) * m for x, y in zip(a, b))

FMT = re.compile(r"""\s*[\(\[]?\b(\d\s*[x×]\s*)?(lp|ep|2lp|3lp|12|10|7)\b["″”']?\s*(\d\s*[x×]\s*\d+["″”']?)?[\)\]]?\s*$""", re.I)

def clean_title(t):
    """shop titles carry format junk ('… LP 2×12″', '(2LP + 10" LTD EDITION)'); all-caps titles get title case"""
    t = digs.cap_title(t) if hasattr(digs, "cap_title") else t
    t = re.sub(r"\s*\((\d\s*)?(lp|ep|x?\s*12|vinyl|ltd|limited|gatefold|sticker)[^)]*\)\s*$", "", t, flags=re.I)
    for _ in range(3):
        t2 = FMT.sub("", t).strip(" -–")
        if t2 == t or not t2:
            break
        t = t2
    if t.isupper() and len(t) > 3:
        t = " ".join(w if any(ch.isdigit() for ch in w) else w.capitalize() for w in t.lower().split())
    return t

def info(p):
    """text for one release from digs.prepare() output"""
    title = clean_title(p["t"])
    meta = "  ·  ".join(v for v in [p.get("l"), p.get("fmt")] if v)
    shop = ("Pre-order at %s" if p.get("pre") else "Available at %s") % p["shop_full"]
    return dict(a=p["a"], t=title, meta=meta, tr=p["tname"], shop=shop)

def page(img, r, a, dy, frame, lev):
    if a <= 0:
        return
    lay = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(lay)
    c = INK + (int(255 * a),)
    fa = F(110, True)
    if fa.getlength(r["a"]) > 888:
        fa = fit(r["a"], 888, 110, True)
    d.text((90, 316 + dy), r["a"], font=fa, fill=c, anchor="ls")
    ft = F(72, False)
    lines = wrap(r["t"], ft, 888)
    if len(lines) > 2:                                     # very long titles: smaller, still max 2-3 lines
        ft = F(58, False); lines = wrap(r["t"], ft, 888)[:3]
    y = 396 + dy
    for ln in lines[:3]:
        d.text((92, y), ln, font=ft, fill=c, anchor="ls"); y += int(ft.size * 1.11)
    yb = Y0 + BS
    d.text((94, yb + 78 + dy), r["meta"], font=fit(r["meta"], 888, 48, False), fill=c, anchor="ls")
    by = yb + 150 + dy
    d.polygon([(96, by - 30), (96, by - 2), (120, by - 16)], fill=c)
    ftr = fit(r["tr"], 760, 44, False)
    d.text((140, by), r["tr"], font=ftr, fill=c, anchor="ls")
    bx = 140 + int(ftr.getlength(r["tr"])) + 26
    for k in range(5):
        ph = math.sin(frame * 0.45 + k * 1.7) * 0.5 + 0.5
        h = 6 + 30 * lev * (0.4 + 0.6 * ph)
        d.rectangle([bx + k * 14, by - h, bx + 8 + k * 14, by], fill=c)
    d.text((96, 1572 + dy), r["shop"], font=fit(r["shop"], 560, 38, True), fill=c, anchor="ls")
    img.paste(lay, (0, 0), lay)

def chrome(img, date_s, t, seg_s, n):
    d = ImageDraw.Draw(img)
    d.text((96, 170), "TODAY'S DIGS", font=F(34, True), fill=INK, anchor="ls")
    d.text((984, 170), date_s, font=F(34, True), fill=INK, anchor="rs")
    d.text((984, 1572), "monthlyvinyl.net", font=F(38, True), fill=INK, anchor="rs")
    pw = (888 - 2 * 14) / n
    faint = tuple(int(b + (c - b) * .25) for b, c in zip(BG, INK))
    for k in range(n):
        x0 = 96 + k * (pw + 14)
        d.rectangle([x0, 1496, x0 + pw, 1500], fill=faint)
        p_ = 1.0 if k < t // seg_s else (min(1.0, (t - k * seg_s) / seg_s) if k == t // seg_s else 0.0)
        if p_ > 0:
            d.rectangle([x0, 1494, x0 + pw * p_, 1502], fill=INK)

def render(ps, mixes, seg_s, date_s, path, poster):
    """ps: digs.prepare() dicts with 'cover'; mixes: one audio segment per release (seg_s seconds each)"""
    n = len(ps)
    covs = []
    for p in ps:
        c = p["cover"].convert("RGB"); s = min(c.size)
        covs.append(c.crop(((c.width - s) // 2, (c.height - s) // 2, (c.width + s) // 2, (c.height + s) // 2)).resize((BS, BS), Image.LANCZOS))
    R = [info(p) for p in ps]
    mix = np.concatenate(mixes)
    peak = np.abs(mix).max()
    if peak > 0.97:
        mix = mix * (0.97 / peak)
    total = int(seg_s * FPS) * n
    hop = SR // FPS
    m = mix.mean(1)
    levs = np.array([np.sqrt(np.mean(m[f * hop:(f + 1) * hop] ** 2)) if f * hop < len(m) else 0 for f in range(total)])
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
    cache = {}
    def cov(i, s):
        k = (i, int(s))
        if k not in cache:
            if len(cache) > 40: cache.clear()
            cache[k] = covs[i].resize((int(s), int(s)), Image.LANCZOS)
        return cache[k]
    for f in range(total):
        t = f / FPS
        sg = min(n - 1, int(t // seg_s))
        mv = ease((t - sg * seg_s) / 0.8) if sg > 0 else 1.0          # covers glide to the new places
        prev = sg - 1 if sg > 0 else 0
        im = Image.new("RGB", (W, H), BG)
        chrome(im, date_s, t, seg_s, n)
        sa, sb = slots(prev, n), slots(sg, n)
        for i in sorted(range(n), key=lambda i: (i == sg, i == prev)):
            x, y, s = lerp(sa[i], sb[i], mv)
            if sg == 0:                                                 # opening: covers glide into place one after another,
                k = ease((t - 0.12 * i) / 0.6)                          # fully visible from the very first frame
                z = 0.9 + 0.1 * k                                       # (first frame = profile thumbnail, never black):
                x, y, s = x + s * (1 - z) / 2, y + s * (1 - z) / 2, s * z   # grow from 90 % around their centre
            c = cov(i, s)
            im.paste(c, (int(x), int(y)))
        if mv < 1:
            page(im, R[prev], 1 - ease(mv / 0.5), -30 * ease(mv / 0.5), f, levs[f])
        a = ease((mv - 0.4) / 0.6) if sg > 0 else 1.0                 # type fully there from the first frame
        page(im, R[sg], a, 30 * (1 - ease((mv - 0.4) / 0.6)) if sg > 0 else 0, f, levs[f])
        if f == int(1.5 * FPS):
            im.save(poster, quality=88)
        g = (total - f) / FPS
        if g < 1.0:
            im = Image.blend(Image.new("RGB", (W, H), (0, 0, 0)), im, max(0.0, g))
        pr.stdin.write(im.tobytes())
    pr.stdin.close()
    if pr.wait() != 0:
        raise RuntimeError("ffmpeg failed")
    os.remove(wav)
