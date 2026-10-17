#!/usr/bin/env python3
"""One detail of a cover comes alive – everything else stays still. Used by the daily single reel.

The daily update looks at the cover and writes a spec into 92h6fy/reel_request.json → "detail":
  {"motion": "figure" | "hop" | "pulse" | "spin" | "sway" | "float" | "wobble" | "eyes",
   "box":   [x0, y0, x1, y1]  – generous frame around the detail, cover coordinates 0..1 (required, except "eyes")
   "pivot": [x, y]            – sway/spin centre (optional; sway: bottom centre, spin: box centre)
   "path":  [[x, y], ...]     – figure only: footholds from where it stands to where it goes (stairs: one per step;
                                 flat ground: start and end are enough); snapped to the surface below
   "loop":  "back" | "down"   – figure only: walk the path and back (default) or only forwards, over and over
                                 (fades out at the end, reappears at the start) – e.g. for a title like "Get Down"
   "energy": "calm" | "wild"  – figure only: smooth groove (default) or big dance moves
   "eyes":  [...]             – eyes only: spec of tools/eyes.py
   "note":  "what it is"}     – free text, shown in the log
Everything moves on the beat of the preview (tempo and phase are measured from the audio).
"""
import math
import numpy as np
import cv2

MOTIONS = ("figure", "hop", "pulse", "spin", "sway", "float", "wobble", "eyes")

# ---------------------------------------------------------------- beat
def beat_grid(aud, sr, lo=96, hi=140):
    """(bpm, phase in s) from the spectral flux of the preview"""
    x = aud.mean(1) if aud.ndim == 2 else aud
    hop, n = 512, 2048
    if len(x) < n * 4:
        return 124.0, 0.0
    idx = np.arange(0, len(x) - n, hop)
    win = np.hanning(n).astype(np.float32)
    S = np.abs(np.fft.rfft(np.stack([x[i:i + n] * win for i in idx]), axis=1))
    flux = np.maximum(0, np.diff(np.log1p(S * 10), axis=0)).sum(1)
    flux = (flux - flux.mean()) / (flux.std() + 1e-9)
    fps = sr / hop
    best = None
    for bpm in np.arange(lo, hi, 0.1):
        per = fps * 60 / bpm
        sc = 0.0
        for k in (1, 2, 4):
            l = int(round(per * k))
            if l < len(flux):
                sc += float(np.dot(flux[:-l], flux[l:])) / len(flux)
        if best is None or sc > best[0]:
            best = (sc, bpm)
    bpm = float(best[1]); per = fps * 60 / bpm
    nb = int((len(flux) - per) / per)
    ph = max(np.arange(0, per, 0.5), key=lambda p: sum(flux[int(p + per * k)] for k in range(max(1, nb))))
    return bpm, float(ph / fps)

# ---------------------------------------------------------------- cut-out
def _px(box, S):
    x0, y0, x1, y1 = [int(round(v * S)) for v in box]
    x0, y0 = max(0, min(x0, x1)), max(0, min(y0, y1))
    x1, y1 = min(S - 1, max(x0 + 8, x1)), min(S - 1, max(y0 + 8, y1))
    return x0, y0, x1, y1

def segment(cov, box):
    """mask (uint8 0/255) of the object inside the box: colour difference to the box border, refined by GrabCut"""
    S = cov.shape[0]
    x0, y0, x1, y1 = _px(box, S)
    reg = cov[y0:y1, x0:x1].astype(np.float32)
    border = np.concatenate([reg[0], reg[-1], reg[:, 0], reg[:, -1]])
    bgc = np.median(border, axis=0)
    diff = np.linalg.norm(reg - bgc, axis=2)
    fg = (diff > max(28, np.percentile(diff, 60) * 0.6)).astype(np.uint8)
    gc = np.full(cov.shape[:2], cv2.GC_BGD, np.uint8)
    gc[y0:y1, x0:x1] = np.where(fg > 0, cv2.GC_PR_FGD, cv2.GC_PR_BGD)
    try:
        bgd, fgd = np.zeros((1, 65), np.float64), np.zeros((1, 65), np.float64)
        cv2.grabCut(cv2.cvtColor(cov, cv2.COLOR_RGB2BGR), gc, None, bgd, fgd, 4, cv2.GC_INIT_WITH_MASK)
        m = np.isin(gc, (cv2.GC_FGD, cv2.GC_PR_FGD)).astype(np.uint8)
    except Exception:
        m = np.zeros(cov.shape[:2], np.uint8); m[y0:y1, x0:x1] = fg
    m = cv2.morphologyEx(m, cv2.MORPH_OPEN, np.ones((3, 3), np.uint8))
    m = cv2.morphologyEx(m, cv2.MORPH_CLOSE, np.ones((5, 5), np.uint8))
    # keep the components that matter (big ones and those near the box centre); drop what leaks out of the box
    n, lab, st, cen = cv2.connectedComponentsWithStats(m, 8)
    keep = np.zeros_like(m)
    if n > 1:
        big = st[1:, 4].max()
        cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
        for i in range(1, n):
            inside = st[i, 0] >= x0 - 2 and st[i, 1] >= y0 - 2 and st[i, 0] + st[i, 2] <= x1 + 2 and st[i, 1] + st[i, 3] <= y1 + 2
            near = abs(cen[i][0] - cx) < (x1 - x0) * 0.45 and abs(cen[i][1] - cy) < (y1 - y0) * 0.45
            if inside and (st[i, 4] > big * 0.08 or near) and st[i, 4] > 40:
                keep[lab == i] = 1
    if keep.sum() < 50:
        keep = m
        keep[:y0] = 0; keep[y1:] = 0; keep[:, :x0] = 0; keep[:, x1:] = 0
    # shapes that merely touch the object (stairs under a foot) and run far beyond the box are not part of it
    objc = np.median(cov[keep > 0].astype(np.float32), axis=0) if keep.any() else bgc
    span = max(30.0, float(np.linalg.norm(objc - bgc)))
    strong = (np.linalg.norm(cov.astype(np.float32) - bgc, axis=2) > span * 0.55).astype(np.uint8)
    n, lab, st, _ = cv2.connectedComponentsWithStats(strong, 4)
    inbox = np.zeros(cov.shape[:2], bool); inbox[y0:y1, x0:x1] = True
    for i in range(1, n):
        comp = lab == i
        if not (comp & (keep > 0)).any():
            continue
        out_px = int((comp & ~inbox).sum())
        core = comp & (keep > 0)
        rest = (keep > 0) & ~comp
        if out_px > max(200, 0.5 * int((comp & inbox).sum())) and rest.sum() > 2 * core.sum():
            keep[core] = 0                                                  # a big neighbour shape touching the object
        elif 0 < out_px <= 1.5 * int((comp & inbox).sum()):
            keep[comp] = 1                                                  # the object sticks out of the box: take all of it
    return keep * 255

def fill(cov, mask, seed=3):
    """background without the object: inpaint + the cover's own grain. Neighbouring shapes that the object touches
    (stairs under a foot, a line behind a hand) are protected: only background-coloured pixels around the object
    may be repainted."""
    S = cov.shape[0]
    r = max(5, S // 180)
    big = cv2.dilate(mask, np.ones((r * 2 + 1, r * 2 + 1), np.uint8))
    ring = (big > 0) & (mask == 0)
    ys, xs = np.where(mask > 0)
    pad = r * 4
    y0, y1, x0, x1 = max(0, ys.min() - pad), min(S, ys.max() + pad), max(0, xs.min() - pad), min(S, xs.max() + pad)
    around = cv2.dilate(big, np.ones((pad, pad), np.uint8)) - big
    win = np.zeros_like(mask); win[y0:y1, x0:x1] = 1
    sel = (around > 0) & (win > 0)
    far = np.zeros(mask.shape, bool)
    if sel.any():
        bgc = np.median(cov[sel].astype(np.float32), axis=0)
        objc = np.median(cov[mask > 0].astype(np.float32), axis=0)
        span = max(30.0, float(np.linalg.norm(objc - bgc)))
        far = (np.linalg.norm(cov.astype(np.float32) - bgc, axis=2) > span * 0.6) & (mask == 0)
        n, lab = cv2.connectedComponents(far.astype(np.uint8), connectivity=4)
        outside = np.unique(lab[far & (big == 0)])                        # shapes that continue beyond the ring
        foreign = np.isin(lab, outside[outside > 0]) & ring
        big = np.where(foreign, 0, big).astype(np.uint8)                  # keep foreign shapes, repaint the object's rim
    work = cov
    if sel.any():
        flat = float(np.linalg.norm(cov[sel & ~far].astype(np.float32).std(0))) < 30 if (sel & ~far).any() else False
        if flat:
            # flat background (graphic covers): neighbouring shapes must not bleed into the hole
            near = cv2.dilate(big, np.ones((r * 6 + 1, r * 6 + 1), np.uint8)) > 0
            work = cov.copy()
            work[near & far & (big == 0)] = bgc.astype(np.uint8)
    out = cv2.inpaint(work, big, r, cv2.INPAINT_TELEA).astype(np.float32)
    out[big == 0] = cov[big == 0]
    ring2 = cv2.dilate(big, np.ones((15, 15), np.uint8)) - big
    noise = cov.astype(np.float32) - cv2.GaussianBlur(cov, (0, 0), 2).astype(np.float32)
    sd = float(noise[ring2 > 0].std()) if (ring2 > 0).any() else 2.5
    g = np.random.default_rng(seed).normal(0, max(1.0, min(sd, 8)), cov.shape).astype(np.float32)
    w = cv2.GaussianBlur(big.astype(np.float32) / 255, (0, 0), 2)[..., None]
    return np.clip(out + g * w, 0, 255).astype(np.uint8)

# ---------------------------------------------------------------- the stick figure (pictograms)
def _ease(t):
    return t * t * (3 - 2 * t)

def _ik(h, f, a, b, facing):
    dx, dy = f[0] - h[0], f[1] - h[1]
    d = max(1e-3, min(math.hypot(dx, dy), a + b - 0.5))
    c = (a * a + d * d - b * b) / (2 * a * d)
    k = math.atan2(dy, dx) - math.acos(max(-1, min(1, c))) * facing
    return (h[0] + a * math.cos(k), h[1] + a * math.sin(k))

class Figure:
    """A pictogram figure redrawn as a rig: walks along footholds, dances at the ends, all on the beat."""
    def __init__(self, cov, bg, mask, spec, beat, ph, dur):
        S = cov.shape[0]
        ys, xs = np.where(mask > 0)
        self.col = tuple(int(v) for v in np.median(cov[mask > 0], axis=0))
        Hf = float(ys.max() - ys.min())                                    # head top to feet
        k = Hf / 310.0
        self.k = k
        dt = cv2.distanceTransform((mask > 0).astype(np.uint8), cv2.DIST_L2, 5)
        self.w = float(max(6, min(2 * np.percentile(dt[dt > 0], 92), 0.16 * Hf)))
        self.head_r = max(self.w * 0.62, 23 * k)
        self.L = dict(thigh=74 * k, shin=76 * k, uarm=56 * k, farm=52 * k, torso=88 * k, neck=54 * k)
        self.beat, self.ph, self.dur, self.S = beat, ph, dur, S
        pts = [(p[0] * S, p[1] * S) for p in (spec.get("path") or [])]
        if len(pts) < 2:                                                  # no path: dance where it stands
            fx = float(np.median(xs)); fy = float(ys.max())
            pts = [(fx, fy), (fx + 1, fy)]
        pts = [self._snap(bg, p, Hf) for p in pts]
        # subdivide long gaps into strides
        stride = 0.34 * Hf
        holds = [pts[0]]
        for p in pts[1:]:
            q = holds[-1]
            n = max(1, int(math.hypot(p[0] - q[0], p[1] - q[1]) / stride + 0.5))
            for i in range(1, n + 1):
                holds.append((q[0] + (p[0] - q[0]) * i / n, q[1] + (p[1] - q[1]) * i / n))
        self.holds = holds
        n = len(holds) - 1
        self.energy = spec.get("energy", "calm")
        loop = spec.get("loop", "back")
        self.plan = [("stand", 0, 2)]
        k = 0
        while sum(p[-1] for p in self.plan) < dur / beat + 8:
            if loop in ("down", "forward", "up"):
                # only ever in one direction: walk the path, fade out at its end, reappear at the start
                self.plan += [("walk", 1, n)]
                if k % 2 == 1:
                    self.plan += [("groove", n, 4)]
                self.plan += [("fade", n, 1), ("appear", 0, 1)]
            else:
                self.plan += [("walk", 1, n), ("groove" if self.energy == "calm" else "dance", n, 8),
                              ("walk", -1, n), ("groove" if self.energy == "calm" else "party", 0, 8)]
            k += 1

    def _snap(self, bg, p, Hf):
        """foothold onto the surface: nearest strong horizontal edge within ±12 % of the figure height"""
        S = self.S if hasattr(self, "S") else bg.shape[0]
        x, y = int(min(S - 1, max(0, p[0]))), int(min(S - 1, max(0, p[1])))
        g = cv2.cvtColor(bg, cv2.COLOR_RGB2GRAY).astype(np.float32)
        col = g[:, max(0, x - 3):x + 4].mean(1)
        r = int(Hf * 0.12)
        best, by = 0, y
        for yy in range(max(1, y - r), min(S - 2, y + r)):
            e = abs(col[yy + 1] - col[yy - 1])
            if e > best * 1.15 + 6:
                best, by = e, yy
        return (float(x), float(by))

    def _hip_h(self, f=0.9):
        return (self.L["thigh"] + self.L["shin"]) * f

    def pose(self, t):
        B = self.beat
        b = (t - self.ph) / B
        bp = b - math.floor(b)
        bounce = math.cos(bp * 2 * math.pi)
        acc = -1.0
        seg = self.plan[-1]; sb = 0
        for item in self.plan:
            if b < acc + item[2]:
                seg, sb = item, b - acc
                break
            acc += item[2]
        name = seg[0]
        H = self.holds
        self.alpha = 1.0
        if name in ("fade", "appear"):
            i = len(H) - 1 if name == "fade" else 0
            fx, fy = H[i]
            k = self.k
            self.alpha = 1 - _ease(min(1, sb)) if name == "fade" else _ease(min(1, sb))
            facing = 1 if H[-1][0] >= H[0][0] else -1
            L, R = (fx - 12 * k, fy), (fx + 12 * k, fy)
            hip = (fx, fy - self._hip_h(0.94) + 2 * k * bounce)
            return hip, L, R, (math.radians(95), math.radians(85)), facing, 0.0
        if name == "groove":                               # calm: knees on the beat, a little shoulder sway, feet stay
            fx, fy = H[seg[1]] if seg[1] < len(H) else H[-1]
            k = self.k
            soft = 0.5 + 0.5 * math.cos(bp * 2 * math.pi)                       # smooth, no snap
            sway = math.sin((b - self.ph) * math.pi / 2)                       # one sway over two beats
            L, R = (fx - 18 * k, fy), (fx + 18 * k, fy)
            hip = (fx + 5 * k * sway, fy - self._hip_h(0.92) + 6 * k * soft)
            facing = 1 if H[-1][0] >= H[0][0] else -1
            arms = (math.radians(100 + 14 * sway), math.radians(80 + 14 * sway))
            return hip, L, R, arms, facing, 0.04 * sway
        if name in ("stand", "dance", "party"):
            i = 0 if name in ("stand", "party") else len(H) - 1
            fx, fy = H[i]
            k = self.k
            if name == "stand":
                L, R = (fx - 14 * k, fy), (fx + 14 * k, fy)
                hip = (fx, fy - self._hip_h(0.95) + 3 * k * bounce)
                return hip, L, R, (math.radians(100), math.radians(80)), 1, 0.0
            if name == "dance":
                side = math.sin(sb * math.pi / 2) * 10 * k
                L, R = (fx - 22 * k + side, fy), (fx + 22 * k + side, fy)
                if int(sb) % 2 == 0 and bp < 0.5:
                    L = (L[0], fy - 12 * k * math.sin(bp * 2 * math.pi))
                hip = (fx + side, fy - self._hip_h(0.88) + 8 * k * bounce)
                pump = math.sin(bp * 2 * math.pi)
                arms = (math.radians(-30 - 20 * pump), math.radians(-150 + 20 * pump)) if (int(sb) // 2) % 2 else \
                       (math.radians(30 + 40 * pump), math.radians(150 - 40 * pump))
                return hip, L, R, arms, 1 if int(sb / 4) % 2 == 0 else -1, 0.0
            jump = max(0, math.sin(bp * math.pi)) * 34 * k if int(sb) % 4 == 3 else 0
            sw = (24 + 10 * math.sin(sb * math.pi)) * k
            L, R = (fx - sw, fy - jump), (fx + sw, fy - jump)
            hip = (fx, fy - jump - self._hip_h(0.86) + 9 * k * bounce)
            wv = math.sin(sb * math.pi)
            arms = (math.radians(-35 - 25 * wv), math.radians(-145 - 25 * wv)) if int(sb) % 8 < 4 else \
                   (math.radians(-20 + 50 * wv), math.radians(-160 - 50 * wv))
            return hip, L, R, arms, 1 if math.cos(sb * math.pi / 4) > 0 else -1, 0.0
        # walk: one foothold per beat
        d = seg[1]; n = seg[2]
        kk = min(sb, n - 1e-3); i = int(kk); f = _ease(kk - i)
        ai = i if d > 0 else n - i
        bi = ai + d
        (ax, ay), (bx, by) = H[ai], H[bi]
        facing = 1 if bx >= ax else -1
        upstairs = by < ay - 4
        lift = math.sin(f * math.pi) * ((36 if upstairs else 22) if self.energy != "calm" else (28 if upstairs else 16)) * self.k
        swing = (ax + (bx - ax) * f, ay + (by - ay) * f - lift)
        stance = (ax, ay)
        L, R = (swing, stance) if i % 2 == 0 else (stance, swing)
        hip = ((ax + swing[0]) / 2 + 10 * self.k * facing,
               min(ay, ay + (by - ay) * f) - self._hip_h(0.9) + 5 * self.k * math.sin(f * math.pi))
        s = math.sin(kk * math.pi)
        amp = 38 if self.energy != "calm" else 24
        return hip, L, R, (math.radians(90 + amp * s), math.radians(90 - amp * s)), facing, (0.08 if self.energy != "calm" else 0.05) * facing

    def draw(self, img, t, ss=2):
        from PIL import Image, ImageDraw
        S = self.S
        hip, L, R, (aL, aR), facing, lean = self.pose(t)
        lay = Image.new("L", (S * ss, S * ss), 0)
        d = ImageDraw.Draw(lay)
        P = lambda p: (p[0] * ss, p[1] * ss)
        def limb(pts, w):
            d.line([P(p) for p in pts], fill=255, width=max(2, int(w * ss)), joint="curve")
            for p in pts:
                r = w * ss / 2
                d.ellipse([P(p)[0] - r, P(p)[1] - r, P(p)[0] + r, P(p)[1] + r], fill=255)
        Lg = self.L
        neck = (hip[0] + Lg["torso"] * math.sin(lean), hip[1] - Lg["torso"] * math.cos(lean))
        head = (neck[0] + 6 * self.k * facing, neck[1] - Lg["neck"])
        sh = (neck[0], neck[1] + 6 * self.k)
        for foot in (L, R):
            limb([hip, _ik(hip, foot, Lg["thigh"], Lg["shin"], facing), foot], self.w)
        for ang, side in ((aL, -1), (aR, 1)):
            el = (sh[0] + Lg["uarm"] * math.cos(ang), sh[1] + Lg["uarm"] * math.sin(ang))
            a2 = ang + (0.5 * facing * side if math.sin(ang) > -0.3 else -0.35 * side)
            hd = (el[0] + Lg["farm"] * math.cos(a2), el[1] + Lg["farm"] * math.sin(a2))
            limb([sh, el, hd], self.w * 0.82)
        limb([hip, neck], self.w)
        r = self.head_r * ss
        d.ellipse([P(head)[0] - r, P(head)[1] - r, P(head)[0] + r, P(head)[1] + r], fill=255)
        m = np.asarray(lay.resize((S, S), Image.LANCZOS)).astype(np.float32)[..., None] / 255 * getattr(self, "alpha", 1.0)
        return (img * (1 - m) + np.array(self.col, np.float32) * m).astype(np.uint8)

# ---------------------------------------------------------------- the detail
class Detail:
    def __init__(self, cov, spec, aud, sr, dur, seed=1, log=print):
        self.cov, self.spec, self.dur = cov, spec, dur
        self.S = S = cov.shape[0]
        self.motion = spec.get("motion")
        if self.motion not in MOTIONS:
            raise ValueError("unknown motion %r" % self.motion)
        bpm, ph = beat_grid(aud, sr)
        self.beat, self.ph = 60.0 / bpm, ph
        log("detail: %s (%s) · %.1f BPM, first beat %.2f s" % (self.motion, spec.get("note", ""), bpm, ph))
        if self.motion == "eyes":
            import eyes as _eyes
            self.eyes = _eyes.Eyes(cov, spec["eyes"], seed, dur)
            return
        if self.motion == "spin":
            # records, labels, wheels: a clean disc turning in place – no hole to fill
            x0, y0, x1, y1 = _px(spec["box"], S)
            pv = spec.get("pivot")
            cx, cy = (pv[0] * S, pv[1] * S) if pv else ((x0 + x1) / 2, (y0 + y1) / 2)
            m = segment(cov, spec["box"])
            area = max(1.0, float((m > 0).sum()))
            r = min(math.sqrt(area / math.pi), min(cx - x0, x1 - cx, cy - y0, y1 - cy) + 2)
            yy, xx = np.mgrid[0:S, 0:S]
            self.mask = (((xx - cx) ** 2 + (yy - cy) ** 2) <= (r - 1.5) ** 2).astype(np.uint8) * 255
            self.bg = cov.copy()
            a = cv2.GaussianBlur(self.mask.astype(np.float32) / 255, (0, 0), 1.0)
            self.rgba = np.dstack([cov.astype(np.float32), a])
            self.pivot, self.h, self.bb = (cx, cy), 2 * r, (cx - r, cy - r, cx + r, cy + r)
            return
        self.mask = segment(cov, spec["box"])
        if self.mask.sum() < 255 * 60:
            raise ValueError("detail not found in the box")
        self.bg = fill(cov, self.mask, seed)
        ys, xs = np.where(self.mask > 0)
        self.bb = (float(xs.min()), float(ys.min()), float(xs.max()), float(ys.max()))
        if self.motion == "figure":
            self.fig = Figure(cov, self.bg, self.mask, spec, self.beat, ph, dur)
            return
        a = cv2.GaussianBlur(self.mask.astype(np.float32) / 255, (0, 0), 0.8)
        self.rgba = np.dstack([cov.astype(np.float32), a])
        x0, y0, x1, y1 = self.bb
        cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
        pv = spec.get("pivot")
        if pv:
            self.pivot = (pv[0] * S, pv[1] * S)
        elif self.motion == "sway":
            self.pivot = (cx, y1)
        elif self.motion in ("hop", "wobble"):
            self.pivot = (cx, y1)
        else:
            self.pivot = (cx, cy)
        self.h = float(y1 - y0)

    def _env(self, t, decay=0.22):
        """1 right on the beat, falling off"""
        b = (t - self.ph) / self.beat
        if b < 0:
            return 0.0, b
        return math.exp(-(b - math.floor(b)) * self.beat / decay), b

    def _place(self, base, M):
        warped = cv2.warpAffine(self.rgba, M, (self.S, self.S), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_CONSTANT, borderValue=0)
        a = warped[..., 3:4]
        return (base.astype(np.float32) * (1 - a) + warped[..., :3] * a).astype(np.uint8)

    def frame(self, t):
        mo = self.motion
        if mo == "eyes":
            return self.eyes.apply(self.cov, t)
        if mo == "figure":
            return self.fig.draw(self.bg, t)
        env, b = self._env(t)
        px, py = self.pivot
        ang, sx, sy, dx, dy = 0.0, 1.0, 1.0, 0.0, 0.0
        bp = b - math.floor(b) if b >= 0 else 0
        if mo == "hop":
            big = 1.6 if int(b) % 4 == 3 else 1.0
            air = math.sin(min(1, bp / 0.7) * math.pi) if bp < 0.7 else 0
            dy = -max(0.2 * self.h, 0.03 * self.S) * big * air
            land = math.exp(-((bp - 0.72) % 1) / 0.08) if bp >= 0.7 else 0
            sy, sx = 1 - 0.10 * land, 1 + 0.08 * land
            if air > 0:
                sy, sx = 1 + 0.05 * air, 1 - 0.04 * air
        elif mo == "pulse":
            sx = sy = 1 + 0.07 * env + (0.04 * env if int(b) % 4 == 0 else 0)
        elif mo == "spin":
            ang = -t * 360 * (33.333 / 60)                                    # 33⅓ rpm, a record spinning
        elif mo == "sway":
            ang = 7 * math.sin(((t - self.ph) / self.beat) * math.pi)          # one swing per beat, back on the next
            sy = 1 - 0.02 * env
        elif mo == "float":
            dy = -0.035 * self.S * math.sin(t * 2 * math.pi / (self.beat * 8))
            dx = 0.012 * self.S * math.sin(t * 2 * math.pi / (self.beat * 16))
            ang = 2.5 * math.sin(t * 2 * math.pi / (self.beat * 8) + 1)
        elif mo == "wobble":
            w = env * math.cos(bp * self.beat * 2 * math.pi * 4)
            sx, sy = 1 + 0.13 * w, 1 - 0.13 * w
        M = cv2.getRotationMatrix2D((px, py), ang, 1.0)
        M[0, 0] *= sx; M[0, 1] *= sx; M[1, 0] *= sy; M[1, 1] *= sy
        M[0, 2] = px - (M[0, 0] * px + M[0, 1] * py) + dx
        M[1, 2] = py - (M[1, 0] * px + M[1, 1] * py) + dy
        return self._place(self.bg, M)
