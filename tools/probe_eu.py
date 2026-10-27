#!/usr/bin/env python3
"""One-off: Underground Solu'shn house/techno category pages + product pages; Monorail electronic collection."""
import json, os, re, sys, time, urllib.request, urllib.parse
UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_5) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0 Safari/537.36"
def get(u):
    try:
        r = urllib.request.urlopen(urllib.request.Request(u, headers={"User-Agent": UA}), timeout=30)
        return r.status, r.read().decode("utf-8", "replace")
    except Exception as e:
        return getattr(e, "code", None) or str(e)[:80], ""
os.makedirs("probe", exist_ok=True)
log = {}
for name, u in [("us_house", "https://undergroundsolution.com/all-formats/electronic-genres/house-genres.html"),
                ("us_techno", "https://undergroundsolution.com/all-formats/electronic-genres/techno-genres.html"),
                ("us_new", "https://undergroundsolution.com/new-releases.html"),
                ("mono_elec", "https://monorailmusic.com/collections/electronic"),
                ("mono_colls", "https://monorailmusic.com/collections.json")]:
    st, b = get(u); open("probe/%s.txt" % name, "w").write(b); log[name] = [u, st, len(b)]; time.sleep(1.5)
b = open("probe/us_house.txt").read()
prods = list(dict.fromkeys(re.findall(r'href="(https://undergroundsolution\.com/[a-z0-9-]+\.html)"', b)))
log["us_prods"] = prods[:15]
for j, p in enumerate([x for x in prods if "genres" not in x and "formats" not in x][:2]):
    st, pb = get(p); open("probe/us_prod%d.txt" % j, "w").write(pb); log["us_prod%d" % j] = [p, st, len(pb)]; time.sleep(1.5)
json.dump(log, open("probe/log.json", "w"), indent=1)
