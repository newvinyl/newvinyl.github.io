#!/usr/bin/env python3
"""One-off probe: for Shopify shops, newest vinyl in our genres -> product page audio coverage, audio reachability."""
import json, os, re, sys, time, urllib.request
sys.path.insert(0, os.path.dirname(__file__))
from shop_feeds import genres
UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_5) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0 Safari/537.36"
AUD = re.compile(r"""https?:(?:\\?/){2}[^\s"'<>]+?\.mp3""", re.I)
def get(u, method="GET"):
    try:
        r = urllib.request.urlopen(urllib.request.Request(u, headers={"User-Agent": UA}, method=method), timeout=30)
        return r.status, (r.read().decode("utf-8", "replace") if method == "GET" else dict(r.headers))
    except Exception as e:
        return str(e)[:100], ""
os.makedirs("probe", exist_ok=True)
res = {}
for base in [l.strip() for l in open(sys.argv[1]) if l.strip() and not l.startswith("#")]:
    st, body = get(base + "/products.json?limit=250")
    prods = json.loads(body).get("products", []) if st == 200 else []
    rows = []
    for p in prods:
        g = genres((p.get("tags") or []) + [p.get("product_type") or ""])
        typ = (p.get("product_type") or "").lower()
        if not g or any(x in typ for x in ("cd", "cassette", "merch", "book", "shirt")):
            continue
        rows.append(p)
    out = []
    for p in rows[:25]:
        time.sleep(1)
        s2, pb = get(base + "/products/" + p["handle"])
        aud = list(dict.fromkeys(a.replace("\\/", "/") for a in AUD.findall(pb)))
        own = [a for a in aud if str(p["id"]) in a] or aud
        head = get(own[0], "HEAD") if own else (None, {})
        out.append({"title": p["title"], "type": p.get("product_type"), "tags": p.get("tags"), "pub": p.get("published_at"), "created": p.get("created_at"),
                    "vendor": p.get("vendor"), "price": (p.get("variants") or [{}])[0].get("price"), "avail": (p.get("variants") or [{}])[0].get("available"),
                    "n_audio": len(own), "audio": own[:4], "head": [head[0], (head[1] or {}).get("Content-Length"), (head[1] or {}).get("Content-Type")],
                    "img": ((p.get("images") or [{}])[0]).get("src")})
    res[base] = {"n_products": len(prods), "n_ours": len(rows), "items": out}
    print(base, len(prods), len(rows), sum(1 for x in out if x["n_audio"]), "/", len(out), file=sys.stderr)
json.dump(res, open("probe/audio2.json", "w"), indent=1)
