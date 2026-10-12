#!/usr/bin/env python3
"""Demo: Today's Digs (three releases of the day) in the flat colour layout – coral, mint, yellow.
Renders three stills and one 21 s video. Runs in GitHub Actions; output JSON on stdout."""
import json, os, subprocess, sys, tempfile
sys.path.insert(0, os.path.dirname(__file__))
import numpy as np
from PIL import Image
import digs
from single_reel import best_cover

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WORK = os.environ.get("REEL_WORK") or tempfile.mkdtemp()
SEG = 7
VARIANTS = {"colour": ["PK", "GN", "YL"], "black": ["BK-Y", "BK-G", "BK-P"]}

def main():
    hist = json.load(open(os.path.join(ROOT, "92h6fy", "history.json"), encoding="utf-8"))[0]
    data = json.load(open(os.path.join(ROOT, "releases.json"), encoding="utf-8"))
    fx = data.get("fx", {})
    G = {}
    for s in data["shops"]:
        for it in s.get("items") or []:
            G.setdefault(digs.gkey(it), []).append(dict(it, shop=s["shop"], cur=s.get("cur", "€"), country=s.get("country", "")))
    day = hist["date"]
    date_s = "%s.%s.%s" % (day[8:10], day[5:7], day[:4])
    P, mixes = [], []
    for i, k in enumerate(hist["keys"]):
        arr = G[k]
        first = min(x.get("first_seen") or "9999" for x in arr)
        feat = next(x for x in arr if (x.get("first_seen") or "9999") == first)
        tracks = digs.playable(arr)
        aud = tr = None
        for j, t in enumerate(tracks[:4]):
            try:
                aud, tr = digs.get_audio(t, False, WORK, 800 + 10 * i + j), t
                break
            except Exception as e:
                digs.log("audio fail", t.get("u"), e)
        cov = best_cover(arr)
        c = {"key": k, "arr": arr, "feat": feat, "shop": feat["shop"], "fam": digs.family(feat.get("g")),
             "strict": True, "tracks": tracks, "score": 0, "track": tr, "cover": cov, "audio": aud}
        R = digs.prepare(c, fx)
        side = cov.crop(((cov.width - min(cov.size)) // 2, (cov.height - min(cov.size)) // 2,
                         (cov.width + min(cov.size)) // 2, (cov.height + min(cov.size)) // 2)).resize((880, 880), Image.LANCZOS)
        shops = list(dict.fromkeys(digs.short(x["shop"]) for x in arr))
        P.append(dict(scheme=None, kicker="TODAY'S DIGS  %d/3" % (i + 1), cov880=side, a=R["a"], t=R["t"],
                      meta=R["meta"], genre=R["genre"].lower(), track=R["tname"], shops_line=" · ".join(shops[:3])))
        start, _ = digs.pick_start(aud)
        mixes.append(digs.fade(digs.seg(aud, max(0.0, start), SEG), 0.25, 0.6))
    mix = np.concatenate(mixes)
    peak = np.abs(mix).max()
    if peak > 0.97:
        mix *= 0.97 / peak
    W, H, FPS, SR = digs.W, digs.H, digs.FPS, digs.SR
    res = {}
    for name, sch in VARIANTS.items():
        out = os.path.join(WORK, "digs-%s-demo.mp4" % name)
        wav = out + ".f32"
        mix.astype("<f4").tofile(wav)
        hop = SR // FPS
        m = mix.mean(1)
        n = SEG * 3 * FPS
        levs = np.array([np.sqrt(np.mean(m[f * hop:(f + 1) * hop] ** 2)) for f in range(n)])
        levs = np.minimum(1, levs / (levs.max() + 1e-9) * 1.15)
        cmd = ["ffmpeg", "-y", "-v", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", "%dx%d" % (W, H), "-r", str(FPS), "-i", "-",
               "-f", "f32le", "-ar", str(SR), "-ac", "2", "-i", wav,
               "-c:v", "libx264", "-profile:v", "high", "-pix_fmt", "yuv420p", "-b:v", "6M", "-preset", "medium",
               "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", "-shortest", out]
        pr = subprocess.Popen(cmd, stdin=subprocess.PIPE)
        stills = []
        for f in range(n):
            i, t = divmod(f, SEG * FPS)
            t /= FPS
            p = dict(P[i], scheme=sch[i])
            im = Image.new("RGB", (W, H), digs.SCHEMES[p["scheme"]]["bg"])
            digs.draw_reel(im, p, date_s, t * digs.RDUR / SEG, levs[f], f)
            if t == 2.0:
                sp = os.path.join(WORK, "demo-%s-%d.jpg" % (name, i + 1))
                im.save(sp, quality=90)
                stills.append(sp)
            pr.stdin.write(im.tobytes())
        pr.stdin.close()
        if pr.wait() != 0:
            raise RuntimeError("ffmpeg failed")
        os.remove(wav)
        res[name] = {"video": out, "stills": stills}
    print(json.dumps({"variants": res, "titles": hist["titles"]}))

if __name__ == "__main__":
    main()
