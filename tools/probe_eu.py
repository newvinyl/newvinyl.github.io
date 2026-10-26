#!/usr/bin/env python3
"""One-off debug: raw data for Divert (Woo API) and Carpet & Snares (list + release pages)."""
import json, os, re, sys, time
sys.path.insert(0, os.path.dirname(__file__))
from fetch_pages import fetch
os.makedirs("probe", exist_ok=True)
st, b = fetch("https://www.divertrecords.sk/wp-json/wc/store/v1/products?per_page=40&orderby=date&order=desc")
open("probe/divert_api.json", "w").write(b)
st, b = fetch("https://shop.carpetandsnares.com/catalogue?sort=added&order=-1")
open("probe/cs_list.html", "w").write(b)
paths = list(dict.fromkeys(re.findall(r'href="(/release/\d+/[^"]+)"', b)))[:3]
for i, p in enumerate(paths):
    time.sleep(1)
    st, rb = fetch("https://shop.carpetandsnares.com" + p)
    open("probe/cs_rel%d.html" % i, "w").write(rb)
print(len(paths), file=sys.stderr)
