#!/usr/bin/env python3
"""Shape & colour loop for the daily single reel (since 26.10.26).

Works on graphic covers (flat colours, few hues, clear shapes). The cover itself is the whole video (square,
1080 px, 45 s, seamless loop: the last frame equals the first). Rules (from the user):
- nothing moves in the first second, then slowly more, never too much
- round shapes turn · long/thin shapes wave · angular/compact shapes inflate and deflate
- only one small group of similar shapes moves on the beat (alternating)
- different tempi and intensities per shape; type (rows of letters) stays still
- colours flow in rings out of the main shape through several colour worlds
Everything is periodic in the loop length, wrapped in an envelope that is 0 at both ends."""
import math, os, subprocess, sys, zlib
import numpy as np, cv2
from PIL import Image

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
S, FPS = 1080, 30

def log(*a):
    print("[shapeloop]", *a, file=sys.stderr, flush=True)

def sstep(x):
    x = np.clip(x, 0, 1); return x * x * (3 - 2 * x)

# ------------------------------------------------------------------ analysis
def segment(im):
    """k-means in Lab → background cluster (most border pixels) vs. foreground"""
    a = np.asarray(im.convert("RGB").resize((S, S), Image.LANCZOS)) if not isinstance(im, np.ndarray) else im
    lab = cv2.cvtColor(a, cv2.COLOR_RGB2LAB).astype(np.float32)
    small = cv2.resize(lab, (180, int(180 * a.shape[0] / a.shape[1])), interpolation=cv2.INTER_AREA).reshape(-1, 3)
    crit = (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 30, 0.5)
    _, _, cent = cv2.kmeans(small, 4, None, crit, 3, cv2.KMEANS_PP_CENTERS)
    # merge near-identical clusters
    keep = []
    for c in cent:
        if all(np.linalg.norm(c - k) > 14 for k in keep):
            keep.append(c)
    cent = np.float32(keep)
    d = np.linalg.norm(lab[..., None, :] - cent[None, None], axis=-1)
    lbl = d.argmin(-1)
    border = np.concatenate([lbl[:6].ravel(), lbl[-6:].ravel(), lbl[:, :6].ravel(), lbl[:, -6:].ravel()])
    share = np.bincount(border, minlength=len(cent)) / len(border)
    bgs = [i for i in range(len(cent)) if share[i] >= 0.2] or [int(share.argmax())]   # e.g. two shades of a printed ground
    fg = (~np.isin(lbl, bgs)).astype(np.uint8)
    fg = cv2.medianBlur(fg * 255, 5) // 255
    return a, lab, fg, len(cent)

def suits(im):
    """score 0..1: flat graphic cover (no photo, no people, not a blank white sleeve) with clear shapes; >= .5 = use it"""
    a = np.asarray(im.convert("RGB").resize((256, 256), Image.LANCZOS))
    lab = cv2.cvtColor(a, cv2.COLOR_RGB2LAB).astype(np.float32)
    L = lab[..., 0]
    mu = cv2.blur(L, (7, 7)); sd = np.sqrt(np.maximum(cv2.blur(L * L, (7, 7)) - mu * mu, 0))
    soft = float(((sd >= 4) & (sd < 14)).mean())                  # photos and gradients have lots of soft texture
    hsv = cv2.cvtColor(a, cv2.COLOR_RGB2HSV).astype(np.float32)
    sat = float(hsv[..., 1].mean())
    h, s_, v = hsv[..., 0], hsv[..., 1], hsv[..., 2]
    skin = float(((h < 25) & (s_ > 40) & (s_ < 180) & (v > 80)).mean())
    white = float(((L > 225) & (s_ < 30)).mean())
    try:
        _, _, fg, k = segment(im)
    except Exception:
        return 0.0, "segmentation failed"
    frac = float(fg.mean())
    n, _, st, _ = cv2.connectedComponentsWithStats(fg, 8)
    shapes = int((st[1:, 4] > 0.0006 * S * S).sum())
    score = 0.35 * (1 - sstep((soft - 0.06) / 0.08))                # graphic, not a photo
    score += 0.25 * min(1.0, sat / 110) + (0.1 if sat < 40 and abs(float(L.mean()) - 128) > 40 else 0)   # colourful or bold mono
    score += 0.2 * min(1.0, shapes / 5) + 0.1 * (1.0 if 0.06 < frac < 0.6 else 0.0)
    score -= 0.6 * max(0.0, white - 0.45) * 3 + 2.0 * max(0.0, skin - 0.06)
    score = float(np.clip(score + 0.1, 0, 1))
    return score, "soft %.2f sat %.0f shapes %d fg %.2f white %.2f skin %.2f" % (soft, sat, shapes, frac, white, skin)

class Shapes:
    def __init__(self, im, seed=1, dur=45.0, canvas=None, motion=1.0):
        """canvas: optional RGB array (e.g. the 9:16 poster built around the cover); shapes and colours then live on it"""
        self.dur = dur
        self.motion = motion                                             # 0 = colours only (photo / illustrated covers)
        self.protect = None                                              # optional HxW weight: where the colour flow stays off the artwork
        rng = np.random.default_rng(seed)
        a, lab, fg, _ = segment(canvas if canvas is not None else im)
        self.a = a.astype(np.float32)
        hh_, ww_ = a.shape[:2]; self.hw = (hh_, ww_)
        hard = fg
        din = cv2.distanceTransform(hard, cv2.DIST_L2, 5); dout = cv2.distanceTransform(1 - hard, cv2.DIST_L2, 5)
        self.sdf = cv2.GaussianBlur(np.where(hard > 0, din, -dout).astype(np.float32), (0, 0), 1.2)
        n, comp, st, cen = cv2.connectedComponentsWithStats(hard, 8)
        _, near = cv2.distanceTransformWithLabels(1 - hard, cv2.DIST_L2, 5, labelType=cv2.DIST_LABEL_PIXEL)
        ys, xs = np.nonzero(hard); pc = np.zeros(near.max() + 1, np.int32); pc[near[ys, xs]] = comp[ys, xs]
        owner = np.where(hard > 0, comp, pc[near]).astype(np.int32)
        # colour fields: foreground colours pushed outwards, background with the shapes removed
        half = cv2.resize(self.a, (ww_ // 2, hh_ // 2)).astype(np.uint8)
        hm = cv2.resize(hard, (ww_ // 2, hh_ // 2), interpolation=cv2.INTER_NEAREST)
        dil = cv2.dilate(hm, np.ones((5, 5), np.uint8))
        ground = cv2.resize(cv2.inpaint(half, dil, 9, cv2.INPAINT_TELEA), (ww_, hh_)).astype(np.float32)
        inkx = cv2.resize(cv2.inpaint(half, ((1 - hm) * cv2.dilate(1 - hm, np.ones((1, 1), np.uint8))).astype(np.uint8), 9, cv2.INPAINT_TELEA), (ww_, hh_)).astype(np.float32)
        inkx = np.where(hard[..., None] > 0, cv2.GaussianBlur(self.a, (0, 0), 1.0), inkx)
        self.ink = inkx
        g_full = np.where(cv2.dilate(hard, np.ones((7, 7), np.uint8))[..., None] > 0, ground, self.a)
        self.grain_g = g_full - cv2.GaussianBlur(g_full, (0, 0), 3)
        self.grain_i = rng.normal(0, 4, (hh_, ww_, 1)).astype(np.float32)
        gl = cv2.cvtColor(np.clip(ground, 0, 255).astype(np.uint8), cv2.COLOR_RGB2LAB)[..., 0].astype(np.float32)
        gmed = max(8.0, float(np.median(gl[hard == 0]))) if (hard == 0).any() else 128.0
        self.glum = np.clip(cv2.GaussianBlur(gl, (0, 0), 5) / gmed, 0.6, 1.45)[..., None]
        self.ground = ground
        self.bgcol = np.median(self.a[hard == 0], axis=0) if (hard == 0).any() else np.float32([30, 30, 30])
        # classify shapes
        A = S * S
        comps = [i for i in range(1, n) if st[i, 4] > 0.0004 * A]
        text = self._text(comps, st, cen)
        letters = self._letters([i for i in comps if i not in text], st, cen)   # big lettering: a gentle bounce, never turned
        self.items = []
        yy, xx = np.mgrid[0:hh_, 0:ww_].astype(np.float32)
        self.xx, self.yy = xx, yy
        small_inflate = []
        kinds = {}
        for i in comps:
            if i in text:
                kinds[i] = "text"; continue
            x, y, w, h, area = st[i]
            mk = (comp[y:y + h, x:x + w] == i).astype(np.uint8)
            allc, hier = cv2.findContours(mk, cv2.RETR_CCOMP, cv2.CHAIN_APPROX_NONE)
            hc = [] if hier is None else [allc[q] for q, hh in enumerate(hier[0]) if hh[3] >= 0 and cv2.contourArea(allc[q]) > 20]
            holes = len(hc)
            hm_ = [cv2.moments(q) for q in hc]
            hcen = [(q["m10"] / q["m00"] + x, q["m01"] / q["m00"] + y) for q in hm_ if q["m00"] > 0]
            concentric = bool(hcen) and all(math.hypot(px - cen[i][0], py - cen[i][1]) < 0.18 * max(w, h) for px, py in hcen)
            cnts, _ = cv2.findContours(mk, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)
            c = max(cnts, key=cv2.contourArea)
            hull = cv2.convexHull(c); ha = max(1.0, cv2.contourArea(hull)); hp = max(1.0, cv2.arcLength(hull, True))
            circ = 4 * math.pi * ha / hp ** 2
            (rx, ry), (rw, rh), rang = cv2.minAreaRect(c)
            asp = max(rw, rh) / max(1.0, min(rw, rh))
            stroke = float(din[comp == i].max())
            if i in letters:
                kind = "letter"
            elif area > 0.22 * A:
                kind = "big"
            elif circ > 0.8 and asp < 1.35:
                kind = "round"
            elif asp > 2.6 or (area / ha < 0.4 and asp > 1.8):
                kind = "long"
            else:
                kind = "angular"
            kinds[i] = kind
            it = {"conc": concentric, "holes": holes, "id": i, "kind": kind, "c": np.float32(cen[i]), "stroke": stroke, "area": float(area),
                  "axis": math.radians(rang if rw >= rh else rang + 90), "len": float(max(rw, rh)),
                  "ph": rng.uniform(0, 2 * math.pi), "m": int(rng.choice([3, 4, 5, 6, 7, 8, 9])), "m2": int(rng.choice([2, 3, 4])),
                  "amp": rng.uniform(0.6, 1.0)}
            # crop for its own distance field (room to move / turn)
            mg = int(0.3 * max(w, h) + 30)
            x0, y0, x1, y1 = max(0, x - mg), max(0, y - mg), min(ww_, x + w + mg), min(hh_, y + h + mg)
            mk_full = (comp[y0:y1, x0:x1] == i).astype(np.uint8)
            it["box"] = (x0, y0, x1, y1)
            it["own"] = cv2.GaussianBlur(np.where(mk_full > 0, cv2.distanceTransform(mk_full, cv2.DIST_L2, 5),
                                                  -cv2.distanceTransform(1 - mk_full, cv2.DIST_L2, 5)).astype(np.float32), (0, 0), 1.2)
            it["reg"] = (owner[y0:y1, x0:x1] == i)
            it["regout"] = np.nonzero((owner == i).ravel())[0]
            self.items.append(it)
            if kind == "angular" and area < 0.006 * A:
                small_inflate.append(it)
        # the beat group: the largest set of similar small angular shapes (2–6)
        self.beat = []
        if len(small_inflate) >= 2:
            small_inflate.sort(key=lambda z: z["area"])
            best = []
            for j, z in enumerate(small_inflate):
                grp = [q for q in small_inflate if 0.6 < q["area"] / z["area"] < 1.65]
                if len(grp) > len(best):
                    best = grp
            if len(best) >= 2:
                self.beat = best[:6]
                for k, z in enumerate(self.beat):
                    z["kind"] = "beat"; z["alt"] = k % 2
        # one round shape turns all the way (the biggest), the others rock
        rounds = sorted([z for z in self.items if z["kind"] == "round"], key=lambda z: -z["area"])
        for k, z in enumerate(rounds):                                # lettering cut into a ring (many holes) never turns round
            z["full"] = (k == 0 and (z["holes"] == 0 or z["conc"]) and z["area"] < 0.06 * A)   # faces / big emblems only rock a little
        main = max([z for z in self.items if z["kind"] != "text"] or [{"c": np.float32([ww_ / 2, hh_ / 2])}], key=lambda z: z.get("area", 0))
        self.focus = main["c"]
        self.rr = np.hypot(xx - self.focus[0], yy - self.focus[1]) / S
        self.text = text
        self.kinds = kinds
        log("shapes:", {k: sum(1 for z in self.items if z["kind"] == k) for k in ("big", "round", "long", "angular", "beat", "letter")}, "text", len(text))
        # moving regions start empty; static ones keep the global field
        self.base = self.sdf.copy()
        if motion <= 0:
            self.items = []                                              # nothing moves: the cover keeps its shapes as they are
        for z in self.items:
            self.base.ravel()[z["regout"]] = -12
        # colour worlds: start from the cover's own background colour and travel round the hue circle
        bg = np.uint8([[np.clip(self.bgcol, 0, 255)]])
        hsv = cv2.cvtColor(bg, cv2.COLOR_RGB2HSV)[0, 0].astype(int)
        sat, val = (max(hsv[1], 150), max(hsv[2], 120)) if hsv[1] > 60 else (170, 150)
        self.cyc = [np.float32(self.bgcol)]
        for k in range(1, 6):
            h = (hsv[0] + k * 30 + int(rng.integers(-6, 7))) % 180
            self.cyc.append(cv2.cvtColor(np.uint8([[[h, sat, val]]]), cv2.COLOR_HSV2RGB)[0, 0].astype(np.float32))
        self.rng = rng
        self.W = 2 * math.pi / dur

    @staticmethod
    def _text(comps, st, cen):
        """letters: rows of 3+ small shapes with similar heights, close together"""
        cand = [i for i in comps if 0.008 * S < st[i, 3] < 0.11 * S and st[i, 4] < 0.005 * S * S]
        text = set()
        for i in cand:
            row = [j for j in cand if abs(cen[j][1] - cen[i][1]) < 0.5 * st[i, 3] and 0.6 < st[j, 3] / st[i, 3] < 1.6
                   and abs(cen[j][0] - cen[i][0]) < 6 * st[i, 3]]
            if len(row) >= 3:
                text.update(row)
        return text

    @staticmethod
    def _letters(comps, st, cen):
        """a word in big type: 3+ shapes side by side in one row with similar heights"""
        out = set()
        for i in comps:
            h = st[i, 3]
            if h < 0.04 * S:
                continue
            row = [j for j in comps if abs(cen[j][1] - cen[i][1]) < 0.45 * h and 0.55 < st[j, 3] / h < 1.8 and abs(cen[j][0] - cen[i][0]) < 3.5 * h]
            if len(row) >= 3:
                out.update(row)
        return out

    def env(self, t):
        return float(sstep((t - 1) / 4) * sstep((self.dur - t) / 5))

    def frame(self, t, beatf):
        W, e = self.W, self.env(t)
        sd = self.base.copy()
        inkf = self.ink.copy()
        for z in self.items:
            x0, y0, x1, y1 = z["box"]
            X = self.xx[y0:y1, x0:x1]; Y = self.yy[y0:y1, x0:x1]
            c = z["c"]; k = z["kind"]; amp = z["amp"] * e * self.motion * (0.65 + 0.35 * math.sin(W * z["m2"] * t + z["ph"]))
            sx = X; sy = Y; s = 1.0; th = 0.0
            if k == "round":
                rock = math.radians(3 if ((z["holes"] > 2 and not z["conc"]) or z["area"] > 0.06 * S * S) else 12)
                ang = (-2 * math.pi * float(sstep((t - 1) / (self.dur - 1))) if z["full"] else 0.0) + rock * amp * math.sin(W * z["m"] * t + z["ph"])
                ca, sa = math.cos(-ang), math.sin(-ang)
                dx, dy = X - c[0], Y - c[1]
                sx = c[0] + dx * ca - dy * sa; sy = c[1] + dx * sa + dy * ca
            elif k == "long":
                ax = z["axis"]; ux, uy = math.cos(ax), math.sin(ax)
                along = (X - c[0]) * ux + (Y - c[1]) * uy
                rel = np.clip(np.abs(along) / max(1.0, z["len"] / 2), 0, 1)
                d = amp * min(14.0, 0.06 * z["len"] + 3) * (0.3 + 0.7 * rel) * np.sin(W * z["m"] * t - along / max(20.0, z["len"] / 3) + z["ph"])
                sx = X + uy * d; sy = Y - ux * d
            elif k in ("angular", "big"):
                s = 1 + (0.025 if k == "big" else min(0.15, 0.05 + 2.5 / math.sqrt(z["area"]) * 4)) * amp * math.sin(W * z["m"] * t + z["ph"])
                sx = c[0] + (X - c[0]) / s; sy = c[1] + (Y - c[1]) / s
                th = min(3.0, 0.45 * z["stroke"]) * amp * math.sin(W * (z["m"] + 2) * t + z["ph"] * 1.7)
            elif k == "letter":                                       # letters bounce one after the other, like a wave through the word
                s = 1 + 0.05 * amp * math.sin(W * 6 * t - c[0] / 140)
                sx = c[0] + (X - c[0]) / s; sy = c[1] + (Y - c[1]) / s + 6 * amp * math.sin(W * 6 * t - c[0] / 140 - 1.2)
            elif k == "beat":
                p = beatf(t, z["alt"]) * e * self.motion
                s = 1 + 0.22 * p
                sx = c[0] + (X - c[0]) / s; sy = c[1] + (Y - c[1]) / s
            sx = (sx - x0).astype(np.float32); sy = (sy - y0).astype(np.float32)
            v = cv2.remap(z["own"], sx, sy, cv2.INTER_LINEAR, borderMode=cv2.BORDER_CONSTANT, borderValue=-30) * s + th
            reg = z["reg"]
            sub = sd[y0:y1, x0:x1]; sub[reg] = v[reg]
            ic = cv2.remap(self.ink, (sx + x0).astype(np.float32), (sy + y0).astype(np.float32), cv2.INTER_LINEAR, borderMode=cv2.BORDER_REPLICATE)
            isub = inkf[y0:y1, x0:x1]; isub[reg] = ic[reg]
        m = sstep((sd + 0.9) / 1.8)[..., None]
        # colours
        u = 12 * (t / self.dur) - self.rr * 1.6 + 0.25 * math.sin(W * 3 * t) * np.sin(self.xx / 260)
        mix = e * (0.72 + 0.28 * math.sin(W * 4 * t))
        if self.protect is not None:                                    # photo / illustration: the artwork keeps its colours, the poster ground flows
            mix = mix * (1 - self.protect * (1 - self.motion))
        kk = len(self.cyc); uu = np.mod(u, kk); fl = np.floor(uu); f = sstep(uu - fl)[..., None]; i0 = fl.astype(int) % kk
        P = np.stack(self.cyc); pal = P[i0] * (1 - f) + P[(i0 + 1) % kk] * f
        mixm = mix if np.isscalar(mix) else mix[..., None]
        gcol = self.ground * (1 - mixm) + pal * self.glum * mixm
        # ink: keeps its own colours, takes on a bit of the complementary world
        Q = np.stack([255 - c_ * 0.6 for c_ in self.cyc]); tint = Q[(i0 + 3) % kk] * (1 - f) + Q[(i0 + 4) % kk] * f
        lum = inkf.mean(2, keepdims=True) / 255
        ink = inkf * (1 - 0.35 * mixm) + tint * (0.4 + 0.6 * lum) * 0.35 * mixm
        out = (gcol + self.grain_g) * (1 - m) + (ink + self.grain_i) * m
        return np.clip(out, 0, 255).astype(np.uint8)

def render(im, aud, sr, out, poster, dur=45.0, seed=1):
    """im: PIL cover, aud: float32 stereo array at sr (already cut to the clip). Writes a square mp4 + poster."""
    import detail_fx as DF
    sh = Shapes(im, seed, dur)
    mono = aud.mean(1) if aud.ndim == 2 else aud
    bpm, ph = DF.beat_grid(mono, sr)
    beat = 60 / bpm
    def beatf(t, alt):
        b = (t - ph) / beat
        if b < 0: return 0.0
        nb = math.floor(b)
        return math.exp(-(b - nb) * 5) if (nb - alt) % 2 == 0 else 0.0
    nfr = int(dur * FPS)
    wav = out + ".f32"
    a2 = aud[:int(dur * sr)]
    if a2.ndim == 1: a2 = np.stack([a2, a2], 1)
    a2.astype("<f4").tofile(wav)
    cmd = ["ffmpeg", "-y", "-v", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", "%dx%d" % (S, S), "-r", str(FPS), "-i", "-",
           "-f", "f32le", "-ar", str(sr), "-ac", "2", "-i", wav, "-c:v", "libx264", "-profile:v", "high", "-pix_fmt", "yuv420p",
           "-b:v", "9M", "-maxrate", "12M", "-bufsize", "18M", "-g", "60", "-preset", "medium", "-c:a", "aac", "-b:a", "192k",
           "-movflags", "+faststart", "-shortest", out]
    pr = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    for f in range(nfr):
        fr = sh.frame(f / FPS, beatf)
        if f == 0:
            Image.fromarray(fr).save(poster, quality=92)
        pr.stdin.write(fr.tobytes())
        if f % 150 == 0:
            log("frame", f, "/", nfr)
    pr.stdin.close()
    assert pr.wait() == 0
    os.remove(wav)
    kinds = {k: sum(1 for z in sh.items if z["kind"] == k) for k in ("round", "long", "angular", "beat")}
    return "shapeloop %.0f bpm · " % bpm + " ".join("%s %d" % (k, v) for k, v in kinds.items() if v)

if __name__ == "__main__":                                           # local test: cover.jpg audio.mp3 out.mp4 [sheet.jpg]
    im = Image.open(sys.argv[1])
    print(suits(im))
    if len(sys.argv) > 4:
        sh = Shapes(im, zlib.crc32(sys.argv[1].encode()))
        ts = [0, 2, 5, 9, 14, 20, 26, 32, 38, 44.97]
        sheet = Image.new("RGB", (5 * 270, 2 * 270))
        for j, t in enumerate(ts):
            sheet.paste(Image.fromarray(sh.frame(t, lambda t, a: 0.0)).resize((270, 270)), ((j % 5) * 270, (j // 5) * 270))
        sheet.save(sys.argv[4], quality=88)
    else:
        sr = 44100
        pcm = subprocess.run(["ffmpeg", "-v", "error", "-ss", "18", "-t", "45", "-i", sys.argv[2], "-ac", "2", "-ar", str(sr), "-f", "f32le", "-"], capture_output=True).stdout
        aud = np.frombuffer(pcm, "<f4").reshape(-1, 2)
        print(render(im, aud, sr, sys.argv[3], sys.argv[3].replace(".mp4", ".jpg"), seed=zlib.crc32(sys.argv[1].encode())))
