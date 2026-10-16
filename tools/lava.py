"""Lava reel: the cover visual stays untouched (only eyes may move); the black around it fills step by step
with lava-lamp blobs made of flowing, distorted cutouts of the same cover. Nothing new is added."""
import math
import numpy as np
import cv2
import reelfx as R

LW2, LH2 = R.W // 2, R.H // 2           # lava is computed at half resolution


def _ss(x):
    x = np.clip(x, 0, 1)
    return x * x * (3 - 2 * x)


def visual_alpha(cov, bg):
    """soft mask of the cover's visual (everything that is not the black ground), holes filled, glow kept"""
    lum = cov.astype(np.float32).max(2) - float(max(bg))
    soft = np.clip((lum - 6) / 30, 0, 1)
    hard = (lum > 25).astype(np.uint8)
    hard = cv2.morphologyEx(hard, cv2.MORPH_CLOSE, np.ones((15, 15), np.uint8))
    ff = hard.copy()
    h, w = ff.shape
    m = np.zeros((h + 2, w + 2), np.uint8)
    cv2.floodFill(ff, m, (0, 0), 2)
    filled = ((ff != 2) | (hard > 0)).astype(np.float32)          # inside of rings counts as visual
    filled = cv2.GaussianBlur(cv2.dilate(filled, np.ones((5, 5), np.uint8)), (0, 0), 2.5)
    return np.maximum(soft, filled)


class Lava:
    def __init__(self, cov, seed, dur, start=3.0, n=9):
        rng = np.random.default_rng(seed + 4242)
        self.cov = cov
        S = cov.shape[0]
        # where the cover is colourful: cutouts come from there
        hsv = cv2.cvtColor(cov, cv2.COLOR_RGB2HSV)
        ys, xs = np.where((hsv[..., 1] > 90) & (hsv[..., 2] > 70))
        if len(xs) < 50:
            ys, xs = np.where(hsv[..., 2] > 60)
        self.blobs = []
        births = start + np.cumsum(np.r_[0, rng.uniform(2.5, 6.5, n - 1)])
        births = start + (births - start) * min(1.0, (dur * .62 - start) / max(1e-3, births[-1] - start))
        for i in range(n):
            k = int(rng.integers(len(xs)))
            self.blobs.append(dict(
                birth=float(births[i]), grow=rng.uniform(5, 9),
                r=rng.uniform(150, 290) * (1.0 if i > 1 else .8),
                x0=rng.uniform(.08, .92) * R.W, ax=rng.uniform(40, 140), wx=rng.uniform(.05, .12), px=rng.uniform(0, 6.3),
                y0=rng.uniform(.1, .9) * R.H, ay=rng.uniform(200, 520), wy=rng.uniform(.03, .07), py=rng.uniform(0, 6.3),
                sx=float(xs[k]), sy=float(ys[k]), sc=rng.uniform(.35, .8), rot=rng.uniform(0, 6.3), spin=rng.uniform(-.12, .12),
                wob=rng.uniform(0, 6.3)))
        yy, xx = np.mgrid[0:LH2, 0:LW2].astype(np.float32)
        self.X, self.Y = xx * 2, yy * 2                               # full-res coordinates
        self.S = S

    def frame(self, t, lev=0.0):
        X, Y = self.X, self.Y
        field = np.zeros_like(X)
        cs = []
        for i, b in enumerate(self.blobs):
            g = _ss((t - b["birth"]) / b["grow"])
            if g <= 0:
                cs.append(None)
                continue
            cx = b["x0"] + b["ax"] * math.sin(b["wx"] * t * 6.28 + b["px"])
            cy = b["y0"] + b["ay"] * math.sin(b["wy"] * t * 6.28 + b["py"])
            r = b["r"] * g * (1 + .07 * math.sin(t * .9 + b["wob"]) + .03 * lev)
            # slightly stretched, wobbling blob like rising wax
            dx = (X - cx) / (1 + .12 * math.sin(t * .7 + b["wob"]))
            dy = (Y - cy) / (1 + .12 * math.cos(t * .6 + b["wob"]))
            c = r * r / (dx * dx + dy * dy + 1.0)
            field += c
            cs.append((cx, cy, r))
        if not any(cs):
            return None, None
        alpha = _ss((field - .85) / .3)
        # texture: every blob carries its own flowing cutout; where blobs meet, the cutouts melt into each other
        acc = np.zeros(X.shape + (3,), np.float32)
        wsum = np.zeros_like(X)
        fx = 38 * np.sin(Y / 110 + t * .55) + 24 * np.sin(X / 75 - t * .4)
        fy = 30 * np.cos(X / 95 - t * .5) + 20 * np.sin(Y / 60 + t * .35)
        for i, b in enumerate(self.blobs):
            if cs[i] is None:
                continue
            cx, cy, r = cs[i]
            qx, qy = X - cx, Y - cy
            d2 = qx * qx + qy * qy
            w = (r * r / (d2 + 1.0)) ** 3
            th = b["rot"] + b["spin"] * t + .9 * np.exp(-np.sqrt(d2) / max(r, 1) * 1.5) * math.sin(t * .25 + b["wob"])
            co, si = np.cos(th), np.sin(th)
            U = b["sx"] + (qx * co - qy * si) * b["sc"] + fx
            V = b["sy"] + (qx * si + qy * co) * b["sc"] + fy
            tx = cv2.remap(self.cov, U.astype(np.float32), V.astype(np.float32), cv2.INTER_LINEAR, borderMode=cv2.BORDER_REFLECT_101)
            acc += tx.astype(np.float32) * w[..., None]
            wsum += w
        tex = acc / (wsum[..., None] + 1e-9)
        shade = .72 + .28 * _ss((field - .85) / 2.0)                 # soft volume: darker rims, lit core
        tex = tex * shade[..., None]
        return tex, alpha


def reel_lava(rel, aud, seed, out, poster, dur=60, eyes=None, blobs=True):
    nfr = int(dur * R.FPS)
    aud = aud[:int(dur * R.SR)]
    lev, kick = R.analyse(aud, nfr)
    _, cov = R.prep_cover(rel["cover"])
    corners = np.concatenate([cov[:20, :20].reshape(-1, 3), cov[:20, -20:].reshape(-1, 3), cov[-20:, :20].reshape(-1, 3), cov[-20:, -20:].reshape(-1, 3)])
    bg = np.median(corners, 0).astype(np.float32)
    va = visual_alpha(cov, bg)
    eyefx = None
    if eyes:
        import eyes as _eyes
        eyefx = _eyes.Eyes(cov, eyes, seed, dur, start=2.5)
    lava = Lava(cov, seed, dur)
    txl = R.text_layer(rel, mono=R.YEL)
    base = np.empty((R.H, R.W, 3), np.float32)
    base[:] = bg
    R.log("Lava reel:", len(lava.blobs), "blobs, births", [round(b["birth"], 1) for b in lava.blobs])

    def zoom(img, t, interp=cv2.INTER_LINEAR):
        z = 1 + .02 * (t / dur)
        M = cv2.getRotationMatrix2D((R.COV_S / 2, R.COV_S / 2), 0, z)
        return cv2.warpAffine(img, M, (R.COV_S, R.COV_S), flags=interp, borderMode=cv2.BORDER_REFLECT)

    def fr(f):
        t = f / R.FPS
        img = base.copy()
        tex, a = lava.frame(t, float(lev[f])) if blobs else (None, None)
        if tex is not None:
            tex = cv2.resize(tex, (R.W, R.H), interpolation=cv2.INTER_LINEAR)
            a = cv2.resize(a, (R.W, R.H), interpolation=cv2.INTER_LINEAR)[..., None]
            img = img * (1 - a) + tex * a
        c = cov if eyefx is None else eyefx.apply(cov, t)
        c = zoom(c, t).astype(np.float32)
        al = zoom(va, t)[..., None]
        reg = img[R.COV_Y:R.COV_Y + R.COV_S]
        img[R.COV_Y:R.COV_Y + R.COV_S] = c * al + reg * (1 - al)
        img = np.clip(img, 0, 255).astype(np.uint8)
        img = R.comp(img, txl)
        return R.fades(img, t, dur)

    R.encode(fr, nfr, aud, out, poster, int(1.2 * R.FPS))
    return ("lava · %d blobs" % len(lava.blobs) if blobs else "still cover") + (" · eyes" if eyes else "")
