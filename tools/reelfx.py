#!/usr/bin/env python3
"""Monthly Vinyl reels with living, psychedelic backgrounds (used by tools/digs.py).

Sorte 1: one release, 20 s.
Sorte 2: three releases, 15 s preview each, 2 s crossfades (audio + visuals melt into each other).

Every reel gets its own random "recipe" (pattern generators, warp, palette from the cover,
filters, audio reaction), so no two reels look the same.
"""
import math, os, subprocess, sys, json, random

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import metamorph

def log(*a):
    print(*a, file=sys.stderr, flush=True)
import numpy as np, cv2
from PIL import Image, ImageDraw, ImageFont

W, H, FPS, SR = 1080, 1920, 30, 44100
LW, LH = 216, 384                      # background is computed small and scaled up (smooth + fast)
SC = W // LW

# website colours
BLACK, WHITE, YEL, NEON, PINK, MUTED = (0, 0, 0), (255, 255, 255), (251, 237, 79), (57, 255, 20), (255, 43, 214), (160, 164, 169)
def _font(*cands):
    for p in cands:
        if os.path.exists(p):
            return p
    raise SystemExit("font missing: %s" % cands[0])
FD = _font("/usr/share/texmf/fonts/opentype/public/tex-gyre/texgyreheros-bold.otf",
           "/usr/share/fonts/opentype/tex-gyre/texgyreheros-bold.otf",
           "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
           "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf")
FDR = _font("/usr/share/texmf/fonts/opentype/public/tex-gyre/texgyreheros-regular.otf",
            "/usr/share/fonts/opentype/tex-gyre/texgyreheros-regular.otf",
            "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
            "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf")
FM = _font("/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf", "/usr/share/fonts/truetype/liberation/LiberationMono-Regular.ttf")
FMB = _font("/usr/share/fonts/truetype/dejavu/DejaVuSansMono-Bold.ttf", "/usr/share/fonts/truetype/liberation/LiberationMono-Bold.ttf")
_fc = {}
def F(path, size):
    if (path, size) not in _fc:
        _fc[(path, size)] = ImageFont.truetype(path, size)
    return _fc[(path, size)]

# layout
COV_Y, COV_S = 300, 1080               # cover: full width
TXT_R = 940                            # right edge of the text block (keeps clear of Instagram's like/comment column)
SHOP_XY = (48, 196)

# ------------------------------------------------------------------ palette from cover
def palette(cover, rng):
    a = np.asarray(cover.convert("RGB").resize((72, 72))).reshape(-1, 3).astype(np.float32)
    k = 6
    _, lab, cen = cv2.kmeans(a, k, None, (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 30, 0.5), 3, cv2.KMEANS_PP_CENTERS)
    cnt = np.bincount(lab.ravel(), minlength=k)
    cen = cen[np.argsort(-cnt)] / 255.0
    hsv = cv2.cvtColor(cen[None].astype(np.float32), cv2.COLOR_RGB2HSV)[0]   # h 0..360, s,v 0..1
    out = []
    for h, s, v in hsv:
        s = min(1.0, s * rng.uniform(1.4, 2.0) + 0.18)
        v = min(1.0, v * rng.uniform(1.3, 1.8) + 0.12)
        out.append((h, s, v))
    # sometimes push in a brand neon or a complementary accent for extra "trip"
    r = rng.random()
    if r < 0.35:
        out.append((float(rng.choice([108.0, 312.0, 55.0])), 1.0, 1.0))   # neon green / pink / yellow
    elif r < 0.65:
        h0 = out[0][0]
        out.append(((h0 + 180) % 360, 0.9, 1.0))
    hsv = np.array(out, np.float32)[None]
    rgb = cv2.cvtColor(hsv, cv2.COLOR_HSV2RGB)[0]
    rng.shuffle(rgb)
    # darkest anchor keeps depth
    dark = (rgb.min(0) * 0.25)[None]
    if rng.random() < 0.6:
        rgb = np.concatenate([rgb, dark])
    return np.clip(rgb, 0, 1).astype(np.float32)

def pal(P, v):
    n = len(P)
    f = np.mod(v, 1.0) * n
    i = np.floor(f).astype(np.int32)
    fr = (f - i)[..., None]
    fr = fr * fr * (3 - 2 * fr)
    return P[i % n] * (1 - fr) + P[(i + 1) % n] * fr

# ------------------------------------------------------------------ pattern generators
yy, xx = np.mgrid[0:LH, 0:LW].astype(np.float32)
X0 = (xx - LW / 2 + .5) / (LH / 2)
Y0 = (yy - LH / 2 + .5) / (LH / 2)

def noise_tex(rng, n=256, blur=9):
    t = rng.random((n, n)).astype(np.float32)
    t = cv2.GaussianBlur(np.tile(t, (3, 3)), (0, 0), blur)[n:2 * n, n:2 * n]   # tileable
    t = (t - t.min()) / (t.max() - t.min() + 1e-6)
    return t

def sample(tex, u, v):
    n = tex.shape[0]
    return cv2.remap(tex, (np.mod(u, 1) * n).astype(np.float32), (np.mod(v, 1) * n).astype(np.float32),
                     cv2.INTER_LINEAR, borderMode=cv2.BORDER_WRAP)

def warp(x, y, t, p, amp):
    for k, (fx, fy, sp, ph) in enumerate(p["wf"]):
        x, y = (x + amp * np.sin(fy * y + t * sp + ph),
                y + amp * np.cos(fx * x - t * sp * 0.83 + ph * 1.3))
    return x, y

def g_liquid(x, y, t, p, A):
    f = p["f"]
    v = (np.sin(f * x + t * .7) + np.sin(f * 1.3 * y - t * .5) + np.sin(f * .7 * (x + y) + t * .4)
         + np.sin(f * np.hypot(x + .3 * np.sin(t * .2), y) * 1.1 - t)) / 8 + .5
    return pal(p["P"], v * p["bands"] + t * p["drift"] + A["kick"] * .08)

def g_check(x, y, t, p, A):
    r = np.hypot(x, y) + 1e-4
    th = np.arctan2(y, x) + p["swirl"] * np.sin(t * .23) / (r + .35)
    rr = r * (1 + .08 * np.sin(t * .9))
    u, v = rr * np.cos(th) * p["n"], rr * np.sin(th) * p["n"]
    s = np.sin(math.pi * u + t * .3) * np.sin(math.pi * v - t * .2)
    m = (.5 + .5 * np.tanh(s * p["sharp"]))[..., None]
    a = pal(p["P"], r * .35 + t * p["drift"])
    b = pal(p["P"], r * .35 + t * p["drift"] + .5)
    return a * m + b * (1 - m)

def g_hypno(x, y, t, p, A):
    r = np.hypot(x, y)
    th = np.arctan2(y, x)
    v = (r * p["n"] - t * p["sp"] - A["kick"] * .25) * .25 + th / (2 * math.pi) * p["arms"] + .03 * np.sin(5 * th + t)
    return pal(p["P"], v)

def g_bubbles(x, y, t, p, A):
    fld = np.zeros_like(x)
    for (ax, bx, ay, by, rad) in p["blobs"]:
        cx = .55 * np.sin(t * ax + bx)
        cy = .95 * np.sin(t * ay + by)
        rr = rad * (1 + .25 * A["kick"])
        fld += rr * rr / ((x - cx) ** 2 + (y - cy) ** 2 + 1e-3)
    col = pal(p["P"], fld * p["bands"] + t * p["drift"])
    shade = np.clip(.55 + .45 * np.tanh((fld - 1.0) * 2), 0, 1)[..., None]
    return col * shade

def g_kaleido(x, y, t, p, A):
    r = np.hypot(x, y)
    th = np.arctan2(y, x) + t * p["rot"]
    seg = 2 * math.pi / p["k"]
    th = np.abs(np.mod(th, seg) - seg / 2)
    return g_liquid(r * np.cos(th), r * np.sin(th), t, p, A)

def g_clouds(x, y, t, p, A):
    tex = p["tex"]
    v = 0.0
    amp, sc, tot = 1.0, p["sc"], 0.0
    for o in range(4):
        v = v + amp * sample(tex, x * sc + t * .021 * (o + 1) + o * .37, y * sc - t * .017 * (o + 1) + o * .61)
        tot += amp; amp *= .5; sc *= 2.03
    v = v / tot
    return pal(p["P"], v * p["bands"] + t * p["drift"])

def g_moire(x, y, t, p, A):
    c1 = (.35 * np.sin(t * .3), .5 * np.cos(t * .21))
    c2 = (-.35 * np.sin(t * .27 + 1), -.5 * np.cos(t * .19 + 2))
    d1 = np.hypot(x - c1[0], y - c1[1]); d2 = np.hypot(x - c2[0], y - c2[1])
    s = np.sin(d1 * p["n"] - t * 2) + np.sin(d2 * p["n"] + t * 1.5)
    m = (.5 + .5 * np.tanh(s * 3))[..., None]
    return pal(p["P"], d1 * .2 + t * p["drift"]) * m + pal(p["P"], d2 * .2 + .45 + t * p["drift"]) * (1 - m)

# ---- subtle, dreamy, homogeneous, hypnotic generators (low frequency, slow, low contrast)
def g_silk(x, y, t, p, A):
    f = p["f"]
    v = (np.sin(f * x + t * .25 + np.sin(f * .6 * y - t * .2)) + np.sin(f * .8 * y - t * .18 + np.cos(f * .5 * x + t * .15))) / 4 + .5
    return pal(p["P"], v * p["bands"] + t * p["drift"])

def g_breath(x, y, t, p, A):
    r = np.hypot(x * p["ax"], y)
    br = .5 + .5 * np.sin(t * p["sp"])                       # slow breathing
    v = r * (p["n"] * (.8 + .3 * br)) - t * .12 + .04 * A["lev"]
    soft = .5 + .5 * np.sin(v * 2 * math.pi)
    return pal(p["P"], r * .35 + t * p["drift"] + soft * p["bands"] * .25)

def g_aurora(x, y, t, p, A):
    v = y * p["n"] + .35 * np.sin(x * 2.2 + t * .3) + .25 * np.sin(x * 4.1 - t * .22 + y) + t * .05
    return pal(p["P"], v * .25 + t * p["drift"])

def g_haze(x, y, t, p, A):
    tex = p["tex"]
    v = .65 * sample(tex, x * p["sc"] + t * .008, y * p["sc"] - t * .006) + .35 * sample(tex, x * p["sc"] * 2.1 - t * .011 + .3, y * p["sc"] * 2.1 + t * .009)
    return pal(p["P"], v * p["bands"] + t * p["drift"])

def g_tunnel(x, y, t, p, A):
    r = np.hypot(x, y) + 1e-3
    th = np.arctan2(y, x)
    v = 1.0 / r * .35 + t * p["sp"] + .05 * np.sin(th * p["arms"] + t * .3)
    glow = np.exp(-r * p["fall"])[..., None]
    c = pal(p["P"], v * .5)
    return c * (.55 + .45 * glow)

GENS = {"liquid": g_liquid, "check": g_check, "hypno": g_hypno, "bubbles": g_bubbles,
        "kaleido": g_kaleido, "clouds": g_clouds, "moire": g_moire}
SOFT = {"silk": g_silk, "breath": g_breath, "aurora": g_aurora, "haze": g_haze, "tunnel": g_tunnel}
ALLG = dict(GENS, **SOFT)

def gen_params(name, P, rng):
    p = {"P": P, "drift": rng.uniform(.015, .06) * rng.choice([-1, 1]), "bands": rng.uniform(.8, 2.4)}
    if name in ("liquid", "kaleido"):
        p["f"] = rng.uniform(2.5, 7)
        p["k"] = int(rng.integers(5, 10)); p["rot"] = rng.uniform(-.15, .15)
    if name == "check":
        p["n"] = rng.uniform(3, 7); p["sharp"] = rng.uniform(3, 14); p["swirl"] = rng.uniform(.6, 2.2)
    if name == "hypno":
        p["n"] = rng.uniform(6, 16); p["sp"] = rng.uniform(.4, 1.4); p["arms"] = int(rng.integers(1, 6)) * rng.choice([-1, 1])
    if name == "bubbles":
        p["blobs"] = [(rng.uniform(.15, .6), rng.uniform(0, 6), rng.uniform(.1, .5), rng.uniform(0, 6), rng.uniform(.12, .3))
                      for _ in range(int(rng.integers(5, 10)))]
        p["bands"] = rng.uniform(.15, .45)
    if name in ("clouds", "haze"):
        p["tex"] = noise_tex(rng, blur=9 if name == "clouds" else 18); p["sc"] = rng.uniform(.25, .6) if name == "clouds" else rng.uniform(.15, .3)
    if name == "moire":
        p["n"] = rng.uniform(18, 40)
    # soft family: slow drift, few bands
    if name in SOFT:
        p["drift"] = rng.uniform(.006, .02) * rng.choice([-1, 1]); p["bands"] = rng.uniform(.25, .7)
    if name == "silk":
        p["f"] = rng.uniform(1.2, 2.6)
    if name == "breath":
        p["n"] = rng.uniform(1.5, 4); p["sp"] = rng.uniform(.35, .8); p["ax"] = rng.uniform(.7, 1.3)
    if name == "aurora":
        p["n"] = rng.uniform(.8, 2)
    if name == "tunnel":
        p["sp"] = rng.uniform(.08, .25) * rng.choice([-1, 1]); p["arms"] = int(rng.integers(2, 7)); p["fall"] = rng.uniform(.6, 1.6)
    return p

# ---- moods: same cover palette, different atmosphere
MOODS = ["cover", "dark", "hell", "erdig", "schrill", "geheimnisvoll", "dreamy"]
def mood(P, name, rng):
    hsv = cv2.cvtColor(P[None].astype(np.float32), cv2.COLOR_RGB2HSV)[0]
    h, s, v = hsv[:, 0], hsv[:, 1], hsv[:, 2]
    if name == "dark":
        v = .06 + v * rng.uniform(.35, .55); s = np.minimum(1, s * 1.1)
    elif name == "hell":
        v = .82 + .18 * v; s = s * rng.uniform(.25, .5)
    elif name == "erdig":
        h = np.mod(20 + (h - 20) * .25 + rng.uniform(-8, 12), 360)       # pull hues to ochre / umber / olive
        s = .35 + .35 * s; v = .25 + .55 * v
    elif name == "schrill":
        s = np.ones_like(s); v = np.maximum(v, .9)
        h = np.mod(h + rng.uniform(-25, 25), 360)
    elif name == "geheimnisvoll":
        h = np.mod(255 + (h - 255) * .3 + rng.uniform(-35, 35), 360)    # deep violet / teal
        v = .08 + .35 * v; s = .5 + .45 * s
        k = int(rng.integers(len(v))); v[k] = .85; s[k] = .9             # one glowing accent
    elif name == "dreamy":
        s = .2 + .35 * s; v = .65 + .3 * v
    out = cv2.cvtColor(np.stack([h, np.clip(s, 0, 1), np.clip(v, 0, 1)], -1)[None].astype(np.float32), cv2.COLOR_HSV2RGB)[0]
    return np.clip(out, 0, 1).astype(np.float32)

class Recipe:
    """One unique look: wild (1-2 psychedelic generators melting into each other + filters)
    or soft (dreamy, homogeneous, slow, low contrast), each with a mood."""
    def __init__(self, cover, seed, family=None, mood_name=None):
        rng = np.random.default_rng(seed)
        base = palette(cover, rng)
        self.family = family or ("soft" if rng.random() < .45 else "wild")
        self.mood = mood_name or str(rng.choice(MOODS, p=[.22, .14, .12, .14, .14, .12, .12]))
        self.P = mood(base, self.mood, rng)
        soft = self.family == "soft"
        names = list(SOFT if soft else GENS)
        self.g1 = str(rng.choice(names))
        self.g2 = str(rng.choice([n for n in names if n != self.g1])) if rng.random() < (.4 if soft else .65) else None
        self.p1 = gen_params(self.g1, self.P, rng)
        self.p2 = gen_params(self.g2, self.P, rng) if self.g2 else None
        self.wp = {"wf": [(rng.uniform(1, 4), rng.uniform(1, 4), rng.uniform(.2, .9), rng.uniform(0, 6))
                          for _ in range(int(rng.integers(1, 4)))]}
        self.wamp = rng.uniform(.03, .1) if soft else rng.uniform(.05, .28)
        self.zoom = rng.uniform(.8, 1.3) if soft else rng.uniform(.8, 1.6)
        self.feedback = 0.0 if soft else (rng.uniform(.3, .6) if rng.random() < .35 else 0.0)
        self.fb_rot = rng.uniform(-1.2, 1.2); self.fb_zoom = rng.uniform(1.006, 1.03)
        self.rgbsplit = 0 if soft else (int(rng.integers(1, 4)) if rng.random() < .55 else 0)
        self.poster = 0 if soft else (int(rng.integers(4, 8)) if rng.random() < .25 else 0)
        self.hue_spin = (rng.uniform(-4, 4) if soft else rng.uniform(-14, 14)) if rng.random() < .4 else 0.0
        self.speed = rng.uniform(.4, .75) if soft else rng.uniform(.6, 1.3)
        self.contrast = rng.uniform(.45, .8) if soft else 1.0
        self.react = .35 if soft else 1.0
        self.prev = None

    def describe(self):
        fx = [n for n, on in (("feedback trails", self.feedback), ("rgb split", self.rgbsplit),
                              ("posterize", self.poster), ("hue spin", self.hue_spin)) if on]
        return "%s/%s: %s%s, warp %.2f%s" % (self.family, self.mood, self.g1, " melting into " + self.g2 if self.g2 else "", self.wamp,
                                            (", " + ", ".join(fx)) if fx else "")

    def frame(self, t, A):
        A = {k: v * self.react for k, v in A.items()}
        t = t * self.speed
        amp = self.wamp * (1 + 1.4 * A["kick"])
        z = self.zoom * (1 - .05 * A["kick"])
        x, y = warp(X0 * z, Y0 * z, t, self.wp, amp)
        c = ALLG[self.g1](x, y, t, self.p1, A)
        if self.g2:
            c2 = ALLG[self.g2](x, y, t * .9 + 3, self.p2, A)
            m = np.tanh((np.sin(1.3 * X0 + t * .21) + np.sin(1.7 * Y0 - t * .16) + .6 * np.sin(2.3 * (X0 - Y0) + t * .11)) * 1.8)
            m = (.5 + .5 * m)[..., None]
            c = c * m + c2 * (1 - m)
        c = np.clip(c, 0, 1).astype(np.float32)
        if self.contrast < 1:
            mu = c.mean((0, 1), keepdims=True)
            c = mu + (c - mu) * self.contrast
            c = cv2.GaussianBlur(c, (0, 0), 1.2)
        if self.hue_spin:
            hsv = cv2.cvtColor(c, cv2.COLOR_RGB2HSV)
            hsv[..., 0] = np.mod(hsv[..., 0] + self.hue_spin * t, 360)
            c = cv2.cvtColor(hsv, cv2.COLOR_HSV2RGB)
        if self.feedback:
            if self.prev is not None:
                M = cv2.getRotationMatrix2D((LW / 2, LH / 2), self.fb_rot, self.fb_zoom + .02 * A["kick"])
                pv = cv2.warpAffine(self.prev, M, (LW, LH), borderMode=cv2.BORDER_REFLECT)
                c = c * (1 - self.feedback) + pv * self.feedback
            self.prev = c.copy()
        if self.poster:
            c = np.round(c * self.poster) / self.poster
        if self.rgbsplit:
            d = self.rgbsplit + int(round(2 * A["kick"]))
            c = np.stack([np.roll(c[..., 0], d, 1), c[..., 1], np.roll(c[..., 2], -d, 0)], -1)
        return c

def upscale(c):
    big = cv2.resize(c, (W, H), interpolation=cv2.INTER_CUBIC)
    return np.clip(big * 255, 0, 255).astype(np.uint8)

# ------------------------------------------------------------------ audio analysis
def analyse(aud, nfr):
    hop = SR // FPS
    m = aud.mean(1)
    lev = np.array([np.sqrt(np.mean(m[f * hop:(f + 1) * hop] ** 2) + 1e-12) for f in range(nfr)])
    # bass energy via FFT per frame (30-160 Hz)
    win = 2048
    freqs = np.fft.rfftfreq(win, 1 / SR)
    band = (freqs > 30) & (freqs < 160)
    bass = []
    for f in range(nfr):
        c = f * hop + hop // 2
        s = m[max(0, c - win // 2): max(0, c - win // 2) + win]
        if len(s) < win:
            s = np.pad(s, (0, win - len(s)))
        bass.append(np.abs(np.fft.rfft(s * np.hanning(win)))[band].sum())
    bass = np.array(bass)
    bass /= (np.percentile(bass, 98) + 1e-9)
    kick, env, slow = np.zeros(nfr), 0.0, bass[0]
    for f in range(nfr):
        on = max(0.0, bass[f] - slow)
        slow = slow * .85 + bass[f] * .15
        env = max(env * .82, min(1.0, on * 2.2))
        kick[f] = env
    lev = np.minimum(1, lev / (np.percentile(lev, 98) + 1e-9))
    return lev, kick

# ------------------------------------------------------------------ text (website look: black boxes, yellow shop, green date)
def box_line(text, font, col, pad=(16, 10), bg=(0, 0, 0, 235)):
    d = ImageDraw.Draw(Image.new("RGBA", (10, 10)))
    l, tp, r, b = d.textbbox((0, 0), text, font=font)
    w, h = r - l + 2 * pad[0], font.size + 2 * pad[1]
    im = Image.new("RGBA", (w, h), bg)
    ImageDraw.Draw(im).text((pad[0] - l, pad[1] + font.size * .82), text, font=font, fill=col, anchor="ls")
    return im

def fit_font(path, size, text, maxw):
    d = ImageDraw.Draw(Image.new("RGBA", (10, 10)))
    while size > 20 and d.textlength(text, font=F(path, size)) > maxw:
        size -= 2
    return F(path, size)

def text_layer(rel):
    """Full-frame RGBA overlay: shop tag top-left, artist/track/date/label right-aligned under the cover."""
    L = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    # shop tag like the website's shop header: yellow uppercase name + country code box
    name = box_line(rel["shop"].upper(), F(FD, 34), YEL, pad=(16, 11))
    L.alpha_composite(name, SHOP_XY)
    if rel.get("cc"):
        cc = Image.new("RGBA", (64, name.height), (0, 0, 0, 235))
        dd = ImageDraw.Draw(cc)
        dd.rectangle([10, 13, 53, name.height - 14], outline=WHITE, width=2)
        dd.text((32, name.height / 2 + 1), rel["cc"], font=F(FM, 19), fill=WHITE, anchor="mm")
        L.alpha_composite(cc, (SHOP_XY[0] + name.width - 4, SHOP_XY[1]))
    lines = [
        (rel["a"], fit_font(FD, 44, rel["a"], 820), WHITE),
        (rel["track"], fit_font(FDR, 34, rel["track"], 820), WHITE),
        (rel["date"], F(FMB, 25), NEON),
        (rel["label"], fit_font(FM, 25, rel["label"], 820), WHITE),
    ]
    y = COV_Y + COV_S + 26
    for text, font, col in lines:
        im = box_line(text, font, col)
        L.alpha_composite(im, (TXT_R - im.width, y))
        y += im.height + 6
    return np.asarray(L)

def eq_bars(img, x_right, y, lev, frame, col=YEL):
    """small live equalizer left of the track line"""
    for b in range(4):
        ph = math.sin(frame * .45 + b * 1.7) * .5 + .5
        h = int(6 + 24 * lev * (.4 + .6 * ph))
        x = x_right - (4 - b) * 11
        img[y - h:y, x:x + 7] = col

# ------------------------------------------------------------------ cover handling
def cover_frame(cov, t, dur, kick):
    """cover with slow Ken-Burns zoom + tiny beat pulse, returns 1080x1080 uint8"""
    z = 1 + .035 * (t / dur) + .008 * kick
    M = cv2.getRotationMatrix2D((COV_S / 2, COV_S / 2), 0, z)
    return cv2.warpAffine(cov, M, (COV_S, COV_S), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_REFLECT)

def melt(img, amt, t):
    """liquid displacement used while one cover melts into the next"""
    if amt <= 1e-3:
        return img
    yy2, xx2 = np.mgrid[0:img.shape[0], 0:img.shape[1]].astype(np.float32)
    dx = amt * 60 * np.sin(yy2 / 47 + t * 7) + amt * 25 * np.sin(xx2 / 31 - t * 5)
    dy = amt * 45 * np.cos(xx2 / 53 - t * 6)
    return cv2.remap(img, (xx2 + dx).astype(np.float32), (yy2 + dy).astype(np.float32), cv2.INTER_LINEAR, borderMode=cv2.BORDER_REFLECT)

# ------------------------------------------------------------------ cover melts into the background
CY, CX = np.mgrid[0:COV_S, 0:COV_S].astype(np.float32)
_u = CX / (COV_S - 1); _v = CY / (COV_S - 1)
EDGE = np.minimum(np.minimum(_u, 1 - _u), np.minimum(_v, 1 - _v)) * 2      # 0 at the border, 1 in the centre
CR = np.hypot(CX - COV_S / 2, CY - COV_S / 2)
CTH = np.arctan2(CY - COV_S / 2, CX - COV_S / 2)
_small = np.mgrid[0:270, 0:270].astype(np.float32) / 270

def sstep(x):
    x = np.clip(x, 0, 1)
    return x * x * (3 - 2 * x)

class CoverFX:
    """Clear cover for the first 2 s, then it starts to merge with the background: very slowly at first,
    then stronger. Four characters: dissolve (drifts completely into the background), swing (just sways along),
    illusion (optical illusion), glitch (interference)."""
    MODES = ["dissolve", "swing", "illusion", "glitch"]
    ALL = MODES + list(metamorph.FX)              # + freeze, pixelate, shatter, flow, particles, coexist, adapt, symbiosis, one

    def __init__(self, seed, dur, mode=None):
        rng = np.random.default_rng(seed + 77)
        self.mode = mode or str(rng.choice(self.MODES, p=[.27, .28, .25, .2]))
        self.dur, self.seed = dur, seed
        self.pw = rng.uniform(1.8, 2.8)                    # slow start, then stronger
        em = {"dissolve": (.95, 1.3), "swing": (.55, .8), "illusion": (.75, 1.0), "glitch": (.7, 1.0)}
        em.update(metamorph.EMAX)
        self.emax = rng.uniform(*em[self.mode])
        self.tex = noise_tex(rng, n=256, blur=14)
        self.stripes = str(rng.choice(["rings", "diagonal", "vertical"]))
        self.sfreq = rng.uniform(10, 22)

    def amount(self, t):
        if t < 2.0:
            return 0.0
        return self.emax * min(1.0, (t - 2.0) / max(1.0, self.dur - 3.0)) ** self.pw

    def noise(self, t, sc, ox, oy):
        u, v = _small[1] * sc + t * ox, _small[0] * sc + t * oy
        n = sample(self.tex, u, v)
        return cv2.resize(n, (COV_S, COV_S), interpolation=cv2.INTER_CUBIC)

    def apply(self, cov, bg, t, kick, frame):
        e = self.amount(t)
        if e <= 1e-3:
            return cov
        if self.mode in metamorph.FX:
            return metamorph.FX[self.mode](self, cov, bg, t, e, kick, frame)
        return getattr(self, "_" + self.mode)(cov, bg, t, e, kick, frame)

    def _dissolve(self, cov, bg, t, e, kick, frame):
        n1 = self.noise(t, .9, .018, -.013); n2 = self.noise(t + 50, .9, -.015, .02)
        A = 150 * e
        c = cv2.remap(cov, (CX + (n1 - .5) * 2 * A).astype(np.float32), (CY + (n2 - .5) * 2 * A).astype(np.float32), cv2.INTER_LINEAR, borderMode=cv2.BORDER_REFLECT).astype(np.float32)
        lum = c.mean(2) / 255
        k = 1 + (EDGE * .9 + n1 * .7 + lum * .35 - 1.05) * e * 2.4
        keep = sstep(k)[..., None]
        b = bg.astype(np.float32)
        c = c * (1 - .25 * e) + b * .25 * e                 # colours drift towards the background
        return (c * keep + b * (1 - keep)).astype(np.uint8)

    def _swing(self, cov, bg, t, e, kick, frame):
        dx = e * (46 * np.sin(CY / 85 + t * 2.6) + 30 * kick * np.sin(CY / 23 + t * 9))
        dy = e * 34 * np.sin(CX / 110 - t * 2.1)
        c = cv2.remap(cov, (CX + dx).astype(np.float32), (CY + dy).astype(np.float32), cv2.INTER_LINEAR, borderMode=cv2.BORDER_REFLECT).astype(np.float32) / 255
        b = bg.astype(np.float32) / 255
        soft = np.where(b < .5, 2 * c * b + c * c * (1 - 2 * b), 2 * c * (1 - b) + np.sqrt(c) * (2 * b - 1))   # soft light
        c = c * (1 - .35 * e) + soft * .35 * e
        keep = sstep(EDGE / (e * .35 + 1e-3))[..., None]
        return (np.clip(c * keep + b * (1 - keep), 0, 1) * 255).astype(np.uint8)

    def _illusion(self, cov, bg, t, e, kick, frame):
        th = CTH + e * 1.1 * np.sin(CR / 85 - t * 1.4)                 # rings turning against each other
        r = CR * (1 + e * .05 * np.sin(CTH * 6 + t * 1.1))
        c = cv2.remap(cov, (COV_S / 2 + r * np.cos(th)).astype(np.float32), (COV_S / 2 + r * np.sin(th)).astype(np.float32), cv2.INTER_LINEAR, borderMode=cv2.BORDER_REFLECT).astype(np.float32)
        b = bg.astype(np.float32)
        if self.stripes == "rings":
            s = np.sin(CR / self.sfreq - t * 3.5)
        elif self.stripes == "diagonal":
            s = np.sin((CX + CY) / self.sfreq + t * 3)
        else:
            s = np.sin((CX + 40 * np.sin(CY / 140 + t)) / self.sfreq - t * 2.5)
        m = (sstep(s * 3 + .5) * min(1.0, e * 1.2) * (.35 + .65 * (1 - EDGE)))[..., None]
        diff = np.abs(c - b)
        c = c * (1 - m) + (diff * .5 + b * .5) * m
        keep = sstep(EDGE / (e * .2 + 1e-3))[..., None]
        return (c * keep + b * (1 - keep)).astype(np.uint8)

    def _glitch(self, cov, bg, t, e, kick, frame):
        rng = np.random.default_rng(self.seed * 100003 + frame)
        c = cov.copy()
        j = int(e * 6)
        if j:
            c = np.roll(c, int(rng.integers(-j, j + 1)), 1)      # constant jitter
        if rng.random() < e * .85 + kick * e:
            for _ in range(1 + int(e * 9 * rng.random())):
                y0 = int(rng.integers(0, COV_S - 10)); h = int(rng.integers(6, 30 + int(140 * e)))
                sl = slice(y0, min(COV_S, y0 + h))
                r = rng.random()
                if r < .55:
                    c[sl] = np.roll(c[sl], int(rng.integers(-1, 2) * rng.integers(10, 30 + int(240 * e))), 1)
                elif r < .8:
                    c[sl] = bg[sl]
                else:
                    c[sl] = 255 - bg[sl]
            d = int(e * 16 * rng.random())
            if d:
                c = np.stack([np.roll(c[..., 0], d, 1), c[..., 1], np.roll(c[..., 2], -d, 1)], -1)
            if rng.random() < e * .5:
                x0, y0 = int(rng.integers(0, COV_S - 100)), int(rng.integers(0, COV_S - 100))
                w, h = int(rng.integers(60, 100 + int(380 * e))), int(rng.integers(20, 60 + int(160 * e)))
                blk = bg[y0:y0 + h, x0:x0 + w]
                c[y0:y0 + h, x0:x0 + w] = (blk // 64) * 64 + 32 if rng.random() < .5 else blk
        return c

def comp(base, layer):
    a = layer[..., 3:4].astype(np.float32) / 255
    if a.max() == 0:
        return base
    m = a[..., 0] > 0
    ys, xs = np.where(m.any(1))[0], np.where(m.any(0))[0]
    y0, y1, x0, x1 = ys[0], ys[-1] + 1, xs[0], xs[-1] + 1
    b = base[y0:y1, x0:x1].astype(np.float32)
    base[y0:y1, x0:x1] = (b * (1 - a[y0:y1, x0:x1]) + layer[y0:y1, x0:x1, :3] * a[y0:y1, x0:x1]).astype(np.uint8)
    return base

def blend_layer(base, layer, alpha):
    if alpha <= 0:
        return base
    L = layer.copy()
    L[..., 3] = (L[..., 3].astype(np.float32) * alpha).astype(np.uint8)
    return comp(base, L)

def smooth(x):
    x = min(1.0, max(0.0, x))
    return x * x * (3 - 2 * x)

# ------------------------------------------------------------------ render
def encode(frames_fn, nfr, aud, path, poster, poster_at):
    wav = path + ".f32"
    aud.astype("<f4").tofile(wav)
    cmd = ["ffmpeg", "-y", "-v", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", "%dx%d" % (W, H), "-r", str(FPS), "-i", "-",
           "-f", "f32le", "-ar", str(SR), "-ac", "2", "-i", wav,
           "-c:v", "libx264", "-profile:v", "high", "-pix_fmt", "yuv420p", "-b:v", "10M", "-maxrate", "14M", "-bufsize", "20M",
           "-g", "60", "-preset", "medium", "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", "-shortest", path]
    pr = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    for f in range(nfr):
        im = frames_fn(f)
        if f == poster_at:
            Image.fromarray(im).save(poster, quality=90)
        pr.stdin.write(im.tobytes())
        if f % 150 == 0:
            log("  frame", f, "/", nfr)
    pr.stdin.close()
    assert pr.wait() == 0
    os.remove(wav)

def fades(img, t, dur, fin=.5, fout=1.0):
    a = min(1.0, t / fin, (dur - t) / fout)
    return img if a >= 1 else (img.astype(np.float32) * max(0, a)).astype(np.uint8)

def prep_cover(im):
    im = im.convert("RGB")
    return im, np.asarray(im.resize((COV_S, COV_S), Image.LANCZOS))

def reel_single(rel, aud, seed, out, poster, kw=None, cmode=None, avoid=None):
    dur = 20
    nfr = dur * FPS
    aud = aud[:dur * SR]
    lev, kick = analyse(aud, nfr)
    im, cov = prep_cover(rel["cover"])
    import coverlife
    look = coverlife.make_look(im, seed, avoid=avoid)
    cfx = CoverFX(seed, dur, mode=cmode or look.cfx_mode)
    log("Sorte 1 look:", look.describe())
    txl = text_layer(rel)
    trk_y = None
    def fr(f):
        t = f / FPS
        A = {"lev": lev[f], "kick": kick[f]}
        img = upscale(look.bg.frame(t, A))
        reg = img[COV_Y:COV_Y + COV_S]
        img[COV_Y:COV_Y + COV_S] = cfx.apply(look.life.apply(cover_frame(cov, t, dur, kick[f]), t, A), reg, t, kick[f], f)
        img = comp(img, txl)
        return fades(img, t, dur)
    encode(fr, nfr, aud, out, poster, int(1.2 * FPS))
    return look.describe()

def reel_triple(rels, auds, offs, seeds, out, poster, seg=15.0, xf=2.0, kws=None, cmodes=None, avoid=None):
    """offs: start second inside each preview"""
    starts = [i * (seg - xf) for i in range(len(rels))]
    dur = starts[-1] + seg
    nfr = int(dur * FPS)
    mix = np.zeros((int(dur * SR) + SR, 2), np.float32)
    for i, a in enumerate(auds):
        s = a[int(offs[i] * SR): int(offs[i] * SR) + int(seg * SR)].copy()
        if len(s) < int(seg * SR):
            s = np.concatenate([s, np.zeros((int(seg * SR) - len(s), 2), np.float32)])
        s = s * min(4.0, .14 / (np.sqrt(np.mean(s ** 2)) + 1e-6))   # loudness match
        n = len(s); tt = np.arange(n) / SR
        g = np.ones(n, np.float32)
        fi = .4 if i == 0 else xf
        fo = 1.5 if i == len(auds) - 1 else xf
        g *= np.where(tt < fi, np.sin(np.clip(tt / fi, 0, 1) * math.pi / 2), 1)          # equal-power
        g *= np.where(tt > seg - fo, np.cos(np.clip((tt - (seg - fo)) / fo, 0, 1) * math.pi / 2), 1)
        i0 = int(starts[i] * SR)
        mix[i0:i0 + n] += s * g[:, None]
    mix = mix[:int(dur * SR)]
    mix *= min(1.0, .97 / (np.abs(mix).max() + 1e-9))
    lev, kick = analyse(mix, nfr)
    covs, recs, txls, cfxs = [], [], [], []
    for i, r in enumerate(rels):
        im, cov = prep_cover(r["cover"])
        covs.append(cov)
        import coverlife
        av = set(avoid or ())
        for r_ in recs:                                   # the three releases get three different looks
            av |= {"bg:" + r_.bg.name.split("(")[0], "fx:" + r_.cfx_mode}
        recs.append(coverlife.make_look(im, seeds[i], avoid=av))
        cfxs.append(CoverFX(seeds[i], seg, mode=(cmodes or [None] * 3)[i] or recs[-1].cfx_mode))
        txls.append(text_layer(r))
        log("Sorte 2 track %d look:" % (i + 1), recs[-1].describe())
    def fr(f):
        t = f / FPS
        A = {"lev": lev[f], "kick": kick[f]}
        # which release is on, and how far into the crossfade to the next
        i = max(k for k, s in enumerate(starts) if t >= s - 1e-6)
        nxt = i + 1 if i + 1 < len(rels) and t > starts[i + 1] - xf / 2 - 1e-6 else None
        if i > 0 and t < starts[i] + xf / 2:
            i, nxt = i - 1, i
        if nxt is None:
            img = upscale(recs[i].bg.frame(t, A))
            reg = img[COV_Y:COV_Y + COV_S]
            cv_ = recs[i].life.apply(cover_frame(covs[i], t - starts[i], seg, kick[f]), t - starts[i], A)
            img[COV_Y:COV_Y + COV_S] = cfxs[i].apply(cv_, reg, t - starts[i], kick[f], f)
            return fades(comp(img, txls[i]), t, dur)
        c = (t - (starts[nxt] - xf / 2)) / xf          # 0..1 across the crossfade
        a = smooth(c)
        bg = recs[i].bg.frame(t, A) * (1 - a) + recs[nxt].bg.frame(t, A) * a
        img = upscale(bg)
        m = math.sin(math.pi * c)                       # melt strength peaks mid-transition
        reg = img[COV_Y:COV_Y + COV_S].copy()
        cv_ = recs[i].life.apply(cover_frame(covs[i], t - starts[i], seg, kick[f]), t - starts[i], A)
        c1 = melt(cfxs[i].apply(cv_, reg, t - starts[i], kick[f], f), m, t).astype(np.float32)
        c2 = melt(cover_frame(covs[nxt], t - starts[nxt], seg, kick[f]), m, t + 1).astype(np.float32)
        img[COV_Y:COV_Y + COV_S] = (c1 * (1 - a) + c2 * a).astype(np.uint8)
        img = blend_layer(img, txls[i], max(0, 1 - c * 2))
        img = blend_layer(img, txls[nxt], max(0, c * 2 - 1))
        return fades(img, t, dur)
    encode(fr, nfr, mix, out, poster, int(1.2 * FPS))
    return [r.describe().rsplit(" · melt:", 1)[0] + " · melt: " + c.mode for r, c in zip(recs, cfxs)], dur
