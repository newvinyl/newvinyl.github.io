#!/usr/bin/env python3
"""One-off: run the new shop feeds for real and save their items (test before they go into the daily update)."""
import json, os, sys, time
sys.path.insert(0, os.path.dirname(__file__))
import shop_feeds as SF
from fetch_pages import fetch
os.makedirs("probe", exist_ok=True)
ids = [l.strip() for l in open(sys.argv[1]) if l.strip() and not l.startswith("#")]
for fid, shop, where, country, cur, fn in SF.FEEDS:
    if fid not in ids:
        continue
    t = time.time()
    try:
        items = fn(fetch); err = None
    except Exception as e:
        items, err = [], repr(e)[:300]
    chk = []
    import urllib.request
    for it in [i for i in items if i.get("tr")][:3]:
        for u in (it["tr"][0]["u"], it.get("cover")):
            try:
                r = urllib.request.urlopen(urllib.request.Request(u, headers={"User-Agent": "Mozilla/5.0", "Range": "bytes=0-1000"}), timeout=30)
                chk.append([u[:120], r.status, r.headers.get("Content-Type"), r.headers.get("Content-Range")])
            except Exception as e:
                chk.append([u[:120], repr(e)[:80]])
    json.dump({"check": chk, "shop": shop, "err": err, "secs": round(time.time() - t), "items": items}, open("probe/%s.json" % fid, "w"), indent=1, ensure_ascii=False)
    print(fid, len(items), sum(1 for i in items if i.get("tr")), err, file=sys.stderr)
