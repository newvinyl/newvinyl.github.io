#!/usr/bin/env python3
"""One-off: Common Ground product pages (track markup) + Divert audio with browser headers."""
import json, os, re, sys, time, urllib.request
UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_5) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0 Safari/537.36"
os.makedirs("probe", exist_ok=True)
def get(u, h=None):
    try:
        r = urllib.request.urlopen(urllib.request.Request(u, headers=dict({"User-Agent": UA}, **(h or {}))), timeout=30)
        return r.status, r.read(3000 if u.endswith(".mp3") else 10**8)
    except Exception as e:
        return repr(e)[:100], b""
for name, base, path in (("carpet", "https://shop.carpetandsnares.com", "/catalogue?sort=added&order=-1"), ("kma", "https://www.kma60.com", "/collection/2/new-arrivals?sort=added&order=-1")):
    st, b = get(base + path); b = b.decode("utf-8", "replace")
    paths = list(dict.fromkeys(re.findall(r'href="(/release/\d+/[^"]+)"', b)))[:2]
    for i, p in enumerate(paths):
        time.sleep(1); st, pb = get(base + p); open("probe/%s_rel%d.html" % (name, i), "wb").write(pb); print(name, p, st, len(pb), file=sys.stderr)
u = "https://www.divertrecords.sk/wp-content/uploads/2026/10/a-sirob-leon-ge-mini-where-is-my-lipgloss-wiml001-vinyl.mp3"
for h in ({}, {"Referer": "https://monthlyvinyl.net/"}, {"Referer": "https://www.divertrecords.sk/", "Accept": "audio/*,*/*", "Range": "bytes=0-1000"},
          {"Accept": "*/*", "Accept-Language": "en", "Sec-Fetch-Dest": "audio", "Range": "bytes=0-"}):
    st, x = get(u, h); print("divert", h, st, len(x), file=sys.stderr); time.sleep(1)
