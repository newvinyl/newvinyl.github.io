#!/usr/bin/env python3
"""Text-Hook für Reels und «Today's Digs»: gelbe Box, schwarze Schrift (Schibsted Grotesk Black, Versal),
immer einzeilig, leicht schräg, zufällig über dem Cover platziert. Sichtbar ab Sekunde 0, blendet nach 3 s aus.

apply(path, kind, seed, ...) legt den Hook über ein fertiges Video (in place)."""
import os, random, re, subprocess
from PIL import Image, ImageDraw, ImageFont

FONT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fonts", "SchibstedGrotesk.ttf")
YELLOW, BLACK = (0xF2, 0xE3, 0x3A, 255), (0, 0, 0, 255)
SHOW, FADE = 3.0, 0.4          # seconds fully visible, fade-out

HOOKS = {
    "new": ["WHAT A BANGER!", "MASTERPIECE.", "PURE FIRE.", "INSTANT CLASSIC.", "BIG ONE.", "HEAVY.",
            "ESSENTIAL.", "HEARD THIS YET?", "SOUND ON."],
    "reissue": ["TIMELESS!", "STILL HITS.", "CLASSIC. REPRESSED.", "BACK IN STOCK!", "AGELESS.", "FINALLY BACK."],
    "digs": ["SOUND ON.", "WHICH ONE?", "FRESH IN.", "JUST LANDED.", "NEW IN.", "HOT OFF THE PRESS.",
             "HELLO, YOU THREE!", "THREE'S A CROWD.", "THE USUAL SUSPECTS.", "TRIPLE TROUBLE.", "THREE AMIGOS.",
             "TODAY'S LINEUP.", "MEET THE NEWCOMERS."],
}
# cover area in the frame (x0, y0, x1, y1): the hook always stays on the cover, never on artist/title/shop
AREA = {"digs": (100, 360, 980, 1240), "reel": (40, 330, 1040, 1350)}

REISSUE_RE = re.compile(r"\b(re-?issue|re-?press(ed|ing)?|remaster(ed)?|re-?edition|back in stock|anniversary)\b", re.I)

def is_reissue(*texts):
    return any(t and REISSUE_RE.search(t) for t in texts)

def pick(kind, seed, avoid=()):
    pool = HOOKS[kind]
    rnd = random.Random("hook|%s|%s" % (kind, seed))
    fresh = [h for h in pool if h not in set(avoid)] or pool
    return rnd.choice(fresh)

def render(text, maxw, angle, out):
    """one line, uppercase; shrinks the type until the box fits maxw"""
    text = text.upper()
    size = 130
    while True:
        f = ImageFont.truetype(FONT, size)
        try:
            f.set_variation_by_axes([900])            # Black
        except Exception:
            pass
        l, t, r, b = f.getbbox(text)
        px, py = int(size * .32), int(size * .26)
        if r - l + 2 * px <= maxw or size <= 40:
            break
        size -= 2
    im = Image.new("RGBA", (r - l + 2 * px, b - t + 2 * py), YELLOW)
    ImageDraw.Draw(im).text((px - l, py - t), text, font=f, fill=BLACK)
    im = im.rotate(angle, expand=True, resample=Image.BICUBIC)
    im.save(out)
    return im.size

def apply(path, kind, seed, reissue=False, avoid=()):
    """kind: 'digs' or 'reel'. Returns the hook text (for logs/history)."""
    hk = "digs" if kind == "digs" else ("reissue" if reissue else "new")
    text = pick(hk, seed, avoid)
    rnd = random.Random("hookpos|%s|%s" % (kind, seed))
    x0, y0, x1, y1 = AREA["digs" if kind == "digs" else "reel"]
    angle = rnd.uniform(3, 8) * rnd.choice([-1, 1])
    png = path + ".hook.png"
    w, h = render(text, int((x1 - x0) * .86), angle, png)
    x = rnd.randint(x0, max(x0, x1 - w))
    y = rnd.randint(y0, max(y0, y1 - h))
    tmp = path + ".hook.mp4"
    cmd = ["ffmpeg", "-y", "-v", "error", "-i", path, "-loop", "1", "-t", str(SHOW + FADE + .2), "-i", png,
           "-filter_complex", "[1]format=rgba,fade=t=out:st=%s:d=%s:alpha=1[h];[0:v][h]overlay=x=%d:y=%d:eof_action=pass[v]"
           % (SHOW, FADE, x, y),
           "-map", "[v]", "-map", "0:a?", "-c:v", "libx264", "-profile:v", "high", "-level", "4.0", "-pix_fmt", "yuv420p",
           "-b:v", "8M", "-maxrate", "10M", "-bufsize", "16M", "-g", "60", "-preset", "medium",
           "-c:a", "copy", "-movflags", "+faststart", tmp]
    subprocess.run(cmd, check=True)
    os.replace(tmp, path)
    os.remove(png)
    return text
