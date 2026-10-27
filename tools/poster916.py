#!/usr/bin/env python3
"""9:16 reel built only from the cover itself (since 27.10.26, prototype).

1. Poster: the cover's own ground (colour, gradient, paper/print grain) is continued above and below, so the artwork
   looks as if it had been designed upright. Close to the seam the cover is mirrored (keeps gradients and texture
   continuous), further away it settles into the cover's calm ground colour.
2. The shape & colour loop (tools/shapeloop.py) runs on the whole poster: shapes may move past the old cover edge,
   the colour rings flow over the full height.
3. Opening: the camera starts close on the main shape and pulls back in the first seconds; at the end it moves in
   again, so the loop stays seamless.
4. A quiet line of type at the bottom (artist / title / label · shop) in a colour that reads on the moving ground."""
import math, os, subprocess, sys
import numpy as np, cv2
from PIL import Image, ImageDraw, ImageFont

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import shapeloop as SL

W, H, FPS = 1080, 1920, 30
CY = 330                                     # top of the cover on the poster (inside the 3:4 grid crop, above the caption zone)

def sstep(x):
    x = np.clip(x, 0, 1); return x * x * (3 - 2 * x)

def build_canvas(im):
    """continue the cover's ground; where shapes touch the edge they run on as soft streaks that dissolve"""
    a, lab, fg, _ = SL.segment(im)
    a = a.astype(np.float32)
    half = cv2.resize(a, (540, 540)).astype(np.uint8)
    hm = cv2.resize(fg, (540, 540), interpolation=cv2.INTER_NEAREST)
    ground = cv2.resize(cv2.inpaint(half, cv2.dilate(hm, np.ones((5, 5), np.uint8)), 9, cv2.INPAINT_TELEA), (1080, 1080)).astype(np.float32)
    far = np.median(ground[fg == 0].reshape(-1, 3), axis=0) if (fg == 0).any() else np.median(ground.reshape(-1, 3), axis=0)
    # grain: same strength as the paper/print grain of the cover's ground, but synthetic (no ghosts of shapes)
    hp = (a - cv2.GaussianBlur(a, (0, 0), 3))[cv2.dilate(fg, np.ones((9, 9), np.uint8)) == 0]
    gs = float(hp.std()) if hp.size > 100 else 3.0
    rng = np.random.default_rng(5)
    out = np.zeros((H, W, 3), np.float32)
    out[CY:CY + 1080] = a
    def extend(n, edge_img, edge_ground):
        d = np.arange(1, n + 1, dtype=np.float32)[:, None, None]
        er = cv2.GaussianBlur(edge_img.mean(0, keepdims=True), (0, 0), 2)          # the cover's edge row
        eg = cv2.GaussianBlur(edge_ground.mean(0, keepdims=True), (0, 0), 30)      # its ground along the edge
        gr = eg * (1 - sstep(d / 520)) + far * sstep(d / 520)                    # ground settles into the main colour
        streak = er * (1 - sstep(d / 170)) + gr * sstep(d / 170)                 # shapes at the edge dissolve as streaks
        noise = cv2.GaussianBlur(rng.normal(0, 1, (n, W)).astype(np.float32), (0, 0), 0.7)[..., None] * gs * 1.4
        return streak + noise
    out[:CY] = extend(CY, a[:6], ground[:24])[::-1]
    nb = H - CY - 1080
    out[CY + 1080:] = extend(nb, a[-6:], ground[-24:])
    return np.clip(out, 0, 255).astype(np.uint8)

def font(size, bold):
    here = os.path.dirname(os.path.abspath(__file__))
    for f in (["texgyreheros-bold.otf", "TeXGyreHeros-Bold.otf"] if bold else ["texgyreheros-regular.otf", "TeXGyreHeros-Regular.otf"]):
        for d in (os.path.join(here, "fonts"), here, "/usr/share/fonts/opentype/tex-gyre", "/usr/share/texmf/fonts/opentype/public/tex-gyre"):
            p = os.path.join(d, f)
            if os.path.exists(p):
                return ImageFont.truetype(p, size)
    try:
        import reelfx
        return reelfx.F(reelfx.FD if bold else reelfx.FDR, size)
    except Exception:
        return ImageFont.load_default()

def type_layer(rel):
    """type of the earlier reels (Helvetica bold / regular, same sizes and left edge), without the black boxes:
    artist, title, label · shop, and monthlyvinyl.net small on the right. Returns an alpha mask (1 = ink)."""
    import reelfx as R
    L = Image.new("L", (W, H), 0)
    d = ImageDraw.Draw(L)
    x, y = 64, CY + 1080 + 34
    lines = [(rel["a"], R.fit_font(R.FD, 58, rel["a"], 880), 14),
             (rel.get("t") or "", R.fit_font(R.FDR, 42, rel.get("t") or "", 880), 16)]
    meta = "  ·  ".join(v for v in (rel.get("l"), rel.get("shop")) if v)
    for text, f, gap in lines:
        if not text:
            continue
        d.text((x, y), text, font=f, fill=255)
        y += f.size + gap
    fm = R.fit_font(R.FDR, 27, meta, 640)
    d.text((x, y + 4), meta, font=fm, fill=255)
    fu = R.F(R.FD, 24)
    d.text((R.TXT_R, y + 4 + fm.size), "monthlyvinyl.net", font=fu, fill=255, anchor="rs")
    return np.asarray(L).astype(np.float32)[..., None] / 255

class Poster:
    def __init__(self, im, rel, seed=1, dur=45.0, motion=1.0):
        self.canvas = build_canvas(im)
        self.sh = SL.Shapes(im, seed, dur, canvas=self.canvas, motion=motion)
        if motion < 1:                                                      # keep the artwork's own colours, feathered 90 px past the cover edge
            yy = np.arange(H, dtype=np.float32)[:, None]
            pr = sstep((yy - (CY - 90)) / 90) * sstep(((CY + 1080 + 90) - yy) / 90)
            self.sh.protect = np.repeat(pr, W, axis=1)
        self.dur = dur
        self.mask = type_layer(rel)
        fy0 = CY + 1080 + 40
        self.fy = (fy0, fy0 + 200)
        f = self.sh.focus
        self.z0 = 1.9
        hw, hh = W / 2 / self.z0, H / 2 / self.z0                               # the opening shot stays inside the cover
        self.zc = (float(np.clip(f[0], hw, W - hw)), float(np.clip(f[1], CY + hh, CY + 1080 - hh)))

    def cam(self, t):
        """zoom factor: close at the start, pulled back by ~3 s, moving in again during the last 3 s"""
        k = min(float(sstep(t / 3.2)), float(sstep((self.dur - t) / 3.0)))
        return self.z0 + (1 - self.z0) * k

    def frame(self, t, beatf):
        fr = self.sh.frame(t, beatf).astype(np.float32)
        # type colour: reads on whatever colour the ground has right now (light on dark, dark on light)
        y0, y1 = self.fy
        col = np.float32([251, 237, 79])                                     # type is always the site yellow
        fr = fr * (1 - self.mask) + col * self.mask
        z = self.cam(t)
        if z > 1.001:
            cx = self.zc[0] + (W / 2 - self.zc[0]) * (1 - (z - 1) / (self.z0 - 1)) if self.z0 > 1 else W / 2
            cy = self.zc[1] + (H / 2 - self.zc[1]) * (1 - (z - 1) / (self.z0 - 1)) if self.z0 > 1 else H / 2
            M = np.float32([[z, 0, W / 2 - z * cx], [0, z, H / 2 - z * cy]])
            fr = cv2.warpAffine(fr, M, (W, H), flags=cv2.INTER_CUBIC, borderMode=cv2.BORDER_REFLECT)
        return np.clip(fr, 0, 255).astype(np.uint8)

def render(im, rel, aud, sr, out, poster, dur=45.0, seed=1, motion=1.0):
    import detail_fx as DF
    P = Poster(im, rel, seed, dur, motion)
    mono = aud.mean(1) if aud.ndim == 2 else aud
    bpm, ph = DF.beat_grid(mono, sr)
    beat = 60 / bpm
    def beatf(t, alt):
        b = (t - ph) / beat
        if b < 0: return 0.0
        nb = math.floor(b)
        return math.exp(-(b - nb) * 5) if (nb - alt) % 2 == 0 else 0.0
    wav = out + ".f32"
    a2 = aud[:int(dur * sr)]
    if a2.ndim == 1: a2 = np.stack([a2, a2], 1)
    a2.astype("<f4").tofile(wav)
    cmd = ["ffmpeg", "-y", "-v", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", "%dx%d" % (W, H), "-r", str(FPS), "-i", "-",
           "-f", "f32le", "-ar", str(sr), "-ac", "2", "-i", wav, "-c:v", "libx264", "-profile:v", "high", "-pix_fmt", "yuv420p",
           "-b:v", "10M", "-maxrate", "14M", "-bufsize", "20M", "-g", "60", "-preset", "medium", "-c:a", "aac", "-b:a", "192k",
           "-movflags", "+faststart", "-shortest", out]
    pr = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    for f in range(int(dur * FPS)):
        fr = P.frame(f / FPS, beatf)
        if f == int(4 * FPS):
            Image.fromarray(fr).save(poster, quality=92)
        pr.stdin.write(fr.tobytes())
    pr.stdin.close(); assert pr.wait() == 0
    os.remove(wav)
    return "poster916 %.0f bpm" % bpm + ("" if motion >= 1 else " · colours only" if motion <= 0 else " · motion %.1f" % motion)

if __name__ == "__main__":     # cover.jpg audio.mp3 out.mp4|sheet.jpg "Artist" "Title" "Label" "Shop"
    im = Image.open(sys.argv[1]); rel = dict(a=sys.argv[4], t=sys.argv[5], l=sys.argv[6], shop=sys.argv[7])
    if sys.argv[3].endswith(".jpg"):
        P = Poster(im, rel, 7)
        ts = [0.0, 1.5, 3.5, 8, 16, 24, 32, 40, 43.5]
        sheet = Image.new("RGB", (9 * 240, 427))
        for j, t in enumerate(ts):
            sheet.paste(Image.fromarray(P.frame(t, lambda t, a: 0.0)).resize((240, 427)), (j * 240, 0))
        sheet.save(sys.argv[3], quality=88)
        Image.fromarray(P.frame(16, lambda t, a: 0.0)).save(sys.argv[3].replace(".jpg", "-full.jpg"), quality=90)
    else:
        sr = 44100
        pcm = subprocess.run(["ffmpeg", "-v", "error", "-ss", sys.argv[8] if len(sys.argv) > 8 else "18", "-t", "45", "-i", sys.argv[2], "-ac", "2", "-ar", str(sr), "-f", "f32le", "-"], capture_output=True).stdout
        aud = np.frombuffer(pcm, "<f4").reshape(-1, 2)
        print(render(im, rel, aud, sr, sys.argv[3], sys.argv[3].replace(".mp4", ".jpg"), seed=7))
