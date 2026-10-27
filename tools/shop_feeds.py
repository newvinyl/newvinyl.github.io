#!/usr/bin/env python3
"""Shops whose new releases can be read as structured data. Each feed returns finished items in the format of
releases.json (without "m"/"first_seen"); fetch_pages.py writes them to pages/items/<id>.json and lists them in
pages/items/index.json. The daily update only merges these items (see tools/daily_update.md).

Feeds: Vinyl Underground (Shopify), Sound Metaphors + Discos Paradiso (Common Ground shop system),
Syncrophone, Betino's, Bordello A Parigi (WooCommerce), Diggers.fr (WooCommerce), Carpet & Snares + KMA60 (Common Ground),
Side One (IdoSell), SoundGround (own shop), Divert Records + Ultrasuoni (WooCommerce)."""
import datetime as dt, html as H, json, re, time

# ---------------------------------------------------------------- genres
GENRES = [  # text (lower case, substring) -> our genre, most specific first
    ("dub techno", "Dub Techno"), ("deep techno", "Deep Techno"), ("deeptechno", "Deep Techno"), ("minimal techno", "Minimal Techno"),
    ("acid techno", "Acid Techno"), ("acid house", "Acid House"), ("deep house", "Deep House"), ("tech house", "Tech House"),
    ("minimal house", "Minimal House"), ("dub house", "Deep House"), ("chicago", "Chicago House"), ("detroit", "Detroit House"),
    ("detriot", "Detroit House"), ("italo", "Italo Disco"), ("cosmic", "Cosmic"), ("balearic", "Balearic"), ("downtempo", "Downtempo"),
    ("down tempo", "Downtempo"), ("downbeat", "Downtempo"), ("ambient", "Ambient"), ("electro", "Electro"), ("breaks", "Breakbeat"),
    ("breakbeat", "Breakbeat"), ("minimal", "Minimal"), ("techno", "Techno"), ("edits", "Edits"), ("nu disco", "Disco"),
    ("disco", "Disco"), ("deephouse", "Deep House"), ("techhouse", "Tech House"), ("soulful house", "House"), ("garage house", "House"), ("house", "House"), ("acid", "Acid House"),
]
SKIP = ("jungle", "drum & bass", "drum and bass", "drum n bass", "dnb", "hip hop", "hip-hop", "dancehall", "lovers rock",
        "uk garage", "dubstep", "grime", "trance", "hard techno", "hardcore", "gabber", "rock", "pop", "jazz", "reggae", "soul-funk",
        "cassette", "merch", "t-shirt", "slipmat", "book")
NOT_SKIP_IF = ("house", "techno", "disco", "electro", "ambient", "balearic")   # "acid jazz house" etc. stays

def genres(words, reissue=False):
    """list of shop genre words -> our genre string, or None if nothing of ours / clearly another genre"""
    low = [re.sub(r"\s+", " ", (w or "").lower()).strip() for w in words if w]
    hits = []
    for t in low:
        for k, name in GENRES:
            if k in t:
                if name not in hits:
                    hits.append(name)
                break
    if not hits:
        return None
    ours = any(any(n in t for n in NOT_SKIP_IF) for t in low)
    if not ours and any(t == s or t.startswith(s) for t in low for s in SKIP):
        return None
    if "House" in hits and any(x.endswith("House") and x != "House" for x in hits):
        hits.remove("House")
    g = " / ".join(hits[:3])
    return g + (" · Reissue" if reissue else "")

def is_reissue(*texts):
    return any(re.search(r"\b(reissue|repress|remaster(ed)?|classic)\b", t or "", re.I) for t in texts)

def fmt_of(text):
    t = (text or "").lower().replace("×", "x").replace("&quot;", '"').replace("″", '"')
    for k, v in (("4xlp", "4×LP"), ("3xlp", "3×LP"), ("2xlp", "2×LP"), ("2x12", '2×12"'), ("3x12", '3×12"'), ("12", '12"'),
                 ("10", '10"'), ("7", '7"'), ("lp", "LP"), ("ep", '12"')):
        if re.search(r"(^|[^0-9a-z])" + re.escape(k) + r"($|[^0-9a-z])", t):
            return v
    return ""

def clean(s):
    return re.sub(r"\s+", " ", H.unescape(re.sub(r"<[^>]+>", " ", s or ""))).strip()

def price_of(s):
    m = re.search(r"(\d+)[.,](\d{2})", s or "")
    return float("%s.%s" % m.groups()) if m else None

# ---------------------------------------------------------------- Vinyl Underground (Shopify)
VU = "https://www.vinylunderground.co.uk"

def feed_vinylunderground(fetch, days=3):
    st, body = fetch(VU + "/products.json?limit=250")
    since = (dt.date.today() - dt.timedelta(days=days - 1)).isoformat()
    out = []
    for pr in json.loads(body).get("products") or []:
        if (pr.get("published_at") or "")[:10] < since:
            continue
        tags = [t.strip() for t in pr.get("tags") or []]
        low = [t.lower() for t in tags]
        if any(t.startswith(("cassette", "cd", "merch")) for t in low):
            continue
        g = genres(tags, reissue=any(t in ("reissue", "classic", "detroit reissue", "repress") for t in low))
        title = pr.get("title") or ""
        if not g or " | " not in title:
            continue
        a, t = [x.strip() for x in title.split(" | ", 1)]
        t = re.sub(r"\s+-\s+(Expected|Exp)\b.*$", "", t).strip()
        var = (pr.get("variants") or [{}])[0]
        trs = [{"s": "", "n": clean(n) or "Preview", "u": u}
               for u, n in re.findall(r'<a[^>]+href="([^"]+?\.mp3)"[^>]*>(.*?)</a>', pr.get("body_html") or "", re.S)]
        pre = "presale" in low or (pr.get("product_type") or "").lower() == "inbound" or re.search(r"\bExpected\b", title)
        img = (pr.get("images") or [{}])[0].get("src") or ""
        out.append({"a": a, "t": t, "l": pr.get("vendor") or "", "cat": var.get("sku") or "",
                    "f": next((fmt_of(x) for x in tags if fmt_of(x)), ""), "p": price_of(var.get("price")), "g": g,
                    "url": "%s/products/%s" % (VU, pr["handle"]), "cover": img + ("&" if "?" in img else "?") + "width=800" if img else "",
                    "tr": trs, "st": "pre" if pre else ("in" if var.get("available") else "out")})
    return out

# ---------------------------------------------------------------- Common Ground shop system (Sound Metaphors, Discos Paradiso)
def _rsc(body):
    chunks = re.findall(r'self\.__next_f\.push\(\[1,"(.*?)"\]\)</script>', body, re.S)
    out = []
    for c in chunks:
        try:
            out.append(json.loads('"' + c + '"'))
        except Exception:
            pass
    return "".join(out)

def feed_commonground(fetch, base, list_path, max_items=40):
    """list page = newest first; each release page has description, styles, price and the audio snippets"""
    st, body = fetch(base + list_path)
    paths = list(dict.fromkeys(re.findall(r'href="(/release/\d+/[^"]+)"', body)))[:max_items]
    SNIP = r'creators-audio-snippets-production\.fra1\.cdn\.digitaloceanspaces\.com/((?:custom/)?\d+)/'
    listed = set(re.findall(SNIP, body))                      # some shops keep the snippets under custom/<release id>
    out = []
    for path in paths:
        try:
            time.sleep(0.8)
            _, rb = fetch(base + path)
        except Exception:
            continue
        data = _rsc(rb)
        i = data.find('"descriptions":{"main":"')
        if i < 0:
            continue
        main = clean(json.loads(data[i + 23:data.index('"}', i) + 1]))
        own = data[i:i + 8000]
        left, _, right = main.rpartition(" | ") if " | " in main else (main, "", "")
        if " - " not in left:
            continue
        a, t = [x.strip() for x in left.split(" - ", 1)]
        lm = re.match(r"(.*?)\s*\(([^()]*)\)\s*$", right)
        label, cat = (lm.group(1).strip(), lm.group(2).strip()) if lm else (right.strip(), "")
        rid = re.match(r"/release/(\d+)/", path).group(1)
        fm = re.search(SNIP, own)
        folder = fm.group(1) if fm else ("custom/" + rid if "custom/" + rid in listed else None)
        if not folder:                                         # snippet links further down the page: the folder used most often
            cnt = {}
            for f in re.findall(SNIP, rb):
                cnt[f] = cnt.get(f, 0) + 1
            folder = max(cnt, key=lambda k: (cnt[k], -rb.find(k))) if cnt else None
        trs = []
        # the release's own tracklist in the page data carries the snippet uri per track (also when the
        # rendered track rows are not marked "playable", e.g. releases imported from Discogs)
        k = data.find('"tracklist":[', i)
        if 0 <= k < i + 20000:
            seg = data[k:data.find("]", data.find("}]", k) + 1) + 1] if data.find("}]", k) > 0 else ""
            for tm in re.finditer(r'"type_":"track","title":"((?:[^"\\]|\\.)*)","position":"([^"]*)"([^{}]*)\}', seg):
                um = re.search(r'"uri":"(https://creators-audio-snippets-production[^"]+?\.mp3[^"]*)"', tm.group(3))
                if um:
                    fu = re.search(SNIP, um.group(1))
                    folder = folder or (fu.group(1) if fu else None)
                    trs.append({"s": tm.group(2), "n": clean(json.loads('"%s"' % tm.group(1))), "u": um.group(1)})
        if folder:
            snip = "https://creators-audio-snippets-production.fra1.cdn.digitaloceanspaces.com/%s/" % folder
            for pos, name in re.findall(r'data-track-position="([^"]+)"[^>]*class="track playable[^"]*".*?class="description"><span>(.*?)</span>', rb, re.S):
                if any(x["s"] == pos for x in trs):
                    continue
                trs.append({"s": pos, "n": clean(name), "u": snip + pos + ".mp3?version=1"})
            trs.sort(key=lambda x: (len(x["s"]) > 3, x["s"]))
        img = (re.search(r'"images":\[\{"uri":"([^"]+)"', own) or [None, ""])[1]
        pm = re.search(r'"prices":\{"sale":([\d.]+)', data)
        sb = re.search(r'<div class="styles">(.*?)</div>', rb, re.S)
        styles = [H.unescape(x).replace("%20", " ").replace("%26", "&") for x in re.findall(r'catalogue\?styles=([^"&]+)', sb.group(1) if sb else "")]
        fd = re.search(r'data-format-descriptions="([^"]+)"', rb)
        g = genres(list(dict.fromkeys(styles)), reissue=is_reissue(t))
        if not g:
            continue
        pre = re.search(r'"preOrder":true', own)
        out.append({"a": a, "t": t, "l": label, "cat": cat, "f": fmt_of(H.unescape(fd.group(1))) if fd else "",
                    "p": float(pm.group(1)) if pm else None, "g": g, "url": base + path, "cover": img, "tr": trs})
        if pre:
            out[-1]["st"] = "pre"
    return out

def feed_soundmetaphors(fetch):
    return feed_commonground(fetch, "https://www.soundmetaphors.com", "/collection/2/news?sort=added&order=-1")

def feed_discosparadiso(fetch):
    return feed_commonground(fetch, "https://www.discosparadiso.com", "/collection/1/new-releases?sort=added&order=-1")

# ---------------------------------------------------------------- Syncrophone (Paris)
def feed_syncrophone(fetch, max_items=40):
    st, body = fetch("https://www.syncrophone.fr/news/")
    out = []
    for blk in re.split(r'<div class="product_box', body)[1:max_items + 1]:
        um = re.search(r'class="bp_designation">\s*<a href="([^"]+)">\s*(.*?)\s*</a>', blk, re.S)
        if not um:
            continue
        url, des = um.group(1), clean(um.group(2))
        if " - " not in des:
            continue
        a, t = [x.strip() for x in des.split(" - ", 1)]
        label = clean((re.search(r'class="bp_marque">\s*<a[^>]*>(.*?)</a>', blk, re.S) or [None, ""])[1])
        pm = re.search(r'class="bp_prix">.*?<div class="d-inline-block">\s*([\d.,]+)', blk, re.S)
        img = (re.search(r'data-url-img="([^"?]+)', blk) or re.search(r'<img[^>]+src="(https://www\.syncrophone\.fr/upload/image/[^"?]+)', blk)
               or [None, ""])[1].replace("-moyenne.", "-grande.")
        trs = []
        for u, n in re.findall(r'class="piste-mp3"\s+data-url="([^"]+)"[^>]*data-title="([^"]*)"', blk):
            n = clean(n)
            sm = re.match(r"([A-Z]\d{0,2})\s*[.:]\s*(.*)", n)
            trs.append({"s": sm.group(1) if sm else "", "n": sm.group(2) if sm else n, "u": u})
        stock = clean((re.search(r'class="articleDispo">(.*?)</span>', blk, re.S) or [None, ""])[1]).lower()
        carac = {}
        try:
            time.sleep(0.8)
            _, pb = fetch(url)
            for l, v in re.findall(r'label_carac[^>]*>(.*?)</[^>]+>.*?label_valeur[^>]*>(.*?)</(?:span|div|li)', pb, re.S):
                carac[clean(l).rstrip(":")] = clean(v)
        except Exception:
            pass
        g = genres([s.strip() for s in carac.get("Style", "").split(",")], reissue=is_reissue(t, carac.get("Format")))
        if not g:
            continue
        out.append({"a": a, "t": re.sub(r"\s*\((Reissue|Repress)\)\s*$", "", t, flags=re.I), "l": carac.get("Label") or label,
                    "cat": "", "f": fmt_of(carac.get("Format", "")), "p": price_of(pm.group(1)) if pm else None, "g": g, "url": url,
                    "cover": img, "tr": trs, "st": "in" if "in stock" in stock else ("pre" if "pre" in stock or "coming" in stock else "")})
        if not out[-1]["st"]:
            del out[-1]["st"]
    return out

# ---------------------------------------------------------------- Betino's (Paris)
def feed_betinos(fetch):
    st, body = fetch("https://www.betinos.com/")
    out = []
    for blk in re.split(r'<div class="views-row ', body)[1:]:
        um = re.search(r'views-field-title">\s*<a href="[./]*(disque/\d+)">(.*?)</a>', blk, re.S)
        am = re.search(r'field-auteur">.*?<a[^>]*>(.*?)</a>', blk, re.S)
        if not um or not am:
            continue
        url = "https://www.betinos.com/" + um.group(1)
        label = clean((re.search(r'field-label">.*?<a[^>]*>(.*?)</a>', blk, re.S) or [None, ""])[1])
        cat = clean((re.search(r'field-ref-du-label">\s*<div class="field-content">(.*?)</div>', blk, re.S) or [None, ""])[1]).rstrip(" -")
        fmt = clean((re.search(r'field-format">\s*<div class="field-content">(.*?)</div>', blk, re.S) or [None, ""])[1]).rstrip(" -")
        gen = [clean(x) for x in re.findall(r'href="[./]*genre/\d+">(.*?)</a>', blk)]
        g = genres(gen, reissue=is_reissue(fmt, um.group(2)))
        if not g:
            continue
        img = (re.search(r'<img[^>]+src="([^"]+)"', blk) or [None, ""])[1]
        img = re.sub(r"/styles/[^/]+/public/", "/", img).split("?")[0]
        trs = [{"s": "", "n": clean(n), "u": u.replace("http://", "https://")}
               for u, n in re.findall(r'<button[^>]*id="([^"]+\.mp3)"[^>]*>(.*?)</button>', blk, re.S)]
        out.append({"a": clean(am.group(1)), "t": clean(um.group(2)), "l": label, "cat": cat, "f": fmt_of(fmt),
                    "p": price_of((re.search(r'basic-cart-price">(.*?)<', blk) or [None, ""])[1]), "g": g, "url": url,
                    "cover": img, "tr": trs})
    return out

# ---------------------------------------------------------------- WooCommerce shops (Store API)
def _woo(fetch, base, n=40):
    st, body = fetch(base + "/wp-json/wc/store/v1/products?per_page=%d&orderby=date&order=desc" % n)
    return json.loads(body)

def _price(p):
    pr = p.get("prices") or {}
    try:
        return int(pr["price"]) / 10 ** int(pr.get("currency_minor_unit", 2))
    except Exception:
        return None

def _attrs(p):
    return {a["name"].rstrip(": ").strip(): [clean(t["name"]) for t in a.get("terms", [])] for a in p.get("attributes", [])}

def feed_bordello(fetch):
    out = []
    for p in _woo(fetch, "https://bordelloaparigi.com"):
        at = _attrs(p)
        name = clean(p["name"])
        if " | " not in name:
            continue
        artist, t = [x.strip() for x in name.split(" | ", 1)]
        t = re.sub(r'\s*(12|10|7)["″]\s*$', "", t).strip()
        g = genres(at.get("Genre", []), reissue=is_reissue(t))
        if not g:
            continue
        trs = []
        try:
            time.sleep(0.8)
            _, pb = fetch(p["permalink"])
            ul = re.search(r'<ul data-playlist="%s">(.*?)</ul>' % p["id"], pb, re.S)
            for u, n in re.findall(r'class="fap-single-track[^"]*"\s+href="([^"]+\.mp3)"[^>]*>(?:<i[^>]*></i>)?(.*?)</a>', ul.group(1) if ul else ""):
                n = clean(n)
                trs.append({"s": "", "n": n.split(" - ", 1)[1] if " - " in n else n, "u": u})
        except Exception:
            pass
        status = " ".join(at.get("Status", [])).lower()
        out.append({"a": (at.get("Artist") or [artist])[0], "t": t, "l": (at.get("Label") or [""])[0], "cat": p.get("sku") or "",
                    "f": fmt_of(" ".join(at.get("Format", []))), "p": _price(p), "g": g, "url": p["permalink"],
                    "cover": (p.get("images") or [{}])[0].get("src", ""), "tr": trs,
                    "st": "pre" if "upcoming" in status else ("in" if p.get("is_in_stock") else "out")})
    return out

def feed_diggers(fetch):
    out, year = [], dt.date.today().year
    for p in _woo(fetch, "https://diggers.fr"):
        at = _attrs(p)
        yr = (at.get("Année") or ["0"])[0]
        if not yr.isdigit() or int(yr) < year:                       # the list also holds back catalogue
            continue
        t = clean(p["name"])
        slug = p["permalink"].rstrip("/").rsplit("/", 1)[-1]
        tslug = re.sub(r"[^a-z0-9]+", "-", t.lower()).strip("-")
        tags = [clean(x["name"]) for x in p.get("tags", [])]
        aslug = slug[:-len(tslug)].strip("-") if tslug and slug.endswith(tslug) else ""
        artist = next((x for x in tags if re.sub(r"[^a-z0-9]+", "-", x.lower()).strip("-") == aslug), "")
        if not artist:
            continue
        label = next((x for x in tags if x != artist), "")
        g = genres([c["name"] for c in p.get("categories", [])], reissue=is_reissue(t))
        if not g:
            continue
        sku = (p.get("sku") or "").lower()
        trs = []
        try:
            time.sleep(0.8)
            _, pb = fetch(p["permalink"])
            for u in dict.fromkeys(re.findall(r'https?://[^\s"\'<>]+?\.mp3', pb)):
                fn = u.rsplit("/", 1)[-1].lower()
                if sku and sku in fn:
                    sm = re.search(r"-([a-d]\d?)\.mp3$", fn)
                    trs.append({"s": sm.group(1).upper() if sm else "", "n": sm.group(1).upper() if sm else "Preview", "u": u})
        except Exception:
            pass
        status = " ".join(at.get("Statut", [])).lower()
        out.append({"a": artist, "t": t, "l": label, "cat": p.get("sku") or "", "f": fmt_of(" ".join(at.get("Formats", []))),
                    "p": _price(p), "g": g, "url": p["permalink"], "cover": (p.get("images") or [{}])[0].get("src", ""), "tr": trs,
                    "st": "pre" if "coming" in status else ("in" if p.get("is_in_stock") else "out")})
    return out

# ---------------------------------------------------------------- more Common Ground shops
def feed_carpetsnares(fetch):
    return feed_commonground(fetch, "https://shop.carpetandsnares.com", "/catalogue?sort=added&order=-1")

def feed_kma60(fetch):
    return feed_commonground(fetch, "https://www.kma60.com", "/collection/2/new-arrivals?sort=added&order=-1")

# ---------------------------------------------------------------- Side One (Warsaw, IdoSell): everything is on the "new" list pages
SO = "https://www.sideone.pl"

def feed_sideone(fetch, pages=3):
    out = []
    for pg in range(pages):
        try:
            st, body = fetch(SO + "/NOWOSCI-snewproducts-pol.html" + ("?counter=%d" % pg if pg else ""))
        except Exception:
            if not pg:
                raise
            break
        for blk in body.split('<div class="product_wrapper">')[1:]:
            nm = re.search(r'class="product_name" href="([^"]+)"[^>]*>(.*?)</a>', blk, re.S)
            if not nm:
                continue
            fmt = " ".join(clean(x) for x in re.findall(r'class="product_format"[^>]*>(.*?)</a>', blk, re.S))
            if not re.search(r'12|10|7"|LP|EP|Vinyl|Winyl', fmt, re.I) or re.search(r"\bCD\b|MC|Kaseta", fmt):
                continue
            styles = [clean(x) for x in re.findall(r'class="btn-small product_style"[^>]*>(.*?)</a>', blk, re.S)]
            t = clean(nm.group(2))
            g = genres(styles, reissue=is_reissue(t, fmt))
            if not g:
                continue
            artist = ", ".join(clean(x) for x in re.findall(r'class="product_author"[^>]*>(.*?)</a>', blk, re.S)) or "Various"
            label = clean((re.search(r'class="firm_name"[^>]*>(.*?)</a>', blk, re.S) or [None, ""])[1])
            cat = clean((re.search(r'class="code_name">(.*?)</div>', blk, re.S) or [None, ""])[1])
            img = (re.search(r'<img src="([^"]+)"', blk) or [None, ""])[1]
            trs = []
            for u, n in re.findall(r'data-mp3="([^"]+)"[^>]*data-artist="([^"]*)"', blk):
                n = re.sub(r"\.mp3$", "", clean(n), flags=re.I)
                sm = re.match(r"([A-Da-d]?\d{1,2})[\s.\-_]+(.*)", n)
                trs.append({"s": sm.group(1).upper() if sm else "", "n": sm.group(2) if sm else n, "u": u.replace("pl//settings", "pl/settings")})
            stock = clean((re.search(r'class="prod_aviability">(.*?)</span>', blk, re.S) or [None, ""])[1]).lower()
            if re.search(r"used|second[ -]hand", t, re.I):
                continue                                               # second-hand listings
            out.append({"a": artist, "t": re.sub(r"\s*\((180g|LP|EP|12\"|Repress|Reissue)\)\s*$", "", t, flags=re.I), "l": label, "cat": cat,
                        "f": fmt_of(fmt), "p": price_of((re.search(r'class="price">(.*?)</span>', blk, re.S) or [None, ""])[1]), "g": g,
                        "url": SO + nm.group(1), "cover": (SO + "/" + img.lstrip("/")).replace("/pol_il_", "/pol_pl_") if img else "", "tr": trs,
                        "st": "pre" if "przedsprzeda" in stock or "zapowied" in stock else ("in" if "magazyn" in stock else "")})
            if not out[-1]["st"]:
                del out[-1]["st"]
        time.sleep(1.2)
    return out

# ---------------------------------------------------------------- SoundGround (Sofia): product data is serialized into the collection pages
SG = "https://www.soundground.bg"

def feed_soundground(fetch):
    out, seen, year = [], set(), dt.date.today().year
    for coll in ("electronic-music", "house-vinyl", "techno-vinyl", "techhouse-vinyl"):
        try:
            st, body = fetch(SG + "/collections/" + coll)
        except Exception:
            continue
        starts = [m.start() for m in re.finditer(r'\$R\[\d+\]=\{id:"[^"]+",slug:"', body)] + [len(body)]
        for i0, i1 in zip(starts, starts[1:]):
            chunk = body[i0:i1]
            sm = re.search(r'slug:"([^"]+)",artist:\$R\[\d+\]=\[(.*?)\],title:"((?:[^"\\]|\\.)*)",format:"((?:[^"\\]|\\.)*)",cover_url:"([^"]*)"', chunk)
            if not sm or sm.group(1) in seen:
                continue
            slug, arts, title, fmt, cover = sm.groups()
            seen.add(slug)
            yr = re.search(r",year:(\d{4})", chunk)
            stat = (re.search(r'stock_status:"(\w+)"', chunk) or [None, ""])[1]
            if not (yr and int(yr.group(1)) >= year - 1) and stat != "preorder":
                continue
            if re.search(r"\bCD\b|Cassette|MC\b", fmt):
                continue
            styles = re.findall(r'"([^"]+)"', (re.search(r"styles:\$R\[\d+\]=\[(.*?)\]", chunk) or [None, ""])[1])
            g = genres(styles, reissue=is_reissue(title, fmt))
            if not g:
                continue
            pe = re.search(r"price_eur:([\d.]+)", chunk); pb = re.search(r"price_bgn:([\d.]+)", chunk)
            price = float(pe.group(1)) if pe else (round(float(pb.group(1)) / 1.95583, 2) if pb else None)   # BGN is pegged 1.95583 per €
            trs = []
            for u in sorted(set(re.findall(r'preview_url:"(https://[^"]+\.mp3)"', chunk))):
                fn = urllib_unquote(u.rsplit("/", 1)[-1])[:-4]
                fn = re.sub(r"^\d+_\d+_", "", fn).replace("_", " ").strip()
                n = fn.split(" - ", 1)[1] if " - " in fn else fn
                trs.append({"s": "", "n": re.sub(r"\s+", " ", n).strip(), "u": u})
            artist = ", ".join(json.loads('"%s"' % a) for a in re.findall(r'"((?:[^"\\]|\\.)*)"', arts))
            out.append({"a": artist, "t": json.loads('"%s"' % title), "l": json.loads('"%s"' % (re.search(r'label:"((?:[^"\\]|\\.)*)"', chunk) or [None, ""])[1]),
                        "cat": "", "f": fmt_of(json.loads('"%s"' % fmt)), "p": price, "g": g, "url": SG + "/music/product/" + slug,
                        "cover": cover, "tr": trs, "st": "pre" if stat == "preorder" else ("in" if stat in ("in_stock", "instock", "available") else "out" if stat else "")})
            if not out[-1]["st"]:
                del out[-1]["st"]
        time.sleep(1.2)
    return out

def urllib_unquote(s):
    import urllib.parse
    return urllib.parse.unquote(s)

# ---------------------------------------------------------------- Divert Records (Bratislava) + Ultrasuoni (Rome): WooCommerce, audio on the product page
def feed_divert(fetch):
    out, year = [], dt.date.today().year
    for p in _woo(fetch, "https://www.divertrecords.sk", 100):              # newest by date is mostly restocks of old records
        at = _attrs(p)
        rel = " ".join(at.get("Released", []) + at.get("Rok vydania", []))
        ym = re.search(r"(20\d\d)", rel)
        if ym and int(ym.group(1)) < year - 1:                        # restocks of old records
            continue
        name = clean(p["name"])
        if "second-hand" in p["permalink"] or any("second" in c["name"].lower() or "bazar" in c["name"].lower() for c in p.get("categories", [])):
            continue
        if " – " not in name and " - " not in name:
            continue
        a, t = [x.strip() for x in re.split(r" [–-] ", name, 1)]
        fmt = " ".join(at.get("Format", []))
        if "vinyl" not in fmt.lower() and not re.search(r"\b(12|10|7|LP)\b", fmt):
            continue
        g = genres(at.get("Style", []) + [c["name"] for c in p.get("categories", [])], reissue=is_reissue(t, fmt))
        if not g:
            continue
        trs = []
        try:
            time.sleep(0.8)
            _, pb = fetch(p["permalink"])
            for u, tt in re.findall(r'data-audiopath="([^"]+\.mp3)".*?data-trackTitle="([^"]*)"', pb, re.S):
                tt = clean(tt).split(" | ")[0]
                sm = re.match(r"([A-D]\d?)\s*[:.]\s*(.*)", tt)
                if not any(x["u"] == u for x in trs):
                    trs.append({"s": sm.group(1) if sm else "", "n": sm.group(2) if sm else tt, "u": u})
        except Exception:
            pass
        out.append({"a": a, "t": t, "l": (at.get("Label") or [""])[0], "cat": (at.get("Catalog") or [p.get("sku") or ""])[0],
                    "f": fmt_of(fmt.replace(" ", "")) or fmt_of(fmt), "p": _price(p), "g": g, "url": p["permalink"],
                    "cover": (p.get("images") or [{}])[0].get("src", ""), "tr": trs, "st": "in" if p.get("is_in_stock") else "out"})
    return out

def feed_ultrasuoni(fetch):
    out = []
    for p in _woo(fetch, "https://www.ultrasuonirecords.com"):
        cats = [c["name"] for c in p.get("categories", [])]
        if not ({"News", "Upcoming"} & set(cats)):
            continue
        at = _attrs(p)
        if (at.get("Condition") or ["New"])[0].lower() != "new":
            continue
        a = (at.get("Artist") or [""])[0]
        a = "Various Artists" if re.match(r"V/?A\b", a) else a.title() if a.isupper() else a
        t = clean(p["name"])
        t = t.title() if t.isupper() else t
        fmt = " ".join(at.get("Format", []))
        g = genres([c for c in cats if c not in ("News", "Upcoming", "Electronic")], reissue=is_reissue(t, fmt))
        if not g or not a:
            continue
        trs = []
        try:
            time.sleep(0.8)
            _, pb = fetch(p["permalink"])
            ul = re.search(r'<ul data-playlist="list_%s".*?</ul>' % p["id"], pb, re.S)
            for u, n in re.findall(r'data-value="([^"]+\.mp3)" data-track-name="([^"]*)"', ul.group(0) if ul else ""):
                sm = re.match(r"([A-D]\d?)-", u.rsplit("/", 1)[-1])
                n = clean(n)
                trs.append({"s": sm.group(1) if sm else "", "n": n.split(" - ", 1)[1] if " - " in n and a != "Various Artists" else n, "u": u})
        except Exception:
            pass
        lab = (at.get("Label") or [""])[0]
        out.append({"a": a, "t": t, "l": lab.title() if lab.islower() or lab.isupper() else lab,
                    "cat": "", "f": fmt_of(fmt), "p": _price(p), "g": g, "url": p["permalink"], "cover": (p.get("images") or [{}])[0].get("src", ""),
                    "tr": trs, "st": "pre" if "Upcoming" in cats else ("in" if p.get("is_in_stock") else "out")})
    return out

# ---------------------------------------------------------------- Rubadub (Glasgow, Shopify): previews per track on Dropbox, linked in the product page
RB = "https://rubadub.co.uk"

def feed_rubadub(fetch, days=3):
    st, body = fetch(RB + "/products.json?limit=250")
    since = (dt.date.today() - dt.timedelta(days=days - 1)).isoformat()
    out = []
    for pr in json.loads(body).get("products") or []:
        if (pr.get("published_at") or "")[:10] < since or (pr.get("product_type") or "").lower() != "records":
            continue
        tags = [t.strip() for t in pr.get("tags") or []]
        tv = lambda k: [t.split("|", 1)[1].strip() for t in tags if t.lower().startswith(k.lower() + "|")]
        fmts = tv("Format")
        if any(f.lower() in ("tape", "cassette", "cd") for f in fmts) and not any(f.lower() in ("vinyl", "12\"", "10\"", "7\"", "lp", "2xlp") for f in fmts):
            continue
        low = [t.lower() for t in tags]
        g = genres(tv("Genre"), reissue=any("reissue" in t or "repress" in t for t in low))
        if not g:
            continue
        artists = tv("Artist") + tv("Artists")
        if not artists:
            continue
        trs = []
        try:
            time.sleep(0.8)
            _, pb = fetch(RB + "/products/" + pr["handle"])
            for u, n in re.findall(r'class="rp-track"\s+data-src="([^"]+)".*?aria-label="Play ([^"]*)"', pb, re.S):
                u = H.unescape(u); n = clean(n)
                sm = re.match(r"([A-H]\d{0,2})\s*[.:]\s*(.*)", n)
                trs.append({"s": sm.group(1) if sm else "", "n": sm.group(2) if sm else n, "u": u})
        except Exception:
            pass
        var = (pr.get("variants") or [{}])[0]
        img = (pr.get("images") or [{}])[0].get("src") or ""
        pre = any("pre-order" in t for t in low)
        out.append({"a": " & ".join(dict.fromkeys(artists)), "t": clean(pr.get("title") or ""), "l": (tv("Label") or [pr.get("vendor") or ""])[0],
                    "cat": var.get("sku") or "", "f": next((fmt_of(f) for f in fmts if fmt_of(f)), "") or ('12"' if "Vinyl" in fmts else ""),
                    "p": price_of(var.get("price")), "g": g, "url": "%s/products/%s" % (RB, pr["handle"]),
                    "cover": img + ("&" if "?" in img else "?") + "width=800" if img else "", "tr": trs,
                    "st": "pre" if pre else ("in" if var.get("available") else "out")})
    return out

# ---------------------------------------------------------------- registry
FEEDS = [
    # id, shop name in releases.json, city, country, currency, function
    ("vinylunderground", "Vinyl Underground", "Northampton", "UK", "£", feed_vinylunderground),
    ("soundmetaphors", "Sound Metaphors", "Berlin", "DE", "€", feed_soundmetaphors),
    ("discosparadiso", "Discos Paradiso", "Barcelona", "ES", "€", feed_discosparadiso),
    ("syncrophone", "Syncrophone", "Paris", "FR", "€", feed_syncrophone),
    ("betinos", "Betino's", "Paris", "FR", "€", feed_betinos),
    ("bordello", "Bordello A Parigi", "Amsterdam", "NL", "€", feed_bordello),
    ("diggers", "Diggers.fr", "France", "FR", "€", feed_diggers),
    ("carpetsnares", "Carpet & Snares", "Lisbon", "PT", "€", feed_carpetsnares),
    ("kma60", "KMA60", "Paris", "FR", "€", feed_kma60),
    ("sideone", "Side One", "Warsaw", "PL", "zł", feed_sideone),
    ("soundground", "SoundGround", "Sofia", "BG", "€", feed_soundground),
    ("divert", "Divert Records", "Bratislava", "SK", "€", feed_divert),
    ("ultrasuoni", "Ultrasuoni", "Rome", "IT", "€", feed_ultrasuoni),
    ("rubadub", "Rubadub", "Glasgow", "UK", "£", feed_rubadub),
]
