"""More ways for the cover to change in the second half of a reel (besides melting):
freeze, pixelate, shatter, flow, particles (dissolve into dust), coexist, adapt, symbiosis, one.

Each function gets (fx, cov, bg, t, e, kick, frame): fx is the CoverFX object (seed, rng state, caches),
cov/bg are the 1080x1080 uint8 cover and the background behind it, e the strength 0..1+ (slow start).
"""
import math
import numpy as np, cv2

S = 1080
L = 270                                         # helper fields are computed at 270 and scaled
_Y, _X = np.mgrid[0:S, 0:S].astype(np.float32)
_ly, _lx = np.mgrid[0:L, 0:L].astype(np.float32)
_u = _X / (S - 1); _v = _Y / (S - 1)
EDGE = np.minimum(np.minimum(_u, 1 - _u), np.minimum(_v, 1 - _v)) * 2


def sstep(x):
    x = np.clip(x, 0, 1)
    return x * x * (3 - 2 * x)


def up(a, interp=cv2.INTER_LINEAR):
    return cv2.resize(a, (S, S), interpolation=interp)


def voronoi(rng, n, size=L):
    pts = rng.uniform(0, size, (n, 2)).astype(np.float32)
    yy, xx = np.mgrid[0:size, 0:size].astype(np.float32)
    d = (xx[..., None] - pts[:, 0]) ** 2 + (yy[..., None] - pts[:, 1]) ** 2
    lab = d.argmin(2).astype(np.int32)
    ds = np.sort(d, 2)
    border = np.sqrt(ds[..., 1]) - np.sqrt(ds[..., 0])        # distance to the nearest cell edge
    return pts, lab, border


def _noise(fx, t, sc, ox, oy):
    return fx.noise(t, sc, ox, oy)


# ---------------------------------------------------------------- freeze: frost crystals grow in from the edges
def freeze(fx, cov, bg, t, e, kick, frame):
    if not hasattr(fx, "_fz"):
        rng = np.random.default_rng(fx.seed + 11)
        pts, lab, border = voronoi(rng, 140)
        fx._fz = (up(lab.astype(np.float32), cv2.INTER_NEAREST).astype(np.int32), up(border),
                  rng.uniform(0, 1, len(pts)).astype(np.float32))
    lab, border, rnd = fx._fz
    n = _noise(fx, 0.0, 1.3, 0, 0)
    front = (1 - EDGE) * .7 + n * .5 + rnd[lab] * .25        # where the ice arrives first
    m = sstep((e * 1.5 - (1.2 - front)) * 4)[..., None]
    c = cov.astype(np.float32)
    # faceted: each crystal takes the mean colour of the cover underneath
    small = cv2.resize(cov, (L, L), interpolation=cv2.INTER_AREA).astype(np.float32)
    sums = np.zeros((len(rnd), 3), np.float32); cnt = np.zeros(len(rnd), np.float32)
    lab_s = cv2.resize(lab.astype(np.float32), (L, L), interpolation=cv2.INTER_NEAREST).astype(np.int32)
    np.add.at(sums, lab_s.ravel(), small.reshape(-1, 3)); np.add.at(cnt, lab_s.ravel(), 1)
    mean = sums / np.maximum(cnt, 1)[:, None]
    facet = mean[lab] * .55 + c * .45
    g = facet.mean(2, keepdims=True)
    ice = (g * .55 + facet * .2 + _bright(cov) * .35)                           # pale: the cover's own lightest colour
    ice = ice + (rnd[lab][..., None] - .5) * 30                                 # facets catch the light differently
    edge = np.exp(-border / 1.6)[..., None]
    ice = ice * (1 - edge * .6) + _bright(cov) * edge * .6                      # crystal edges in that light colour
    sp = (np.sin(rnd[lab] * 60 + t * 3) > .985)[..., None] * np.exp(-border / 3)[..., None] * _bright(cov) * .8
    out = c * (1 - m) + (ice + sp) * m
    return np.clip(out, 0, 255).astype(np.uint8)


# ---------------------------------------------------------------- pixelate: the image breaks into growing blocks
def pixelate(fx, cov, bg, t, e, kick, frame):
    n = _noise(fx, t, .8, .01, -.008)
    big = 6 + e * 110 * (1 + .25 * kick)
    out = cov.astype(np.float32)
    w = sstep(e * 1.6 - (1 - EDGE) * .2 - n * .5)[..., None]               # some areas go first
    s = max(2, int(big))
    small = cv2.resize(cov, (max(2, S // s), max(2, S // s)), interpolation=cv2.INTER_AREA)
    blocks = up(small, cv2.INTER_NEAREST).astype(np.float32)
    if e > .5:                                                             # blocks pick up background colours
        bsm = up(cv2.resize(bg, small.shape[1::-1], interpolation=cv2.INTER_AREA), cv2.INTER_NEAREST).astype(np.float32)
        k = min(1.0, (e - .5) * 1.2)
        chk = ((np.floor(_X / s) + np.floor(_Y / s)) % 2)[..., None]
        blocks = blocks * (1 - k * chk * .7) + bsm * k * chk * .7
    grid = (((_X % s) < 1.5) | ((_Y % s) < 1.5))[..., None] * min(1.0, e * 2) * .35
    blocks = blocks * (1 - grid)
    return np.clip(out * (1 - w) + blocks * w, 0, 255).astype(np.uint8)


# ---------------------------------------------------------------- shatter: cracks, then shards drift apart
def shatter(fx, cov, bg, t, e, kick, frame):
    if not hasattr(fx, "_sh"):
        rng = np.random.default_rng(fx.seed + 23)
        n = int(rng.integers(18, 34))
        pts, lab, border = voronoi(rng, n)
        c = pts * (S / L)
        ctr = np.array([S / 2, S / 2], np.float32)
        out = (c - ctr) / (np.linalg.norm(c - ctr, axis=1, keepdims=True) + 1)
        fx._sh = (up(lab.astype(np.float32), cv2.INTER_NEAREST).astype(np.int32), up(border), c,
                  out * rng.uniform(.6, 1.4, (n, 1)), rng.uniform(-1, 1, n) * .35, rng.uniform(.4, 1, n))
    lab, border, c, dirv, rot, delay = fx._sh
    k = np.clip(e * 1.3 - (1 - delay) * .5, 0, None) ** 1.5                 # shards leave one after another
    off = dirv * (k[:, None] * 340)
    ang = rot * k
    l = lab
    cx, cy = c[l, 0], c[l, 1]
    px, py = _X - cx - off[l, 0], _Y - cy - off[l, 1]
    ca, sa = np.cos(-ang[l]), np.sin(-ang[l])
    sx = (px * ca - py * sa + cx).astype(np.float32); sy = (px * sa + py * ca + cy).astype(np.float32)
    src = cv2.remap(cov, sx, sy, cv2.INTER_LINEAR, borderMode=cv2.BORDER_CONSTANT, borderValue=(0, 0, 0)).astype(np.float32)
    labsrc = cv2.remap(lab.astype(np.float32), sx, sy, cv2.INTER_NEAREST, borderMode=cv2.BORDER_CONSTANT, borderValue=-1)
    inside = (labsrc == l) & (sx >= 0) & (sy >= 0) & (sx < S) & (sy < S)
    crack = np.exp(-border / 1.2) * min(1.0, e * 4)                        # thin bright cracks first
    src = src * (1 - crack[..., None] * .7) + 255 * crack[..., None] * .7 * (k[l] < .05)[..., None]
    shade = 1 - .25 * np.abs(np.sin(ang[l]))[..., None]                     # tilted shards get darker
    m = inside[..., None].astype(np.float32)
    out = src * shade * m + bg.astype(np.float32) * (1 - m)
    return np.clip(out, 0, 255).astype(np.uint8)


# ---------------------------------------------------------------- flow: wet paint running down
def flow(fx, cov, bg, t, e, kick, frame):
    if not hasattr(fx, "_fl"):
        rng = np.random.default_rng(fx.seed + 31)
        cols = cv2.GaussianBlur(rng.random((1, 90)).astype(np.float32), (0, 0), 1.2)
        fx._fl = up(np.repeat(cols, 4, 0), cv2.INTER_CUBIC)
    speed = fx._fl
    lum = cv2.cvtColor(cov, cv2.COLOR_RGB2GRAY).astype(np.float32) / 255
    drop = e ** 1.4 * (speed * 420 + 30) * (.6 + .6 * cv2.GaussianBlur(lum, (0, 0), 9))
    acc = np.zeros(cov.shape, np.float32)
    for k in range(5):                                                       # smear along the run
        sy = np.clip(_Y - drop * (k / 4), 0, S - 1).astype(np.float32)
        acc += cv2.remap(cov, _X, sy, cv2.INTER_LINEAR).astype(np.float32)
    out = acc / 5
    wet = sstep(e * 2)[..., None] * .18
    hl = np.clip(cv2.Sobel(out.mean(2), cv2.CV_32F, 0, 1, ksize=5) / 2000, 0, 1)[..., None] * 255 * wet
    bottom = sstep((_Y / S - (1 - e * .25)) * 6)[..., None]                   # paint pools into the background
    out = (out + hl) * (1 - bottom * .6) + bg.astype(np.float32) * bottom * .6
    return np.clip(out, 0, 255).astype(np.uint8)


# ---------------------------------------------------------------- particles: dissolve into dust that drifts away
def particles(fx, cov, bg, t, e, kick, frame):
    if not hasattr(fx, "_pt"):
        rng = np.random.default_rng(fx.seed + 41)
        n = 9000
        p = rng.uniform(0, S, (n, 2)).astype(np.float32)
        th = _noise(fx, 0.0, 1.1, 0, 0)
        when = th[p[:, 1].astype(int), p[:, 0].astype(int)] * .7 + rng.uniform(0, .3, n)
        v = np.stack([rng.normal(.2, .5, n), rng.uniform(-1.6, -.5, n)], 1).astype(np.float32)
        fx._pt = (p, when, v, rng.integers(3, 8, n), th)
    p, when, v, size, th = fx._pt
    gone = sstep((e * 1.25 - th) * 6)[..., None]                             # dust front sweeps over the cover
    out = cov.astype(np.float32) * (1 - gone) + bg.astype(np.float32) * gone
    rel = np.clip(e * 1.25 - when, 0, None)
    act = rel > 0
    if act.any():
        col = cov[p[act, 1].astype(int), p[act, 0].astype(int)].astype(np.float32)
        age = rel[act] * 9
        pos = p[act] + v[act] * (age[:, None] * 120) + np.stack([np.sin(age * 2 + p[act, 0]) * 14, np.zeros(act.sum())], 1)
        a = np.clip(1 - age / 6, 0, 1)
        sz = size[act]
        for s in np.unique(sz):
            sel = sz == s
            xs = pos[sel, 0].astype(int); ys = pos[sel, 1].astype(int)
            ok = (xs >= 0) & (ys >= 0) & (xs < S - s) & (ys < S - s)
            for dy in range(s):
                for dx in range(s):
                    yy, xx = ys[ok] + dy, xs[ok] + dx
                    al = a[sel][ok][:, None]
                    out[yy, xx] = out[yy, xx] * (1 - al) + col[sel][ok] * al
    return np.clip(out, 0, 255).astype(np.uint8)


# ---------------------------------------------------------------- coexist: both stay themselves and share the light
def coexist(fx, cov, bg, t, e, kick, frame):
    c = cov.astype(np.float32)
    b = cv2.resize(cv2.GaussianBlur(bg, (0, 0), 30), (S, S)).astype(np.float32)
    rim = sstep(1 - EDGE / .12)[..., None]                                    # the background's light on the edges
    breathe = .5 + .5 * math.sin(t * .9)
    light = b / (b.mean() + 1e-3)
    c = c * (1 - .18 * e) + c * light * .18 * e
    c = c * (1 - rim * e * (.35 + .2 * breathe)) + b * rim * e * (.35 + .2 * breathe)
    return np.clip(c, 0, 255).astype(np.uint8)


# ---------------------------------------------------------------- adapt: cover and background grow alike in colour
def adapt(fx, cov, bg, t, e, kick, frame):
    c = cov.astype(np.float32)
    lab_c = cv2.cvtColor(cov, cv2.COLOR_RGB2LAB).astype(np.float32)
    lab_b = cv2.cvtColor(bg, cv2.COLOR_RGB2LAB).astype(np.float32)
    mc, sc = lab_c.reshape(-1, 3).mean(0), lab_c.reshape(-1, 3).std(0) + 1e-3
    mb, sb = lab_b.reshape(-1, 3).mean(0), lab_b.reshape(-1, 3).std(0) + 1e-3
    k = min(1.0, e) * .85
    tgt_m, tgt_s = mc * (1 - k) + mb * k, sc * (1 - k) + sb * k
    out = (lab_c - mc) / sc * tgt_s + tgt_m
    out = cv2.cvtColor(np.clip(out, 0, 255).astype(np.uint8), cv2.COLOR_LAB2RGB).astype(np.float32)
    rim = sstep(1 - EDGE / (.04 + .1 * e))[..., None]
    out = out * (1 - rim * .5 * e) + bg.astype(np.float32) * rim * .5 * e
    return np.clip(out, 0, 255).astype(np.uint8)


# ---------------------------------------------------------------- symbiosis: tendrils of the background grow into the cover
def symbiosis(fx, cov, bg, t, e, kick, frame):
    n1 = _noise(fx, t * .2, 1.6, .006, 0)
    n2 = _noise(fx, t * .2 + 9, 3.2, 0, .006)
    ridge = 1 - np.abs(n1 * .7 + n2 * .3 - .5) * 2                          # vein-like lines
    reach = sstep((e * 1.5 - EDGE * .9 - n2 * .3) * 3)                      # how far the growth has come in
    thr = .955 - .14 * min(1.0, e)                                          # veins get thicker over time
    m = (sstep((ridge - thr) * 14) * reach)[..., None]
    c = cov.astype(np.float32); b = bg.astype(np.float32)
    veins = b * .75 + c * .25
    glow = (sstep((ridge - thr + .06) * 8) * reach)[..., None] * .25        # soft halo around the veins
    out = c * (1 - glow) + (c * .5 + b * .5) * glow
    out = out * (1 - m) + veins * m
    return np.clip(out, 0, 255).astype(np.uint8)


# ---------------------------------------------------------------- one: cover and background become a single image
def one(fx, cov, bg, t, e, kick, frame):
    k = sstep(min(1.0, e) * 1.05)
    sig = 1 + 22 * k
    c = cv2.GaussianBlur(cov, (0, 0), sig).astype(np.float32) if sig > 1.3 else cov.astype(np.float32)
    n = _noise(fx, t, 1.0, .01, -.01)
    a = sstep((k * 1.3 - n * .3 - EDGE * .2) * 2)[..., None]
    detail = cov.astype(np.float32) - cv2.GaussianBlur(cov, (0, 0), 6).astype(np.float32)
    b = bg.astype(np.float32) + detail * (1 - k) * .6                         # the cover's fine structure lives on in the background
    out = c * (1 - a) + b * a
    return np.clip(out, 0, 255).astype(np.uint8)


FX = {"freeze": freeze, "pixelate": pixelate, "shatter": shatter, "flow": flow, "particles": particles,
      "coexist": coexist, "adapt": adapt, "symbiosis": symbiosis, "one": one}
EMAX = {"freeze": (.85, 1.1), "pixelate": (.7, 1.0), "shatter": (.75, 1.05), "flow": (.7, 1.0), "particles": (.85, 1.1),
        "coexist": (.7, 1.0), "adapt": (.8, 1.0), "symbiosis": (.8, 1.1), "one": (.9, 1.05)}


# ---------------------------------------------------------------- dive: camera flies into the cover, and inside it finds the cover again
# Only the cover's own pixels are used: no new elements.
def _bright(cov):
    px = cv2.resize(cov, (64, 64)).reshape(-1, 3).astype(np.float32)
    return px[np.argsort(px.sum(1))[-40:]].mean(0)


def dive(fx, cov, bg, t, e, kick, frame):
    if not hasattr(fx, "_dv"):
        gray = cv2.cvtColor(cov, cv2.COLOR_RGB2GRAY).astype(np.float32)
        det = cv2.GaussianBlur(np.abs(cv2.Laplacian(gray, cv2.CV_32F)), (0, 0), 40)
        det[:220] = det[-220:] = 0; det[:, :220] = 0; det[:, -220:] = 0
        y0, x0 = np.unravel_index(np.argmax(det), det.shape)                   # dive into the most detailed spot ...
        try:                                                                     # ... or into an eye, if the cover has one
            g8 = cv2.equalizeHist(cv2.resize(cv2.cvtColor(cov, cv2.COLOR_RGB2GRAY), (540, 540)))
            eyes = cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_eye.xml").detectMultiScale(g8, 1.1, 8, minSize=(18, 18))
            eyes = [e_ for e_ in eyes if 110 < e_[0] * 2 + e_[2] < S - 110 and 110 < e_[1] * 2 + e_[3] < S - 110]
            if len(eyes):
                ex, ey, ew, eh = max(eyes, key=lambda r: r[2] * r[3])
                x0, y0 = ex * 2 + ew, ey * 2 + eh
        except Exception:
            pass
        fx._dv = np.array([x0, y0], np.float32)
    p = fx._dv
    levels = 2.6                                                                 # how many times we pass through the cover
    s = max(0.0, e) * levels
    f = s - int(s)
    Z = 16 ** f * (1 + .008 * kick)
    # zoom about the detail spot; the next copy of the cover sits there, anchored at the same spot,
    # so at Z = 16 it has become the whole picture and the dive continues seamlessly
    M = np.float32([[Z, 0, p[0] * (1 - Z)], [0, Z, p[1] * (1 - Z)]])
    out = cv2.warpAffine(cov, M, (S, S), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_REFLECT).astype(np.float32)
    z2 = Z / 16
    M2 = np.float32([[z2, 0, p[0] * (1 - z2)], [0, z2, p[1] * (1 - z2)]])
    inner = cv2.warpAffine(cov, M2, (S, S), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_CONSTANT).astype(np.float32)
    x0, y0 = p[0] * (1 - z2), p[1] * (1 - z2)                                   # where the inner copy lies
    x1, y1 = x0 + z2 * S, y0 + z2 * S
    fe = max(2.0, z2 * S * .06)
    m = (sstep((_X - x0) / fe) * sstep((x1 - _X) / fe) * sstep((_Y - y0) / fe) * sstep((y1 - _Y) / fe))[..., None]
    a = m * (sstep(f * 4) if s < 1 else 1.0)                                     # the first copy fades in gently
    out = out * (1 - a) + inner * a
    if f > .03 and s > .2:                                                       # speed: soft radial blur towards the spot
        sm = cv2.warpAffine(out, np.float32([[1.035, 0, -p[0] * .035], [0, 1.035, -p[1] * .035]]), (S, S), borderMode=cv2.BORDER_REFLECT)
        out = out * .72 + sm * .28
    return np.clip(out, 0, 255).astype(np.uint8)


# ---------------------------------------------------------------- descend: from the surface down into the layers below
# The layers underneath are made of the cover itself: mirrored, stretched, darker the deeper we go.
def _strip(cov, rng):
    s = 540
    top = cv2.resize(cov, (s, s)).astype(np.float32)
    flip = top[::-1]
    stretch = cv2.resize(top[s // 2:], (s, s))[::-1]                            # the lower half pulled down like strata
    deep = cv2.resize(top[s - s // 6:], (s, s))                                 # the last strip of the cover, stretched far
    layers = [top, flip * .8, stretch * .6, deep * .42]
    img = np.concatenate(layers, 0)
    for k in range(1, len(layers)):                                            # soft seams between the layers
        y = k * s
        img[y - 30:y + 30] = cv2.GaussianBlur(img[y - 30:y + 30], (0, 0), 6)
    return np.clip(img, 0, 255).astype(np.uint8)


def descend(fx, cov, bg, t, e, kick, frame):
    if not hasattr(fx, "_ds"):
        fx._ds = _strip(cov, np.random.default_rng(fx.seed + 61))
    st = fx._ds
    s = st.shape[1]
    k = sstep(min(1.0, e))
    off = k * (st.shape[0] - s)
    win = cv2.resize(st[int(off):int(off) + s].astype(np.float32), (S, S))
    depth = off / (st.shape[0] - s)
    if depth > .5:                                                              # the deep layers shimmer slightly
        a = (depth - .5) * 10
        dx = (np.sin(_Y / 29 + t * 6) * a).astype(np.float32)
        win = cv2.remap(win, _X + dx, _Y, cv2.INTER_LINEAR, borderMode=cv2.BORDER_REFLECT)
    return np.clip(win, 0, 255).astype(np.uint8)


FX.update({"dive": dive, "descend": descend})
EMAX.update({"dive": (1.0, 1.0), "descend": (1.0, 1.0)})
