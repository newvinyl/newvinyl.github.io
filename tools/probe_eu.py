#!/usr/bin/env python3
"""One-off: save raw pages / API answers for the new shop feeds."""
import os, sys, time, urllib.request
UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_5) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0 Safari/537.36"
os.makedirs("probe", exist_ok=True)
for line in [l.strip() for l in open(sys.argv[1]) if l.strip() and not l.startswith("#")]:
    name, url = line.split(" ", 1)
    try:
        r = urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": UA}), timeout=30)
        body = r.read().decode("utf-8", "replace"); st = r.status
    except Exception as e:
        body, st = "", str(e)[:80]
    open("probe/" + name, "w").write(body)
    print(name, st, len(body), file=sys.stderr); time.sleep(1.5)
