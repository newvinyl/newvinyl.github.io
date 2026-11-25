#!/usr/bin/env python3
"""Shop carousel (user, 25.11.26): up to 10 fresh records that are all available in ONE shop, so the shop can be invited
as co-author (collab post). See tools/instagram_post.md section 5a.

    python3 tools/shop_carousel.py                  shops of today, best first, with their records
    python3 tools/shop_carousel.py --write Hardwax  write tools/carousel_pick.json for that shop (+ log for the rotation)
    optional: --skip "artist|title"                 leave a record out (e.g. today's record of the day)

Rules: fresh today (first appearance over all shops), not in Today's Digs, preview in that shop, no Sony rights,
new releases before represses («RE?» = check by hand, they go last), shop has a verified Instagram account,
a shop is not repeated while another shop with at least 3 records has not had its turn in the last 3 carousels."""
import io, contextlib, json, os, sys, datetime
sys.path.insert(0, os.path.dirname(__file__))
import digs, ig_handles as ih
from record_of_day import followers, RE_HINT

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LOG = os.path.join(ROOT, "tools", "shop_carousel_log.json")
MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]

def main():
    data = json.load(open(os.path.join(ROOT, "releases.json"), encoding="utf-8"))
    day = data["updated"]
    handles = json.load(open(os.path.join(ROOT, "tools", "shop_instagram.json"), encoding="utf-8"))
    hist = json.load(open(os.path.join(ROOT, "92h6fy", "history.json"), encoding="utf-8"))
    dk = set(next((e.get("keys", []) for e in hist if e.get("date") == day), []))
    seen = set(k for e in hist if e.get("date") != day for k in e.get("keys", []))
    skip = set()
    a = sys.argv[1:]
    while "--skip" in a:
        i = a.index("--skip"); skip.add(a[i + 1].lower()); del a[i:i + 2]
    with contextlib.redirect_stderr(io.StringIO()):
        cands = list(digs.candidates(data, day, seen))
    shops, done = {}, set()
    for c in cands:
        if c["key"] in dk or c["key"] in done or c["key"] in skip:
            continue
        done.add(c["key"])
        for x in c["arr"]:
            h = handles.get(x["shop"])
            if not h or not isinstance(h, str) or not any(t.get("u") for t in x.get("tr") or []):
                continue
            s = ih.status(x["a"], x.get("l"))
            shops.setdefault(x["shop"], []).append({"x": x, "key": c["key"], "s": s, "re": bool(RE_HINT.search(x["t"] + " " + (x.get("g") or ""))),
                                                    "fol": followers(x["a"]) + .3 * followers(x.get("l") or "")})
    for v in shops.values():
        v.sort(key=lambda r: (r["re"], -(bool(r["s"]["a"]) + bool(r["s"]["l"])), -r["fol"]))
    try:
        log = json.load(open(LOG, encoding="utf-8"))
    except FileNotFoundError:
        log = []
    recent = [e["shop"] for e in log if e.get("date") != day][-3:]
    order = sorted(shops, key=lambda k: (k in recent, -min(10, sum(not r["re"] for r in shops[k]))))
    if "--write" in a:
        shop = a[a.index("--write") + 1]
        rows = shops[shop][:10]
        d = datetime.date.fromisoformat(day)
        note = "%d %s %d" % (d.day, MONTHS[d.month - 1], d.year)
        cfg = {"name": "shop-%s-%s" % (day, digs.norm(shop).replace(" ", "-")), "seg": 30,
               "items": [{"a": digs.norm(r["x"]["a"]), "t": digs.norm(r["x"]["t"]), "shop": shop, "note": note} for r in rows]}
        json.dump(cfg, open(os.path.join(ROOT, "tools", "carousel_pick.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
        log = [e for e in log if e.get("date") != day] + [{"date": day, "shop": shop, "n": len(rows)}]
        json.dump(log[-60:], open(LOG, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
        print("written:", shop, len(rows), "records")
        return
    for k in order:
        v = shops[k]
        print("%s (@%s)%s: %d fresh records, %d new" % (k, handles[k], "  [recently]" if k in recent else "", len(v), sum(not r["re"] for r in v)))
        for r in v[:10]:
            x, s = r["x"], r["s"]
            print("   %s%s – %s | %s%s | artist %s | label %s" % ("RE? " if r["re"] else "", x["a"], x["t"], x.get("l") or "", " | pre" if x.get("st") == "pre" else "",
                  ",".join("@" + h for h in s["a"]) or ("TODO" if s["a_unknown"] else "-"), ("@" + s["l"]) if s["l"] else ("TODO" if s["l_unknown"] else "-")))

if __name__ == "__main__":
    main()
