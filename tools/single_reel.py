#!/usr/bin/env python3
"""Ein Reel für eine bestimmte Platte (auf Wunsch), im gleichen Look wie das tägliche Reel.
Wunsch in tools/single_reel.json: {"artist": "...", "title": "..."} (Teilwörter genügen).
Läuft in GitHub Actions; Ausgabe JSON auf stdout."""
import json, os, re, sys, tempfile
sys.path.insert(0, os.path.dirname(__file__))
import digs, reelfx

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WORK = os.environ.get("REEL_WORK") or tempfile.mkdtemp()

def main():
    want = json.load(open(os.path.join(ROOT, "tools", "single_reel.json"), encoding="utf-8"))
    data = json.load(open(os.path.join(ROOT, "releases.json"), encoding="utf-8"))
    fx = data.get("fx", {})
    G = {}
    for s in data["shops"]:
        for it in s.get("items") or []:
            G.setdefault(digs.gkey(it), []).append(dict(it, shop=s["shop"], cur=s.get("cur", "€"), country=s.get("country", "")))
    wa, wt = digs.norm(want["artist"]), digs.norm(want["title"])
    hits = [(k, arr) for k, arr in G.items() if any(wa in digs.norm(x["a"]) and wt in digs.norm(x["t"]) for x in arr)]
    if not hits:
        raise SystemExit("release not found: %s – %s" % (want["artist"], want["title"]))
    k, arr = hits[0]
    tracks = digs.playable(arr)
    if not tracks:
        raise SystemExit("no playable preview")
    first = min(x.get("first_seen") or "9999" for x in arr)
    feat = next(x for x in arr if (x.get("first_seen") or "9999") == first)
    aud = tr = None
    pref = [t for t in tracks if want.get("track") and digs.norm(want["track"]) in digs.norm(t["n"])] + tracks
    for i, t in enumerate(pref[:4]):
        try:
            aud, tr = digs.get_audio(t, False, WORK, 700 + i), t
            break
        except Exception as e:
            digs.log("audio fail", t.get("u"), e)
    if aud is None:
        raise SystemExit("audio failed")
    cov = digs.get_cover(arr, False, 1)
    c = {"key": k, "arr": arr, "feat": feat, "shop": feat["shop"], "fam": digs.family(feat.get("g")),
         "strict": True, "tracks": tracks, "score": 0, "track": tr, "cover": cov, "audio": aud}
    R = digs.prepare(c, fx)
    start, _ = digs.pick_start(aud)
    mix = digs.reel_mix(aud, max(0.0, start - 1.0))
    slug = re.sub(r"[^a-z0-9]+", "-", (R["a"] + " " + R["t"]).lower()).strip("-")[:60]
    out = os.path.join(WORK, "reel-%s.mp4" % slug)
    poster = out.replace(".mp4", ".jpg")
    look = reelfx.reel_single(digs.reel_rel(R, cov), mix, digs.look_seed(slug, "single"), out, poster, cmode=want.get("fx"))
    cap = digs.reel_caption(R, arr)
    capp = out.replace(".mp4", ".txt")
    open(capp, "w", encoding="utf-8").write(cap + "\n")
    print(json.dumps({"video": out, "poster": poster, "caption": capp, "look": look, "release": "%s – %s" % (R["a"], R["t"]),
                      "track": tr.get("n"), "cover_px": cov.width}))

if __name__ == "__main__":
    main()
