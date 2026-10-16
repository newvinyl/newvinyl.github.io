"""Eyes on a cover come alive: they look around and blink, built only from the cover's own pixels.

Eye spec (cover coordinates 0..1, from tools/single_reel.json "eyes"):
  {"cx": .., "cy": .., "a": half width, "c": half height, "ix": .., "iy": .., "r": iris radius}
"""
import numpy as np
import cv2


def _sstep(x):
    x = np.clip(x, 0, 1)
    return x * x * (3 - 2 * x)


class Eyes:
    def __init__(self, cov, specs, seed, dur, start=1.2):
        S = cov.shape[0]
        self.S, self.dur = S, dur
        self.eyes = []
        for e in specs:
            cx, cy, a, c = e["cx"] * S, e["cy"] * S, e["a"] * S, e["c"] * S
            ix, iy, r = e["ix"] * S, e["iy"] * S, e["r"] * S
            pad = int(max(a, c) * 2.2)
            x0, y0 = int(cx - pad), int(cy - pad * 1.4)
            x1, y1 = int(cx + pad), int(cy + pad)
            yy, xx = np.mgrid[y0:y1, x0:x1].astype(np.float32)
            patch = cov[y0:y1, x0:x1].astype(np.float32)
            ell = ((xx - cx) / a) ** 2 + ((yy - cy) / c) ** 2
            rr, gg, bb = patch[..., 0], patch[..., 1], patch[..., 2]
            skin = (bb > rr + 35) & (bb > 70)
            opening = ((ell < 1.0) & ~skin).astype(np.uint8)
            opening = cv2.morphologyEx(opening, cv2.MORPH_CLOSE, np.ones((5, 5), np.uint8))
            opening = cv2.GaussianBlur(opening.astype(np.float32), (0, 0), 1.2)
            iris = (np.hypot(xx - ix, yy - iy) < r * 1.1).astype(np.uint8)
            # sclera without the iris: fill the iris hole from the surrounding white of the eye
            hole = ((np.hypot(xx - ix, yy - iy) < r * 1.4) & (ell < 1.3)).astype(np.uint8) * 255
            sclera = cv2.inpaint(patch.astype(np.uint8), hole, 15, cv2.INPAINT_TELEA).astype(np.float32)
            sclera = cv2.GaussianBlur(sclera, (0, 0), 2.5)          # smooth, no trace of the old iris
            imask = cv2.GaussianBlur(iris.astype(np.float32), (0, 0), 1.0)
            self.eyes.append(dict(x0=x0, y0=y0, x1=x1, y1=y1, xx=xx, yy=yy, cx=cx, cy=cy, a=a, c=c, r=r,
                                  patch=patch, sclera=sclera, imask=imask, opening=opening))
        rng = np.random.default_rng(seed + 991)
        # gaze: hold, then a quick saccade to a new target
        t, g, self.gaze = start, (0.0, 0.0), [(0.0, 0.0, 0.0)]
        targets = [(-1, 0), (1, 0), (0, 0), (-1, -.5), (1, -.5), (-.6, .6), (.6, .6), (0, -.7)]
        while t < dur:
            nt = targets[int(rng.integers(len(targets)))]
            while nt == g:
                nt = targets[int(rng.integers(len(targets)))]
            g = nt
            self.gaze.append((t, g[0], g[1]))
            t += rng.uniform(.6, 2.4)
        # blinks: every 2.5–5.5 s, now and then a double blink
        self.blinks, t = [], start + rng.uniform(.8, 1.8)
        while t < dur - .5:
            self.blinks.append(t)
            if rng.random() < .25:
                self.blinks.append(t + .38)
            t += rng.uniform(2.5, 5.5)

    def gaze_at(self, t):
        prev = self.gaze[0]
        for k, g in enumerate(self.gaze):
            if g[0] > t:
                break
            prev = g
            nxt_i = k
        else:
            nxt_i = len(self.gaze) - 1
        # saccade of 0.14 s from the previous target
        i = self.gaze.index(prev)
        before = self.gaze[i - 1] if i else prev
        s = _sstep((t - prev[0]) / .14)
        return before[1] + (prev[1] - before[1]) * s, before[2] + (prev[2] - before[2]) * s

    def blink_at(self, t):
        b = 0.0
        for bt in self.blinks:
            d = t - bt
            if 0 <= d < .26:   # close fast, open a little slower
                b = max(b, _sstep(d / .09) if d < .09 else 1 - _sstep((d - .11) / .15) if d > .11 else 1.0)
        return b

    def apply(self, cov, t):
        out = cov.copy()
        gx, gy = self.gaze_at(t)
        b = self.blink_at(t)
        for e in self.eyes:
            dx, dy = gx * e["a"] * .42, gy * e["c"] * .38
            M = np.float32([[1, 0, dx], [0, 1, dy]])
            h, w = e["patch"].shape[:2]
            iris = cv2.warpAffine(e["patch"], M, (w, h), borderMode=cv2.BORDER_REFLECT)
            im = cv2.warpAffine(e["imask"], M, (w, h))[..., None] * e["opening"][..., None]
            op = e["opening"][..., None]
            eye = e["patch"] * (1 - op) + (e["sclera"] * (1 - im) + iris * im) * op + e["patch"] * 0  # inside: moved iris on clean sclera
            if b > 1e-3:
                # upper lid slides down: skin above the eye is pulled over the opening
                xx, yy = e["xx"], e["yy"]
                prof = np.sqrt(np.clip(1 - ((xx - e["cx"]) / (e["a"] * 1.08)) ** 2, 0, 1))
                yu = e["cy"] - e["c"] * prof
                yl = e["cy"] + e["c"] * prof * .95
                travel = b * (yl - yu) * 1.04
                L = yu + travel                                          # new lid line
                reach = e["c"] * 4.5
                w = np.where(yy >= yu, 1.0, _sstep((yy - (yu - reach)) / reach))
                f = np.where(yy < L, w, 0.0)
                srcy = (yy - travel * f - e["y0"]).astype(np.float32)
                srcx = (xx - e["x0"]).astype(np.float32)
                eye = cv2.remap(eye.astype(np.float32), srcx, srcy, cv2.INTER_LINEAR, borderMode=cv2.BORDER_REFLECT)
            out[e["y0"]:e["y1"], e["x0"]:e["x1"]] = np.clip(eye, 0, 255).astype(np.uint8)
        return out
