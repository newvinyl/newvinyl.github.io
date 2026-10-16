"""Crowd reel: the people on a cover photo come alive. First everyone holds still and leans in towards the
camera, then they start to bob, sway, dance and shake to the beat; the mood builds over the whole minute.
Only the cover's own pixels are moved; nothing is added.

Dancer spec (cover coordinates 0..1): {"x": .., "y": .., "r": radius, "k": 1.0 strength, "z": 1 front / 0 back}
"""
import math
import numpy as np
import cv2
import reelfx as R

HS = R.COV_S // 2          # displacement field is computed at half resolution


def _ss(x):
    x = np.clip(x, 0, 1)
    return x * x * (3 - 2 * x)


def tempo(kick, fps):
    """beats per second from the kick envelope (autocorrelation, 100–150 bpm)"""
    k = kick - kick.mean()
    best, bl = -1, int(fps * 60 / 125)
    for lag in range(int(fps * 60 / 150), int(fps * 60 / 100) + 1):
        c = (k[:-lag] * k[lag:]).mean()
        if c > best:
            best, bl = c, lag
    return fps / bl


class Crowd:
    def __init__(self, cov, dancers, seed, dur, kick, fps, grid=None):
        rng = np.random.default_rng(seed + 313)
        S = cov.shape[0]
        self.S, self.dur = S, dur
        self.bps = tempo(kick, fps)
        # beat phase: integrate so the dance locks to the music
        self.phase = np.cumsum(np.full(len(kick), self.bps / fps))
        ds = []
        for d in dancers:
            ds.append(dict(x=d["x"] * S, y=d["y"] * S, r=d["r"] * S, k=d.get("k", 1.0), z=d.get("z", 1),
                           ph=rng.uniform(0, 6.3), sway=rng.uniform(.5, 1.3), bob=rng.uniform(.6, 1.2),
                           nod=rng.uniform(-1, 1), tilt=rng.uniform(.4, 1.0), half=int(rng.integers(2)),
                           shake=rng.uniform(0, 1), onset=rng.uniform(0, 1)))
        # dense crowd areas: a jittered grid of small dancers
        for g in grid or []:
            nx, ny = g.get("nx", 8), g.get("ny", 3)
            for j in range(ny):
                for i in range(nx):
                    x = g["x0"] + (g["x1"] - g["x0"]) * (i + .5 + rng.uniform(-.3, .3)) / nx
                    y = g["y0"] + (g["y1"] - g["y0"]) * (j + .5 + rng.uniform(-.3, .3)) / ny
                    ds.append(dict(x=x * S, y=y * S, r=g["r"] * S, k=g.get("k", .7), z=g.get("z", 0),
                                   ph=rng.uniform(0, 6.3), sway=rng.uniform(.4, 1.2), bob=rng.uniform(.5, 1.2),
                                   nod=rng.uniform(-1, 1), tilt=rng.uniform(.3, .9), half=int(rng.integers(2)),
                                   shake=rng.uniform(0, 1), onset=rng.uniform(0, 1)))
        self.d = ds
        yy, xx = np.mgrid[0:HS, 0:HS].astype(np.float32) * 2
        self.X, self.Y = xx, yy
        # per dancer: gaussian weight (head + body below it), precomputed at half res
        for d in ds:
            dx = (xx - d["x"]) / d["r"]
            dy = (yy - d["y"]) / d["r"]
            body = np.where(dy > 0, dy * .45, dy)                 # the body below the head moves along, softer
            w = np.exp(-(dx * dx + body * body) * 1.6)
            w[w < .02] = 0
            ys, xs = np.where(w > 0)
            if len(ys) == 0:
                d["box"] = None
                continue
            y0, y1, x0, x1 = ys.min(), ys.max() + 1, xs.min(), xs.max() + 1
            d["box"] = (y0, y1, x0, x1)
            d["w"] = w[y0:y1, x0:x1] * d["k"]
            d["rx"] = (xx[y0:y1, x0:x1] - d["x"]) / d["r"]
            d["ry"] = (yy[y0:y1, x0:x1] - d["y"]) / d["r"]

    # ---------------------------------------------------------------- mood over the minute
    def energy(self, t):
        """0 = frozen, 1 = full party"""
        a = _ss((t - 9) / 14) * .45          # 9–23 s: first gentle bobbing
        b = _ss((t - 23) / 18) * .4          # 23–41 s: dancing
        c = _ss((t - 41) / 12) * .15         # 41–53 s: everybody shakes
        return a + b + c

    def lean(self, t):
        """0–9 s: everyone slowly leans in towards the camera (faces grow a little, heads lift)"""
        return _ss((t - 1.0) / 7.0)

    def field(self, f, t, kick):
        X, Y = self.X, self.Y
        DX = np.zeros_like(X); DY = np.zeros_like(Y)
        e = self.energy(t)
        ln = self.lean(t)
        ph = self.phase[f] * 2 * math.pi
        for d in self.d:
            if d["box"] is None:
                continue
            y0, y1, x0, x1 = d["box"]
            w, rx, ry = d["w"], d["rx"], d["ry"]
            r = d["r"]
            # own energy: front people start earlier, everyone joins over time
            ei = e * _ss((e - d["onset"] * .35) / .3 + .5) * (1.15 if d["z"] else .85)
            p = ph * (.5 if d["half"] else 1.0) + d["ph"]
            bob = -abs(math.sin(p)) * r * .16 * d["bob"] * ei           # up on the beat
            bob -= kick * r * .06 * ei                                    # kick punch
            sway = math.sin(p * .5 + d["ph"]) * r * .14 * d["sway"] * ei
            tilt = math.sin(p * .5 + d["ph"] * 2) * .09 * d["tilt"] * ei  # head tilts side to side
            shake = 0.0
            if ei > .55 and d["shake"] > .35:
                sh = (ei - .55) / .45
                shake = math.sin(t * 31 + d["ph"] * 7) * r * .035 * sh * d["shake"]
            # lean in: the head grows slightly and lifts
            grow = ln * .045 * d["k"] * (1.3 if d["z"] else 1.0)
            lift = -ln * r * .05 * d["k"]
            ddx = sway + shake - rx * grow * r + (-ry) * tilt * r
            ddy = bob + lift - ry * grow * r + rx * tilt * r
            DX[y0:y1, x0:x1] += w * ddx
            DY[y0:y1, x0:x1] += w * ddy
        return DX, DY

    def apply(self, cov, f, t, kick):
        DX, DY = self.field(f, t, kick)
        DX = cv2.resize(cv2.GaussianBlur(DX, (0, 0), 3), (self.S, self.S), interpolation=cv2.INTER_LINEAR)
        DY = cv2.resize(cv2.GaussianBlur(DY, (0, 0), 3), (self.S, self.S), interpolation=cv2.INTER_LINEAR)
        yy, xx = np.mgrid[0:self.S, 0:self.S].astype(np.float32)
        # pull: a pixel at (x,y) shows the source at (x-dx, y-dy)
        return cv2.remap(cov, (xx - DX).astype(np.float32), (yy - DY).astype(np.float32), cv2.INTER_LINEAR, borderMode=cv2.BORDER_REFLECT)


def reel_crowd(rel, aud, seed, out, poster, dur=60, dancers=None, grid=None):
    nfr = int(dur * R.FPS)
    aud = aud[:int(dur * R.SR)]
    lev, kick = R.analyse(aud, nfr)
    _, cov = R.prep_cover(rel["cover"])
    corners = np.concatenate([cov[:20, :20].reshape(-1, 3), cov[:20, -20:].reshape(-1, 3), cov[-20:, :20].reshape(-1, 3), cov[-20:, -20:].reshape(-1, 3)])
    bg = np.median(corners, 0).astype(np.float32)
    crowd = Crowd(cov, dancers or [], seed, dur, kick, R.FPS, grid)
    txl = R.text_layer(rel, mono=R.YEL)
    base = np.empty((R.H, R.W, 3), np.float32)
    base[:] = bg
    R.log("Crowd reel: %d dancers, %.1f bpm" % (len(crowd.d), crowd.bps * 60))
    yy, xx = np.mgrid[0:R.COV_S, 0:R.COV_S].astype(np.float32)
    vig = 1 - .35 * np.clip((np.hypot(xx - R.COV_S / 2, yy - R.COV_S / 2) / (R.COV_S * .5) - .55) / .45, 0, 1)

    def fr(f):
        t = f / R.FPS
        img = base.copy()
        c = crowd.apply(cov, f, t, float(kick[f])).astype(np.float32)
        e = crowd.energy(t)
        # camera: slow push-in while they look at you, later a light handheld sway with the music
        z = 1 + .06 * crowd.lean(t) + .01 * e * math.sin(t * 1.3)
        ang = .25 * e * math.sin(crowd.phase[f] * math.pi + .7)
        cx = R.COV_S / 2 + 10 * e * math.sin(t * .9)
        M = cv2.getRotationMatrix2D((cx, R.COV_S * .55), ang, z)
        c = cv2.warpAffine(c, M, (R.COV_S, R.COV_S), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_REFLECT)
        # light: when the party starts, the room pulses softly with the kick and the edges darken a bit
        c = c * (1 + .10 * e * kick[f]) * (1 - .5 * e + .5 * e * vig)[..., None]
        img[R.COV_Y:R.COV_Y + R.COV_S] = c
        img = np.clip(img, 0, 255).astype(np.uint8)
        img = R.comp(img, txl)
        return R.fades(img, t, dur)

    R.encode(fr, nfr, aud, out, poster, int(1.2 * R.FPS))
    return "crowd · %d dancers · %.0f bpm" % (len(crowd.d), crowd.bps * 60)
