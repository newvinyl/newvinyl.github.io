#!/usr/bin/env python3
"""«Lines» reel (user, 24.11.26): a screenshot of a release card from monthlyvinyl.net stands still, only its lines
(frame, underlines, button) come alive – they swing and tremble smoothly through the screen. Never any zoom, the type
never moves. Loop: at the end every line is back in its place.

    reel_lines(card_path, aud, seed, out, poster, dur=45)

Lines are found automatically: long, thin, straight horizontal/vertical runs in the screenshot."""
import math, os, sys
import numpy as np, cv2
from PIL import Image, ImageDraw
sys.path.insert(0, os.path.dirname(__file__))
import reelfx as R

W, H, SS = R.W, R.H, 2            # SS = supersampling of the line layer
MINLEN = 110                      # px in the screenshot: shorter runs are type, not lines

def find_lines(g, thr=70):
    """[(x0, y0, x1, y1, thickness, grey)] of straight lines in a greyscale screenshot (inclusive pixel boxes)"""
    out = []
    for horiz in (True, False):
        a = g if horiz else g.T
        runs = {}
        for y in range(a.shape[0]):
            on = np.concatenate([[0], (a[y] > thr).astype(np.int8), [0]])
            d = np.diff(on)
            for s, e in zip(np.where(d == 1)[0], np.where(d == -1)[0]):
                if e - s >= MINLEN:
                    runs.setdefault((int(s), int(e)), []).append(y)
        for (s, e), ys in runs.items():
            ys.sort()
            grp = [ys[0]]
            for y in ys[1:] + [None]:
                if y is not None and y == grp[-1] + 1:
                    grp.append(y); continue
                if len(grp) <= 10:                       # thin: a line, not a block
                    val = float(a[grp[0]:grp[-1] + 1, s:e].mean())
                    box = (s, grp[0], e - 1, grp[-1]) if horiz else (grp[0], s, grp[-1], e - 1)
                    out.append(box + (len(grp), val))
                grp = [y] if y is not None else []
    return out

def ss(x):
    x = min(1.0, max(0.0, x))
    return x * x * (3 - 2 * x)

def reel_lines(card_path, aud, seed, out, poster, dur=45, site="monthlyvinyl.net"):
    rng = np.random.default_rng(seed + 2411)
    nfr = int(dur * R.FPS)
    aud = aud[:int(dur * R.SR)]
    lev, _ = R.analyse(aud, nfr)
    k = np.ones(R.FPS) / R.FPS
    lev = np.convolve(np.pad(lev, (len(k), len(k)), mode="edge"), k, "same")[len(k):-len(k)]     # the music's breath
    card = Image.open(card_path).convert("RGB")
    a = np.asarray(card).copy()
    g = a.astype(np.float32).mean(2)
    bg = np.median(a.reshape(-1, 3), 0)
    found = find_lines(g)
    R.log("Lines:", len(found), "lines found")
    for x0, y0, x1, y1, th, val in found:                # take the lines out of the still picture
        a[max(0, y0 - 2):y1 + 3, max(0, x0 - 2):x1 + 3] = bg
    sc = W / card.width
    ch = int(round(card.height * sc))
    oy = (H - ch) // 2 - 30
    base = np.empty((H, W, 3), np.uint8); base[:] = bg
    base[oy:oy + ch] = np.asarray(Image.fromarray(a).resize((W, ch), Image.LANCZOS))
    if site:                                              # small, still, in the yellow of the card
        yel = a[(a[..., 0] > 200) & (a[..., 2] < 140)]
        col = tuple(int(v) for v in (yel.mean(0) if len(yel) else (245, 230, 90)))
        im = Image.fromarray(base); dr = ImageDraw.Draw(im)
        f = R.F(os.path.join(os.path.dirname(__file__), "fonts", "texgyreheros-bold.otf"), 30)
        fx0 = min(l[0] for l in found) * sc if found else 40
        dr.text((fx0, oy + ch + 26), site, font=f, fill=col)
        base = np.asarray(im).copy()

    L = []
    for x0, y0, x1, y1, th, val in found:
        horiz = (x1 - x0) > (y1 - y0)
        if horiz:
            p0 = np.array([x0 * sc, oy + (y0 + y1 + 1) / 2 * sc]); p1 = np.array([(x1 + 1) * sc, p0[1]])
        else:
            p0 = np.array([(x0 + x1 + 1) / 2 * sc, oy + y0 * sc]); p1 = np.array([p0[0], oy + (y1 + 1) * sc])
        ln = float(np.linalg.norm(p1 - p0))
        small = ln < 420
        T = float(dur)
        def osc(n, amp):                                  # smooth path that closes after the reel (whole cycles)
            return [(amp * rng.uniform(.45, 1) / (1 + .6 * j), int(rng.integers(1, 3)) + j, rng.uniform(0, 6.283)) for j in range(n)]
        if horiz:
            dx, dy = osc(2, 150 if small else 60), osc(3, 520 if small else 640)
            tgt = np.array([rng.uniform(250, W - 250) if small else W / 2, rng.uniform(620, 1180)])
        else:
            dx, dy = osc(3, 360 if small else 400), osc(2, 520 if small else 300)
            tgt = np.array([rng.uniform(330, W - 330), rng.uniform(500, 1300) if small else rng.uniform(820, 1020)])
        rot = osc(2, .75 if small else .2)
        c0 = (p0 + p1) / 2
        ts = np.arange(nfr) / R.FPS
        def val_of(o, t):
            return sum(am * np.sin(6.2832 * m * t / T + ph) for am, m, ph in o)
        # in flight a line circles around a place of its own; keep it on the screen: scale the path down if it would leave
        for o, c, lo, hi in ((dx, tgt[0], 60, W - 60), (dy, tgt[1], 190, H - 330)):
            v = val_of(o, ts)
            f = min(1.0, (hi - c) / max(1e-6, v.max()), (c - lo) / max(1e-6, -v.min()))
            o[:] = [(am * f, m, ph) for am, m, ph in o]
        modes = [(rng.uniform(.6, 1) * amp, kk, rng.uniform(lo, hi), rng.uniform(0, 6.283))
                 for kk, amp, lo, hi in ((1, .050, .16, .30), (2, .026, .30, .52), (3, .014, .50, .85), (5, .006, .9, 1.4))]
        trav = (rng.uniform(.010, .018), rng.uniform(1.2, 2.2), rng.uniform(.25, .5) * rng.choice([-1, 1]), rng.uniform(0, 6.283))
        trem = [(rng.uniform(.7, 1.3), rng.uniform(2.5, 6), rng.uniform(4.5, 8), rng.uniform(0, 6.283)) for _ in range(3)]
        gate = (rng.uniform(.05, .11), rng.uniform(0, 6.283), rng.uniform(.13, .21), rng.uniform(0, 6.283))
        L.append(dict(p0=p0, p1=p1, ln=ln, th=max(1.6, th * sc), val=min(255, val * 1.04), dx=dx, dy=dy, rot=rot, modes=modes,
                      trav=trav, trem=trem, gate=gate, tgt=tgt, delay=rng.uniform(0, 2.2), n=max(24, int(ln / 6)), val_of=val_of))

    def fr(f):
        t = f / R.FPS
        T = float(dur)
        back = 1 - ss((t - (T - 9.5)) / 8.0)                            # everything finds its place again
        layer = np.zeros((H * SS, W * SS), np.uint8)
        for l in L:
            ev = ss((t - 1.0 - .4 * l["delay"]) / 5.0) * back           # 1. trembling and swinging in place …
            ed = ss((t - 2.6 - l["delay"]) / 9.0) * back                # 2. … then they set off through the screen
            c0 = (l["p0"] + l["p1"]) / 2
            off = (l["tgt"] - c0 + np.array([l["val_of"](l["dx"], t), l["val_of"](l["dy"], t)])) * ed
            th = l["val_of"](l["rot"], t) * ed
            c = c0 + off
            d = (l["p1"] - l["p0"]) / l["ln"]
            d = np.array([d[0] * math.cos(th) - d[1] * math.sin(th), d[0] * math.sin(th) + d[1] * math.cos(th)])
            nrm = np.array([-d[1], d[0]])
            s = np.linspace(0, 1, l["n"])
            u = np.zeros_like(s)
            for am, kk, fq, ph in l["modes"]:                           # the string swings
                u += am * l["ln"] * np.sin(math.pi * kk * s) * math.sin(6.2832 * fq * t + ph)
            am, kk, fq, ph = l["trav"]                                  # a slow wave runs along it
            u += am * l["ln"] * np.sin(6.2832 * (kk * s - fq * t) + ph) * np.sin(math.pi * s) ** .6
            g0 = l["gate"]
            burst = max(0.0, math.sin(6.2832 * g0[0] * t + g0[1]) * .6 + math.sin(6.2832 * g0[2] * t + g0[3]) * .6) ** 1.5
            tr = (.7 + 2.6 * burst) * (.55 + .9 * float(lev[min(f, nfr - 1)]))      # trembling comes and goes, with the music
            for am, kk, fq, ph in l["trem"]:
                u += tr * am * np.sin(6.2832 * (kk * s * l["ln"] / 520 + fq * t) + ph) * np.sin(math.pi * s) ** .35
            u *= ev
            pts = c[None] + (s[:, None] - .5) * l["ln"] * d[None] + u[:, None] * nrm[None]
            q = np.round(pts * SS * 16).astype(np.int32)
            cv2.polylines(layer, [q], False, int(l["val"]), max(1, int(round(l["th"] * SS))), cv2.LINE_AA, 4)
        lay = cv2.resize(layer, (W, H), interpolation=cv2.INTER_AREA)
        return np.maximum(base, lay[..., None])

    R.encode(fr, nfr, aud, out, poster, int(11 * R.FPS))
    return "lines %d" % len(L)

if __name__ == "__main__":                                 # local test without music: python3 tools/linecard.py card.jpg out.mp4 [dur]
    dur = int(sys.argv[3]) if len(sys.argv) > 3 else 45
    t = np.arange(dur * R.SR) / R.SR
    sil = (np.sin(6.2832 * t / 7)[:, None] * 1e-3 * np.ones((1, 2))).astype(np.float32)
    print(reel_lines(sys.argv[1], sil, 1, sys.argv[2], sys.argv[2].replace(".mp4", ".jpg"), dur=dur))
