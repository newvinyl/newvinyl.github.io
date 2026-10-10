#!/usr/bin/env python3
"""Lädt jeden Morgen die Neuheiten-Seiten der Shops und speichert sie als kompakten Text
(Links, Bilder und Text, ohne Skripte) im Branch "shop-pages", Ordner pages/.
Grund: die geplante Claude-Aufgabe darf Shop-Seiten nicht selbst abrufen (WebFetch lässt nur
Adressen aus Benutzernachrichten zu). Sie liest stattdessen diese Dateien.
Ausgabe: <OUT>/pages/*.txt, <OUT>/pages/index.json"""
import datetime as dt, html.parser, json, os, re, sys, time, urllib.parse, urllib.request

OUT = sys.argv[1] if len(sys.argv) > 1 else "out"
UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_5) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0 Safari/537.36"
URLS = """
https://hardwax.com/this-week/
https://hardwax.com/this-week/?page=2
https://hardwax.com/this-week/?page=3
https://www.rushhour.nl/
https://www.decks.de/decks/workfloor/lists/list.php?wo=ten&now_Sub=zh&now_Was=news&now_Date=nodate&aktuell=0
https://www.decks.de/decks/workfloor/lists/list.php?wo=ten&now_Sub=zz&now_Was=news&now_Date=nodate&aktuell=0
https://www.deejay.de/m_House/sm_News
https://www.deejay.de/m_House/sm_News/page_2
https://www.deejay.de/m_Techno/sm_News
https://www.deejay.de/m_Techno/sm_News/page_2
https://clone.nl/all/new
https://clone.nl/all/new?page=2
https://clone.nl/all/tag/Dub+Techno
https://clone.nl/all/tag/Minimal
https://clone.nl/all/tag/Tech+House
https://clone.nl/all/tag/Italo
https://clone.nl/all/tag/Ambient
https://clone.nl/all/genre/Electro
https://clone.nl/all/genre/Disco
https://clone.nl/all/genre/Acid
https://www.phonicarecords.com/new-releases
https://www.phonicarecords.com/new-releases/18
https://www.redeyerecords.co.uk/house-disco/new-releases
https://www.redeyerecords.co.uk/techno-electro/new-releases
https://www.redeyerecords.co.uk/balearic-and-downtempo/new-releases
https://www.redeyerecords.co.uk/experimental/new-releases
https://yoyaku.io/releases/
https://kompakt.fm/releases
https://kompakt.fm/releases?page=2
https://www.juno.co.uk/house/this-week/
https://www.juno.co.uk/techno/this-week/
https://www.juno.co.uk/disco/this-week/
https://www.juno.co.uk/downtempo/this-week/
https://www.juno.co.uk/ambient-drone/this-week/
https://www.juno.co.uk/deep-house/this-week/
https://www.juno.co.uk/tech-house/this-week/
https://www.juno.co.uk/minimal-tech-house/this-week/
https://www.juno.co.uk/electro/this-week/
https://www.juno.co.uk/balearic-downtempo/this-week/
""".split()

def fetch(url):
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "text/html,*/*", "Accept-Language": "en,de;q=0.8"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return r.status, r.read().decode(r.headers.get_content_charset() or "utf-8", "replace")

class Compact(html.parser.HTMLParser):
    """Text mit [link: url] / [img: url] / [audio: url], ohne Skripte, Styles und Navigation-Ballast."""
    SKIP = {"script", "style", "noscript", "svg", "head", "iframe"}
    BLOCK = {"div", "li", "tr", "p", "h1", "h2", "h3", "h4", "article", "section", "br", "td", "ul", "table"}
    def __init__(self, base):
        super().__init__(convert_charrefs=True)
        self.base, self.out, self.skip = base, [], 0
    def abs(self, u):
        return urllib.parse.urljoin(self.base, u.strip())
    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag in self.SKIP:
            self.skip += 1
            return
        if self.skip:
            return
        if tag in self.BLOCK:
            self.out.append("\n")
        if tag == "a" and a.get("href") and not a["href"].startswith(("#", "javascript:", "mailto:")):
            self.out.append(" [link: %s] " % self.abs(a["href"]))
        if tag == "img":
            src = a.get("data-src") or a.get("data-lazy-src") or a.get("src") or ""
            if src and not src.startswith("data:"):
                self.out.append(" [img: %s] " % self.abs(src))
        for k in ("data-src", "data-mp3", "data-url", "data-audio", "data-track", "src", "href"):
            v = a.get(k) or ""
            if re.search(r"\.mp3(\?|$)", v):
                self.out.append(" [audio: %s] " % self.abs(v))
                break
    def handle_endtag(self, tag):
        if tag in self.SKIP and self.skip:
            self.skip -= 1
    def handle_data(self, d):
        if not self.skip and d.strip():
            self.out.append(" " + d.strip())
    def text(self):
        t = "".join(self.out)
        t = re.sub(r"[ \t]+", " ", t)
        return re.sub(r"\n\s*\n+", "\n", t).strip()

def slug(u):
    return re.sub(r"[^a-z0-9]+", "-", re.sub(r"^https?://(www\.)?", "", u.lower())).strip("-")[:90]

def main():
    pdir = os.path.join(OUT, "pages")
    os.makedirs(pdir, exist_ok=True)
    idx = {"fetched": dt.datetime.utcnow().strftime("%Y-%m-%dT%H:%MZ"), "pages": []}
    rush = []
    for u in URLS:
        e = {"url": u, "file": slug(u) + ".txt"}
        try:
            st, body = fetch(u)
            c = Compact(u); c.feed(body)
            t = c.text()
            t += "\n" + "\n".join(sorted(set(" [audio: %s]" % m for m in re.findall(r"https?://[^\s\"'<>]+?\.mp3", body))))
            open(os.path.join(pdir, e["file"]), "w", encoding="utf-8").write("SOURCE %s\nFETCHED %s\n\n%s\n" % (u, idx["fetched"], t))
            e.update(status=st, chars=len(t))
            if "rushhour.nl" in u:
                rush = sorted(set(re.findall(r"https://www\.rushhour\.nl/record/[^\s\"'<>#?]+", body)))[:40]
        except Exception as ex:
            e.update(error=str(ex)[:300])
        print(e, file=sys.stderr)
        idx["pages"].append(e)
        time.sleep(1.5)
    # Rush Hour: mp3-Links stehen nur auf den Produktseiten
    found = {}
    for u in rush:
        try:
            st, body = fetch(u)
            mp3 = sorted(set(re.findall(r"https?://[^\s\"'<>]*objectstore[^\s\"'<>]+?\.mp3", body)))
            if mp3:
                found[u] = mp3
        except Exception as ex:
            if "429" in str(ex):
                break
        time.sleep(2)
    json.dump(found, open(os.path.join(pdir, "rushhour-product-mp3.json"), "w"), indent=1)
    idx["rushhour_products_checked"] = len(rush)
    json.dump(idx, open(os.path.join(pdir, "index.json"), "w"), indent=1)

if __name__ == "__main__":
    main()
