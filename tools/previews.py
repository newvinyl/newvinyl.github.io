#!/usr/bin/env python3
"""Hörproben-Sicherung für monthlyvinyl.net (läuft als GitHub Action).

1. Liest releases.json (wird vom täglichen Update geschrieben).
2. Holt für Platten ohne Einzeltrack-Hörproben die Clips direkt von der Produktseite
   des Shops (Rush Hour, Phonica, Kompakt, Yoyaku; Redeye: Trackliste zum Gesamtclip).
3. Übernimmt Einzeltracks von derselben Platte in einem anderen Shop.
4. Prüft JEDE Hörprobe per HTTP; was nicht antwortet, fliegt raus.
5. Schreibt das Ergebnis nach OUT (Standard: beta/releases.json) und einen Statusbericht.

Respektiert robots.txt, bremst pro Shop, umgeht keine Bot-Sperren.
"""
import concurrent.futures as cf
import datetime
import html
import json
import os
import re
import sys
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
import urllib.robotparser
from zoneinfo import ZoneInfo

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "tools"))
from build_static import norm, parse_tracklist  # noqa: E402

SRC = os.environ.get("SRC", os.path.join(ROOT, "releases.json"))
OUT = os.environ.get("OUT", os.path.join(ROOT, "beta", "releases.json"))
CACHE = os.path.join(ROOT, "tools", "preview_cache.json")
STATUS = os.path.join(os.path.dirname(OUT), "status.json")
UA = "MonthlyVinylBot/1.0 (+https://monthlyvinyl.net; preview check for listed records)"
TODAY = datetime.datetime.now(ZoneInfo("Europe/Zurich")).date()
RETRY_DAYS = 14          # Platten ohne Hörprobe so lange täglich neu prüfen
PAGE_DELAY = {"default": 1.0, "www.rushhour.nl": 2.5, "www.phonicarecords.com": 4.0}
REDEYE_CLIP = "sounds.redeyerecords.co.uk"


# ---------------------------------------------------------------- HTTP
_host_lock = {}
_host_last = {}
_robots = {}
_glock = threading.Lock()


def _polite(host):
    with _glock:
        lk = _host_lock.setdefault(host, threading.Lock())
    with lk:
        wait = PAGE_DELAY.get(host, PAGE_DELAY["default"]) - (time.time() - _host_last.get(host, 0))
        if wait > 0:
            time.sleep(wait)
        _host_last[host] = time.time()


def allowed(url):
    p = urllib.parse.urlparse(url)
    base = f"{p.scheme}://{p.netloc}"
    with _glock:
        rp = _robots.get(base)
    if rp is None:
        rp = urllib.robotparser.RobotFileParser()
        try:
            req = urllib.request.Request(base + "/robots.txt", headers={"User-Agent": UA})
            with urllib.request.urlopen(req, timeout=20) as r:
                rp.parse(r.read().decode("utf-8", "replace").splitlines())
        except Exception:
            rp.parse([])  # keine robots.txt -> erlaubt
        with _glock:
            _robots[base] = rp
    return rp.can_fetch(UA, url) and rp.can_fetch("*", url)


def get_page(url, tries=3):
    """Produktseite holen (höflich, mit robots.txt). None bei Fehler/Verbot."""
    if not allowed(url):
        return None, "robots"
    host = urllib.parse.urlparse(url).netloc
    err = "http429"
    for t in range(tries):
        _polite(host)
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "text/html,application/xhtml+xml", "Accept-Language": "en"})
            with urllib.request.urlopen(req, timeout=90) as r:
                body = r.read().decode("utf-8", "replace")
                if re.search(r"<title>\s*(Just a moment|Nur einen Moment|Attention Required)", body) or ("_cf_chl_opt" in body and len(body) < 40000):
                    return None, "botcheck"
                return body, "ok"
        except urllib.error.HTTPError as e:
            if e.code in (429, 503):
                time.sleep(15 * (t + 1))  # Shop bremst -> warten statt abbrechen
                continue
            return None, f"http{e.code}"
        except Exception as e:
            err = type(e).__name__
            time.sleep(5 * (t + 1))
    return None, "failed:" + err


def check_audio(url):
    """True, wenn der Clip antwortet und nach Audio aussieht."""
    host = urllib.parse.urlparse(url).netloc
    for t in range(2):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA, "Range": "bytes=0-1023"})
            with urllib.request.urlopen(req, timeout=25) as r:
                ct = (r.headers.get("Content-Type") or "").lower()
                data = r.read(1024)
                if r.status not in (200, 206) or not data:
                    return False
                if "html" in ct or data.lstrip()[:1] == b"<":
                    return False
                return True
        except urllib.error.HTTPError as e:
            if e.code in (429, 503) and t == 0:
                time.sleep(5)
                continue
            return False
        except Exception:
            if t == 0:
                time.sleep(2)
                continue
            return False
    return False


# ---------------------------------------------------------------- Extraktoren
def tracks_rushhour(page):
    out = []
    for li in re.findall(r'<li class="[^"]*\btrack\b[^"]*"\s*>(.*?)</li>', page, re.S):
        u = re.search(r'field-name-field-audio[^>]*>\s*(https://objectstore\.true\.nl/[^<\s]+\.mp3)', li)
        n = re.search(r'field-name-field-title"[^>]*>(.*?)</div>', li, re.S)
        if u:
            out.append({"s": "", "n": html.unescape(re.sub("<[^>]+>", "", n.group(1))).strip() if n else "Track", "u": u.group(1)})
    for i, t in enumerate(out):
        m = re.search(r"[-_](\d?)([a-d]\d?)[_.]", t["u"].rsplit("/", 1)[-1].lower())
        if m:
            t["s"] = m.group(2).upper()
    return out


PHONICA_AUDIO = "https://dmpqep8cljqhc.cloudfront.net/"


def tracks_phonica(page):
    # Erster Hörproben-Block auf der Seite gehört zur Hauptplatte (danach folgen Empfehlungen)
    i = page.find("single-listenall")
    if i < 0:
        return []
    j = page.find('class="archive-playlist', i)
    if j < 0:
        return []
    block = page[j:j + 20000]
    end = re.search(r"</span>\s*</span>", block)
    block = block[: end.end()] if end else block[:4000]
    out = []
    for fid, name in re.findall(r'<span id="([0-9a-f]{32})\.mp3"\s*>([^<]*)</span>', block):
        out.append({"s": "", "n": html.unescape(name).strip() or "Track", "u": PHONICA_AUDIO + fid + ".mp3"})
    return out


def tracks_kompakt(page):
    out = []
    for li in re.findall(r'<ul[^>]*class="[^"]*track[^"]*"[^>]*>(.*?)</ul>', page, re.S) or [page]:
        for title, src in re.findall(r'<li class="title">([^<]*)</li>.*?<li class="audio-src">([^<]*)</li>', li, re.S):
            u = html.unescape(src).split("?")[0]  # signierte Links laufen nach 3 h ab -> ungesignierte Adresse testen
            out.append({"s": "", "n": html.unescape(title).strip(), "u": u})
    seen, res = set(), []
    for t in out:
        if t["u"] not in seen:
            seen.add(t["u"])
            res.append(t)
    return res


def tracks_yoyaku(page):
    """Yoyaku lädt die Clips über seine öffentliche Player-API (/wp-json/fwap/v1/track/<Produkt-ID>)."""
    m = re.search(r'"current_product_id":(\d+)', page) or re.search(r'class="alltracks fwap-play" data-product="(\d+)"', page)
    if not m:
        return []
    body, st = get_page(f"https://yoyaku.io/wp-json/fwap/v1/track/{m.group(1)}")
    if not body:
        return []
    try:
        js = json.loads(body)
    except ValueError:
        return []
    out = []
    for t in js.get("data") or []:
        if t.get("mp3") and t.get("playable", True):
            out.append({"s": "", "n": (t.get("title") or "Track").strip(), "u": t["mp3"]})
    return out


def tracks_clone(page):
    out = []
    for href, title in re.findall(r'<a class="preview"[^>]*href="(https://clone\.nl/platen/mp3/[^"]+\.mp3)"[^>]*title="([^"]*)"', page):
        name = html.unescape(title).rsplit(" - ", 1)[-1].strip()
        m = re.match(r"^(\d{1,2}|[A-D]\d?)\s+(.+)$", name)
        s, n = (m.group(1), m.group(2)) if m else ("", name)
        out.append({"s": s, "n": n, "u": urllib.parse.quote(html.unescape(href), safe=":/%")})
    return out


def tracklist_redeye(page):
    m = re.search(r'<[^>]+class="tracks"[^>]*>(.*?)</(?:p|div|span|li)>', page, re.S)
    if not m:
        return []
    txt = html.unescape(re.sub(r"<br\s*/?>", " | ", m.group(1)))
    txt = re.sub("<[^>]+>", "", txt)
    return parse_tracklist(" | ".join(s.strip() for s in txt.split("|") if s.strip()))


EXTRACT = {
    "Clone": tracks_clone,
    "Rush Hour": tracks_rushhour,
    "Phonica": tracks_phonica,
    "Kompakt": tracks_kompakt,
    "Yoyaku": tracks_yoyaku,
}


# ---------------------------------------------------------------- Hilfen
def per_track(r):
    """Hat die Platte mindestens eine Einzeltrack-Hörprobe (nicht nur Redeyes Gesamtclip)?"""
    return any((t.get("u") and REDEYE_CLIP not in t["u"]) or t.get("yt") or t.get("ytl") for t in r.get("tr", []))


def playable(r):
    return any(t.get("u") or t.get("yt") or t.get("ytl") for t in r.get("tr", []))


def rkey(r):
    return (norm(r.get("a")), norm(re.split(r"\s+-\s+", r.get("t") or "", maxsplit=1)[0]))


def main():
    data = json.load(open(SRC, encoding="utf-8"))
    cache = json.load(open(CACHE, encoding="utf-8")) if os.path.exists(CACHE) else {}
    now = f"{TODAY.year}-{TODAY.month:02d}"
    pm = TODAY.month - 1 or 12
    prev = f"{TODAY.year if TODAY.month > 1 else TODAY.year - 1}-{pm:02d}"
    months = {now, prev}
    items = [(S, r) for S in data.get("shops", []) for r in (S.get("items") or []) if r.get("m") in months]

    ver = cache.setdefault("_verified", {})
    hosts = {}
    unverifiable = set()
    removed = 0

    def verify_and_prune():
        nonlocal removed, unverifiable
        urls = sorted({t["u"] for _, r in items for t in r.get("tr", []) if t.get("u")})
        need = [u for u in urls if ver.get(u, {}).get("d") != str(TODAY)]
        with cf.ThreadPoolExecutor(max_workers=12) as ex:
            for u, ok in zip(need, ex.map(check_audio, need)):
                ver[u] = {"d": str(TODAY), "ok": ok}
        # Hosts, die aus dem Rechenzentrum generell nicht antworten (Bot-Schutz), nicht bestrafen:
        # fällt die Mehrheit eines Hosts durch, gelten seine Clips als «nicht prüfbar» und bleiben drin.
        hosts.clear()
        for u in urls:
            d = hosts.setdefault(urllib.parse.urlparse(u).netloc, [0, 0, []])
            d[0] += 1
            if not ver.get(u, {}).get("ok"):
                d[1] += 1
                if len(d[2]) < 3:
                    d[2].append(u)
        unverifiable = {h for h, (n, f, _) in hosts.items() if n >= 5 and f / n > 0.5}
        bad = {u for u in urls if not ver.get(u, {}).get("ok") and urllib.parse.urlparse(u).netloc not in unverifiable}
        for _, r in items:
            n0 = len(r.get("tr", []))
            r["tr"] = [t for t in r.get("tr", []) if not (t.get("u") and t["u"] in bad)]
            removed += n0 - len(r["tr"])
        return urls

    # 1) Alle vorhandenen Hörproben prüfen, defekte entfernen
    verify_and_prune()

    # Bereits Gefundenes aus dem Cache einsetzen (auch dort, wo gerade defekte Clips entfernt wurden)
    for S, r in items:
        c = cache.get(r.get("url"), {})
        if c.get("tl") and not r.get("tl"):
            r["tl"] = c["tl"]
        if c.get("tr") and not per_track(r):
            r["tr"] = [dict(t) for t in c["tr"]]

    # 2) Für Platten ohne (funktionierende) Einzeltracks die Produktseite des Shops lesen
    todo = []
    for S, r in items:
        shop, url = S["shop"], r.get("url")
        if not url:
            continue
        c = cache.get(url, {})
        if c.get("checked") == str(TODAY):
            continue
        if shop == "Redeye Records":
            if not r.get("tl"):
                todo.append((S, r))
            continue
        if shop not in EXTRACT or per_track(r):
            continue
        first = c.get("first_try", str(TODAY))
        if (TODAY - datetime.date.fromisoformat(first)).days > RETRY_DAYS:
            continue
        todo.append((S, r))

    stats = {"pages": 0, "found": 0, "blocked": {}}

    def work(sr):
        S, r = sr
        page, st = get_page(r["url"])
        return S, r, page, st

    with cf.ThreadPoolExecutor(max_workers=6) as ex:
        for S, r, page, st in ex.map(work, todo):
            c = cache.setdefault(r["url"], {"first_try": str(TODAY)})
            c["checked"] = str(TODAY)
            stats["pages"] += 1
            if page is None:
                k = f'{S["shop"]}: {st}'
                stats["blocked"][k] = stats["blocked"].get(k, 0) + 1
                continue
            if S["shop"] == "Redeye Records":
                tl = tracklist_redeye(page)
                if len(tl) > 1:
                    c["tl"] = r["tl"] = tl
                continue
            tr = EXTRACT[S["shop"]](page)
            if tr:
                c["tr"] = tr
                r["tr"] = [dict(t) for t in tr]
                stats["found"] += 1

    # Neu Gefundenes ebenfalls prüfen
    urls = verify_and_prune()

    # 3) Einzeltracks von derselben Platte in einem anderen Shop übernehmen
    best = {}
    for S, r in items:
        if per_track(r):
            k = rkey(r)
            n = sum(1 for t in r["tr"] if t.get("u") or t.get("yt"))
            if n > len(best.get(k, [])):
                best[k] = [dict(t) for t in r["tr"]]
    copied = 0
    for S, r in items:
        if not per_track(r) and rkey(r) in best:
            r["tr"] = [dict(t) for t in best[rkey(r)]]
            copied += 1

    # Alte Prüfergebnisse aufräumen
    keep = set(urls)
    cache["_verified"] = {u: v for u, v in ver.items() if u in keep}

    # 4) Schreiben + Bericht
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=1)
    with open(CACHE, "w", encoding="utf-8") as f:
        json.dump(cache, f, ensure_ascii=False, indent=0, sort_keys=True)

    per_shop = {}
    for S, r in items:
        d = per_shop.setdefault(S["shop"], {"records": 0, "tracks": 0, "clip": 0, "none": 0})
        d["records"] += 1
        d["tracks" if per_track(r) else "clip" if playable(r) else "none"] += 1
    tot = {k: sum(d[k] for d in per_shop.values()) for k in ("records", "tracks", "clip", "none")}
    report = {"date": str(TODAY), "total": tot, "shops": per_shop, "pages_checked": stats["pages"],
              "new_from_shop_pages": stats["found"], "copied_from_other_shop": copied,
              "broken_clips_removed": removed, "clips_verified": len(urls), "not_reachable": stats["blocked"],
              "clip_hosts": {h: {"clips": n, "failed": f, "sample": smp} for h, (n, f, smp) in sorted(hosts.items())},
              "unverifiable_hosts": sorted(unverifiable)}
    with open(STATUS, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=1)
    pct = lambda k: round(100 * tot[k] / max(1, tot["records"]))
    print(f"{tot['records']} Platten: {pct('tracks')}% Einzeltracks, {pct('clip')}% Gesamtclip, {pct('none')}% ohne Hörprobe "
          f"| {stats['found']} neu von Produktseiten, {copied} von anderem Shop, {removed} defekte Clips entfernt")
    for sh, d in sorted(per_shop.items()):
        print(f"  {sh}: {d}")
    if stats["blocked"]:
        print("  nicht erreichbar:", stats["blocked"])


if __name__ == "__main__":
    if len(sys.argv) > 2 and sys.argv[1] == "--probe":
        page, st = get_page(sys.argv[2])
        print("status:", st, "len:", len(page or ""))
        if page and len(sys.argv) > 3:
            for needle in sys.argv[3].split("||"):
                for m in list(re.finditer(re.escape(needle), page))[:3]:
                    print(f"=== {needle} @{m.start()}:\n", page[max(0, m.start() - 200): m.start() + 2500], "\n")
            sys.exit(0)
        if page:
            for pat in [r"\.mp3", r"\.m4a", r"fwa-(?:track|play|item|list)", r"data-(?:track|audio|file|sample|preview)[a-z-]*=", r"admin-ajax|wc-ajax|wp-json", r"tracklist", r"yioAudio\w*\s*=", r"sample|preview"]:
                for m in list(re.finditer(pat, page, re.I))[:3]:
                    print(f"--- {pat} @{m.start()}:", re.sub(r"\s+", " ", page[max(0, m.start() - 250): m.start() + 200]))
        sys.exit(0)
    main()
