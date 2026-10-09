#!/usr/bin/env python3
"""Cover-driven looks for the reels.

The cover itself is the template: its structure, colours, geometry and style (photo, painting,
illustration, flat graphic, geometric, record label, dark/minimal) decide how the background is
built (out of the cover's own pixels) and which small details of the cover come to life.

    look = make_look(cover_image, seed)
    look.bg.frame(t, A)        -> background canvas (BH x BW x 3, float 0..1)
    look.life.apply(cov, t, A) -> the 1080 cover with its living details
    look.cfx_mode              -> how the cover later melts into the background
"""
import math
import numpy as np, cv2
from PIL import Image

BW, BH = 360, 640                 # background canvas (scaled 3x to 1080x1920)
CS = 1080                         # cover size in the video
CTOP = 100                        # cover top in canvas pixels (300 / 3)
SRC = 512                         # source cover resolution for sampling

def sstep(x):
    x = np.clip(x, 0, 1)
    return x * x * (3 - 2 * x)

def noise_tex(rng, n=256, blur=12):
    t = rng.random((n, n)).astype(np.float32)
    t = cv2.GaussianBlur(np.tile(t, (3, 3)), (0, 0), blur)[n:2 * n, n:2 * n]
    return (t - t.min()) / (t.max() - t.min() + 1e-6)

def tex_at(tex, u, v):
    n = tex.shape[0]
    return cv2.remap(tex, (np.mod(u, 1) * n).astype(np.float32), (np.mod(v, 1) * n).astype(np.float32),
                     cv2.INTER_LINEAR, borderMode=cv2.BORDER_WRAP)

# canvas grids: u,v = cover coordinates (0..1 inside the cover, beyond = continuation)
_cy, _cx = np.mgrid[0:BH, 0:BW].astype(np.float32)
CU = (_cx + .5) / BW
CV = (_cy - CTOP + .5) / BW
CU0, CV0 = CU - .5, CV - .5           # centred on the cover centre

def sample(src, u, v, border=cv2.BORDER_REFLECT_101):
    n = src.shape[0]
    return cv2.remap(src, (u * n - .5).astype(np.float32), (v * n - .5).astype(np.float32), cv2.INTER_LINEAR, borderMode=border)

def grade(c, dark=.8, sat=1.0):
    if sat != 1.0:
        g = c.mean(2, keepdims=True)
        c = g + (c - g) * sat
    return np.clip(c * dark, 0, 1)

# ------------------------------------------------------------------ analysis
def analyse(im):
    a = np.asarray(im.convert("RGB").resize((256, 256), Image.LANCZOS)).astype(np.float32) / 255
    g = cv2.cvtColor(a, cv2.COLOR_RGB2GRAY)
    hsv = cv2.cvtColor(a, cv2.COLOR_RGB2HSV)
    q = np.minimum((a * 8).astype(np.int32), 7)
    codes = q[..., 0] * 64 + q[..., 1] * 8 + q[..., 2]
    cnt = np.sort(np.bincount(codes.ravel(), minlength=512))[::-1]
    gx = cv2.Sobel(g, cv2.CV_32F, 1, 0, ksize=3); gy = cv2.Sobel(g, cv2.CV_32F, 0, 1, ksize=3)
    jxx = cv2.GaussianBlur(gx * gx, (0, 0), 4); jyy = cv2.GaussianBlur(gy * gy, (0, 0), 4); jxy = cv2.GaussianBlur(gx * gy, (0, 0), 4)
    tr = jxx + jyy
    coh = np.sqrt((jxx - jyy) ** 2 + 4 * jxy ** 2) / (tr + 1e-6)
    g8 = (g * 255).astype(np.uint8)
    edges = cv2.Canny(g8, 60, 160)
    lines = cv2.HoughLinesP(edges, 1, np.pi / 180, 70, minLineLength=60, maxLineGap=3)
    circles = cv2.HoughCircles(cv2.GaussianBlur(g8, (5, 5), 1.5), cv2.HOUGH_GRADIENT, dp=1.2, minDist=30,
                               param1=140, param2=60, minRadius=24, maxRadius=128)
    gm = np.hypot(gx, gy) / 8
    q32 = np.minimum((a * 32).astype(np.int32), 31)
    c32 = np.sort(np.bincount((q32[..., 0] * 1024 + q32[..., 1] * 32 + q32[..., 2]).ravel()))[::-1]
    f = {
        "flat": float((gm < .004).mean()), "mid": float(((gm >= .004) & (gm < .03)).mean()), "sharp": float((gm > .12).mean()),
        "n80": int(np.searchsorted(np.cumsum(c32) / c32.sum(), .8)) + 1,
        "sat": float(hsv[..., 1].mean()), "val": float(hsv[..., 2].mean()), "contrast": float(g.std()),
        "coh": float((coh * tr).sum() / (tr.sum() + 1e-6)),
        "lines": 0 if lines is None else len(lines),
        "circles": [] if circles is None else [tuple(map(float, c)) for c in circles[0][:4]],
        "sym": float(max(0.0, 1 - np.abs(g - g[:, ::-1]).mean() / (g.std() + 1e-3) / 2)),
    }
    # a record / label shot: big centred circle that clearly differs from what is around it
    rec = 0.0
    yy, xx = np.mgrid[0:256, 0:256]
    for (x, y, r) in f["circles"]:
        if r > 85 and abs(x - 128) < 25 and abs(y - 128) < 25:
            d = np.hypot(xx - x, yy - y)
            ins, out = a[(d > r - 10) & (d < r - 3)], a[(d > r + 3) & (d < r + 10)]
            if len(out) > 50 and len(ins) > 50:
                rec = max(rec, float(np.abs(ins.mean(0) - out.mean(0)).sum()))
    f["record"] = rec > .7
    if f["record"]:      # keep the record circle first so it spins
        f["circles"].sort(key=lambda c: -(c[2] if abs(c[0] - 128) < 25 and abs(c[1] - 128) < 25 else 0))
    cl = lambda x: float(np.clip(x, 0, 1))
    S, M, SH, FL, SAT, VAL = f["sat"], f["mid"], f["sharp"], f["flat"], f["sat"], f["val"]
    s = {
        "record": 3.0 if f["record"] else 0.0,
        "dark": 2.2 * cl((.32 - VAL) / .15),
        "photo": 1.0 * (1 - cl(SAT / .3)) + .6 * cl(M / .5) + .4 * (1 - cl(FL / .7)) - .8 * cl((SH - .25) / .1),
        "graphic": 1.2 * cl((FL - .3) / .4) + .6 * cl(SAT / .5) + .4 * cl(SH / .15),
        "geometric": 1.4 * cl((SH - .15) / .2) + .8 * min(1, f["lines"] / 30) + .4 * f["sym"],
        "painterly": .9 * cl(SAT / .45) + .8 * cl((M - .3) / .3) + .4 * (1 - cl(SH / .12)),
        "organic": .6 * cl(f["n80"] / 250) + .6 * cl(SAT / .5) + .6 * f["coh"] + .4 * cl(SH / .15) * (1 - cl((SH - .3) / .2)),
    }
    f["scores"] = s
    return f, a

def pick_style(f, rng):
    s = f["scores"]
    names = list(s)
    w = np.array([s[n] for n in names], np.float64)
    w = np.exp((w - w.max()) * 5.0)                # mostly the best match, sometimes the runner-up
    return names[int(rng.choice(len(names), p=w / w.sum()))]

def palette(a, rng, k=6):
    px = cv2.resize(a, (72, 72)).reshape(-1, 3).astype(np.float32)
    _, lab, cen = cv2.kmeans(px, k, None, (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 30, .5), 3, cv2.KMEANS_PP_CENTERS)
    cnt = np.bincount(lab.ravel(), minlength=k)
    return cen[np.argsort(-cnt)], cnt[np.argsort(-cnt)] / cnt.sum()

# ------------------------------------------------------------------ backgrounds made of the cover
class Bg:
    dark = .78
    def __init__(self, src, f, rng):
        self.src, self.f, self.rng = src, f, rng
        self.t1 = noise_tex(rng, blur=14); self.t2 = noise_tex(rng, blur=20)
    def warp(self, u, v, t, amp, sc=1.0, sp=.02):
        n1 = tex_at(self.t1, u * sc * .6 + t * sp, v * sc * .6 - t * sp * .7)
        n2 = tex_at(self.t2, u * sc * .6 - t * sp * .8 + .3, v * sc * .6 + t * sp * .6 + .7)
        return u + (n1 - .5) * 2 * amp, v + (n2 - .5) * 2 * amp

class Continue(Bg):
    """the cover continues beyond its edges (mirrored), gently flowing like liquid"""
    name = "continue"
    def __init__(self, src, f, rng):
        super().__init__(src, f, rng)
        self.z = rng.uniform(1.0, 1.35); self.amp = rng.uniform(.03, .09); self.sp = rng.uniform(.012, .03)
        self.blur = rng.uniform(.8, 2.5); self.sat = rng.uniform(.85, 1.25)
        self.dark = rng.uniform(.62, .85)
    def frame(self, t, A):
        z = self.z * (1 + .02 * math.sin(t * .23)) * (1 - .015 * A["kick"])
        u, v = self.warp(.5 + CU0 / z, .5 + CV0 / z, t, self.amp * (1 + .6 * A["kick"]), sp=self.sp)
        c = sample(self.src, u, v)
        c = cv2.GaussianBlur(c, (0, 0), self.blur)
        return grade(c, self.dark, self.sat)

class PosterFlow(Bg):
    """flat colour fields of the cover (posterised), enlarged, slowly flowing – for graphic covers"""
    name = "posterflow"
    def __init__(self, src, f, rng):
        super().__init__(src, f, rng)
        k = int(rng.integers(4, 8))
        px = src.reshape(-1, 3)
        _, lab, cen = cv2.kmeans(px[::7].copy(), k, None, (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 20, .5), 2, cv2.KMEANS_PP_CENTERS)
        d = ((px[:, None, :] - cen[None]) ** 2).sum(2)
        q = cen[d.argmin(1)].reshape(src.shape).astype(np.float32)
        self.q = cv2.medianBlur((q * 255).astype(np.uint8), 7).astype(np.float32) / 255
        self.z = rng.uniform(1.6, 3.2); self.amp = rng.uniform(.04, .1); self.rot = rng.uniform(-.03, .03)
        self.cx, self.cy = rng.uniform(.3, .7), rng.uniform(.3, .7)
        self.dark = rng.uniform(.7, .9)
    def frame(self, t, A):
        a = self.rot * t
        ca, sa = math.cos(a), math.sin(a)
        x, y = (CU0 * ca - CV0 * sa) / self.z, (CU0 * sa + CV0 * ca) / self.z
        u, v = self.warp(self.cx + x + .01 * t, self.cy + y, t, self.amp * (1 + .5 * A["kick"]), sc=1.4, sp=.015)
        return grade(sample(self.q, u, v), self.dark)

class Kaleido(Bg):
    """kaleidoscope or mirror tiles cut from the cover – for geometric covers"""
    name = "kaleido"
    def __init__(self, src, f, rng):
        super().__init__(src, f, rng)
        self.mode = str(rng.choice(["kaleido", "tiles"]))
        self.k = int(rng.choice([4, 6, 8, 10, 12])); self.sc = rng.uniform(.35, .8)
        self.spin = rng.uniform(.02, .07) * rng.choice([-1, 1]); self.ox, self.oy = rng.uniform(.3, .7), rng.uniform(.3, .7)
        self.tile = rng.uniform(.18, .35)
        self.dark = rng.uniform(.6, .82)
    def frame(self, t, A):
        if self.mode == "kaleido":
            x, y = CU0, (_cy - BH / 2) / BW
            r = np.hypot(x, y) * self.sc * (1 + .04 * A["kick"])
            th = np.arctan2(y, x) + self.spin * t
            seg = 2 * math.pi / self.k
            th = np.abs(np.mod(th, seg) - seg / 2)
            u = self.ox + r * np.cos(th + .3 * math.sin(t * .1)); v = self.oy + r * np.sin(th)
        else:
            s = self.tile * (1 + .03 * math.sin(t * .3))
            u = np.mod(CU / s + t * .025, 2.0); v = np.mod(CV / s - t * .018, 2.0)
            u = np.where(u > 1, 2 - u, u) * .55 + self.ox - .27; v = np.where(v > 1, 2 - v, v) * .55 + self.oy - .27
        c = sample(self.src, u, v)
        return grade(cv2.GaussianBlur(c, (0, 0), .7), self.dark)

class PaintFlow(Bg):
    """the painting starts to flow: cover pixels advected along the cover's own brush/line directions"""
    name = "paintflow"
    def __init__(self, src, f, rng):
        super().__init__(src, f, rng)
        self.z = rng.uniform(1.0, 1.5)
        base = sample(src, .5 + CU0 / self.z, .5 + CV0 / self.z)
        self.base = base
        g = cv2.cvtColor(base, cv2.COLOR_RGB2GRAY)
        gx = cv2.Sobel(g, cv2.CV_32F, 1, 0, ksize=5); gy = cv2.Sobel(g, cv2.CV_32F, 0, 1, ksize=5)
        jxx = cv2.GaussianBlur(gx * gx, (0, 0), 6); jyy = cv2.GaussianBlur(gy * gy, (0, 0), 6); jxy = cv2.GaussianBlur(gx * gy, (0, 0), 6)
        ang = .5 * np.arctan2(2 * jxy, jxx - jyy) + math.pi / 2       # along the strokes
        self.fx, self.fy = np.cos(ang).astype(np.float32), np.sin(ang).astype(np.float32)
        self.speed = rng.uniform(.5, 1.3); self.keep = rng.uniform(.015, .04)
        self.s = base.copy(); self.dark = rng.uniform(.68, .88); self.last = 0.0
        self.flip = np.sign(tex_at(self.t1, CU * 1.5, CV * 1.5) - .5).astype(np.float32)
    def frame(self, t, A):
        n = tex_at(self.t2, CU * 1.2 + t * .01, CV * 1.2 - t * .008) - .5
        sp = self.speed * (1 + .8 * A["kick"])
        dx = (self.fx * self.flip + n * .8) * sp; dy = (self.fy * self.flip + n * .5) * sp
        self.s = cv2.remap(self.s, (_cx - dx).astype(np.float32), (_cy - dy).astype(np.float32), cv2.INTER_LINEAR, borderMode=cv2.BORDER_REFLECT)
        self.s = self.s * (1 - self.keep) + self.base * self.keep
        return grade(self.s, self.dark)

class Bokeh(Bg):
    """photo covers: a dreamy, out-of-focus close-up of the cover with drifting light discs"""
    name = "bokeh"
    def __init__(self, src, f, rng):
        super().__init__(src, f, rng)
        self.blur = cv2.GaussianBlur(src, (0, 0), rng.uniform(10, 22))
        self.z = rng.uniform(1.8, 3.2); self.cx, self.cy = rng.uniform(.3, .7), rng.uniform(.3, .7)
        self.pan = (rng.uniform(-.01, .01), rng.uniform(-.008, .008))
        lum = src.mean(2)
        ys, xs = np.where(lum > np.percentile(lum, 85))
        idx = rng.choice(len(ys), size=min(28, len(ys)), replace=False) if len(ys) else []
        self.discs = [(rng.uniform(0, BW), rng.uniform(0, BH), rng.uniform(5, 26), src[ys[i], xs[i]].copy(),
                       rng.uniform(-3, 3), rng.uniform(-9, -2), rng.uniform(0, 6), rng.uniform(.08, .3)) for i in idx]
        self.dark = rng.uniform(.62, .85)
    def frame(self, t, A):
        u = self.cx + CU0 / self.z + self.pan[0] * t; v = self.cy + CV0 / self.z + self.pan[1] * t
        c = grade(sample(self.blur, u, v), self.dark)
        for (x, y, r, col, vx, vy, ph, al) in self.discs:
            px = (x + vx * t) % (BW + 60) - 30; py = (y + vy * t) % (BH + 60) - 30
            d = np.hypot(_cx - px, _cy - py)
            m = sstep((r - d) / 2.5) * al * (.75 + .25 * math.sin(t * .9 + ph)) * (1 + .6 * A["kick"])
            c = c + m[..., None] * col[None, None, :]
        return np.clip(c, 0, 1)

class Echo(Bg):
    """hypnotic tunnel of copies of the cover – for dark, minimal and typographic covers"""
    name = "echo"
    def __init__(self, src, f, rng):
        super().__init__(src, f, rng)
        self.small = cv2.resize(src, (BW, BW), interpolation=cv2.INTER_AREA)
        self.base = rng.uniform(1.35, 1.8); self.sp = rng.uniform(.06, .16) * rng.choice([-1, 1])
        self.rot = rng.uniform(-6, 6); self.dark = rng.uniform(.5, .72)
        self.fill = cv2.GaussianBlur(sample(src, .5 + CU0 / 2.5, .5 + CV0 / 2.5), (0, 0), 14)
    def frame(self, t, A):
        out = self.fill * .55
        ph = (t * self.sp) % 1.0
        for k in range(5, -3, -1):
            s = self.base ** (k + ph - 2) * (1 + .02 * A["kick"])
            if s < .05 or s > 6:
                continue
            M = cv2.getRotationMatrix2D((BW / 2, BW / 2), self.rot * (k + ph), s)
            M[0, 2] += 0; M[1, 2] += BH / 2 - BW / 2
            layer = cv2.warpAffine(self.small, M, (BW, BH), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_CONSTANT, borderValue=(-1, -1, -1))
            m = (layer[..., :1] >= 0).astype(np.float32)
            fade = min(1.0, s * 1.5) * (.55 + .45 * (k % 2))
            out = out * (1 - m * fade) + np.clip(layer, 0, 1) * m * fade
        return grade(out, self.dark)

class Pattern(Bg):
    """the earlier psychedelic / dreamy generators, coloured from the cover"""
    name = "pattern"
    def __init__(self, src, f, rng, im=None, family=None):
        super().__init__(src, f, rng)
        import reelfx
        self.rec = reelfx.Recipe(im, int(rng.integers(1 << 30)), family=family)
        self.name = "pattern(%s)" % self.rec.describe().split(":")[0]
    def frame(self, t, A):
        return cv2.resize(self.rec.frame(t, A), (BW, BH), interpolation=cv2.INTER_CUBIC)

ENGINES = {
    "photo":     [("bokeh", .45), ("continue", .25), ("echo", .2), ("pattern-soft", .1)],
    "graphic":   [("posterflow", .4), ("kaleido", .2), ("pattern-wild", .1), ("echo", .15), ("continue", .15)],
    "geometric": [("kaleido", .45), ("posterflow", .25), ("pattern-wild", .15), ("echo", .15)],
    "painterly": [("paintflow", .5), ("continue", .3), ("kaleido", .1), ("pattern-soft", .1)],
    "organic":   [("continue", .4), ("paintflow", .35), ("kaleido", .15), ("bokeh", .1)],
    "dark":      [("echo", .35), ("bokeh", .3), ("continue", .15), ("pattern-soft", .2)],
    "record":    [("echo", .3), ("kaleido", .3), ("posterflow", .2), ("continue", .1), ("pattern-soft", .1)],
}

def make_bg(name, src, f, rng, im):
    if name.startswith("pattern"):
        return Pattern(src, f, rng, im=im, family=name.split("-")[1])
    return {"continue": Continue, "posterflow": PosterFlow, "kaleido": Kaleido, "paintflow": PaintFlow,
            "bokeh": Bokeh, "echo": Echo}[name](src, f, rng)

# ------------------------------------------------------------------ the cover comes to life
LS = 270                                   # displacement fields are computed at 270 and scaled to 1080
_ly, _lx = np.mgrid[0:LS, 0:LS].astype(np.float32)
_fy, _fx = np.mgrid[0:CS, 0:CS].astype(np.float32)

def spectral_saliency(g):
    s = cv2.resize(g, (64, 64))
    F = np.fft.fft2(s)
    la = np.log(np.abs(F) + 1e-6); ph = np.angle(F)
    res = la - cv2.blur(la, (3, 3))
    sal = np.abs(np.fft.ifft2(np.exp(res + 1j * ph))) ** 2
    sal = cv2.GaussianBlur(sal.astype(np.float32), (0, 0), 3)
    sal = cv2.resize(sal / (sal.max() + 1e-9), (LS, LS))
    return sstep((sal - .15) / .5)

LIFE = {
    "photo":     ["breathe", "parallax", "sweep", "grain", "glint", "bloom"],
    "graphic":   ["accent", "sweep", "breathe", "parallax", "wobble"],
    "geometric": ["accent", "spin", "sweep", "breathe", "wobble"],
    "painterly": ["sway", "glint", "accent", "bloom", "ripple", "breathe"],
    "organic":   ["sway", "ripple", "glint", "breathe", "bloom"],
    "dark":      ["glint", "bloom", "sweep", "breathe", "grain"],
    "record":    ["spin", "sweep", "glint", "accent", "breathe"],
}

class Life:
    def __init__(self, im, f, a, style, rng):
        self.rng = rng
        cov = np.asarray(im.convert("RGB").resize((LS, LS), Image.LANCZOS)).astype(np.float32) / 255
        g = cv2.cvtColor(cov, cv2.COLOR_RGB2GRAY)
        gx = cv2.Sobel(g, cv2.CV_32F, 1, 0, ksize=5); gy = cv2.Sobel(g, cv2.CV_32F, 0, 1, ksize=5)
        jxx = cv2.GaussianBlur(gx * gx, (0, 0), 3); jyy = cv2.GaussianBlur(gy * gy, (0, 0), 3); jxy = cv2.GaussianBlur(gx * gy, (0, 0), 3)
        ang = .5 * np.arctan2(2 * jxy, jxx - jyy) + math.pi / 2
        self.tx, self.ty = np.cos(ang), np.sin(ang)
        energy = cv2.GaussianBlur(np.abs(cv2.Laplacian(g, cv2.CV_32F)), (0, 0), 4)
        self.texm = sstep(energy / (np.percentile(energy, 90) + 1e-6))
        grad = cv2.GaussianBlur(np.hypot(gx, gy), (0, 0), 5)
        self.smoothm = sstep(1 - grad / (np.percentile(grad, 60) + 1e-6))
        self.fg = spectral_saliency(g)
        self.phase = (noise_tex(rng, n=LS, blur=10) * 2 * math.pi).astype(np.float32)
        # effects
        pool = list(LIFE[style])
        n = int(rng.integers(3, 5))
        must = ["spin"] if style == "record" and f["circles"] else []
        fx = must + [str(x) for x in rng.permutation([p for p in pool if p not in must])][: n - len(must)]
        if "spin" in fx and not f["circles"]:
            fx.remove("spin")
        self.fx = fx
        self.p = {
            "breathe": rng.uniform(.004, .009), "bsp": rng.uniform(.5, 1.0),
            "par": rng.uniform(3, 8), "psp": rng.uniform(.25, .5), "pang": rng.uniform(0, 2 * math.pi),
            "sway": rng.uniform(2.0, 5.0), "swsp": rng.uniform(1.2, 2.6),
            "rip": rng.uniform(1.2, 2.8), "rc": (rng.uniform(.2, .8) * LS, rng.uniform(.2, .8) * LS), "rl": rng.uniform(7, 14),
            "wob": rng.uniform(1.0, 2.5),
            "spin": rng.uniform(.25, 1.2) * rng.choice([-1, 1]) if style == "record" else rng.uniform(.04, .15) * rng.choice([-1, 1]),
            "acc_h": rng.uniform(14, 40) * rng.choice([-1, 1]), "acc_sp": rng.uniform(.3, .7),
            "sweep_per": rng.uniform(5, 9), "sweep_ang": rng.uniform(.5, 1.1), "sweep_w": rng.uniform(.06, .14),
        }
        self.circles = [(x / 256 * LS, y / 256 * LS, r / 256 * LS) for x, y, r in sorted(f["circles"], key=lambda c: -c[2])[:2]]
        big = np.asarray(im.convert("RGB").resize((CS, CS), Image.LANCZOS)).astype(np.float32) / 255
        if "accent" in fx:
            hsv = cv2.cvtColor(cov, cv2.COLOR_RGB2HSV)
            pal, _ = palette(cov, rng)
            ph = cv2.cvtColor(pal[None].astype(np.float32), cv2.COLOR_RGB2HSV)[0]
            k = int(np.argmax(ph[:, 1] * (ph[:, 2] > .2)))
            d = np.linalg.norm(cov - pal[k][None, None], axis=2)
            self.accm = cv2.resize(sstep(1 - d / .28), (CS, CS))[..., None]
            bh = cv2.cvtColor(big, cv2.COLOR_RGB2HSV)
            bh[..., 0] = np.mod(bh[..., 0] + self.p["acc_h"], 360)
            self.acc_alt = cv2.cvtColor(bh, cv2.COLOR_HSV2RGB)
        if "glint" in fx or "bloom" in fx:
            lum = cv2.cvtColor(big, cv2.COLOR_RGB2GRAY)
            hl = np.clip((lum - np.percentile(lum, 97)) / (1 - np.percentile(lum, 97) + 1e-3), 0, 1)
            self.bloom_img = cv2.GaussianBlur(big * hl[..., None], (0, 0), 18) * 1.6
            dil = cv2.dilate(lum, np.ones((25, 25), np.uint8))
            ys, xs = np.where((lum >= dil) & (lum > max(.6, np.percentile(lum, 99))))
            sel = rng.permutation(len(ys))[:14]
            self.glints = [(int(xs[i]), int(ys[i]), rng.uniform(0, 6.3), rng.uniform(.6, 1.6), rng.uniform(14, 34)) for i in sel]
            self.star = self._star()
        if "grain" in fx:
            self.grain = [(rng.standard_normal((CS // 2, CS // 2)).astype(np.float32) * .035) for _ in range(6)]

    def _star(self, n=97):
        y, x = np.mgrid[0:n, 0:n].astype(np.float32) - n // 2
        r = np.hypot(x, y) + 1
        s = np.exp(-r / 4) + .55 * (np.exp(-np.abs(x) / 1.2) + np.exp(-np.abs(y) / 1.2)) * np.exp(-r / 22)
        return (s / s.max()).astype(np.float32)

    def amount(self, t):
        return float(sstep((t - .6) / 8.0))          # wakes up slowly over ~8 s

    def describe(self):
        return "+".join(self.fx)

    def apply(self, cov, t, A):
        e = self.amount(t)
        if e <= 1e-3:
            return cov
        P = self.p
        dx = np.zeros((LS, LS), np.float32); dy = np.zeros((LS, LS), np.float32)
        c0 = LS / 2
        if "breathe" in self.fx:
            s = P["breathe"] * math.sin(t * P["bsp"]) + .003 * A["kick"]
            dx += (_lx - c0) * s * e; dy += (_ly - c0) * s * e
        if "parallax" in self.fx:
            a = P["pang"] + .3 * math.sin(t * .2)
            m = P["par"] / 4 * math.sin(t * P["psp"]) * e
            dx += self.fg * m * math.cos(a); dy += self.fg * m * math.sin(a)
        if "sway" in self.fx:
            w = np.sin(self.phase + t * P["swsp"]) * (P["sway"] / 4) * e * self.texm * (1 + .5 * A["kick"])
            dx += self.tx * w; dy += self.ty * w
        if "wobble" in self.fx:
            w = np.sin(self.phase + t * 1.3) * (P["wob"] / 4) * e
            dx += w * np.cos(self.phase * 2); dy += w * np.sin(self.phase * 2)
        if "ripple" in self.fx:
            rx, ry = P["rc"]
            r = np.hypot(_lx - rx, _ly - ry) + 1e-3
            w = np.sin(r / (P["rl"] / 4) - t * 2.4) * (P["rip"] / 4) * e * self.smoothm * np.exp(-r / LS * 2)
            dx += (_lx - rx) / r * w; dy += (_ly - ry) / r * w
        if "spin" in self.fx:
            for (cx, cy, rr) in self.circles:
                ang = P["spin"] * t * e if abs(P["spin"]) > .2 else P["spin"] * math.sin(t * .4) * e * 3
                ca, sa = math.cos(ang), math.sin(ang)
                px, py = _lx - cx, _ly - cy
                m = sstep((rr - np.hypot(px, py)) / 3)
                dx += m * ((px * ca - py * sa) - px); dy += m * ((px * sa + py * ca) - py)
                break                                    # the biggest circle only
        out = cov
        if np.abs(dx).max() > .01 or np.abs(dy).max() > .01:
            DX = cv2.resize(dx, (CS, CS)) * 4; DY = cv2.resize(dy, (CS, CS)) * 4
            out = cv2.remap(cov, (_fx + DX).astype(np.float32), (_fy + DY).astype(np.float32), cv2.INTER_LINEAR, borderMode=cv2.BORDER_REFLECT)
        need_f = any(x in self.fx for x in ("accent", "sweep", "glint", "bloom", "grain"))
        if not need_f:
            return out
        o = out.astype(np.float32) / 255
        if "accent" in self.fx:
            w = (.5 + .5 * math.sin(t * P["acc_sp"])) * e * .8 + .2 * A["kick"] * e
            o = o * (1 - self.accm * w) + self.acc_alt * self.accm * w
        if "bloom" in self.fx:
            o = o + self.bloom_img * e * (.25 + .9 * A["kick"])
        if "glint" in self.fx:
            n = self.star.shape[0]; h = n // 2
            for (x, y, ph, sp, size) in self.glints:
                a = max(0.0, math.sin(t * sp + ph)) ** 6 * e
                if a < .02:
                    continue
                k = max(9, int(size * (.7 + .3 * a)) | 1)
                st = cv2.resize(self.star, (k, k))[..., None] * a * .9
                x0, y0 = x - k // 2, y - k // 2
                xa, ya = max(0, x0), max(0, y0); xb, yb = min(CS, x0 + k), min(CS, y0 + k)
                if xb > xa and yb > ya:
                    o[ya:yb, xa:xb] += st[ya - y0:yb - y0, xa - x0:xb - x0]
        if "sweep" in self.fx:
            ph = (t % P["sweep_per"]) / P["sweep_per"]
            pos = -.4 + ph * 1.8
            d = (_fx / CS * math.cos(P["sweep_ang"]) + _fy / CS * math.sin(P["sweep_ang"])) - pos
            o = o + (np.exp(-(d / P["sweep_w"]) ** 2) * .16 * e)[..., None]
        if "grain" in self.fx:
            gr = cv2.resize(self.grain[int(t * 24) % len(self.grain)], (CS, CS), interpolation=cv2.INTER_NEAREST)
            o = o + gr[..., None] * e
        return (np.clip(o, 0, 1) * 255).astype(np.uint8)

# ------------------------------------------------------------------ the whole look
CFX = {
    "photo":     [("dissolve", .15), ("swing", .1), ("glitch", .05), ("freeze", .1), ("particles", .15), ("coexist", .1), ("adapt", .1), ("one", .15), ("pixelate", .1), ("descend", .12), ("dive", .12)],
    "graphic":   [("illusion", .15), ("glitch", .1), ("swing", .1), ("pixelate", .2), ("shatter", .15), ("adapt", .1), ("coexist", .1), ("symbiosis", .1), ("dive", .12), ("descend", .1)],
    "geometric": [("illusion", .25), ("shatter", .25), ("pixelate", .2), ("glitch", .1), ("coexist", .1), ("adapt", .1), ("dive", .15)],
    "painterly": [("dissolve", .2), ("swing", .1), ("flow", .25), ("symbiosis", .15), ("one", .15), ("adapt", .15), ("dive", .15), ("descend", .1)],
    "organic":   [("dissolve", .15), ("swing", .1), ("symbiosis", .25), ("flow", .15), ("particles", .15), ("one", .1), ("freeze", .1), ("dive", .2), ("descend", .1)],
    "dark":      [("dissolve", .15), ("glitch", .15), ("particles", .2), ("freeze", .15), ("coexist", .15), ("one", .1), ("pixelate", .1), ("descend", .12), ("dive", .1)],
    "record":    [("illusion", .2), ("swing", .1), ("glitch", .1), ("shatter", .2), ("pixelate", .15), ("coexist", .1), ("freeze", .15), ("dive", .12)],
}

def wchoice(rng, items, avoid=()):
    """weighted choice; things in avoid (recently used) only if nothing else is left"""
    fresh = [x for x in items if x[0] not in avoid]
    names, w = zip(*(fresh or items))
    w = np.array(w, np.float64)
    return names[int(rng.choice(len(names), p=w / w.sum()))]

class Look:
    def __init__(self, im, seed, style=None, avoid=None):
        avoid = set(avoid or ())
        rng = np.random.default_rng(seed)
        im = im.convert("RGB")
        self.f, a = analyse(im)
        self.style = style or pick_style(self.f, rng)
        src = np.asarray(im.resize((SRC, SRC), Image.LANCZOS)).astype(np.float32) / 255
        bga = {a[3:] for a in avoid if a.startswith("bg:")}
        self.bg = make_bg(wchoice(rng, ENGINES[self.style], {b for b, _ in ENGINES[self.style] if b.split("-")[0] in bga}), src, self.f, rng, im)
        self.life = Life(im, self.f, a, self.style, rng)
        self.cfx_mode = wchoice(rng, CFX[self.style], {a[3:] for a in avoid if a.startswith("fx:")})

    def describe(self):
        return "%s cover · background %s · alive: %s · melt: %s" % (self.style, self.bg.name, self.life.describe(), self.cfx_mode)

def make_look(im, seed, style=None, avoid=None):
    return Look(im, seed, style, avoid)

# ------------------------------------------------------------------ choosing the best cover version
def autocrop(im):
    """Shop images that show the sleeve as a mockup on a plain background: cut out the artwork itself."""
    im = im.convert("RGB")
    if analyse(im)[0]["record"]:
        return im                                   # a record on a plain background stays as it is
    a = np.asarray(im.resize((256, 256))).astype(np.float32) / 255
    edge = np.concatenate([a[:6].reshape(-1, 3), a[-6:].reshape(-1, 3), a[:, :6].reshape(-1, 3), a[:, -6:].reshape(-1, 3)])
    if edge.std(0).max() > .07:
        return im                                   # no plain border
    bc = np.median(edge, 0)
    m = (np.abs(a - bc).max(2) > .14).astype(np.uint8)
    m = cv2.morphologyEx(m, cv2.MORPH_OPEN, np.ones((5, 5), np.uint8))
    ys, xs = np.where(m > 0)
    if len(ys) < 500:
        return im
    y0, y1 = np.percentile(ys, [1, 99]); x0, x1 = np.percentile(xs, [1, 99])
    w, h = x1 - x0, y1 - y0
    if w < 100 or h < 100 or abs(w - h) > .14 * max(w, h) or (w > 238 and h > 238):
        return im
    corners = [m[int(y), int(x)] for y, x in ((y0 + 4, x0 + 4), (y0 + 4, x1 - 4), (y1 - 4, x0 + 4), (y1 - 4, x1 - 4))]
    if sum(corners) <= 1:
        return im                                   # a round object (record, label): keep the whole picture
    sx, sy = im.width / 256, im.height / 256
    ins = .012 * max(w, h)
    return im.crop((int((x0 + ins) * sx), int((y0 + ins) * sy), int((x1 - ins) * sx), int((y1 - ins) * sy)))

def artwork_score(im):
    """How well a cover image works as the hero of a reel: real, rich artwork scores high;
    photos of the vinyl label, blank/minimal sleeves and small images score low."""
    f, a = analyse(im)
    g = a.mean(2)
    yy, xx = np.mgrid[0:256, 0:256]; d = np.hypot(xx - 127.5, yy - 127.5)
    core = g[d < 4]; ring = g[(d > 9) & (d < 18)]
    hole = abs(core.mean() - ring.mean()) > .22 and core.std() < .09 and ring.std() < .12
    centred = any(abs(x - 128) < 12 and abs(y - 128) < 12 and r > 40 for x, y, r in f["circles"])
    s = (min(1.0, f["n80"] / 120) * 1.0 + min(1.0, f["sat"] / .45) * .8 + min(1.0, f["contrast"] / .25) * .6
         + min(1.0, f["mid"] / .4) * .4)
    why = []
    if f["record"] or (hole and centred):
        s -= 3.0; why.append("record label shot")
    elif hole:
        s -= 1.0; why.append("centre hole (record?)")
    if f["flat"] > .7 and f["n80"] < 10:
        s -= 1.5; why.append("blank/minimal sleeve")
    if im.width < 480:
        s -= 1.0; why.append("small image")
    return round(float(s), 2), why
