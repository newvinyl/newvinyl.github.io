#!/usr/bin/env python3
"""Baut aus releases.json die für Suchmaschinen und KI lesbaren Teile der Website:
- eine statische Plattenliste in index.html (zwischen <!--STATIC--> und <!--/STATIC-->),
- Genre-Links im Footer (zwischen <!--GENRES--> und <!--/GENRES-->),
- eine Unterseite pro Genre (/techno/, /ambient/ …),
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

def main():
    data = json.load(open(os.path.join(ROOT, "releases.json"), encoding="utf-8"))
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
        return (f'<li>{img}<h3>{e(r["a"])} – {e(r["t"])}</h3><p>{e(meta)}</p>'
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
        desc = (f"{n} new {g.lower()} vinyl records from independent shops like Hardwax, Clone, Phonica and Redeye. "
                f"Listen to previews, compare prices and order per shop. Updated every morning.")
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
<meta name="twitter:card" content="summary_large_image">
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

    # 3. Sitemap
    urls = [f"{SITE}/"] + [f"{SITE}/{slug(g)}/" for g in genre_list]
    sm = ['<?xml version="1.0" encoding="UTF-8"?>', '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">']
    for i, u in enumerate(urls):
        sm.append(f"  <url><loc>{u}</loc><lastmod>{today.isoformat()}</lastmod><changefreq>daily</changefreq><priority>{'1.0' if i == 0 else '0.8'}</priority></url>")
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
