#!/usr/bin/env python3
"""«Platte des Tages» (test 25.11.–8.12.26, see tools/instagram_post.md section 5): one fresh record as a carousel,
one slide per track. Lists today's candidates, best first:

    python3 tools/record_of_day.py                 list
    python3 tools/record_of_day.py --write 1       write tools/carousel_pick.json for candidate no. 1

Rules: fresh today, not in Today's Digs, artist AND label with a verified Instagram account, at least 2 named
previews in one shop, no Sony rights, new releases before represses (flagged «RE?» – check by hand)."""
import io, contextlib, json, os, re, sys
sys.path.insert(0, os.path.dirname(__file__))
import digs, ig_handles as ih

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RE_HINT = re.compile(r"\b(re-?issue|re-?press|re-?master|re-?edition|anniversary|20\d\d re|\(re\)|classics?|collection|best of)\b", re.I)

def followers(name):
    best = 0
    for n in ih.artists(name) or [name]:
        d, k = ih.db(), ih._n(n)
        v = d.get(k) or d.get(ih.SUFFIX.sub("", k)) or d.get(k + " records")
        if isinstance(v, dict) and v.get("handle"):
            best = max(best, int(v.get("followers") or 0))
    return best

def main():
    data = json.load(open(os.path.join(ROOT, "releases.json"), encoding="utf-8"))
    day = data["updated"]
    hist = json.load(open(os.path.join(ROOT, "92h6fy", "history.json"), encoding="utf-8"))
    dk = set(next((e.get("keys", []) for e in hist if e.get("date") == day), []))
    seen = set(k for e in hist if e.get("date") != day for k in e.get("keys", []))
    with contextlib.redirect_stderr(io.StringIO()):
        cands = list(digs.candidates(data, day, seen))
    rows, done = [], set()
    for c in cands:
        if c["key"] in dk or c["key"] in done:
            continue
        done.add(c["key"])
        x = c["feat"]
        s = ih.status(x["a"], x.get("l"))
        if not (s["a"] and s["l"]):
            continue
        names = []
        for t in x.get("tr") or []:
            n = (t.get("n") or "").strip()
            if t.get("u") and n and n.lower() != "preview" and n.lower() not in [m.lower() for m in names]:
                names.append(n)
        if len(names) < 2:
            continue
        re_hint = bool(RE_HINT.search(x["t"] + " " + (x.get("f") or "")))
        fa, fl = followers(x["a"]), followers(x.get("l") or "")
        rows.append({"re": re_hint, "fa": fa, "fl": fl, "x": x, "s": s, "tracks": names})
    rows.sort(key=lambda r: (r["re"], -(r["fa"] + .3 * r["fl"])))
    if "--write" in sys.argv:
        r = rows[int(sys.argv[sys.argv.index("--write") + 1]) - 1]
        x = r["x"]
        import datetime
        d = datetime.date.fromisoformat(day)
        note = "%d %s %d" % (d.day, ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"][d.month - 1], d.year)
        cfg = {"name": "record-" + day, "seg": 30, "items": [{"a": digs.norm(x["a"]), "t": digs.norm(x["t"]), "shop": x["shop"],
                                                               "note": note, "tracks": 4}]}
        json.dump(cfg, open(os.path.join(ROOT, "tools", "carousel_pick.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
        print("written:", x["a"], "–", x["t"])
        return
    for i, r in enumerate(rows, 1):
        x, s = r["x"], r["s"]
        print("%d. %s%s – %s | %s | %s%s | artist %s (%d) | label @%s (%d) | %d tracks: %s" % (
            i, "RE? " if r["re"] else "", x["a"], x["t"], x.get("l"), x["shop"], " pre" if x.get("st") == "pre" else "",
            ",".join("@" + h for h in s["a"]), r["fa"], s["l"], r["fl"], len(r["tracks"]), "; ".join(r["tracks"][:5])))
    print("%d candidates" % len(rows))

if __name__ == "__main__":
    main()
