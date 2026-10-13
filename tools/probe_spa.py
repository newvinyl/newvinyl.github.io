#!/usr/bin/env python3
"""Probe a JavaScript shop page with a real browser: rendered text, links and the JSON requests it makes."""
import json, sys
from playwright.sync_api import sync_playwright
urls = sys.argv[1:]
out = []
with sync_playwright() as p:
    b = p.chromium.launch()
    pg = b.new_page(user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 14_5) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0 Safari/537.36")
    reqs = []
    pg.on("response", lambda r: reqs.append((r.status, r.request.resource_type, r.url, r.headers.get("content-type", ""))))
    for u in urls:
        reqs.clear()
        try:
            pg.goto(u, wait_until="domcontentloaded", timeout=60000)
            pg.wait_for_timeout(9000)
            txt = pg.inner_text("body")[:6000]
            links = pg.eval_on_selector_all("a[href]", "els=>[...new Set(els.map(e=>e.href))].slice(0,400)")
        except Exception as e:
            txt, links = "ERROR %s" % e, []
        js = [r for r in reqs if "json" in r[3] or r[1] in ("xhr", "fetch")]
        out.append({"url": u, "final": pg.url, "text": txt, "links": links, "api": js[:80]})
    b.close()
print(json.dumps(out, indent=1, ensure_ascii=False))
