#!/usr/bin/env python3
"""One-off: raw pages of Rubadub, Monorail, Underground Solu'shn (robots, list pages, a product page, products.json)."""
import json, os, re, sys, time, urllib.request, urllib.parse
UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_5) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0 Safari/537.36"
def get(u):
    try:
        r = urllib.request.urlopen(urllib.request.Request(u, headers={"User-Agent": UA, "Accept": "text/html,application/json,*/*"}), timeout=30)
        return r.status, r.read().decode("utf-8", "replace"), r.geturl()
    except Exception as e:
        return getattr(e, "code", None) or str(e)[:80], "", u
os.makedirs("probe", exist_ok=True)
URLS = {"rubadub": ["https://rubadub.co.uk/robots.txt", "https://rubadub.co.uk/collections/browse-latest-arrivals", "https://rubadub.co.uk/products.json?limit=30"],
        "monorail": ["https://www.monorailmusic.com/robots.txt", "https://www.monorailmusic.com/", "https://www.monorailmusic.com/products.json?limit=30"],
        "usolution": ["https://www.undergroundsolution.com/robots.txt", "https://www.undergroundsolution.com/", "https://undergroundsolution.com/products.json?limit=30"]}
log = {}
for name, us in URLS.items():
    for k, u in enumerate(us):
        st, b, fin = get(u)
        open("probe/%s_%d.txt" % (name, k), "w").write(b)
        log["%s_%d" % (name, k)] = [u, st, len(b), fin]
        time.sleep(1.5)
    # first product page found on the list/home page
    b = open("probe/%s_1.txt" % name).read()
    base = "{0.scheme}://{0.netloc}".format(urllib.parse.urlparse(log[name + "_1"][3]))
    links = [urllib.parse.urljoin(base, h) for h in re.findall(r'href="([^"#]+)"', b)]
    prod = [l for l in dict.fromkeys(links) if re.search(r"/products?/|/release|/item|/music/new", l)]
    log[name + "_prodlinks"] = prod[:8]
    for j, p in enumerate(prod[:2]):
        st, pb, fin = get(p)
        open("probe/%s_prod%d.txt" % (name, j), "w").write(pb)
        log["%s_prod%d" % (name, j)] = [p, st, len(pb)]
        time.sleep(1.5)
json.dump(log, open("probe/log.json", "w"), indent=1)
