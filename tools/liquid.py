"""Liquid-metal reel: the cover grows out of its frame at the top and bottom like molten aluminium,
flows until it fills the whole screen, then turns liquid itself and mixes more and more.

Only the cover's own pixels are used (advected, stretched, mixed); the metal look comes from shading a
height field made of the image itself (environment reflection + specular highlights). Nothing new is drawn.

Timeline (default 60 s):
  0-4 s    cover still, the black around it untouched
  4-22 s   drips and tongues of the cover grow out of the top and bottom edge and fill the black
  18-38 s  the cover loosens: it is no longer held in place, the surface turns to chrome
  38-60 s  everything swirls and mixes more and more; last second fades out
"""
import math
import numpy as np
import cv2
from PIL import Image
import reelfx as R

HW, HH = R.W // 2, R.H // 2                      # simulation at half resolution
CT, CB = R.COV_Y // 2, (R.COV_Y + R.COV_S) // 2  # cover top / bottom in half-res rows


def _ss(x):
    x = np.clip(x, 0, 1)
    return x * x * (3 - 2 * x)


def _s(x):
    x = min(1.0, max(0.0, x))
    return x * x * (3 - 2 * x)


class Liquid:
    def __init__(self, cov, seed, dur):
        self.dur = dur
        self.k = dur / 60.0                      # timeline scales with the reel length
        rng = np.random.default_rng(seed + 777)
        yy, xx = np.mgrid[0:HH, 0:HW].astype(np.float32)
        self.X, self.Y = xx, yy
        self.cov = cv2.resize(cov, (HW, CB - CT), interpolation=cv2.INTER_AREA).astype(np.float32)
        self.S = np.zeros((HH, HW, 3), np.float32)
        self.A = np.zeros((HH, HW), np.float32)          # where there is matter (the cover's metal)
        self.S[CT:CB] = self.cov
        self.covF = self.S.copy()
        self.A[CT:CB] = 1
        self.cmask = np.zeros((HH, HW), np.float32)
        self.cmask[CT:CB] = 1
        self.cmask = cv2.GaussianBlur(self.cmask, (0, 0), 1.2)
        # swirl: stream function = sum of travelling waves (analytic curl → divergence-free flow)
        n = 7
        ang = rng.uniform(0, 2 * np.pi, n)
        kk = rng.uniform(1 / 260, 1 / 90, n)
        self.waves = [(math.cos(a) * k, math.sin(a) * k, rng.uniform(.15, .55) * rng.choice([-1, 1]), rng.uniform(0, 6.3), 1 / k)
                      for a, k in zip(ang, kk)]
        # drips: per column speed (some tongues run ahead, others lag)
        self.drip_ph = rng.uniform(0, 6.3, 4)
        self.drip_k = rng.uniform(1 / 90, 1 / 30, 4)
        # environment map for the metal: soft studio bands (cool grey / white / dark), built from the cover's own tones
        lum = cov.astype(np.float32).mean(2)
        lo, hi = np.percentile(lum, 8), np.percentile(lum, 97)
        tint = cov.reshape(-1, 3).astype(np.float32).mean(0)
        tint = tint / max(1.0, tint.max()) * 255
        g = np.linspace(0, 1, 256, dtype=np.float32)
        bands = .5 + .5 * np.sin(g * 5.0 + .6) * np.cos(g * 1.7)
        bands = lo + (hi - lo) * (.15 + .85 * bands ** 1.6)
        self.env = (bands[:, None] * (.75 + .25 * tint[None, :] / 255)).astype(np.float32)   # 256x3

    def tl(self, s):
        return s * self.k

    def flow(self, t, kick):
        X, Y = self.X, self.Y
        tl = self.tl
        vx = np.zeros_like(X)
        vy = np.zeros_like(Y)
        for kx, ky, w, ph, L in self.waves:
            arg = kx * X + ky * Y + w * t + ph
            c = np.cos(arg) * L
            vx += c * ky                         # v = (dpsi/dy, -dpsi/dx), psi amplitude = L (so speed ~ 1)
            vy -= c * kx
        swirl = .22 + 1.5 * _s((t - tl(16)) / tl(26)) + 1.3 * _s((t - tl(36)) / tl(20)) + .6 * kick
        # before the growth starts the black stays untouched: no swirl outside the cover
        calm = _s((t - tl(4)) / tl(4))
        gate = self.cmask + (1 - self.cmask) * calm
        vx *= swirl * gate
        vy *= swirl * gate
        # outward growth: above the cover everything flows up, below it flows down (drips with different speeds)
        grow = _s((t - tl(4)) / tl(3)) * (1 - .7 * _s((t - tl(30)) / tl(8))) * max(1.0, (60.0 / self.dur) ** .5)
        if grow > 0:
            d = np.zeros(HW, np.float32)
            xs = np.arange(HW, dtype=np.float32)
            for ph, k in zip(self.drip_ph, self.drip_k):
                d += np.sin(xs * k + ph + .25 * t)
            drip = .35 + .65 * _ss(.5 + d / 3)[None, :]
            up = _ss((CT + 2 - Y) / 6)
            down = _ss((Y - CB + 2) / 6)
            U = grow * (1.1 + .5 * kick) * drip
            vy += (-up * U * .8 + down * U * 1.3)
        return vx, vy

    def step(self, t, kick):
        vx, vy = self.flow(t, kick)
        mx, my = self.X - vx, self.Y - vy
        self.S = cv2.remap(self.S, mx, my, cv2.INTER_LINEAR, borderMode=cv2.BORDER_REPLICATE)
        self.A = cv2.remap(self.A, mx, my, cv2.INTER_LINEAR, borderMode=cv2.BORDER_REPLICATE)
        tl = self.tl
        # hold the cover in place at first; let go of it step by step
        hold = 1 - _s((t - tl(18)) / tl(16))
        if hold > 0:
            w = (self.cmask * hold)[..., None]
            self.S = self.S * (1 - w) + self.covF * w
            self.A = np.maximum(self.A, self.cmask * hold)
        # keep the liquid crisp: mild unsharp mask against the blur of repeated resampling
        lum = self.S.mean(2)
        sh = (lum - cv2.GaussianBlur(lum, (0, 0), 2.0)) * .07
        self.S = np.clip(self.S + sh[..., None], 0, 255)
        # matter edges stay sharp like a liquid surface
        self.A = np.clip((self.A - .5) * 1.08 + .5, 0, 1)

    def render(self, t, kick):
        tl = self.tl
        A = _ss((self.A - .35) / .3)
        S = self.S
        lum = S.mean(2)
        h = cv2.GaussianBlur(lum * A, (0, 0), 3.0) / 255 * 40 + cv2.GaussianBlur(A, (0, 0), 2.0) * 30
        gx = cv2.Sobel(h, cv2.CV_32F, 1, 0, ksize=3)
        gy = cv2.Sobel(h, cv2.CV_32F, 0, 1, ksize=3)
        nz = 1 / np.sqrt(gx * gx + gy * gy + 1)
        nx, ny = -gx * nz, -gy * nz
        # environment lookup by normal direction (reflection of a studio), slowly rotating
        ang = .35 * math.sin(t * .11)
        ex = nx * math.cos(ang) - ny * math.sin(ang)
        idx = np.clip((.5 + .5 * ex * 1.6 + .25 * ny) * 255, 0, 255).astype(np.int32)
        env = self.env[idx]
        # specular highlight from a light top-left, pulsing slightly on the kick
        lx, ly, lz = -.45, -.6, .66
        spec = np.clip(nx * lx + ny * ly + nz * lz, 0, 1) ** 28 * (230 + 120 * kick)
        rim = np.clip(1 - nz, 0, 1) ** .8
        # how metallic: the grown tongues are metal from the start, the cover itself turns to chrome later
        outside = 1 - self.cmask
        m_out = .48
        m_in = .08 + .45 * _s((t - tl(20)) / tl(22))
        metal = (outside * m_out + (1 - outside) * m_in)
        metal = np.maximum(metal, rim * .6)[..., None]
        col = S * (1 - metal) + env * metal
        col = col * (.92 + .16 * nz[..., None]) + spec[..., None] * (.35 + .65 * metal)
        col = col * A[..., None]
        return np.clip(col, 0, 255)


def suits(im):
    """Is this cover a good candidate for the liquid-metal reel? Best: textured, colourful or high-contrast art
    without big type and without people. Returns a score 0..1 (>= .5 = yes) and a short reason.
    (No face detector available in the Action's OpenCV; people are only guessed from skin tones.)"""
    a = np.asarray(im.convert("RGB").resize((256, 256), Image.LANCZOS)).astype(np.float32)
    hsv = cv2.cvtColor(a.astype(np.uint8), cv2.COLOR_RGB2HSV).astype(np.float32)
    sat = hsv[..., 1].mean() / 255
    lum = a.mean(2)
    contrast = lum.std() / 255
    # people: skin-tone share
    h, s_, v = hsv[..., 0], hsv[..., 1], hsv[..., 2]
    skin = ((h < 25) & (s_ > 40) & (s_ < 180) & (v > 80)).mean()
    # big type: long straight horizontal / vertical edges
    ed = cv2.Canny(a.astype(np.uint8), 80, 160)
    hor = cv2.morphologyEx(ed, cv2.MORPH_OPEN, np.ones((1, 15), np.uint8)).mean() / 255
    ver = cv2.morphologyEx(ed, cv2.MORPH_OPEN, np.ones((15, 1), np.uint8)).mean() / 255
    typ = hor + ver
    texture = ed.mean() / 255
    score = .2 + .6 * min(sat, .5) + .5 * min(contrast, .35) + 2.5 * min(texture, .14) - 9 * typ - 2 * max(0, skin - .05)
    score = float(np.clip(score, 0, 1))
    why = "sat %.2f contrast %.2f texture %.3f type %.3f skin %.2f" % (sat, contrast, texture, typ, skin)
    return score, why


def reel_liquid(rel, aud, seed, out, poster, dur=60):
    nfr = int(dur * R.FPS)
    aud = aud[:int(dur * R.SR)]
    lev, kick = R.analyse(aud, nfr)
    _, cov = R.prep_cover(rel["cover"])
    liq = Liquid(cov, seed, dur)
    col = rel.get("col")
    if col:                                       # daily reel: flat site look with live bars
        txl, bars = R.text_layer_flat(rel, col)
    else:
        txl, bars = R.text_layer(rel, mono=R.YEL), None
    covf = cov.astype(np.float32)
    R.log("Liquid metal reel:", dur, "s")

    def fr(f):
        t = f / R.FPS
        liq.step(t, float(kick[f]))
        img = liq.render(t, float(kick[f]))
        img = cv2.resize(img, (R.W, R.H), interpolation=cv2.INTER_CUBIC)
        # the first seconds show the sharp full-resolution cover; it hands over to the liquid as it loosens
        sharp = 1 - _s((t - liq.tl(14)) / liq.tl(8))
        if sharp > 0:
            reg = img[R.COV_Y:R.COV_Y + R.COV_S]
            img[R.COV_Y:R.COV_Y + R.COV_S] = covf * sharp + reg * (1 - sharp)
        img = np.clip(img, 0, 255).astype(np.uint8)
        img = R.comp(img, txl)
        if bars:
            img = np.ascontiguousarray(img)
            for b in range(5):
                ph = math.sin(f * .45 + b * 1.7) * .5 + .5
                hh = int(6 + 26 * lev[f] * (.4 + .6 * ph))
                x = bars[0] - (5 - b) * 11
                img[bars[1] - hh:bars[1], x:x + 7] = col
        return R.fades(img, t, dur)

    R.encode(fr, nfr, aud, out, poster, int(min(30, dur / 2) * R.FPS))
    return "liquid metal · grows out top and bottom, fills the screen, mixes"
