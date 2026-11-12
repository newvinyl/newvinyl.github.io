"""Mistwood reel (user request 12.11.26, Jake Muir – Pareidolia): a foggy forest cover comes alive.
The reel opens on the untouched cover; then the forest grows over the light side strip (obi), fog drifts playfully
through the trees, the trees sway like slow figures, stretch and grow, and the whole scene bends very gently
(a soft trip, nothing hasty). Scene and mood of the cover stay; nothing foreign is added – strip fill, fog colour
and sky extension all come from the cover itself.

    reel_mist(rel, aud, seed, out, poster, dur=45, info=None)
"""
import math
import numpy as np
import cv2
from PIL import Image, ImageDraw
import reelfx as R

W, H = R.W, R.H
COV_Y, S = 360, 1080                    # cover square inside the 9:16 frame
GW, GH = W // 4, H // 4                 # motion and fog are computed on a coarse grid


def _ss(x):
    x = np.clip(x, 0, 1)
    return x * x * (3 - 2 * x)


def _fbm(n, beta, rng):
    """tileable 1/f noise, 0..1"""
    f = np.hypot(*np.meshgrid(np.fft.fftfreq(n), np.fft.fftfreq(n)))
    f[0, 0] = 1
    spec = (rng.normal(size=(n, n)) + 1j * rng.normal(size=(n, n))) / f ** beta
    spec[0, 0] = 0
    x = np.fft.ifft2(spec).real
    lo, hi = np.percentile(x, [1, 99])
    return np.clip((x - lo) / (hi - lo), 0, 1).astype(np.float32)


def _samp(tex, u, v):
    n = tex.shape[0]
    return cv2.remap(tex, np.mod(u, n).astype(np.float32), np.mod(v, n).astype(np.float32), cv2.INTER_LINEAR, borderMode=cv2.BORDER_WRAP)


def strip_width(cov):
    """width of a light side strip on the left (obi with artist/title), 0 if there is none"""
    g = cov.astype(np.float32).mean(2)
    band = g[int(S * .86):int(S * .99)]                    # down here the photo is dark, the strip is not
    col = cv2.GaussianBlur(band.mean(0)[None], (0, 0), 3)[0]
    ref = np.median(col[S // 2:])
    if col[:20].mean() < ref + 60:
        return 0
    w = int(np.argmax(col < (col[:20].mean() + ref) / 2))
    return w if 30 < w < S * .35 else 0


def fill_strip(cov, s, rng):
    """the forest continues over the strip: the neighbouring forest, mirrored at the seam, stretched and shifted
    (continuous at the seam, no visible symmetry further out)"""
    if not s:
        return cov.copy()
    m = 10                                                  # blurry edge of the strip
    s2 = s + m
    src = cov[:, s2:s2 + int(s2 * 1.35)].astype(np.float32)
    patch = cv2.resize(src, (s2, S), interpolation=cv2.INTER_CUBIC)[:, ::-1]
    n = _fbm(256, 2.2, rng)
    yy, xx = np.mgrid[0:S, 0:s2].astype(np.float32)
    far = 1 - xx / s2                                       # 0 at the seam, 1 at the outer edge
    dy = 70 * far * (cv2.resize(n, (s2, S))[:, :] - .5) * 2
    dx = 26 * far * (cv2.resize(n.T.copy(), (s2, S)) - .5) * 2
    patch = cv2.remap(patch, np.clip(xx + dx, 0, s2 - 1), yy + dy, cv2.INTER_LINEAR, borderMode=cv2.BORDER_REPLICATE)
    # keep the cover's own vertical light (fog above, dark below)
    rows = cv2.GaussianBlur(cov[:, s2:s2 + 3 * s2].astype(np.float32).mean((1, 2))[:, None], (0, 0), 25)[:, 0]
    prow = cv2.GaussianBlur(patch.mean((1, 2))[:, None], (0, 0), 25)[:, 0]
    patch = patch + (rows - prow)[:, None, None] * (.6 * far[..., None])
    out = cov.astype(np.float32).copy()
    out[:, :s2] = patch
    return np.clip(out, 0, 255)


def canvas(sq):
    """9:16 scene: fog above the cover continues upwards, the dark ground continues downwards"""
    sq = sq.astype(np.float32)
    c = np.empty((H, W, 3), np.float32)
    c[COV_Y:COV_Y + S] = sq
    top = cv2.GaussianBlur(sq[:14].mean(0)[None], (0, 0), 60)[0]
    slope = float(np.clip((sq[:10].mean() - sq[110:130].mean()) / 115, -.05, .12))       # fog keeps getting lighter
    for y in range(COV_Y):
        c[y] = np.clip(top + slope * (COV_Y - y) * .45, 0, 255)
    bot = cv2.GaussianBlur(sq[-14:].mean(0)[None], (0, 0), 60)[0]
    c[COV_Y + S:] = bot
    for y0 in (COV_Y, COV_Y + S):                           # soften both seams
        a, b = y0 - 40, y0 + 40
        c[a:b] = cv2.GaussianBlur(c[a - 30:b + 30], (0, 0), 9)[30:-30] * .7 + c[a:b] * .3
    return c


def text_layer(info):
    L = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(L)
    X, y = 64, COV_Y + S - 30
    soft, mute = (232, 232, 228, 255), (150, 152, 152, 255)
    f = R.fit_font(R.FD, 70, info["artist"], 860)
    d.text((X, y + f.size), info["artist"], font=f, fill=soft, anchor="ls"); y += f.size + 14
    f = R.fit_font(R.FDR, 52, info["title"], 860)
    d.text((X, y + f.size), info["title"], font=f, fill=soft, anchor="ls"); y += f.size + 26
    if info.get("meta"):
        f = R.fit_font(R.FDR, 28, info["meta"], 860)
        d.text((X, y + f.size), info["meta"], font=f, fill=mute, anchor="ls"); y += f.size + 12
    f = R.F(R.FD, 28)
    d.text((X, y + f.size), info["avail"], font=f, fill=R.YEL + (255,), anchor="ls")
    d.text((R.TXT_R, y + f.size), "monthlyvinyl.net", font=f, fill=R.YEL + (255,), anchor="rs")
    return np.asarray(L)


def reel_mist(rel, aud, seed, out, poster, dur=45, info=None):
    rng = np.random.default_rng(seed + 1211)
    nfr = int(dur * R.FPS)
    aud = aud[:int(dur * R.SR)]
    lev, _ = R.analyse(aud, nfr)
    k = np.ones(R.FPS * 2) / (R.FPS * 2)
    lev = np.convolve(np.pad(lev, (len(k), len(k)), mode="edge"), k, "same")[len(k):-len(k)]      # slow breath of the music
    _, cov = R.prep_cover(rel["cover"])
    s = strip_width(cov)
    orig, full = canvas(cov), canvas(fill_strip(cov, s, rng))
    sw = s + 14
    R.log("Mistwood: strip", s, "px, dur", dur)
    info = info or {}
    info = {"artist": info.get("artist") or rel["a"], "title": info.get("title") or rel.get("t") or rel["track"],
            "meta": info.get("meta") or rel.get("label") or "", "avail": info.get("avail") or rel["shop"]}
    txl = text_layer(info)

    fogcol = orig[COV_Y + 4:COV_Y + 60].mean((0, 1)) * 1.06 + 6           # the cover's own fog
    yg = COV_Y + S * .80                                                   # where the trees stand
    gy, gx = np.mgrid[0:GH, 0:GW].astype(np.float32)
    X, Y = gx * 4 + 2, gy * 4 + 2
    hgt = np.clip((yg - Y) / (S * .55), 0, 1.5)                            # 0 at the ground, 1 around the tree tops
    n_a, n_b, n_c = _fbm(512, 2.4, rng), _fbm(512, 2.4, rng), _fbm(512, 1.7, rng)
    fog1, fog2 = _fbm(1024, 2.5, rng), _fbm(1024, 2.1, rng)
    ph = _samp(n_a, X * .55, X * 0 + 40) * 6.28 * 2.2                      # every tree its own phase (varies along x)
    ph2 = _samp(n_b, X * .8, Y * .15) * 6.28 * 1.6
    grow_x = .55 + .9 * _samp(n_b, X * .5, X * 0 + 300)                    # some trees grow more than others
    fog_prof = _ss((Y - 40) / 420) * (1 - _ss((Y - (yg + 20)) / 200))      # fog lives between sky and ground
    grain = [cv2.resize(rng.normal(0, 1, (H // 2, W // 2)).astype(np.float32), (W, H), interpolation=cv2.INTER_LINEAR) for _ in range(6)]
    FX, FY = np.meshgrid(np.arange(W, dtype=np.float32), np.arange(H, dtype=np.float32))
    thr = np.clip((sw - FX[:, :sw]) / max(1, sw), 0, 1)                    # strip: fog creeps in from the forest side
    rev_n = cv2.resize(_fbm(256, 2.6, rng), (sw, H))
    state = {"prev": None}

    def fr(f):
        t = f / R.FPS
        life = float(_ss((t - 1.2) / 6.0))                                 # opens on the still, untouched cover
        prog = t / dur
        trip = float(_ss((t - 6) / (dur * .75)))                           # the bending comes very slowly
        # ---------- scene: the forest takes over the strip
        if s and t < 12:
            p = (t - 1.6) / 7.0
            m = _ss((p * 2.1 - thr - .5 * (rev_n - .5)) / .6)[..., None]
            base = full.copy()
            base[:, :sw] = orig[:, :sw] * (1 - m) + full[:, :sw] * m
        else:
            base = full
        # ---------- motion (inverse map on the coarse grid)
        z = 1 + .012 * life * math.sin(6.28 * t / 15)
        sx = W / 2 + (X - W / 2) / z
        sy = yg + (Y - yg) / z
        g = 1 + life * (.03 * math.sin(6.28 * t / 19) + .20 * _ss(np.float32(prog * 1.15)) * grow_x
                        + .035 * trip * np.sin(6.28 * t / 13 + ph2))       # trees stretch and grow, breathing
        sy = np.where(sy < yg, yg - (yg - sy) / g, sy)
        h = np.clip((yg - sy) / (S * .55), 0, 1.5)
        sway = (11 * h ** 1.3 * np.sin(6.28 * t / 11 + ph)                 # the body leans …
                + 7 * h ** 3 * np.sin(6.28 * t / 11 + ph - 1.1)            # … the head follows a little later
                + 5 * h * np.sin(6.28 * t / 23 + ph2))
        sx = sx - life * sway * (1 + .5 * trip)
        wa = life * (3 + 20 * trip)
        sx = sx + wa * (_samp(n_a, X * .22 + t * 5, Y * .22 + t * 2.5) - .5) * 2 * (.4 + .6 * np.minimum(h + .3, 1))
        sy = sy + wa * .7 * (_samp(n_b, X * .22 - t * 3.5, Y * .22 + t * 4) - .5) * 2 * (.4 + .6 * np.minimum(h + .3, 1))
        mx = cv2.resize(sx, (W, H), interpolation=cv2.INTER_CUBIC)
        my = cv2.resize(sy, (W, H), interpolation=cv2.INTER_CUBIC)
        img = cv2.remap(base, mx, my, cv2.INTER_LINEAR, borderMode=cv2.BORDER_REPLICATE)
        # ---------- fog: two veils drifting at different speeds, curling playfully
        cu = (_samp(n_a, X * .3 + t * 4, Y * .3 - t * 2) - .5) * 190
        cv_ = (_samp(n_b, X * .3 - t * 3, Y * .3 + t * 3) - .5) * 150
        v1 = _samp(fog1, X * .30 + cu - t * 15, Y * .62 + cv_ + 30 * math.sin(t / 7))
        v2 = _samp(fog2, X * .5 - cu * .6 + t * 8 + 500, Y * 1.0 + cv_ * .7 - t * 3)
        den = _ss((v1 - .40) / .55) * .42 + _ss((v2 - .45) / .5) * .26
        den = den * fog_prof * (.25 + .75 * life) * (.85 + .3 * float(lev[f]))
        den = np.clip(den, 0, .6)
        # a breath of colour in the fog, hardly there
        hue = 6.28 * (t / 31) + (_samp(n_c, X * .25 + t * 3, Y * .25) - .5) * 5
        tint = np.stack([np.sin(hue), np.sin(hue + 2.1), np.sin(hue + 4.2)], -1) * (7 * trip)
        a = cv2.resize(den, (W, H), interpolation=cv2.INTER_LINEAR)[..., None]
        fc = fogcol + cv2.resize(tint.astype(np.float32), (W, H), interpolation=cv2.INTER_LINEAR)
        img = img * (1 - a) + fc * a
        # ---------- soft trails once the trip is there
        if state["prev"] is not None and trip > 0:
            w = .22 * trip
            img = img * (1 - w) + state["prev"] * w
        state["prev"] = img
        o = img + grain[f % len(grain)][..., None] * 3.2
        o = np.clip(o, 0, 255).astype(np.uint8)
        o = R.blend_layer(o, txl, float(_ss((t - 2.5) / 2.5)))
        return R.fades(o, t, dur, fin=.6, fout=2.0)

    R.encode(fr, nfr, aud, out, poster, int(14 * R.FPS))
    return "mistwood · strip %d px" % s
