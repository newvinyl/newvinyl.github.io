#!/usr/bin/env python3
"""One-off probe: raw products.json + a few product pages per shop (to find audio players), saved to probe/."""
import json, os, re, sys, time, urllib.request
UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_5) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0 Safari/537.36"
def get(u):
    try:
        r = urllib.request.urlopen(urllib.request.Request(u, headers={"User-Agent": UA}), timeout=30)
        return r.status, r.read().decode("utf-8", "replace")
    except Exception as e:
        return str(e)[:100], ""
os.makedirs("probe", exist_ok=True)
for base in [l.strip() for l in open(sys.argv[1]) if l.strip() and not l.startswith("#")]:
    name = re.sub(r"\W+", "_", base.split("//")[1]).strip("_")
    st, body = get(base.rstrip("/") + "/products.json?limit=40")
    open("probe/%s_products.json" % name, "w").write(body)
    try:
        prods = json.loads(body)["products"]
    except Exception:
        prods = []
    vin = [p for p in prods if "record" in (p.get("product_type") or "").lower() or "vinyl" in (p.get("product_type") or "").lower()][:3]
    for i, p in enumerate(vin):
        time.sleep(1)
        st, pb = get(base.rstrip("/") + "/products/" + p["handle"])
        open("probe/%s_page%d.html" % (name, i), "w").write(pb)
        time.sleep(1)
        st, js = get(base.rstrip("/") + "/products/" + p["handle"] + ".js")
        open("probe/%s_page%d.js.json" % (name, i), "w").write(js)
    print(base, st, len(prods), file=sys.stderr)
