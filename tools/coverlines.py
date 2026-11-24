#!/usr/bin/env python3
"""«Cover lines» reel (user, 24.11.26; Maryos Syawish – Qurmami): the drawn lines of a cover come alive – they swing and
tremble smoothly through the 9:16 screen. Nothing else moves, never any zoom. The paper of the cover carries on above
and below. Loop: at the end every line is back in its place.

    reel_coverlines(cover, aud, seed, out, poster, lines, info, dur=45)

lines = {"name": {"pts": [[x, y], …], "col": "grey"|"purple"}}: rough centre lines in a 1080 px cover; every ink pixel
goes to the nearest one of its colour."""
import math, os, sys
import numpy as np, cv2
from PIL import Image, ImageDraw
sys.path.insert(0, os.path.dirname(__file__))
import reelfx as R

W, H, S = R.W, R.H, 1080
OY = (H - S) // 2 - 20

def ss(x):
    x = min(1.0, max(0.0, x))
    return x * x * (3 - 2 * x)

def split(cover, lines):
    """base picture without the lines (float 0..1) and one transmittance layer per line"""
    c = cv2.resize(np.asarray(cover.convert("RGB")), (S, S), interpolation=cv2.INTER_AREA).astype(np.float32)
    P = cv2.GaussianBlur(cv2.medianBlur(c.astype(np.uint8), 151).astype(np.float32), (0, 0), 25)     # the bare paper
    ink = (P - c).max(2)
    ink[:6] = ink[-6:] = 0; ink[:, :3] = ink[:, -3:] = 0        # the photographed edge of the cover is not a line
    m = (ink > 14).astype(np.uint8)
    n, lab, st, _ = cv2.connectedComponentsWithStats(cv2.morphologyEx(m, cv2.MORPH_CLOSE, np.ones((9, 9), np.uint8)))
    photo = np.zeros((S, S), bool)
    for i in range(1, n):                                    # dense blocks (a photo on the cover) stay where they are
        x, y, w, h, a = st[i]
        if a > .5 * w * h and a > 4000:
            photo[max(0, y - 5):y + h + 5, max(0, x - 5):x + w + 5] = True
    if photo.any():                                          # the paper tone must not know about the photo
        c2 = c.copy(); c2[photo] = np.median(c[~photo].reshape(-1, 3), 0)
        P = cv2.GaussianBlur(cv2.medianBlur(c2.astype(np.uint8), 151).astype(np.float32), (0, 0), 25)
        ink = (P - c).max(2)
        ink[:6] = ink[-6:] = 0; ink[:, :3] = ink[:, -3:] = 0
    purple = (c[..., 2] - c[..., 0]) > 10                    # RGB: blue clearly above red
    names = list(lines)
    D = []
    for k in names:
        im = np.full((S, S), 255, np.uint8)
        cv2.polylines(im, [np.array(lines[k]["pts"], np.int32)], False, 0, 1)
        d = cv2.distanceTransform(im, cv2.DIST_L2, 5)
        isp = lines[k].get("col") == "purple"
        d = np.where((ink > 22) & (purple != isp), d + 60, d)        # clear colours only go to lines of that colour
        D.append(d)
    near = np.argmin(np.stack(D), 0)
    inkm = cv2.dilate((ink > 6).astype(np.uint8), np.ones((5, 5), np.uint8)) > 0
    strong = cv2.dilate((ink > 14).astype(np.uint8), np.ones((25, 25), np.uint8)) > 0     # faint specks far from any stroke are paper
    inkm &= strong & ~photo
    ratio = np.clip(c / np.maximum(P, 1), 0, 1)
    T, M = [], []
    for i in range(len(names)):
        mi = inkm & (near == i)
        M.append(mi)
        T.append(np.where(mi[..., None], ratio, 1.0).astype(np.float32))
    for i in range(len(names)):                              # where another line crosses, this one carries on underneath
        other = np.zeros((S, S), bool)
        for j in range(len(names)):
            if j != i:
                other |= M[j]
        hole = (other & (cv2.dilate(M[i].astype(np.uint8), np.ones((15, 15), np.uint8)) > 0)).astype(np.uint8)
        if hole.any():
            t8 = cv2.inpaint((T[i] * 255).astype(np.uint8), hole, 5, cv2.INPAINT_TELEA).astype(np.float32) / 255
            T[i] = np.where(hole[..., None] > 0, t8, T[i])
    prod = np.ones_like(T[0])
    for t in T:
        prod *= t
    base = np.minimum(c / np.maximum(prod, .05), P + 3)
    base[photo] = c[photo]
    return base, P, T, M, names, c, photo

def reel_coverlines(cover, aud, seed, out, poster, lines, info, dur=45):
    rng = np.random.default_rng(seed + 771)
    nfr = int(dur * R.FPS)
    aud = aud[:int(dur * R.SR)]
    lev, _ = R.analyse(aud, nfr)
    k = np.ones(R.FPS) / R.FPS
    lev = np.convolve(np.pad(lev, (len(k), len(k)), mode="edge"), k, "same")[len(k):-len(k)]
    base, P, T, M, names, c, photo = split(cover, lines)
    R.log("Coverlines:", len(names), "lines")
    # ---------- the paper carries on above and below: smooth paper tone + the cover's own grain, mirrored
    top, bot = OY, H - OY - S
    Pf = cv2.copyMakeBorder(P, top, bot, 0, 0, cv2.BORDER_REPLICATE)
    res = base - P
    grain = res.copy(); grain[photo] = 0
    edge = np.minimum(np.minimum(np.arange(S), S - 1 - np.arange(S)) / 14.0, 1).astype(np.float32)        # the photographed edge of the sleeve: no seam
    grain *= (edge[:, None] * edge[None, :])[..., None]
    resf = cv2.copyMakeBorder(grain, top, bot, 0, 0, cv2.BORDER_REFLECT)
    full = np.clip(Pf + resf, 0, 255)
    ph = np.zeros((H, W), bool); ph[OY:OY + S] = photo
    full[ph] = c[photo]
    # ---------- type: only what is needed, in the purple of the cover (yellow cannot be read on white paper)
    pm = ((c[..., 2] - c[..., 0]) > 25) & ((P - c).max(2) > 40)
    col = tuple(int(v) for v in (c[pm].mean(0) * .82 if pm.sum() > 50 else (70, 60, 160)))
    im = Image.fromarray(full.astype(np.uint8)); dr = ImageDraw.Draw(im)
    fd = os.path.join(os.path.dirname(__file__), "fonts")
    fb, fr_ = os.path.join(fd, "texgyreheros-bold.otf"), os.path.join(fd, "texgyreheros-regular.otf")
    dr.text((64, 196), info["artist"], font=R.fit_font(fb, 66, info["artist"], W - 128), fill=col)
    dr.text((64, 278), info["title"], font=R.fit_font(fr_, 52, info["title"], W - 128), fill=col)
    dr.text((64, H - 398), info["meta"], font=R.fit_font(fr_, 34, info["meta"], W - 128), fill=col)
    dr.text((64, H - 350), "monthlyvinyl.net", font=R.F(fb, 34), fill=col)
    full = np.asarray(im).astype(np.float32)

    G = 6                                                                  # the motion is smooth: work it out on a coarse grid
    gx, gy = np.meshgrid(np.arange(0, W + G, G, dtype=np.float32) + (G - 1) / 2, np.arange(0, H + G, G, dtype=np.float32) + (G - 1) / 2)
    FW, FH = gx.shape[1] * G, gx.shape[0] * G
    L = []
    T0 = float(dur)
    for i, name in enumerate(names):
        ys, xs = np.where(M[i])
        cen = np.array([xs.mean(), ys.mean() + OY])
        ext = max(xs.max() - xs.min(), ys.max() - ys.min())
        flat = (xs.max() - xs.min()) > 2.2 * (ys.max() - ys.min())        # a lying line: travels up and down
        def osc(n, amp):
            return [(amp * rng.uniform(.5, 1) / (1 + .7 * j), int(rng.integers(1, 3)) + j, rng.uniform(0, 6.283)) for j in range(n)]
        dx, dy = (osc(2, 70), osc(2, 560)) if flat else (osc(2, 170), osc(2, 380))
        rot = osc(2, .22 if flat else .5)
        tgt = np.array([W / 2 + rng.uniform(-60, 60) + (cen[0] - W / 2) * .5, rng.uniform(640, 1180)])
        ts = np.arange(nfr) / R.FPS
        def val_of(o, t):
            return sum(am * np.sin(6.2832 * m * t / T0 + ph) for am, m, ph in o)
        for o, cc, lo, hi in ((dx, tgt[0], 200, W - 200), (dy, tgt[1], 260, H - 420)):
            v = val_of(o, ts)
            f = min(1.0, (hi - cc) / max(1e-6, v.max()), (cc - lo) / max(1e-6, -v.min()))
            o[:] = [(am * f, m, ph) for am, m, ph in o]
        waves = []
        for wl, amp, f0, f1 in ((rng.uniform(520, 800), 30, .10, .17), (rng.uniform(300, 430), 15, .15, .26), (rng.uniform(170, 240), 6, .24, .4)):
            a = rng.uniform(0, 6.283)                                       # the line swings: slow waves run through it
            b = a + 1.5708 + rng.uniform(-.5, .5)
            waves.append((amp * rng.uniform(.75, 1.1), math.cos(a) / wl, math.sin(a) / wl, rng.uniform(f0, f1) * rng.choice([-1, 1]),
                          rng.uniform(0, 6.283), math.cos(b), math.sin(b)))
        trem = []
        for _ in range(2):                                                  # … and trembles: small and quick
            a = rng.uniform(0, 6.283); wl = rng.uniform(70, 130); b = a + 1.5708
            trem.append((rng.uniform(.8, 1.2), math.cos(a) / wl, math.sin(a) / wl, rng.uniform(4.5, 7.5), rng.uniform(0, 6.283), math.cos(b), math.sin(b)))
        gate = (rng.uniform(.06, .12), rng.uniform(0, 6.283), rng.uniform(.14, .22), rng.uniform(0, 6.283))
        Tf = cv2.copyMakeBorder(T[i], top, bot, 0, 0, cv2.BORDER_CONSTANT, value=(1, 1, 1))
        L.append(dict(T=Tf, cen=cen, dx=dx, dy=dy, rot=rot, tgt=tgt, waves=waves, trem=trem, gate=gate, val_of=val_of,
                      delay=rng.uniform(0, 1.6), ext=ext))

    def fr(f):
        t = f / R.FPS
        back = 1 - ss((t - (T0 - 9.0)) / 8.0)
        img = full.copy()
        for l in L:
            ev = ss((t - .05) / .9) * back                                 # in motion from the very first moment
            ed = ss((t - .3 - l["delay"]) / 8.0) * back                    # … and off through the screen
            off = (l["tgt"] - l["cen"] + np.array([l["val_of"](l["dx"], t), l["val_of"](l["dy"], t)])) * ed
            th = l["val_of"](l["rot"], t) * ed
            cx, cy = l["cen"]
            co, si = math.cos(-th), math.sin(-th)
            px, py = gx - cx - off[0], gy - cy - off[1]
            sx = cx + px * co - py * si
            sy = cy + px * si + py * co
            ux = np.zeros_like(sx); uy = np.zeros_like(sy)
            early = 1 + 1.2 * (1 - ss(t / 5.0))                            # a clear first move, then calmer
            for am, qx, qy, fq, ph, bx, by in l["waves"]:
                w = (am * ev * early) * np.sin(6.2832 * (sx * qx + sy * qy - fq * t) + ph)
                ux += w * bx; uy += w * by
            g0 = l["gate"]
            burst = max(0.0, math.sin(6.2832 * g0[0] * t + g0[1]) * .6 + math.sin(6.2832 * g0[2] * t + g0[3]) * .6) ** 1.5
            tr = (.5 + 1.9 * burst) * (.55 + .9 * float(lev[min(f, nfr - 1)])) * ev
            for am, qx, qy, fq, ph, bx, by in l["trem"]:
                w = (am * tr) * np.sin(6.2832 * (sx * qx + sy * qy - fq * t) + ph)
                ux += w * bx; uy += w * by
            mx = cv2.resize((sx - ux).astype(np.float32), (FW, FH), interpolation=cv2.INTER_CUBIC)[:H, :W]
            my = cv2.resize((sy - uy).astype(np.float32), (FW, FH), interpolation=cv2.INTER_CUBIC)[:H, :W]
            tl = cv2.remap(l["T"], mx, my, cv2.INTER_LINEAR, borderMode=cv2.BORDER_CONSTANT, borderValue=(1, 1, 1))
            img *= tl
        return np.clip(img, 0, 255).astype(np.uint8)

    R.encode(fr, nfr, aud, out, poster, int(12 * R.FPS))
    return "coverlines %d" % len(L)

if __name__ == "__main__":             # local test: python3 tools/coverlines.py cover.jpg lines.json out.mp4 [audio] [dur]
    import json, subprocess
    dur = int(sys.argv[5]) if len(sys.argv) > 5 else 45
    cfg = json.load(open(sys.argv[2]))
    if len(sys.argv) > 4 and sys.argv[4] != "-":
        raw = subprocess.run(["ffmpeg", "-v", "error", "-i", sys.argv[4], "-f", "f32le", "-ac", "2", "-ar", str(R.SR), "-"], capture_output=True).stdout
        aud = np.frombuffer(raw, "<f4").reshape(-1, 2)[:dur * R.SR].copy()
    else:
        aud = np.zeros((dur * R.SR, 2), np.float32) + 1e-4
    print(reel_coverlines(Image.open(sys.argv[1]), aud, 1, sys.argv[3], sys.argv[3].replace(".mp4", ".jpg"), cfg["lines"], cfg["info"], dur=dur))
