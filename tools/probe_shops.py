#!/usr/bin/env python3
"""One-off check of candidate shops: reachable from a data centre? Shopify (products.json)? mp3 links?"""
import json, re, sys, time, urllib.request
UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_5) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0 Safari/537.36"
def get(u):
    try:
        r = urllib.request.urlopen(urllib.request.Request(u, headers={"User-Agent": UA, "Accept": "text/html,application/json,*/*"}), timeout=30)
        b = r.read().decode("utf-8", "replace")
        return r.status, r.url, b, dict(r.headers)
    except Exception as e:
        return getattr(e, "code", None) or str(e)[:120], u, "", {}
out = []
for base in [l.strip() for l in open(sys.argv[1]) if l.strip() and not l.startswith("#")]:
    st, final, body, h = get(base)
    e = {"base": base, "status": st, "final": final, "len": len(body), "server": h.get("Server", ""), "powered": h.get("X-Powered-By", ""),
         "title": (re.search(r"<title[^>]*>(.*?)</title>", body, re.S | re.I) or [None, ""])[1].strip()[:90],
         "mp3": len(set(re.findall(r"https?://[^\s\"'<>]+?\.mp3", body))), "shopify": "cdn.shopify.com" in body,
         "woo": "woocommerce" in body.lower(), "challenge": bool(re.search(r"cf-chl|challenge-platform|captcha|JS-CH|Just a moment", body, re.I)),
         "links": sorted(set(re.findall(r'href="(/[^"#?]*(?:new|neu|latest|release|arrival|nouveau|novedad)[^"]*)"', body, re.I)))[:15]}
    if e["shopify"] or "myshopify" in body:
        s2, _, b2, _ = get(base.rstrip("/") + "/products.json?limit=10")
        try:
            pj = json.loads(b2).get("products", [])
            e["products_json"] = len(pj)
            e["sample"] = [(p["title"][:60], p.get("vendor"), (p.get("published_at") or "")[:10], ",".join(p.get("tags", []))[:80],
                            len(re.findall(r"\.mp3", p.get("body_html") or ""))) for p in pj[:6]]
        except Exception as ex:
            e["products_json"] = "fail %s %s" % (s2, str(ex)[:60])
    out.append(e)
    print(json.dumps(e, ensure_ascii=False), file=sys.stderr)
    time.sleep(1)
print(json.dumps(out, indent=1, ensure_ascii=False))
