#!/usr/bin/env python3
"""One-off: are Rubadub's Dropbox previews playable directly (status, type, range support)?"""
import json, os, urllib.request
UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_5) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0 Safari/537.36"
U = "https://dl.dropbox.com/scl/fi/qo1pb5evjg0sv0q12ixhh/01-Cro-Magnon-A1-Eclipse-DJ-Mitsu-The-Beats-Remix.mp3?rlkey=ntup3e9pqrqtejeqzhqlvmvor&st=xxxf3wjp&dl=0"
os.makedirs("probe", exist_ok=True)
res = {}
for name, h in (("plain", {}), ("range", {"Range": "bytes=1000-1999"}), ("referer", {"Referer": "https://monthlyvinyl.net/", "Range": "bytes=0-99"})):
    try:
        r = urllib.request.urlopen(urllib.request.Request(U, headers=dict(h, **{"User-Agent": UA})), timeout=30)
        b = r.read(4000)
        res[name] = [r.status, r.geturl()[:120], r.headers.get("Content-Type"), r.headers.get("Content-Length"), r.headers.get("Accept-Ranges"),
                     r.headers.get("Access-Control-Allow-Origin"), b[:4].hex()]
    except Exception as e:
        res[name] = [getattr(e, "code", None), str(e)[:100]]
json.dump(res, open("probe/log.json", "w"), indent=1)
