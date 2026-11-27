#!/usr/bin/env python3
"""Stock check (user, 27.11.26): records leave a shop's new-release page after a week or two, so the
daily update never sees them sell out. This script revisits the product pages of recent records
(first_seen within DAYS) directly at the shop and updates "st" in releases.json ("in", "low", "pre", "out").
Feed and Beta crate dim sold-out records and lock the bag. Each run checks at most BUDGET products per
shop, oldest check first (tools/stock_state.json keeps the last check per url), so all are covered every
few days. Only reads public product pages at a slow pace, nothing is bypassed.

  python3 tools/stock_check.py           check and write releases.json
  python3 tools/stock_check.py --probe   write snippets of sample product pages to tools/stock_probe.txt
"""
import datetime as dt, json, os, re, sys, time, urllib.request, urllib.parse, html as H
from concurrent.futures import ThreadPoolExecutor

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REL = os.path.join(ROOT, "releases.json")
STATE = os.path.join(ROOT, "tools", "stock_state.json")
DAYS, BUDGET, PAUSE = 60, 500, 0.8
UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"
SKIP = {"www.juno.co.uk"}        # Juno blocks automated requests since 15.11.26, not bypassed

def fetch(url):
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "text/html,application/json,*/*", "Accept-Language": "en,de;q=0.8"})
    with urllib.request.urlopen(req, timeout=40) as r:
        return r.status, r.read().decode(r.headers.get_content_charset() or "utf-8", "replace")

def probe():
    d = json.load(open(REL))
    by = {}
    for s in d["shops"]:
        for i in s["items"]:
            host = urllib.parse.urlparse(i["url"]).netloc
            if host in SKIP or i.get("first_seen", "") < "2026-10-01":
                continue
            b = by.setdefault(host, {})
            b.setdefault(i.get("st") or "-", []).append(i["url"])
    out = []
    pat = re.compile(r"(?i)(sold.?out|out.of.stock|in.stock|instock|outofstock|availab|add.to.(cart|basket|bag)|basket|warenkorb|pre.?order|backorder|disabled|ausverkauft|vergriffen|niet.op.voorraad|op.voorraad|épuisé|rupture|stock)")
    for host, b in sorted(by.items()):
        for st in ("out", "in", "-", "pre"):
            for url in (b.get(st) or [])[:1]:
                out.append("=" * 100 + "\n%s  st=%s  %s" % (host, st, url))
                try:
                    code, body = fetch(url)
                    body = re.sub(r"\s+", " ", body)
                    out.append("HTTP %s len %d" % (code, len(body)))
                    seen = 0
                    for m in pat.finditer(body):
                        if seen >= 25: break
                        out.append("  ..." + body[max(0, m.start() - 110): m.end() + 110] + "...")
                        seen += 1
                except Exception as e:
                    out.append("ERROR %r" % e)
                time.sleep(1)
    open(os.path.join(ROOT, "tools", "stock_probe.txt"), "w").write("\n".join(out) + "\n")

if __name__ == "__main__":
    if "--probe" in sys.argv:
        probe()
