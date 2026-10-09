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
    ice = (g * .55 + facet * .2 + np.array([170, 205, 235], np.float32) * .35)   # cold, bluish white
    ice = ice + (rnd[lab][..., None] - .5) * 30                                 # facets catch the light differently
    edge = np.exp(-border / 1.6)[..., None]
    ice = ice * (1 - edge * .6) + 255 * edge * .6                               # white crystal edges
    sp = (np.sin(rnd[lab] * 60 + t * 3) > .985)[..., None] * np.exp(-border / 3)[..., None] * 255
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


# ---------------------------------------------------------------- dive: nano-camera into the structure, one level deeper each time
def _palette(cov, k=6):
    px = cv2.resize(cov, (64, 64)).reshape(-1, 3).astype(np.float32)
    _, lab, cen = cv2.kmeans(px, k, None, (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 20, .5), 2, cv2.KMEANS_PP_CENTERS)
    cnt = np.bincount(lab.ravel(), minlength=k)
    return cen[np.argsort(-cnt)]


def _level_cells(cov, rng, s=540):
    """microscope: cells with membranes and nuclei, coloured by the cover"""
    pts, lab, border = voronoi(rng, 260, s)
    blur = cv2.GaussianBlur(cv2.resize(cov, (s, s)), (0, 0), 6).astype(np.float32)
    col = blur[np.clip(pts[:, 1].astype(int), 0, s - 1), np.clip(pts[:, 0].astype(int), 0, s - 1)]
    yy, xx = np.mgrid[0:s, 0:s].astype(np.float32)
    d = np.hypot(xx - pts[lab, 0], yy - pts[lab, 1])
    img = col[lab] * (1.05 - np.clip(d / 40, 0, .45))[..., None]                 # cells bulge towards the centre
    nuc = sstep((9 - d) / 3)[..., None]
    img = img * (1 - nuc * .6) + (col[lab] * .35) * nuc * .6
    mem = np.exp(-border / 1.4)[..., None]
    img = img * (1 - mem * .8) + (255 - col[lab] * .3) * mem * .5
    return np.clip(img, 0, 255).astype(np.uint8)


def _level_atoms(cov, rng, s=540):
    """molecules / atoms: glowing spheres on a lattice with electron orbits"""
    pal = _palette(cov)
    dark = pal.min(0) * .25
    img = np.ones((s, s, 3), np.float32) * dark
    yy, xx = np.mgrid[0:s, 0:s].astype(np.float32)
    r0 = rng.uniform(26, 40)
    step = r0 * 2.6
    for j, y in enumerate(np.arange(-step, s + step, step * .87)):
        for x in np.arange(-step + (j % 2) * step / 2, s + step, step):
            c = pal[int(rng.integers(len(pal)))]
            cx, cy = x + rng.normal(0, 4), y + rng.normal(0, 4)
            d = np.hypot(xx - cx, yy - cy)
            core = sstep((r0 - d) / 3)[..., None]
            shade = np.clip(1.25 - np.hypot(xx - cx + r0 * .35, yy - cy + r0 * .35) / (r0 * 1.4), .25, 1.2)[..., None]
            img = img * (1 - core) + np.clip(c * shade + 40, 0, 255) * core
            glow = np.exp(-np.maximum(d - r0, 0) / 10)[..., None] * (d > r0)[..., None] * .35
            img = img + c * glow
            for ang in (rng.uniform(0, math.pi),):
                ca, sa = math.cos(ang), math.sin(ang)
                ex, ey = (xx - cx) * ca + (yy - cy) * sa, -(xx - cx) * sa + (yy - cy) * ca
                ring = np.abs(np.hypot(ex / (r0 * 1.9), ey / (r0 * .7)) - 1) < .03
                img[ring & (d > r0)] = img[ring & (d > r0)] * .4 + 230 * .6
    return np.clip(img, 0, 255).astype(np.uint8)


def _level_quantum(cov, rng, s=540):
    """sub-atomic: a hot core, particle tracks spiralling out of it"""
    pal = _palette(cov)
    yy, xx = np.mgrid[0:s, 0:s].astype(np.float32)
    d = np.hypot(xx - s / 2, yy - s / 2) + 1
    th = np.arctan2(yy - s / 2, xx - s / 2)
    hot = pal[np.argmax(pal.sum(1))]
    img = np.zeros((s, s, 3), np.float32) + pal.min(0) * .15
    img += hot * np.exp(-d / 45)[..., None] * 1.6
    for i in range(70):
        c = pal[i % len(pal)]
        a0, curl = rng.uniform(-math.pi, math.pi), rng.uniform(-.012, .012)
        w = np.exp(-np.abs(np.angle(np.exp(1j * (th - a0 - curl * d)))) * d / 1.5) * np.exp(-d / rng.uniform(120, 300))
        img += c * w[..., None] * rng.uniform(.4, 1.0)
    dots = rng.random((s, s)) > .9985
    img[dots] = 255
    return np.clip(img, 0, 255).astype(np.uint8)


def dive(fx, cov, bg, t, e, kick, frame):
    if not hasattr(fx, "_dv"):
        rng = np.random.default_rng(fx.seed + 51)
        gray = cv2.cvtColor(cov, cv2.COLOR_RGB2GRAY).astype(np.float32)
        det = cv2.GaussianBlur(np.abs(cv2.Laplacian(gray, cv2.CV_32F)), (0, 0), 40)
        det[:200] = det[-200:] = 0; det[:, :200] = 0; det[:, -200:] = 0
        y0, x0 = np.unravel_index(np.argmax(det), det.shape)                   # dive into the most detailed spot
        lv = [cov] + [up(f(cov, rng)) for f in (_level_cells, _level_atoms, _level_quantum)]
        fx._dv = (lv, np.array([x0, y0], np.float32))
    lv, p0 = fx._dv
    n = len(lv) - 1
    s = min(n - 1e-3, max(0.0, e) * n * .98)
    k, f = int(s), s - int(s)
    Z = 16 ** f * (1 + .01 * kick)
    ctr = np.array([S / 2, S / 2], np.float32)
    c = p0 * (1 - f) + ctr * f if k == 0 else ctr
    M = np.float32([[Z, 0, c[0] * (1 - Z)], [0, Z, c[1] * (1 - Z)]])
    rot = .15 * f * (1 if k % 2 else -1)                                       # a slight twist on the way down
    R = cv2.getRotationMatrix2D((float(c[0]), float(c[1])), math.degrees(rot), 1.0)
    M = (np.vstack([R, [0, 0, 1]]) @ np.vstack([M, [0, 0, 1]]))[:2].astype(np.float32)
    out = cv2.warpAffine(lv[k], M, (S, S), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_REFLECT).astype(np.float32)
    if k + 1 <= n:
        z2 = Z / 16
        M2 = np.float32([[z2, 0, c[0] - z2 * S / 2], [0, z2, c[1] - z2 * S / 2]])
        M2 = (np.vstack([R, [0, 0, 1]]) @ np.vstack([M2, [0, 0, 1]]))[:2].astype(np.float32)
        nxt = cv2.warpAffine(lv[k + 1], M2, (S, S), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_CONSTANT).astype(np.float32)
        rad = z2 * S / 2
        d = np.hypot(_X - c[0], _Y - c[1])
        a = sstep((rad * .92 - d) / (rad * .25 + 1))[..., None] * sstep(f * 3)
        out = out * (1 - a) + nxt * a
    if f > .02:                                                                 # speed: a soft radial blur towards the centre
        sm = cv2.warpAffine(out, np.float32([[1.04, 0, -c[0] * .04], [0, 1.04, -c[1] * .04]]), (S, S), borderMode=cv2.BORDER_REFLECT)
        out = out * .7 + sm * .3
    return np.clip(out, 0, 255).astype(np.uint8)


# ---------------------------------------------------------------- descend: from the sky, through the earth, into the fire
def _strip(cov, rng):
    s = 540
    top = cv2.resize(cov, (s, s)).astype(np.float32)
    h = s * 4
    img = np.zeros((h, s, 3), np.float32)
    img[:s] = top
    pal = _palette(cov)
    yy, xx = np.mgrid[0:h, 0:s].astype(np.float32)
    n = cv2.resize(cv2.GaussianBlur(rng.random((h // 8, s // 8)).astype(np.float32), (0, 0), 1.5), (s, h))
    n2 = cv2.resize(cv2.GaussianBlur(rng.random((h // 3, s // 3)).astype(np.float32), (0, 0), 1), (s, h))
    # earth: strata in darkened, earthy cover colours
    earth = np.array([np.clip(c * .45 + np.array([60, 40, 20]) * .55, 0, 255) for c in pal], np.float32)
    band = ((yy / 38 + n * 6) % len(earth)).astype(int)
    soil = earth[band] * (.7 + .5 * n2[..., None])
    stones = (n2 > .78)[..., None]
    soil = soil * (1 - stones * .5) + 200 * stones * .5 * n2[..., None]
    # fire: magma with dark crust
    heat = np.clip(n * 1.3 + n2 * .6 - .4, 0, 1)[..., None]
    fire = np.array([30, 0, 0], np.float32) * (1 - heat) + (np.array([255, 70, 0], np.float32) * heat + np.array([255, 220, 120], np.float32) * heat ** 4)
    zone = np.clip((yy - s) / s, 0, 3)[..., None]
    mirror = top[np.clip(2 * s - 1 - yy.astype(int), 0, s - 1), xx.astype(int)] * .8   # the image reflected into the ground
    img = np.where(zone < 1, mirror * (1 - zone) + soil * zone, img)
    img = np.where((zone >= 1) & (zone < 2), soil, img)
    img = np.where(zone >= 2, soil * np.clip(3 - zone, 0, 1) + fire * np.clip(zone - 2, 0, 1), img)
    img[:s] = top
    return np.clip(img, 0, 255).astype(np.uint8)


def descend(fx, cov, bg, t, e, kick, frame):
    if not hasattr(fx, "_ds"):
        fx._ds = _strip(cov, np.random.default_rng(fx.seed + 61))
    st = fx._ds
    s = st.shape[1]
    k = sstep(min(1.0, e))
    off = k * (st.shape[0] - s)
    y0 = int(off)
    win = st[y0:y0 + s].astype(np.float32)
    win = cv2.resize(win, (S, S))
    depth = off / (st.shape[0] - s)
    if depth > .55:                                                              # heat shimmer down below
        a = (depth - .55) * 18
        dx = (np.sin(_Y / 23 + t * 9) * a).astype(np.float32)
        win = cv2.remap(win, _X + dx, _Y, cv2.INTER_LINEAR, borderMode=cv2.BORDER_REFLECT)
    return np.clip(win, 0, 255).astype(np.uint8)


FX.update({"dive": dive, "descend": descend})
EMAX.update({"dive": (1.0, 1.0), "descend": (1.0, 1.0)})
