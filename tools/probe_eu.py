#!/usr/bin/env python3
"""One-off: where does Rubadub's track player get its audio from?"""
import json, os, re, sys, time, urllib.request, urllib.parse
UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_5) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0 Safari/537.36"
def get(u):
    try:
        r = urllib.request.urlopen(urllib.request.Request(u, headers={"User-Agent": UA}), timeout=30)
        return r.status, r.read().decode("utf-8", "replace")
    except Exception as e:
        return getattr(e, "code", None) or str(e)[:80], ""
os.makedirs("probe", exist_ok=True)
B = "https://rubadub.co.uk"
log = {}
hit = None
for page in range(1, 5):
    st, b = get(B + "/products.json?limit=250&page=%d" % page)
    for p in json.loads(b or '{"products":[]}').get("products", []):
        if "jazzy sport" in p["title"].lower():
            hit = p; break
    if hit: break
    time.sleep(1)
log["hit"] = hit and {k: hit[k] for k in ("id", "handle", "title", "tags")}
h = hit["handle"] if hit else "teyas-1"
for name, u in [("page", B + "/products/" + h), ("js", B + "/products/" + h + ".js"), ("json", B + "/products/" + h + ".json"),
                ("agents", B + "/agents.md")]:
    st, b = get(u); open("probe/r_%s.txt" % name, "w").write(b); log[name] = [u, st, len(b)]; time.sleep(1)
pg = open("probe/r_page.txt").read()
srcs = re.findall(r'<script[^>]+src="([^"]+)"', pg)
log["scripts"] = srcs
log["urls_media"] = sorted(set(re.findall(r'https?:[^"\'\s<>\\]+?(?:mp3|m4a|ogg|wav|audio|cloudfront|amazonaws|storage\.googleapis|firebase)[^"\'\s<>\\]*', pg)))[:60]
# fetch app scripts that look like a player
for j, s in enumerate([s for s in srcs if re.search(r"audio|player|track|sound|music|preview|app", s, re.I)][:8]):
    u = urllib.parse.urljoin(B, s if not s.startswith("//") else "https:" + s)
    st, b = get(u); open("probe/r_script%d.txt" % j, "w").write(b); log["script%d" % j] = [u, st, len(b)]; time.sleep(1)
json.dump(log, open("probe/log.json", "w"), indent=1)
