#!/usr/bin/env python3
"""One-off probe: which US shops expose audio previews? Saves list page + first product page, counts audio refs."""
import json, os, re, sys, time, urllib.request, urllib.parse
UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_5) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0 Safari/537.36"
AUD = re.compile(r"""(?:https?:)?//[^\s"'<>]+?\.(?:mp3|m4a|ogg|wav)(?:\?[^\s"'<>]*)?""", re.I)
def get(u):
    try:
        r = urllib.request.urlopen(urllib.request.Request(u, headers={"User-Agent": UA}), timeout=30)
        return r.status, r.read().decode("utf-8", "replace")
    except Exception as e:
        return str(e)[:100], ""
os.makedirs("probe", exist_ok=True)
res = []
for line in [l.strip() for l in open(sys.argv[1]) if l.strip() and not l.startswith("#")]:
    name, url = line.split(" ", 1)
    st, body = get(url)
    open("probe/%s_list.html" % name, "w").write(body)
    e = {"name": name, "url": url, "status": st, "len": len(body), "audio_list": len(set(AUD.findall(body))),
         "shopify": "cdn.shopify.com" in body, "sample_audio": list(dict.fromkeys(AUD.findall(body)))[:3]}
    links = [urllib.parse.urljoin(url, h) for h in re.findall(r'href="([^"#]+)"', body)]
    prod = [l for l in links if re.search(r"/(products?|item|release|records?|detail|catalog)/[^/]+", l) and urllib.parse.urlparse(l).netloc == urllib.parse.urlparse(url).netloc]
    prod = list(dict.fromkeys(prod))
    e["n_prod_links"] = len(prod)
    if prod:
        time.sleep(1)
        st2, pb = get(prod[0])
        open("probe/%s_prod.html" % name, "w").write(pb)
        e["prod"] = prod[0]; e["audio_prod"] = len(set(AUD.findall(pb))); e["sample_prod"] = list(dict.fromkeys(AUD.findall(pb)))[:3]
        e["embeds"] = sorted(set(re.findall(r"(soundcloud|bandcamp|youtube|discogs)\.com", pb)))
    res.append(e); print(json.dumps(e), file=sys.stderr)
    time.sleep(1)
json.dump(res, open("probe/audio.json", "w"), indent=1)
