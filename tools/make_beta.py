#!/usr/bin/env python3
"""Erzeugt die versteckte Testseite /beta/ aus index.html (nicht indexiert)."""
import os
import re

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
src = open(os.path.join(ROOT, "index.html"), encoding="utf-8").read()
s = src.replace('href="favicon-32.png"', 'href="/favicon-32.png"').replace('href="apple-touch-icon.png"', 'href="/apple-touch-icon.png"')
s = re.sub(r'<link rel="canonical"[^>]*>', "", s)
s = s.replace("<head>", '<head>\n<meta name="robots" content="noindex,nofollow">', 1)
s = re.sub(r"<title>(.*?)</title>", r"<title>BETA · \1</title>", s, count=1)
s = s.replace(
    "<body>",
    '<body>\n<div style="position:sticky;top:0;z-index:9999;background:#ff2bd6;color:#000;font:600 12px/1.6 ui-monospace,monospace;text-align:center;padding:2px 8px">BETA · Hörproben-Prüfung · <a href="status.json" style="color:#000">Status</a></div>',
    1,
)
os.makedirs(os.path.join(ROOT, "beta"), exist_ok=True)
open(os.path.join(ROOT, "beta", "index.html"), "w", encoding="utf-8").write(s)
print("beta/index.html geschrieben")
