#!/usr/bin/env python3
"""«Fingers» – ein filmisches Reel aus einem einzigen Cover (Vanessa Wagner / Philip Glass, 7.11.26).

Die Hände auf dem Cover bewegen sich in Zeitlupe (weiches Verschiebungsfeld, nur auf den Händen,
Fingerspitzen mehr als Handflächen), eine langsame Kamerafahrt gleitet über das Bild und zieht am
Ende auf das ganze Cover zurück. Filmkorn, leichte Vignette, chromatische Aberration, ein wandernder
Lichtschein und sehr zurückhaltende, breit gesperrte Typografie (Inter Thin/Light). Länge = Hörprobe.

Aufruf (in GitHub Actions über single_reel.py, style "fingers") oder direkt:
    python3 tools/fingers_reel.py --cover cover.jpg --audio track.mp3 --out reel.mp4 [--dur 20] [--text ...]
"""
import argparse, json, math, os, subprocess, sys, tempfile
import numpy as np, cv2
from PIL import Image, ImageDraw, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
W, H, FPS = 1080, 1920, 30
SR = 44100

def log(*a):
    print(*a, file=sys.stderr, flush=True)

def font(name, size):
    p = os.path.join(HERE, "fonts", name)
    if not os.path.exists(p):
        p = os.path.join("/usr/share/fonts/opentype/inter", name)
    return ImageFont.truetype(p, size)

def sstep(x):
    x = min(1.0, max(0.0, x))
    return x * x * (3 - 2 * x)

def ease(x):                     # smoother (quintic) for camera moves
    x = min(1.0, max(0.0, x))
    return x * x * x * (x * (x * 6 - 15) + 10)

# ---------------------------------------------------------------- stage (cover + soft extension), hand mask
def build_stage(cover, S=2200):
    """cover square → uint8 stage of 3 S tall (cover centred), blurred mirrored extension above and below"""
    side = min(cover.size)
    cov = cover.crop(((cover.width - side) // 2, (cover.height - side) // 2, (cover.width + side) // 2, (cover.height + side) // 2))
    src_px = side
    im = np.asarray(cov.convert("RGB"))
    if side < S:
        im = cv2.resize(im, (S, S), interpolation=cv2.INTER_LANCZOS4)
        # gentle unsharp so the upscale does not look soft
        bl = cv2.GaussianBlur(im, (0, 0), 2.0)
        im = cv2.addWeighted(im, 1.35, bl, -0.35, 0)
    elif side > S:
        im = cv2.resize(im, (S, S), interpolation=cv2.INTER_AREA)
    ext = cv2.GaussianBlur(im, (0, 0), S / 40)
    ext = (ext.astype(np.float32) * 0.42).astype(np.uint8)
    stage = np.zeros((3 * S, S, 3), np.uint8)
    stage[0:S] = ext[::-1]
    stage[S:2 * S] = im
    stage[2 * S:3 * S] = ext[::-1]
    # soften the seams: blend 6 % of S on both sides of each seam
    k = int(S * 0.06)
    for y0 in (S, 2 * S):
        a = np.linspace(0, 1, 2 * k, dtype=np.float32)[:, None, None]
        top = cv2.GaussianBlur(stage[y0 - k:y0 + k], (0, 0), S / 150).astype(np.float32)
        stage[y0 - k:y0 + k] = (stage[y0 - k:y0 + k] * (0.2 + 0.8 * np.abs(a - 0.5) * 2) + top * (0.8 - 0.8 * np.abs(a - 0.5) * 2)).astype(np.uint8)
    return stage, im, src_px

def hand_mask(im):
    """soft mask of the hands: the skin is lighter than the red ground (percentile based, so any red tone works)"""
    f = im.astype(np.float32) / 255
    lum = 0.30 * f[..., 0] + 0.59 * f[..., 1] + 0.11 * f[..., 2]
    sat = f.max(2) - f.min(2)
    v = lum - 0.35 * sat                             # pale skin high, saturated red ground low
    lo, hi = np.percentile(v, 38), np.percentile(v, 70)
    m = np.clip((v - lo) / max(1e-4, hi - lo), 0, 1)
    m = m * m * (3 - 2 * m)
    m = cv2.GaussianBlur(m, (0, 0), im.shape[0] / 70)
    m = cv2.GaussianBlur(m, (0, 0), im.shape[0] / 120)
    return m.astype(np.float32)

# ---------------------------------------------------------------- motion field (slow-motion fingers)
WRISTS = [(0.08, 1.02), (0.80, -0.06)]           # lower hand enters bottom-left, lace hand from the top

class Motion:
    def __init__(self, mask_S, seed=7):
        rng = np.random.default_rng(seed)
        self.mask = mask_S                           # S×S float
        self.S = mask_S.shape[0]
        # low-res lattice (cover coords u,v in 0..1 may lie outside the cover for the extension)
        comps = []
        for i in range(5):
            ang = rng.uniform(0, math.pi)
            wl = rng.uniform(0.28, 0.55)             # spatial wavelength in cover units
            comps.append(dict(kx=math.cos(ang) / wl, ky=math.sin(ang) / wl, ph=rng.uniform(0, 6.28),
                              T=rng.uniform(7.0, 14.0), amp=rng.uniform(0.006, 0.011),
                              dx=math.cos(ang + 1.3), dy=math.sin(ang + 1.3)))
        self.comps = comps
        self.rot = [dict(T=rng.uniform(9.0, 15.0), ph=rng.uniform(0, 6.28), amp=0.011) for _ in WRISTS]

    def weights(self, u, v):
        """mask × fingertip emphasis, sampled at cover coords"""
        S = self.S
        xi = np.clip((u * S).astype(np.int32), 0, S - 1)
        yi = np.clip((v * S).astype(np.int32), 0, S - 1)
        inside = (u >= 0) & (u <= 1) & (v >= 0) & (v <= 1)
        m = self.mask[yi, xi] * inside
        d = np.full_like(u, 9.0)
        for wx, wy in WRISTS:
            d = np.minimum(d, np.hypot(u - wx, v - wy))
        tip = np.clip(d / 0.9, 0, 1) ** 1.3
        return m * (0.25 + 0.75 * tip)

    def field(self, u, v, t, speed=1.0):
        """displacement in cover units at (u,v) for time t (seconds, already speed-warped)"""
        w = self.weights(u, v)
        dx = np.zeros_like(u); dy = np.zeros_like(u)
        for c in self.comps:
            s = np.sin(2 * math.pi * (c["kx"] * u + c["ky"] * v + t / c["T"]) + c["ph"]) * c["amp"]
            dx += s * c["dx"]; dy += s * c["dy"]
        for (wx, wy), r in zip(WRISTS, self.rot):
            th = r["amp"] * math.sin(2 * math.pi * t / r["T"] + r["ph"])
            dx += -(v - wy) * th * 0.55
            dy += (u - wx) * th * 0.55
        return dx * w, dy * w

# ---------------------------------------------------------------- camera
def camera(t, dur, wmin):
    """centre (cu, cv) and window width w (cover units) at time t; three-act path, very slow"""
    p = t / max(1e-6, dur)
    wmid = min(0.55, wmin * 1.12)                 # window height ≤ cover while we are close
    K = [(0.00, 0.64, 0.50, wmin),                  # lace fingertips, close (below the printed type of the cover)
         (0.50, 0.42, 0.58, wmid),                  # slide left and down along the hands
         (0.72, 0.46, 0.56, wmid),
         (0.86, 0.50, 0.67, 1.149),                 # pull back: the whole cover, centred high, text below
         (1.00, 0.50, 0.67, 1.149)]
    for (p0, u0, v0, w0), (p1, u1, v1, w1) in zip(K, K[1:]):
        if p <= p1:
            a = ease((p - p0) / max(1e-6, p1 - p0))
            return u0 + (u1 - u0) * a, v0 + (v1 - v0) * a, w0 + (w1 - w0) * a
    return K[-1][1:]

def drift(t):
    return (0.004 * math.sin(2 * math.pi * t / 23.0) + 0.002 * math.sin(2 * math.pi * t / 7.3),
            0.004 * math.cos(2 * math.pi * t / 19.0) + 0.002 * math.sin(2 * math.pi * t / 9.1),
            math.radians(0.45) * math.sin(2 * math.pi * t / 31.0))

# ---------------------------------------------------------------- text
INK = (255, 236, 236)

def tracked(draw, xy, text, fnt, fill, track, anchor="la"):
    """letter-spaced text; returns the width"""
    x, y = xy
    tw = 0
    for ch in text:
        draw.text((x + tw, y), ch, font=fnt, fill=fill, anchor=anchor)
        tw += draw.textlength(ch, font=fnt) + track
    return tw - track

def text_layers(info):
    """RGBA layers (uint8 H×W×4) for the two text states: close-up (A) and final reveal (B)"""
    thin, light, reg = (lambda s: font("Inter-Thin.otf", s)), (lambda s: font("Inter-Light.otf", s)), (lambda s: font("Inter-Regular.otf", s))
    def new():
        im = Image.new("RGBA", (W, H), (0, 0, 0, 0)); return im, ImageDraw.Draw(im)
    L = {}
    # A1: composer, top left
    im, d = new()
    tracked(d, (72, 236), info["composer"].upper(), light(58), INK + (235,), 14)
    L["a1"] = np.asarray(im)
    im, d = new()
    tracked(d, (74, 318), info["work"].upper(), thin(30), INK + (210,), 9)
    L["a2"] = np.asarray(im)
    # A3: pianist + track, bottom left (above the progress hairline)
    im, d = new()
    tracked(d, (72, 1450), info["artist"].upper(), reg(28), INK + (235,), 8)
    tracked(d, (72, 1496), info["track"], thin(28), INK + (205,), 2)
    L["a3"] = np.asarray(im)
    # A4: site, tiny, bottom
    im, d = new()
    tracked(d, (72, 1604), "monthlyvinyl.net", light(24), INK + (190,), 3)
    L["a4"] = np.asarray(im)
    # B: final block under the cover (cover: 940 px wide, centred, top at 800-470 = 330 → bottom 1270)
    im, d = new()
    y = 1340
    tracked(d, (72, y), info["artist"].upper(), reg(34), INK + (240,), 9); y += 56
    tracked(d, (72, y), (info["composer"] + " – " + info["work"]).upper(), thin(28), INK + (215,), 7); y += 60
    tracked(d, (72, y), info["meta"], light(26), INK + (200,), 2); y += 44
    tracked(d, (72, y), info["avail"], light(26), INK + (200,), 2); y += 74
    tracked(d, (72, y), "monthlyvinyl.net", light(24), INK + (190,), 3)
    L["b"] = np.asarray(im)
    return L

# ---------------------------------------------------------------- post
def vignette():
    yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
    r = np.hypot((xx - W / 2) / (W / 2), (yy - H / 2) / (H / 2))
    v = 1 - 0.30 * np.clip((r - 0.55) / 0.9, 0, 1) ** 1.6
    return v[..., None].astype(np.float32)

def grain_bank(n=16, seed=3, amp=4.5):
    """fine film grain as uint8 around 128 (added with -128 later)"""
    rng = np.random.default_rng(seed)
    g = rng.normal(0, 1, (n, H // 2, W // 2)).astype(np.float32)
    return [np.clip(128 + cv2.resize(x, (W, H), interpolation=cv2.INTER_LINEAR) * amp, 0, 255).astype(np.uint8) for x in g]

def light_sweep(t):
    """soft diagonal light band drifting over the frame (multiplier map, cheap outer product)"""
    yy = np.linspace(0, 1, H, dtype=np.float32)[:, None]
    xx = np.linspace(0, 1, W, dtype=np.float32)[None, :]
    c = 0.5 + 0.6 * math.sin(2 * math.pi * t / 37.0)
    d = (xx * 0.6 + yy * 0.8) - c
    return (1.0 + 0.10 * np.exp(-(d * d) / 0.08)).astype(np.float32)

def envelope(audio, dur):
    """RMS per frame (0..1), smoothed – drives the speed of the motion and the bloom"""
    n = int(dur * FPS)
    m = audio.mean(1) if audio.ndim == 2 else audio
    hop = SR // FPS
    e = np.array([np.sqrt(np.mean(m[i * hop:(i + 1) * hop] ** 2)) if (i + 1) * hop <= len(m) else 0.0 for i in range(n)], np.float32)
    if e.max() > 0:
        e = e / np.percentile(e, 97)
    k = int(FPS * 0.6)
    e = np.convolve(np.pad(e, (k, k), mode="edge"), np.ones(2 * k + 1) / (2 * k + 1), mode="valid")
    return np.clip(e, 0, 1.2)

# ---------------------------------------------------------------- render
class Renderer:
    def __init__(self, stage, mask, info, dur, env, wmin, seed=7):
        self.stage, self.S = stage, mask.shape[0]
        self.motion = Motion(mask, seed)
        self.info, self.dur, self.env, self.wmin = info, dur, env, wmin
        self.vig_small = cv2.resize(vignette()[..., 0], (68, 120), interpolation=cv2.INTER_AREA)
        self.grain = [cv2.merge([x, x, x]) for x in grain_bank()]
        self.layers = text_layers(info)
        self.bbox = {}
        for k, L in self.layers.items():
            ys, xs = np.nonzero(L[..., 3])
            self.bbox[k] = (ys.min(), ys.max() + 1, xs.min(), xs.max() + 1)
        xs = np.linspace(0, 1, 256, dtype=np.float32)
        f = 0.03 + 0.97 * xs
        f = f * f * (3 - 2 * f) * 0.35 + f * 0.65
        self.lut = (np.clip(f, 0, 1) * 255).astype(np.uint8)
        self.M_r = cv2.getRotationMatrix2D((W / 2, H / 2), 0, 1.0025)
        self.M_b = cv2.getRotationMatrix2D((W / 2, H / 2), 0, 0.9975)
        self.warp_t = np.cumsum(0.75 + 0.55 * env) / FPS           # speed-warped time
        # low-res lattice for the displacement field
        self.lw, self.lh = 96, 171
        gx = (np.arange(self.lw) + 0.5) / self.lw
        gy = (np.arange(self.lh) + 0.5) / self.lh
        self.LX, self.LY = np.meshgrid(gx.astype(np.float32), gy.astype(np.float32))
        gx = (np.arange(W) + 0.5) / W
        gy = (np.arange(H) + 0.5) / H
        self.GX, self.GY = np.meshgrid(gx.astype(np.float32), gy.astype(np.float32))

    def cam_px(self, t):
        cu, cv_, w = camera(t, self.dur, self.wmin)
        du, dv, rot = drift(t)
        fade = 1.0 - ease((t / self.dur - 0.80) / 0.08)              # no drift in the final reveal
        cu, cv_ = cu + du * fade, cv_ + dv * fade
        h = w * H / W
        if w <= 1.0:                                                  # keep the window inside the cover while close
            cu = min(max(cu, w / 2 + 0.01), 1 - w / 2 - 0.01)
        if h <= 1.0:
            top = 0.13 if h <= 0.86 else 0.01                      # keep the printed type at the top of the cover out of frame
            cv_ = min(max(cv_, h / 2 + top), 1 - h / 2 - 0.01)
        return cu, cv_, w, rot * fade

    def maps(self, i):
        """source coordinates for every output pixel: camera (affine) + displacement, computed on the lattice and
        interpolated up (the affine part is exact under bilinear interpolation, the displacement is smooth)"""
        t = i / FPS
        cu, cv_, w, rot = self.cam_px(t)
        h = w * H / W
        S = self.S
        c, s = math.cos(rot), math.sin(rot)
        x = (self.LX - 0.5) * w; y = (self.LY - 0.5) * h
        lu, lv = cu + x * c - y * s, cv_ + x * s + y * c
        dx, dy = self.motion.field(lu, lv, self.warp_t[i])
        mx = ((lu + dx) * S).astype(np.float32)
        my = ((lv + dy) * S + S).astype(np.float32)
        return mx, my, t

    def frame(self, i):
        mx, my, t = self.maps(i)
        MX = cv2.resize(mx, (W, H), interpolation=cv2.INTER_LINEAR)
        MY = cv2.resize(my, (W, H), interpolation=cv2.INTER_LINEAR)
        out = cv2.remap(self.stage, MX, MY, cv2.INTER_CUBIC, borderMode=cv2.BORDER_REFLECT)
        # chromatic aberration: red a touch wider, blue a touch narrower
        out[..., 0] = cv2.warpAffine(out[..., 0], self.M_r, (W, H), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_REFLECT)
        out[..., 2] = cv2.warpAffine(out[..., 2], self.M_b, (W, H), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_REFLECT)
        # bloom on the highlights (quarter resolution), a touch stronger when the music swells
        e = float(self.env[min(i, len(self.env) - 1)])
        small = cv2.resize(out, (W // 4, H // 4), interpolation=cv2.INTER_AREA).astype(np.float32) / 255
        hi = cv2.GaussianBlur(np.clip(small - 0.62, 0, 1), (0, 0), 18) * (0.30 + 0.22 * e) * 255
        bloom = cv2.resize(hi.astype(np.uint8), (W, H), interpolation=cv2.INTER_LINEAR)
        out = cv2.add(out, bloom)
        # light sweep × vignette as one multiplier (uint8, ×1/224), then grain, then the film curve (LUT)
        mult = cv2.resize(self.sweep_small(t), (W, H), interpolation=cv2.INTER_LINEAR)
        out = cv2.multiply(out, cv2.merge([mult, mult, mult]), scale=1 / 224.0)
        g = self.grain[i % len(self.grain)]
        out = cv2.addWeighted(out, 1.0, g, 1.0, -128.0)
        out = cv2.LUT(out, self.lut)
        self.overlay(out, i, t)
        a = min(1.0, t / 1.6) * min(1.0, (self.dur - t) / 2.5)
        if a < 1:
            out = cv2.convertScaleAbs(out, alpha=a)
        return out

    def sweep_small(self, t):
        yy = np.linspace(0, 1, 120, dtype=np.float32)[:, None]
        xx = np.linspace(0, 1, 68, dtype=np.float32)[None, :]
        c = 0.5 + 0.6 * math.sin(2 * math.pi * t / 37.0)
        d = (xx * 0.6 + yy * 0.8) - c
        m = (1.0 + 0.10 * np.exp(-(d * d) / 0.08)) * self.vig_small
        return np.clip(m * 224, 0, 255).astype(np.uint8)

    def overlay(self, out, i, t):
        p = t / self.dur
        reveal = ease((p - 0.82) / 0.06)             # 0 close-up text … 1 final block
        def put(name, alpha):
            if alpha <= 0.003:
                return
            y0, y1, x0, x1 = self.bbox[name]
            L = self.layers[name][y0:y1, x0:x1]
            a = L[..., 3:4].astype(np.float32) / 255 * alpha
            out[y0:y1, x0:x1] = (out[y0:y1, x0:x1] * (1 - a) + L[..., :3] * a).astype(np.uint8)
        A = 1 - reveal
        put("a1", sstep((t - 2.4) / 2.0) * A)
        put("a2", sstep((t - 3.6) / 2.0) * A)
        put("a3", sstep((t - 7.0) / 2.0) * A)
        put("a4", sstep((t - 8.0) / 2.0) * A)
        put("b", reveal)
        # progress hairline (close-up state): 72 … 1008 at y = 1560
        if A > 0.003:
            x1 = int(72 + (1008 - 72) * p)
            y = 1560
            col = np.array(INK, np.float32)
            seg = out[y:y + 2, 72:1008].astype(np.float32)
            seg = seg * (1 - 0.22 * A) + col * 0.22 * A
            out[y:y + 2, 72:1008] = seg.astype(np.uint8)
            seg = out[y:y + 2, 72:x1].astype(np.float32)
            seg = seg * (1 - 0.75 * A) + col * 0.75 * A
            out[y:y + 2, 72:x1] = seg.astype(np.uint8)
            cv2.circle(out, (x1, y + 1), 4, tuple(int(c * A + out[y + 1, min(x1, W - 1)][k] * (1 - A)) for k, c in enumerate(INK)), -1, cv2.LINE_AA)

def encode(path, frames_iter, nframes, workers_note=""):
    tmp = path + ".part.mp4"
    cmd = ["ffmpeg", "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", "%dx%d" % (W, H), "-r", str(FPS), "-i", "-",
           "-c:v", "libx264", "-preset", "fast", "-crf", "20", "-tune", "film", "-pix_fmt", "yuv420p", "-profile:v", "high", "-movflags", "+faststart", tmp]
    p = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    for k, fr in enumerate(frames_iter):
        p.stdin.write(fr.tobytes())
        if k % 150 == 0:
            log("frame %d/%d %s" % (k, nframes, workers_note))
    p.stdin.close()
    if p.wait() != 0:
        raise RuntimeError("ffmpeg failed")
    os.replace(tmp, path)

def _worker(args):
    R, a, b, path = args
    encode(path, (R.frame(i) for i in range(a, b)), b - a, "(%d-%d)" % (a, b))
    return path

def render(cover, audio, dur, info, out, poster, workers=None, seed=7):
    stage, im, src_px = build_stage(cover)
    mask = hand_mask(im)
    wmin = float(np.clip(1080 / (2.1 * src_px), 0.44, 0.54))
    log("cover %d px → wmin %.2f, dur %.1f s" % (src_px, wmin, dur))
    env = envelope(audio, dur)
    R = Renderer(stage, mask, info, dur, env, wmin, seed)
    n = int(round(dur * FPS))
    # poster: a frame from the close-up with the text in place
    Image.fromarray(R.frame(int(min(n - 1, 12 * FPS)))).save(poster, quality=93)
    workers = workers or max(1, min(4, os.cpu_count() or 1))
    work = os.path.dirname(out) or "."
    parts = []
    bounds = [int(n * k / workers) for k in range(workers + 1)]
    jobs = [(R, bounds[k], bounds[k + 1], os.path.join(work, "part-%02d.mp4" % k)) for k in range(workers)]
    if workers > 1:
        import multiprocessing as mp
        with mp.get_context("fork").Pool(workers) as pool:
            parts = pool.map(_worker, jobs)
    else:
        parts = [_worker(j) for j in jobs]
    lst = os.path.join(work, "parts.txt")
    open(lst, "w").write("".join("file '%s'\n" % os.path.abspath(p) for p in parts))
    silent = os.path.join(work, "silent.mp4")
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "concat", "-safe", "0", "-i", lst, "-c", "copy", silent], check=True)
    # audio: whole preview, soft fade in / 3 s fade out, light limiter
    raw = os.path.join(work, "mix.wav")
    a = audio[: int(dur * SR)].astype(np.float32)
    t = np.arange(len(a)) / SR
    g = np.minimum(1.0, t / 0.8) * np.minimum(1.0, (dur - t) / 3.0)
    a = a * g[:, None]
    peak = np.abs(a).max()
    if peak > 0.98:
        a = a * (0.98 / peak)
    import wave
    with wave.open(raw, "wb") as wf:
        wf.setnchannels(2); wf.setsampwidth(2); wf.setframerate(SR)
        wf.writeframes((a * 32767).astype("<i2").tobytes())
    tmp = out + ".part.mp4"
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", silent, "-i", raw, "-map", "0:v", "-map", "1:a", "-c:v", "copy",
                    "-c:a", "aac", "-b:a", "192k", "-shortest", "-movflags", "+faststart", tmp], check=True)
    os.replace(tmp, out)
    for p in parts + [silent, raw, lst]:
        try: os.remove(p)
        except OSError: pass
    return {"look": "fingers · slow-motion hands · %d s" % int(dur), "wmin": wmin, "cover_px": src_px}

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--cover", required=True); ap.add_argument("--audio")
    ap.add_argument("--out", required=True); ap.add_argument("--dur", type=float)
    ap.add_argument("--workers", type=int); ap.add_argument("--frames", help="only draw these frame times (comma, seconds) as JPEGs")
    ap.add_argument("--info", help="JSON with composer, work, artist, track, meta, avail")
    a = ap.parse_args()
    sys.path.insert(0, HERE)
    import digs
    cover = Image.open(a.cover).convert("RGB")
    if a.audio:
        audio = digs.decode(a.audio)
    else:
        audio = digs.get_audio(None, True, None, 1)
    dur = a.dur or len(audio) / SR
    info = json.loads(open(a.info).read()) if a.info else dict(
        composer="Philip Glass", work="Piano Etudes – Versions", artist="Vanessa Wagner",
        track="Etude No. 2 (Tauceti Version)", meta="InFiné · IF2083LP · 12\"", avail="Available at Rubadub")
    if a.frames:
        stage, im, src_px = build_stage(cover)
        mask = hand_mask(im)
        Image.fromarray((mask * 255).astype(np.uint8)).save(a.out + ".mask.png")
        wmin = float(np.clip(1080 / (2.1 * src_px), 0.44, 0.54))
        R = Renderer(stage, mask, info, dur, envelope(audio, dur), wmin)
        for ts in a.frames.split(","):
            fr = R.frame(int(float(ts) * FPS))
            Image.fromarray(fr).save("%s.%05.1f.jpg" % (a.out, float(ts)), quality=92)
        return
    poster = a.out.replace(".mp4", ".jpg")
    print(json.dumps(render(cover, audio, dur, info, a.out, poster, a.workers)))

if __name__ == "__main__":
    main()
