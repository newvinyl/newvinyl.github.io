#!/usr/bin/env python3
"""One-off probe of candidate EU shops: reachable? robots? shop system? audio on list page and first product page?"""
import json, os, re, sys, time, urllib.request, urllib.parse, urllib.robotparser
UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_5) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0 Safari/537.36"
AUD = re.compile(r"""https?:(?:\\?/){2}[^\s"'<>]+?\.(?:mp3|m4a|ogg)(?:\?[^\s"'<>]*)?""", re.I)
def get(u):
    try:
        r = urllib.request.urlopen(urllib.request.Request(u, headers={"User-Agent": UA, "Accept": "text/html,application/json,*/*"}), timeout=30)
        return r.status, r.read().decode("utf-8", "replace")
    except Exception as e:
        return getattr(e, "code", None) or str(e)[:80], ""
def system(b):
    s = []
    for k, pat in (("shopify", "cdn.shopify.com"), ("woo", "woocommerce"), ("commonground", "creators-audio-snippets|/release/\\d+/"), ("idosell", "iai-shop|idosell"),
                   ("prestashop", "prestashop"), ("squarespace", "squarespace"), ("nextjs", "__next")):
        if re.search(pat, b, re.I): s.append(k)
    return s
os.makedirs("probe", exist_ok=True)
res = []
for line in [l.strip() for l in open(sys.argv[1]) if l.strip() and not l.startswith("#")]:
    name, url, *pat = line.split()
    host = "{0.scheme}://{0.netloc}".format(urllib.parse.urlparse(url))
    rp = urllib.robotparser.RobotFileParser(host + "/robots.txt")
    try: rp.read(); robots_ok = rp.can_fetch("*", url)
    except Exception: robots_ok = None
    st, body = get(url)
    open("probe/%s_list.html" % name, "w").write(body)
    e = {"name": name, "url": url, "status": st, "len": len(body), "robots_ok": robots_ok, "system": system(body),
         "audio_list": len(set(AUD.findall(body))), "sample": list(dict.fromkeys(AUD.findall(body)))[:2],
         "years": {y: body.count(y) for y in ("2026", "2025")}}
    links = list(dict.fromkeys(urllib.parse.urljoin(url, h) for h in re.findall(r'href="([^"#]+)"', body)))
    rx = re.compile(pat[0]) if pat else re.compile(r"/(product|products|release|item|p)/[^/?]+|-p\d+\.html|/\d+-[a-z0-9-]+\.html")
    prod = [l for l in links if rx.search(l) and urllib.parse.urlparse(l).netloc == urllib.parse.urlparse(url).netloc]
    e["n_prod"] = len(prod); e["prod_examples"] = prod[:3]
    if prod:
        time.sleep(1.5)
        s2, pb = get(prod[0])
        open("probe/%s_prod.html" % name, "w").write(pb)
        e["prod_status"] = s2; e["audio_prod"] = len(set(AUD.findall(pb))); e["sample_prod"] = list(dict.fromkeys(AUD.findall(pb)))[:2]
        e["embeds"] = sorted(set(re.findall(r"(soundcloud|bandcamp|youtube)\.com", pb)))
    if "shopify" in e["system"]:
        s3, pj = get(host + "/products.json?limit=5"); e["products_json"] = s3
    if "woo" in e["system"]:
        s3, pj = get(host + "/wp-json/wc/store/v1/products?per_page=5"); e["woo_api"] = s3
    res.append(e); print(json.dumps(e)[:400], file=sys.stderr); time.sleep(1.5)
json.dump(res, open("probe/eu.json", "w"), indent=1)
