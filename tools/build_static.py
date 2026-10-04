#!/usr/bin/env python3
"""Baut aus releases.json die für Suchmaschinen und KI lesbaren Teile der Website:
- eine statische Plattenliste in index.html (zwischen <!--STATIC--> und <!--/STATIC-->),
- Genre-Links im Footer (zwischen <!--GENRES--> und <!--/GENRES-->),
- eine Unterseite pro Genre (/techno/, /ambient/ …),
- eine Release-Seite pro Platte (/r/<slug>/) mit Cover, Previews und Preisvergleich (indexierbar),
- sitemap.xml und llms.txt.
Die interaktive Seite überschreibt die statische Liste beim Laden; Besucher sehen davon nichts.
Aufruf im Repo-Ordner:  python3 tools/build_static.py
"""
import json, re, os, html, unicodedata, datetime
from zoneinfo import ZoneInfo

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SITE = "https://monthlyvinyl.net"
CORE = ["House", "Deep House", "Tech House", "Minimal", "Techno", "Dub Techno", "Electro",
        "Acid House", "Balearic", "Ambient", "Disco", "Italo Disco"]
NOT_GENRE = re.compile(r'^(reissue|repress|remaster(ed)?|lp|ep|edits?|2×12"?|12")$', re.I)
REISSUE = re.compile(r'\b(reissue|repress|remaster(ed)?)\b', re.I)
e = lambda s: html.escape(str(s or ""), quote=True)

def slug(s):
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]+", "-", s).strip("-")

RELEASE_CSS = """:root{color-scheme:dark;--bg:#0d0d0d;--fg:#ecebe7;--muted:#a0a4a9;--line:#3c4046;--yellow:#fbed4f;--neon:#39ff14}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--fg);font:16px/1.5 "Helvetica Neue",Helvetica,Arial,sans-serif;-webkit-text-size-adjust:100%}
a{color:var(--fg)}
.wrap{max-width:1080px;margin:0 auto;padding:16px 16px 64px}
.band{display:block;color:var(--yellow);font-weight:800;font-size:clamp(26px,6vw,48px);letter-spacing:-.01em;line-height:1;text-decoration:none;padding:6px 0 14px;border-bottom:4px solid var(--yellow)}
.crumbs{font-size:13px;color:var(--muted);margin:14px 0 22px}
.crumbs a{color:var(--muted)}
.rel{display:grid;grid-template-columns:minmax(0,1fr);gap:24px}
@media (min-width:760px){.rel{grid-template-columns:minmax(0,440px) minmax(0,1fr);gap:40px}}
.cover{width:100%;height:auto;aspect-ratio:1;object-fit:cover;background:#1a1a1a;display:block}
h1{font-size:clamp(28px,4.4vw,44px);line-height:1.05;margin:0 0 6px}
h1 small{display:block;font-size:.62em;font-weight:400;margin-top:6px}
.meta{color:var(--muted);font-size:14px;margin:0 0 16px}
.tags{margin:0 0 20px;display:flex;flex-wrap:wrap;gap:8px}
.tags a{font-size:13px;border:1.5px solid var(--neon);color:var(--neon);padding:3px 10px;text-decoration:none}
.cta{display:inline-block;background:var(--yellow);color:#000;font-weight:700;text-decoration:none;padding:13px 18px;margin:0 0 26px}
h2{font-size:13px;letter-spacing:.08em;text-transform:uppercase;color:var(--muted);margin:26px 0 8px;font-weight:700}
table{width:100%;border-collapse:collapse;font-size:15px}
td{padding:10px 0;border-top:1px solid var(--line);vertical-align:middle}
td.p{text-align:right;white-space:nowrap;font-weight:700;padding-left:12px}
td.go{text-align:right;width:1%;white-space:nowrap;padding-left:14px}
td .w{display:block;color:var(--muted);font-size:12px}
.best td.p{color:var(--yellow)}
.best td.p::before{content:"cheapest ";font-weight:400;font-size:11px;color:var(--yellow);margin-right:4px}
td.p .w{font-weight:400}
ol{list-style:none;margin:0;padding:0}
ol li{display:flex;align-items:center;gap:12px;padding:8px 0;border-top:1px solid var(--line);flex-wrap:wrap}
ol li b{font-family:ui-monospace,Menlo,monospace;font-weight:400;color:var(--muted);font-size:12px;min-width:2.2em}
ol li span{flex:1;min-width:140px}
audio{height:34px;max-width:100%;width:260px}
@media (max-width:520px){ol li span{flex-basis:calc(100% - 3.4em)}audio{width:100%;margin-left:calc(2.2em + 12px)}}
.more{margin-top:52px;border-top:4px solid var(--yellow);padding-top:8px}
.grid{list-style:none;margin:0;padding:0;display:grid;grid-template-columns:repeat(auto-fill,minmax(150px,1fr));gap:20px}
.grid a{text-decoration:none;display:block}
.grid img{width:100%;aspect-ratio:1;object-fit:cover;background:#1a1a1a;display:block;margin-bottom:6px}
.grid b{display:block;font-size:14px;line-height:1.2}
.grid i{font-style:normal;color:var(--muted);font-size:13px}
footer{margin-top:48px;border-top:1px solid var(--line);padding-top:14px;font-size:13px;color:var(--muted)}
"""

def rslug(a, t):
    # muss genau der Funktion rslug() in index.html entsprechen
    return slug(f"{a} {t}")[:80].strip("-")

def hires(u):
    # grösste Cover-Version pro Shop, wie hiRes() in index.html
    if not u: return u
    if re.search(r"media\.hardwax\.com/images/", u) and not u.endswith("big.jpg"): return re.sub(r"\.jpg$", "big.jpg", u)
    if "redeyerecords.co.uk/imagery/" in u: return re.sub(r"-2\.jpg$", "-1.jpg", u)
    if "rushhourrecords" in u: return u.replace("/styles/cover_medium/", "/styles/cover_large/")
    if "clone.nl/platen/artwork/small/" in u: return u.replace("/artwork/small/", "/artwork/large/")
    if "yoyaku.io/wp-content/uploads/" in u: return re.sub(r"-\d+x\d+(\.\w+)$", r"\1", u)
    if "imagescdn.juno.co.uk/300/" in u: return re.sub(r"-MED\.jpg$", "-BIG.jpg", u.replace("/300/", "/full/"))
    if "decks.de/decks/gfx/co_mid/" in u: return u.replace("/co_mid/", "/co_big/")
    return u

def norm(s):
    s = unicodedata.normalize("NFKD", str(s or "").lower())
    s = "".join(c for c in s if not unicodedata.combining(c))
    s = re.sub(r"\(.*?\)|\[.*?\]", "", s)
    s = re.sub(r'\b(ep|lp|12"?|2x12"?)\b', "", s)
    return re.sub(r"[^\w]", "", s)

def genres_of(g):
    out = []
    for part in re.split(r"[/·]", g or ""):
        x = re.sub(r"\s+Edits$", "", part.strip(), flags=re.I)
        if x and not NOT_GENRE.match(x) and x not in out:
            out.append(x)
    return out

SYM = {"€": "€", "£": "£", "$": "$", "CHF": "CHF "}
def price(S, p):
    if p is None: return "price in shop"
    return f'{SYM.get(S.get("cur"), S.get("cur", ""))}{p:.2f}'.replace(".00", "")

def playable(r):
    return any(t.get("u") or t.get("yt") or t.get("ytl") for t in r.get("tr", []))

def fix_redeye_previews(data):
    """Redeye liefert pro Platte nur einen Clip (sounds.redeyerecords.co.uk/ID.mp3),
    der oft noch nicht existiert (404). Führt ein anderer Shop dieselbe Platte mit
    abspielbaren Tracks, übernimmt der Redeye-Eintrag diese Trackliste."""
    def base(t):  # Redeye-Zusatz wie " - Standard Weight, Blue Ripple Coloured Vinyl" weg
        return norm(re.split(r"\s+-\s+", t or "", maxsplit=1)[0])
    good = {}
    for S in data.get("shops", []):
        if S.get("shop") == "Redeye Records":
            continue
        for r in S.get("items") or []:
            tr = [t for t in r.get("tr", []) if t.get("u") and "redeyerecords" not in t["u"]]
            if not tr:
                continue
            k = (norm(r.get("a")), base(r.get("t")))
            if len(tr) > len(good.get(k, [])):
                good[k] = tr
    n = 0
    for S in data.get("shops", []):
        if S.get("shop") != "Redeye Records":
            continue
        for r in S.get("items") or []:
            tr = r.get("tr", [])
            if tr and not all("sounds.redeyerecords" in (t.get("u") or "") for t in tr):
                continue
            src = good.get((norm(r.get("a")), base(r.get("t"))))
            if src:
                r["tr"] = [dict(t) for t in src]
                n += 1
    return n

def main():
    path = os.path.join(ROOT, "releases.json")
    data = json.load(open(path, encoding="utf-8"))
    fixed = fix_redeye_previews(data)
    if fixed:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=1)
        print(f"Redeye: {fixed} Einträge mit vollständiger Trackliste aus anderem Shop")
    today = datetime.datetime.now(ZoneInfo("Europe/Zurich")).date()
    now = f"{today.year}-{today.month:02d}"
    pm = today.month - 1 or 12
    prev = f"{today.year if today.month > 1 else today.year - 1}-{pm:02d}"
    months = {now, prev}
    MONTHS = ["January", "February", "March", "April", "May", "June", "July", "August",
              "September", "October", "November", "December"]
    mlabel = lambda k: f"{MONTHS[int(k[5:]) - 1]} {k[:4]}"

    # Gleiche Platte in mehreren Shops zusammenführen
    groups, order = {}, []
    for S in data["shops"]:
        if S.get("blocked"): continue
        for r in S.get("items", []):
            if r.get("m") not in months: continue
            k = norm(r["a"]) + "|" + norm(r["t"])
            if k not in groups: groups[k] = []; order.append(k)
            groups[k].append((S, r))
    recs = []
    for k in order:
        offers = groups[k]
        S, r = sorted(offers, key=lambda o: (not playable(o[1]), o[1].get("p") is None))[0]
        recs.append({"S": S, "r": r, "offers": offers, "genres": genres_of(r.get("g")),
                     "m": min(o[1]["m"] for o in offers),
                     "seen": min(o[1].get("first_seen", o[1]["m"] + "-01") for o in offers)})
    recs.sort(key=lambda x: x["seen"], reverse=True)

    def offers_html(rec):
        return " · ".join(f'<a href="{e(r.get("url"))}" rel="nofollow noopener">{e(S["shop"])} {e(price(S, r.get("p")))}</a>'
                          for S, r in rec["offers"])

    def item_html(rec, with_img=False):
        r = rec["r"]
        meta = " · ".join(x for x in [r.get("l"), r.get("cat"), r.get("f"), r.get("g")] if x)
        img = (f'<img src="{e(r.get("cover"))}" alt="{e(r["a"])} – {e(r["t"])} vinyl cover" loading="lazy" width="300" height="300">'
               if with_img and r.get("cover") else "")
        return (f'<li>{img}<h3><a href="/r/{rslug(r["a"], r["t"])}/">{e(r["a"])} – {e(r["t"])}</a></h3><p>{e(meta)}</p>'
                f'<p class="buy">Buy: {offers_html(rec)}</p></li>')

    # Genres mit Platten
    gcount = {}
    for rec in recs:
        for g in rec["genres"]: gcount[g] = gcount.get(g, 0) + 1
    genre_list = [g for g in CORE if gcount.get(g)] + sorted(g for g in gcount if g not in CORE and gcount[g] >= 3)

    # 1. Statische Liste in index.html
    idx_path = os.path.join(ROOT, "index.html")
    idx = open(idx_path, encoding="utf-8").read()
    parts = [f'<section class="static"><h2>New vinyl releases: {e(mlabel(now))} and {e(mlabel(prev))}</h2>'
             f'<p>{len(recs)} new house, techno, disco, balearic and ambient records from {len({o[0]["shop"] for x in recs for o in x["offers"]})} record shops, newest first. Updated {today.isoformat()}.</p><ul>']
    parts += [item_html(x) for x in recs]
    parts.append("</ul></section>")
    static = "".join(parts)
    idx = re.sub(r"<!--STATIC-->.*?<!--/STATIC-->", lambda m: f"<!--STATIC-->{static}<!--/STATIC-->", idx, flags=re.S)
    glinks = " · ".join(f'<a href="/{slug(g)}/">{e(g)}</a>' for g in genre_list)
    idx = re.sub(r"<!--GENRES-->.*?<!--/GENRES-->",
                 lambda m: f'<!--GENRES--><p class="fgenres"><b>Browse by genre:</b> {glinks}</p><!--/GENRES-->', idx, flags=re.S)
    open(idx_path, "w", encoding="utf-8").write(idx)

    # 2. Genre-Seiten
    for g in genre_list:
        gs = slug(g)
        items = [x for x in recs if g in x["genres"]]
        n = len(items)
        others = " · ".join(f'<a href="/{slug(o)}/">{e(o)}</a>' for o in genre_list if o != g)
        title = f"New {g} Vinyl Releases – {mlabel(now)} | Monthly Vinyl Releases"
        desc = f"{n} new {g.lower()} vinyl records from independent shops like Hardwax, Clone and Phonica. Listen, compare prices, order per shop. Updated daily."
        page = f'''<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{e(title)}</title>
<meta name="description" content="{e(desc)}">
<link rel="canonical" href="{SITE}/{gs}/">
<meta property="og:type" content="website">
<meta property="og:title" content="{e(title)}">
<meta property="og:description" content="{e(desc)}">
<meta property="og:url" content="{SITE}/{gs}/">
<meta property="og:image" content="{SITE}/og-image.png">
<link rel="icon" type="image/png" href="/favicon-32.png">
<link rel="apple-touch-icon" href="/apple-touch-icon.png">
<meta name="theme-color" content="#0d0d0d">
<script type="application/ld+json">{json.dumps({"@context": "https://schema.org", "@type": "CollectionPage", "name": f"New {g} vinyl releases", "url": f"{SITE}/{gs}/", "isPartOf": {"@type": "WebSite", "name": "Monthly Vinyl Releases", "url": SITE + "/"}, "dateModified": today.isoformat()}, ensure_ascii=False)}</script>
<style>
:root{{--bg:#0d0d0d;--fg:#ecebe7;--muted:#a0a4a9;--line:#3c4046}}
*{{box-sizing:border-box}}
body{{margin:0;background:var(--bg);color:var(--fg);font:16px/1.5 "Helvetica Neue",Helvetica,Arial,sans-serif}}
.wrap{{max-width:1180px;margin:0 auto;padding:20px 16px 60px}}
a{{color:var(--fg)}}
.band{{display:block;background:#000;border-top:4px solid #fff;border-bottom:4px solid #fff;padding:14px 16px;text-decoration:none;font-weight:700;font-size:clamp(24px,5vw,44px);color:#fff}}
h1{{font-size:clamp(26px,4vw,40px);line-height:1.1;margin:28px 0 8px}}
.lede{{font-size:17px;max-width:760px;margin:0 0 16px}}
.cta{{display:inline-block;margin:6px 0 18px;padding:12px 18px;background:#fff;color:#000;font-weight:700;text-decoration:none}}
.genres{{font-size:14px;color:var(--muted);margin:0 0 24px;line-height:1.9}}
ul{{list-style:none;margin:0;padding:0;display:grid;grid-template-columns:repeat(auto-fill,minmax(240px,1fr));gap:28px 24px}}
li{{border-top:1.5px solid #fff;padding-top:14px;min-width:0}}
li img{{width:100%;height:auto;aspect-ratio:1;object-fit:cover;background:#1a1a1a;display:block;margin-bottom:10px}}
h3{{font-size:18px;line-height:1.2;margin:0 0 4px}}
li p{{margin:0 0 6px;font-size:13px;color:var(--muted)}}
li .buy{{color:var(--fg)}}
footer{{margin-top:48px;border-top:4px solid #fff;padding-top:16px;font-size:13px;color:var(--muted)}}
</style>
</head>
<body>
<div class="wrap">
<a class="band" href="/">Monthly Vinyl Releases</a>
<h1>New {e(g)} vinyl releases</h1>
<p class="lede">{n} new {e(g.lower())} records from {e(mlabel(now))} and {e(mlabel(prev))}, collected every morning from independent record shops. Prices and stock come from the shops and may have changed.</p>
<a class="cta" href="/?genre={e(g)}">Listen to previews &amp; compare prices →</a>
<p class="genres">More genres: {others}</p>
<ul>
{"".join(item_html(x, True) for x in items)}
</ul>
<footer>Updated {today.isoformat()} · <a href="/">monthlyvinyl.net</a> · Monthly Vinyl Releases is independent and not affiliated with the shops listed.</footer>
</div>
</body>
</html>
'''
        os.makedirs(os.path.join(ROOT, gs), exist_ok=True)
        open(os.path.join(ROOT, gs, "index.html"), "w", encoding="utf-8").write(page)

    # 2b. Release-Seiten: eine Seite pro Platte (/r/<slug>/) mit Cover, Tracklist, Previews und Preisvergleich.
    #     Für Google indexierbar. Geteilte Links tragen ?s=1 und springen direkt zur Platte auf der Hauptseite.
    import shutil
    rdir = os.path.join(ROOT, "r")
    if os.path.isdir(rdir): shutil.rmtree(rdir)
    fx = data.get("fx") or {}
    CURK = {"€": "EUR", "£": "GBP", "$": "USD", "CHF": "CHF"}
    def chf(Sx, o):
        p = o.get("p")
        if p is None: return None
        rate = fx.get(CURK.get(Sx.get("cur"), ""), 1 if Sx.get("cur") == "CHF" else None)
        return p * rate if rate else None
    allg, allo = {}, []
    for S in data["shops"]:
        if S.get("blocked"): continue
        for r in S.get("items", []):
            k = norm(r["a"]) + "|" + norm(r["t"])
            if k not in allg: allg[k] = []; allo.append(k)
            allg[k].append((S, r))
    # Hauptslug pro Platte festlegen (für Links und canonical)
    done, prim, alias, info = set(), {}, {}, {}
    for k in allo:
        offers = allg[k]
        slugs = []
        for _, o in offers:
            sl = rslug(o["a"], o["t"])
            if sl and sl not in done and sl not in slugs: slugs.append(sl)
        if not slugs: continue
        done.update(slugs); prim[k] = slugs[0]; alias[k] = slugs[1:]
        S, r = sorted(offers, key=lambda o: (not o[1].get("cover"), not playable(o[1]), o[1].get("p") is None))[0]
        info[k] = {"S": S, "r": r, "offers": offers, "genres": genres_of(r.get("g")),
                   "seen": min(o[1].get("first_seen", o[1].get("m", "2026-01") + "-01") for o in offers)}
    STOCK = {"in": "In stock", "low": "Low stock", "pre": "Pre-order", "out": "Sold out"}
    newest = sorted(info, key=lambda k: info[k]["seen"], reverse=True)
    sitemap_rel = []
    for k, R in info.items():
        S, r, offers = R["S"], R["r"], R["offers"]
        sl = prim[k]; url = f"{SITE}/r/{sl}/"
        name = f'{r["a"]} – {r["t"]}'
        meta_bits = [x for x in [r.get("l"), r.get("cat"), r.get("f")] if x]
        meta = " · ".join(meta_bits)
        gl = R["genres"]
        reiss = bool(REISSUE.search(r.get("g") or ""))
        img = hires(r.get("cover")) or f"{SITE}/og-image.png"
        # Angebote nach Preis in CHF sortieren
        ofs = sorted(offers, key=lambda o: (chf(*o) is None, chf(*o) or 0))
        priced = [o for o in ofs if chf(*o) is not None]
        best = priced[0] if priced else None
        nsh = len({Sx["shop"] for Sx, _ in offers})
        lowtxt = f" from {price(best[0], best[1].get('p'))}" if best else ""
        title = f'{name} · {" ".join(meta_bits[:2]) or "vinyl"} – vinyl previews & prices | Monthly Vinyl'
        desc = (f'{name} on {r.get("f") or "vinyl"}' + (f' ({r.get("l")}' + (f', {r.get("cat")}' if r.get("cat") else "") + ')' if r.get("l") else "")
                + (f'{", " + ", ".join(gl[:3]) if gl else ""}{" reissue" if reiss else ""}.')
                + f' Listen to the previews and compare prices at {nsh} record shop{"" if nsh == 1 else "s"}{lowtxt}.')
        mixed = len({Sx.get("cur") for Sx, o in priced}) > 1
        rows = []
        for Sx, o in ofs:
            st = STOCK.get(o.get("st"), "")
            where = ", ".join(x for x in [Sx.get("where"), Sx.get("country")] if x)
            sub = " · ".join(x for x in [where, st] if x)
            cv = chf(Sx, o)
            conv = f'<span class="w">≈ CHF {cv:.2f}</span>' if mixed and cv is not None else ""
            cls = ' class="best"' if best and o is best[1] and len(priced) > 1 else ""
            rows.append(f'<tr{cls}><td>{e(Sx["shop"])}<span class="w">{e(sub)}</span></td><td class="p">{e(price(Sx, o.get("p")))}{conv}</td>'
                        f'<td class="go"><a href="{e(o.get("url"))}" rel="nofollow noopener" target="_blank" aria-label="Buy at {e(Sx["shop"])}">Buy ↗</a></td></tr>')
        # Tracklist: bevorzugt die Variante mit abspielbaren mp3s
        trsrc = sorted(offers, key=lambda o: -sum(1 for t in o[1].get("tr", []) if t.get("u")))[0][1].get("tr", []) or r.get("tr", [])
        tl = []
        for t in trsrc:
            n = t.get("n") or "Preview"
            if t.get("ytl"): continue
            play = ""
            if t.get("u"): play = f'<audio controls preload="none" src="{e(t["u"])}"></audio>'
            elif t.get("yt"): play = f'<a href="https://www.youtube.com/watch?v={e(t["yt"])}" rel="nofollow noopener" target="_blank">YouTube ↗</a>'
            tl.append(f'<li><b>{e(t.get("s") or "")}</b><span>{e(n)}</span>{play}</li>')
        ytl = next((t["ytl"] for o in offers for t in o[1].get("tr", []) if t.get("ytl")), None)
        if ytl: tl.append(f'<li><b></b><span>Whole release</span><a href="https://www.youtube.com/playlist?list={e(ytl)}" rel="nofollow noopener" target="_blank">YouTube ↗</a></li>')
        tags = "".join(f'<a href="/{slug(g)}/">{e(g)}</a>' for g in gl if os.path.isdir(os.path.join(ROOT, slug(g)))) 
        # Ähnliche Platten: gleiches Genre, neueste zuerst
        rel = []
        for k2 in newest:
            if k2 == k: continue
            if gl and not set(gl[:2]) & set(info[k2]["genres"]): continue
            rel.append(k2)
            if len(rel) == 8: break
        grid = "".join(
            f'<li><a href="/r/{prim[k2]}/"><img src="{e(info[k2]["r"].get("cover"))}" alt="{e(info[k2]["r"]["a"])} – {e(info[k2]["r"]["t"])} vinyl cover" loading="lazy" width="150" height="150">'
            f'<b>{e(info[k2]["r"]["a"])}</b><i>{e(info[k2]["r"]["t"])}</i></a></li>' for k2 in rel)
        g0 = next((g for g in gl if os.path.isdir(os.path.join(ROOT, slug(g)))), None)
        crumb = f' › <a href="/{slug(g0)}/">{e(g0)}</a>' if g0 else ""
        ld_offers = []
        for Sx, o in ofs:
            if o.get("p") is None or not o.get("url"): continue
            of = {"@type": "Offer", "price": f'{o["p"]:.2f}', "priceCurrency": CURK.get(Sx.get("cur"), "EUR"), "url": o["url"],
                  "seller": {"@type": "Organization", "name": Sx["shop"]}}
            if o.get("st") in ("in", "low"): of["availability"] = "https://schema.org/InStock"
            elif o.get("st") == "pre": of["availability"] = "https://schema.org/PreOrder"
            elif o.get("st") == "out": of["availability"] = "https://schema.org/OutOfStock"
            ld_offers.append(of)
        ld = {"@context": "https://schema.org", "@graph": [
            {"@type": "MusicAlbum", "name": r["t"], "byArtist": {"@type": "MusicGroup", "name": r["a"]}, "image": img, "url": url,
             "recordLabel": {"@type": "Organization", "name": r.get("l")} if r.get("l") else None,
             "catalogNumber": r.get("cat") or None, "genre": gl or None,
             "albumReleaseType": "https://schema.org/AlbumRelease",
             "track": {"@type": "ItemList", "numberOfItems": len(trsrc), "itemListElement": [
                 {"@type": "MusicRecording", "name": t.get("n") or "Preview", "position": i + 1} for i, t in enumerate(x for x in trsrc if not x.get("ytl"))]} if trsrc else None,
             "offers": ld_offers or None},
            {"@type": "BreadcrumbList", "itemListElement": [
                {"@type": "ListItem", "position": 1, "name": "Monthly Vinyl", "item": SITE + "/"}]
                + ([{"@type": "ListItem", "position": 2, "name": g0, "item": f"{SITE}/{slug(g0)}/"}] if g0 else [])
                + [{"@type": "ListItem", "position": 3 if g0 else 2, "name": name, "item": url}]}]}
        def clean(x):
            if isinstance(x, dict): return {a: clean(b) for a, b in x.items() if b is not None}
            if isinstance(x, list): return [clean(b) for b in x]
            return x
        ldj = json.dumps(clean(ld), ensure_ascii=False).replace("</", "<\\/")
        page = f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{e(title)}</title>
<meta name="description" content="{e(desc)}">
<link rel="canonical" href="{url}">
<meta property="og:type" content="music.album">
<meta property="og:site_name" content="Monthly Vinyl">
<meta property="og:title" content="{e(name)}">
<meta property="og:description" content="{e(desc)}">
<meta property="og:url" content="{url}">
<meta property="og:image" content="{e(img)}">
<meta property="og:image:alt" content="{e(name)} vinyl cover">
<meta name="theme-color" content="#0d0d0d">
<link rel="icon" type="image/png" sizes="32x32" href="/favicon-32.png">
<link rel="apple-touch-icon" href="/apple-touch-icon.png">
<script>if(/[?&]s=1/.test(location.search))location.replace("/?r={sl}")</script>
<script type="application/ld+json">{ldj}</script>
<script defer src="https://cloud.umami.is/script.js" data-website-id="56d072fe-6ab0-4180-9a6f-e9926985275c" data-domains="monthlyvinyl.net"></script>
<style>{RELEASE_CSS}</style>
</head>
<body>
<div class="wrap">
<a class="band" href="/">MONTHLY VINYL</a>
<nav class="crumbs"><a href="/">New vinyl releases</a>{crumb} › {e(r["a"])}</nav>
<article class="rel">
<img class="cover" src="{e(img)}" alt="{e(name)} vinyl cover" width="440" height="440">
<div>
<h1>{e(r["a"])}<small>{e(r["t"])}</small></h1>
<p class="meta">{e(meta)}{" · Reissue" if reiss else ""}{(" · " + e(r["d"])) if r.get("d") else ""}</p>
<p class="tags">{tags}</p>
<a class="cta" href="/?r={sl}" data-umami-event="Release page: open player">▶ Listen &amp; compare on Monthly Vinyl</a>
<h2>Prices at {nsh} shop{"" if nsh == 1 else "s"}</h2>
<table>{"".join(rows)}</table>
{f'<h2>Tracklist</h2><ol>{"".join(tl)}</ol>' if tl else ""}
</div>
</article>
{f'<section class="more"><h2>More {e(g0 or "new")} vinyl</h2><ul class="grid">{grid}</ul></section>' if grid else ""}
<footer>First seen {e(R["seen"])} · Prices and stock as listed by the shops, they may have changed. · <a href="/">monthlyvinyl.net</a> is independent and not affiliated with any shop.</footer>
</div>
</body>
</html>
"""
        os.makedirs(os.path.join(rdir, sl), exist_ok=True)
        open(os.path.join(rdir, sl, "index.html"), "w", encoding="utf-8").write(page)
        sitemap_rel.append((url, R["seen"]))
        # weitere Schreibweisen derselben Platte: gleiche Seite, canonical auf den Hauptslug
        for al in alias[k]:
            os.makedirs(os.path.join(rdir, al), exist_ok=True)
            open(os.path.join(rdir, al, "index.html"), "w", encoding="utf-8").write(page.replace(f'location.replace("/?r={sl}")', f'location.replace("/?r={al}")'))
    print(f"release pages: {len(sitemap_rel)} (+{sum(len(v) for v in alias.values())} aliases)")

    # 3. Sitemap
    urls = [f"{SITE}/"] + [f"{SITE}/{slug(g)}/" for g in genre_list]
    sm = ['<?xml version="1.0" encoding="UTF-8"?>', '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">']
    for i, u in enumerate(urls):
        sm.append(f"  <url><loc>{u}</loc><lastmod>{today.isoformat()}</lastmod><changefreq>daily</changefreq><priority>{'1.0' if i == 0 else '0.8'}</priority></url>")
    for u, seen in sorted(sitemap_rel, key=lambda x: x[1], reverse=True):
        sm.append(f"  <url><loc>{u}</loc><lastmod>{seen[:10]}</lastmod><changefreq>weekly</changefreq><priority>0.6</priority></url>")
    sm.append("</urlset>")
    open(os.path.join(ROOT, "sitemap.xml"), "w", encoding="utf-8").write("\n".join(sm) + "\n")

    # 4. llms.txt
    shops = sorted({o[0]["shop"] + " (" + o[0].get("where", "") + ", " + o[0].get("country", "") + ")" for x in recs for o in x["offers"]})
    llms = [
        "# Monthly Vinyl Releases",
        "",
        "> Independent overview of new house, techno, disco, balearic and ambient vinyl releases from record shops, updated every morning. Visitors can listen to previews, compare prices across shops and order directly from each shop. No shop affiliation, no sales on this site.",
        "",
        f"Last update: {today.isoformat()} · {len(recs)} releases from {mlabel(prev)} and {mlabel(now)}.",
        "",
        "## Pages",
        f"- [Home: all new releases]({SITE}/): interactive list grouped by shop or by date, with previews, price comparison and a shipping/customs calculator",
    ]
    llms += [f"- [New {g} vinyl releases]({SITE}/{slug(g)}/): {gcount[g]} release{'' if gcount[g]==1 else 's'}" for g in genre_list]
    llms += [
        "",
        "## Data",
        f"- [releases.json]({SITE}/releases.json): full machine-readable list (artist a, title t, label l, catalog number cat, format f, price p in the shop's currency, genre g, month m, first_seen, product url, cover, tracks tr, stock st)",
        "",
        "## Shops",
    ] + [f"- {s}" for s in shops] + [
        "",
        "## Contact",
        "- Record shops that want to be listed: see the footer on the home page.",
    ]
    open(os.path.join(ROOT, "llms.txt"), "w", encoding="utf-8").write("\n".join(llms) + "\n")
    print(f"built: {len(recs)} releases, {len(genre_list)} genre pages: {', '.join(slug(g) for g in genre_list)}")

if __name__ == "__main__":
    main()
