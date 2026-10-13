#!/usr/bin/env python3
"""One-off check of candidate shops: save compact text / JSON of given URLs to probe/ (branch probe-shops)."""
import json, os, re, sys, time
sys.path.insert(0, os.path.dirname(__file__))
from fetch_pages import fetch, Compact, slug
os.makedirs("probe", exist_ok=True)
summary = []
for u in [l.strip() for l in open(sys.argv[1]) if l.strip() and not l.startswith("#")]:
    try:
        st, body = fetch(u)
        if body.lstrip().startswith(("{", "[")):
            txt = body[:60000]
        else:
            c = Compact(u); c.feed(body); txt = c.text()
            txt += "\n" + "\n".join(sorted(set(" [audio: %s]" % m for m in re.findall(r"https?://[^\s\"'<>]+?\.mp3", body)))[:60])
        open("probe/" + slug(u) + ".txt", "w").write("SOURCE %s\nSTATUS %s\n\n%s" % (u, st, txt[:60000]))
        summary.append((u, st, len(body)))
    except Exception as e:
        summary.append((u, str(e)[:100], 0))
    time.sleep(1)
json.dump(summary, open("probe/summary.json", "w"), indent=1)
