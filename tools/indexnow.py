#!/usr/bin/env python3
"""Meldet neue/geänderte URLs per IndexNow an Bing (und damit DuckDuckGo, Ecosia, Yahoo), Yandex, Seznam, Naver.
Läuft als GitHub Action nach jedem Push von sitemap.xml (.github/workflows/indexnow.yml).
Aufruf:  python3 tools/indexnow.py          -> Startseite, Genre-Seiten und Release-Seiten mit neustem lastmod
         python3 tools/indexnow.py --all    -> alle URLs aus sitemap.xml (max. 10'000)
Der Schlüssel liegt als <key>.txt im Repo-Root (muss online bleiben)."""
import glob, json, os, re, sys, urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HOST = "monthlyvinyl.net"
keyfile = [f for f in glob.glob(os.path.join(ROOT, "*.txt")) if re.fullmatch(r"[0-9a-f]{32}\.txt", os.path.basename(f))][0]
key = os.path.basename(keyfile)[:-4]

sm = open(os.path.join(ROOT, "sitemap.xml"), encoding="utf-8").read()
entries = re.findall(r"<loc>([^<]+)</loc><lastmod>([^<]+)</lastmod>", sm)
if "--all" in sys.argv:
    urls = [u for u, _ in entries]
else:
    rel = [(u, d) for u, d in entries if "/r/" in u]
    newest = max((d for _, d in rel), default="")
    urls = [u for u, _ in entries if "/r/" not in u] + [u for u, d in rel if d == newest]
urls = urls[:10000]
body = json.dumps({"host": HOST, "key": key, "keyLocation": f"https://{HOST}/{key}.txt", "urlList": urls}).encode()
req = urllib.request.Request("https://api.indexnow.org/indexnow", data=body,
                             headers={"Content-Type": "application/json; charset=utf-8"})
try:
    with urllib.request.urlopen(req, timeout=60) as r:
        print(f"IndexNow: {len(urls)} URLs gemeldet, HTTP {r.status}")
except Exception as ex:
    # Nie als Fehler enden (keine Fehler-Mails): z.B. 403 SiteVerificationNotCompleted, solange Bing den
    # Schlüssel noch prüft, oder 429. Der nächste Lauf meldet die URLs erneut.
    detail = ex.read()[:300] if hasattr(ex, "read") else ""
    print(f"::warning::IndexNow nicht angenommen: {ex} {detail!r}")
