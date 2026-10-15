#!/usr/bin/env python3
"""One-off: probe US shops – reachable? Shopify? count new electronic releases of the last 7/30 days and overlap with releases.json."""
import json, os, re, sys, time, unicodedata, datetime as dt, urllib.request
sys.path.insert(0, os.path.dirname(__file__))
from shop_feeds import genres
UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_5) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0 Safari/537.36"
def get(u):
    try:
        r = urllib.request.urlopen(urllib.request.Request(u, headers={"User-Agent": UA, "Accept": "text/html,application/json,*/*"}), timeout=30)
        return r.status, r.read().decode("utf-8", "replace")
    except Exception as e:
        return getattr(e, "code", None) or str(e)[:100], ""
def n(s):
    s = unicodedata.normalize("NFKD", s or "").encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]", "", s)
D = json.load(open("releases.json"))
have = {n(x["a"]) + "|" + n(x["t"]) for S in D["shops"] for x in S.get("items") or []}
have_t = {n(x["t"]) for S in D["shops"] for x in S.get("items") or []}
today = dt.date.today()
res = []
for base in [l.strip() for l in open(sys.argv[1]) if l.strip() and not l.startswith("#")]:
    st, body = get(base)
    e = {"base": base, "status": st, "len": len(body), "shopify": "cdn.shopify.com" in body or "Shopify." in body,
         "woo": "woocommerce" in body.lower(), "mp3": len(set(re.findall(r"https?://[^\s\"'<>]+?\.mp3", body))),
         "title": (re.search(r"<title[^>]*>(.*?)</title>", body, re.S | re.I) or [None, ""])[1].strip()[:70]}
    if e["shopify"]:
        prods, page = [], 1
        while page <= 4:
            s2, b2 = get(base.rstrip("/") + "/products.json?limit=250&page=%d" % page)
            try:
                pj = json.loads(b2).get("products", [])
            except Exception:
                e["pj_error"] = str(s2); break
            prods += pj
            if len(pj) < 250: break
            page += 1; time.sleep(1)
        e["products"] = len(prods)
        rec = {7: [], 30: []}
        for p in prods:
            pub = (p.get("published_at") or p.get("created_at") or "")[:10]
            try: age = (today - dt.date.fromisoformat(pub)).days
            except Exception: continue
            tags = p.get("tags") or []
            words = tags + [p.get("product_type") or ""]
            g = genres(words)
            if not g: continue
            title = p.get("title") or ""
            a, t = (title.split(" - ", 1) if " - " in title else title.split(" | ", 1) if " | " in title else ("", title))
            key = n(a) + "|" + n(t)
            known = key in have or (n(t) in have_t and len(n(t)) > 6)
            mp3 = bool(re.search(r"\.mp3", p.get("body_html") or ""))
            for k in rec:
                if age < k: rec[k].append((title[:60], g, known, mp3, (p.get("variants") or [{}])[0].get("price")))
        for k in rec:
            e["new_%dd" % k] = len(rec[k]); e["known_%dd" % k] = sum(1 for x in rec[k] if x[2]); e["mp3_%dd" % k] = sum(1 for x in rec[k] if x[3])
        e["sample"] = rec[30][:12]
        e["all"] = [{"title": p.get("title"), "vendor": p.get("vendor"), "type": p.get("product_type"), "tags": p.get("tags"),
                     "pub": (p.get("published_at") or "")[:10], "created": (p.get("created_at") or "")[:10],
                     "mp3": bool(re.search(r"\.mp3", p.get("body_html") or "")), "price": (p.get("variants") or [{}])[0].get("price"),
                     "handle": p.get("handle")} for p in prods]
        e["tags_example"] = (prods[0].get("tags") if prods else [])[:12]
    res.append(e)
    print(json.dumps({k: v for k, v in e.items() if k != "sample"}), file=sys.stderr)
    time.sleep(1)
os.makedirs("probe", exist_ok=True)
json.dump(res, open("probe/us.json", "w"), indent=1, ensure_ascii=False)
