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
DAYS, BUDGET, PAUSE = 60, 700, 0.8
UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"
TMP = os.path.join(os.environ.get("RUNNER_TEMP", "/tmp"), "stock_changes.json")
SKIP = {"www.juno.co.uk"}        # Juno blocks automated requests since 15.11.26, not bypassed

def q(url):
    return urllib.parse.quote(url, safe=":/?&=%[]#+,;@!$'()*~")

def fetch(url):
    url = q(url)
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

# ---------------------------------------------------------------- readers: url, old st -> new st or None (unknown, keep)
SCHEMA = {"InStock": "in", "LimitedAvailability": "low", "PreOrder": "pre", "PreSale": "pre", "BackOrder": "pre",
          "OutOfStock": "out", "SoldOut": "out", "Discontinued": "out"}

def by_schema(url, old):
    """schema.org Product offer in the page (Redeye, Decks, Yoyaku, SoundGround, Common Ground shops)."""
    _, body = fetch(url)
    m = re.search(r'"availability"\s*:\s*"https?://schema\.org/(\w+)"', body)
    st = SCHEMA.get(m.group(1)) if m else None
    if st == "out" and old == "pre" and "soundground" in url:
        return "pre"                      # SoundGround marks some upcoming records as out of stock
    return keep_pre(st, old) if st == "in" else st   # schema.org tells pre-order and sold out apart

def shopify(url, old):
    _, body = fetch(url.split("?")[0].rstrip("/") + ".js")
    return keep_pre("in" if json.loads(body).get("available") else "out", old)

def woo(url, old):
    u = urllib.parse.urlparse(url)
    slug = [x for x in u.path.split("/") if x][-1]
    _, body = fetch("%s://%s/wp-json/wc/store/v1/products?slug=%s" % (u.scheme, u.netloc, urllib.parse.quote(slug)))
    js = json.loads(body)
    if not js:
        return "out"                      # product taken offline
    return keep_pre("in" if js[0].get("is_in_stock") else "out", old)

def hardwax(url, old):
    _, body = fetch(url)
    iid = re.search(r"hardwax\.com/(\w+)/", url).group(1)
    m = re.search(r'id="item-%s"(.{0,400})' % re.escape(iid), body, re.S)
    if not m:
        return None
    return "out" if "out of stock" in m.group(1) else "in"

def keep_pre(st, old):
    if st == "in" and old in ("pre", "low"):
        return old                        # these systems cannot tell pre-order or low stock apart from "in"
    if st == "out" and old == "pre":
        return old                        # Shopify/Woo shops list upcoming records as "out of stock" (Bordello: outofstock.upcoming)
    return st

READ = {"www.redeyerecords.co.uk": by_schema, "www.decks.de": by_schema, "yoyaku.io": by_schema,
        "www.soundground.bg": by_schema, "shop.carpetandsnares.com": by_schema, "www.discosparadiso.com": by_schema,
        "www.vinylunderground.co.uk": shopify, "rubadub.co.uk": shopify,
        "bordelloaparigi.com": woo, "diggers.fr": woo, "www.ultrasuonirecords.com": woo, "www.divertrecords.sk": woo,
        "hardwax.com": hardwax}
# Not (yet) readable: Clone and Kompakt (no clear marker), Deejay.de (403), Phonica (307), Juno (blocked), others small.

def check():
    d = json.load(open(REL))
    state = json.load(open(STATE)) if os.path.exists(STATE) else {}
    since = (dt.date.today() - dt.timedelta(days=DAYS)).isoformat()
    today = dt.date.today().isoformat()
    todo = {}
    for s in d["shops"]:
        for i in s["items"]:
            host = urllib.parse.urlparse(i.get("url", "")).netloc
            if host in READ and i.get("first_seen", "") >= since:
                todo.setdefault(host, []).append(i)
    def run(host):
        items = sorted(todo[host], key=lambda i: (state.get(i["url"], ""), i.get("first_seen", "")))[:BUDGET]
        n = ch = err = 0
        for i in items:
            if state.get(i["url"]) == today:
                continue
            try:
                st = READ[host](i["url"], i.get("st", ""))
                n += 1
                state[i["url"]] = today
                if st and st != i.get("st"):
                    log.append("%s  %s -> %s  %s" % (host, i.get("st") or "-", st, i["url"]))
                    changes[i["url"]] = st
                    i["st"] = st
                    ch += 1
            except Exception as e:
                err += 1
                if err >= 8 and n == 0:
                    break                 # shop does not answer today, try again tomorrow
            time.sleep(PAUSE)
        return "%s: %d checked, %d changed, %d errors (%d in window)" % (host, n, ch, err, len(todo[host]))
    log, changes = [], {}
    with ThreadPoolExecutor(len(todo) or 1) as ex:
        summary = list(ex.map(run, sorted(todo)))
    keep = {i["url"] for v in todo.values() for i in v}
    state = {u: v for u, v in state.items() if u in keep}
    with open(REL, "w") as f:
        json.dump(d, f, ensure_ascii=False, indent=1)
    json.dump(state, open(STATE, "w"), separators=(",", ":"), sort_keys=True)
    outn = sum(1 for v in todo.values() for i in v if i.get("st") == "out")
    head = "Stock check %s: %d changes, %d sold out of %d checkable records" % (today, len(log), outn, len(keep))
    run_txt = "\n".join([head] + summary + [""] + log) + "\n"
    open(os.path.join(ROOT, "tools", "stock_run.txt"), "w").write(run_txt)
    json.dump({"changes": changes, "state": state, "run": run_txt}, open(TMP, "w"))
    print(head)

def reapply():
    """After a push conflict: fresh checkout, apply only today's changes again (no new requests)."""
    t = json.load(open(TMP))
    d = json.load(open(REL))
    for s in d["shops"]:
        for i in s["items"]:
            if i.get("url") in t["changes"]:
                i["st"] = t["changes"][i["url"]]
    with open(REL, "w") as f:
        json.dump(d, f, ensure_ascii=False, indent=1)
    json.dump(t["state"], open(STATE, "w"), separators=(",", ":"), sort_keys=True)
    open(os.path.join(ROOT, "tools", "stock_run.txt"), "w").write(t["run"])

if __name__ == "__main__":
    if "--probe" in sys.argv:
        probe()
    elif "--reapply" in sys.argv:
        reapply()
    else:
        check()
