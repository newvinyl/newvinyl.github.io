"""Fasst dieselbe Platte aus verschiedenen Shops zu einer Karte zusammen.

Die Shops schreiben Artist und Titel unterschiedlich ("Various" / "VARIOUS" / "Various Artists",
"Tears Maker Chant - Green Vinyl" / "Tears Maker Chant - 2026 Green Vinyl Repress",
"Demuja Presents Dubmuja" / "Presents Dubmuja", "Acid Kickers Vol 2" / "Acid Kickers Vol.2").
Die Seite gruppiert nach norm(a)|norm(t); dieses Skript erkennt solche Varianten und schreibt
allen Einträgen einer Gruppe denselben Schlüssel ins Feld "gk". Seite und build_static.py
verwenden r.gk, wenn vorhanden. Einträge, deren eigener Schlüssel schon passt, bekommen kein "gk".

Aufruf: python3 tools/group_keys.py [releases.json]   (läuft auch automatisch in build_static.py)
"""
import json, os, re, sys, unicodedata


def fold(s):
    s = unicodedata.normalize("NFKD", str(s or "").lower())
    return "".join(c for c in s if not unicodedata.combining(c))


def norm(s):  # identisch mit der Seite
    s = fold(s)
    s = re.sub(r"\(.*?\)|\[.*?\]", "", s)
    s = re.sub(r'\b(ep|lp|12"?|2x12"?)\b', "", s)
    return re.sub(r"[^\w]", "", s)


def base_key(r):
    return norm(r.get("a")) + "|" + norm(r.get("t"))


PART = re.compile(r"[(\[]\s*(part|pt\.?|vol\.?|volume|chapter|disc)\s*([\w]+)\s*[)\]]", re.I)


def keep_parts(t):
    """«(Part 2)» gehört zum Titel: Teil 1 und Teil 2 sind verschiedene Platten."""
    return PART.sub(lambda m: " " + re.sub(r"\W", "", m.group(1)).replace("pt", "part") + m.group(2) + " ", fold(t))


def exact_key(r):
    return norm(r.get("a")) + "|" + norm(keep_parts(r.get("t")))


VARIOUS = {"various", "variousartists", "va", "v/a", "vavariousartists", "unknownartist", "unknown"}


def artist_core(a):
    a = fold(a).strip()
    a = re.split(r"\s*(?:/|,|&|\+| feat\.? | ft\.? | and | x | vs\.? | aka )\s*", a)[0]
    a = re.sub(r"[^\w/]", "", a)
    return "various" if a in VARIOUS or a.startswith("variousartist") else a


def title_core(t):
    t = keep_parts(t)
    t = re.sub(r"\(.*?\)|\[.*?\]", " ", t)
    t = re.split(r"\s[-–—]\s", t)[0]                    # "Titel - Green Vinyl", "Titel - 3x12\""
    t = re.sub(r"^.*?\bpresents?\b:?\s*", "", t)         # "Demuja Presents Dubmuja"
    t = re.sub(r"\bvol(?:ume)?\b\.?\s*", " vol ", t)
    t = re.sub(r'\b(e\.?p\.?|lp|2lp|3lp|12"?|2x12"?|3x12"?|the remixes|remixes|remastered|reissue|repress)\b', " ", t)
    t = re.sub(r"[^\w]", "", t)
    return t


def fuzzy_key(r):
    a, t = artist_core(r.get("a")), title_core(r.get("t"))
    if not a or not t:
        return None
    # Kurze oder allgemeine Titel nur zusammen mit dem Label zusammenfassen
    if len(t) < 3 or (a == "various" and (len(t) < 8 or re.fullmatch(r"vol\d+|\d+", t))):
        lab = re.sub(r"[^\w]", "", fold(r.get("l")))
        if not lab:
            return None
        t = t + "@" + lab
    return a + "|" + t


def label_key(r):
    """Gleicher Titel auf gleichem Label, auch wenn ein Shop nur «Various» als Artist schreibt."""
    t = title_core(r.get("t"))
    lab = re.sub(r"[^\w]", "", fold(r.get("l")))
    if len(t) < 6 or not lab or re.fullmatch(r"(untitled|sampler|various|vol\d+|ep\d+|\d+)", t):
        return None
    return t + "@" + lab


def assign_group_keys(data):
    items = [r for S in data.get("shops", []) for r in S.get("items", []) or []]
    parent = list(range(len(items)))

    def find(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    def union(i, j):
        a, b = find(i), find(j)
        if a != b:
            parent[max(a, b)] = min(a, b)

    for keyf in (exact_key, fuzzy_key, label_key):
        first = {}
        for i, r in enumerate(items):
            k = keyf(r)
            if k is None:
                continue
            if k in first:
                union(i, first[k])
            else:
                first[k] = i

    groups = {}
    for i in range(len(items)):
        groups.setdefault(find(i), []).append(i)
    changed = 0
    for root, idx in groups.items():
        canon = exact_key(items[min(idx)])  # Schlüssel des ersten Eintrags (Reihenfolge in der Datei)
        for i in idx:
            r = items[i]
            want = canon if base_key(r) != canon else None
            if r.get("gk") != want:
                changed += 1
                if want:
                    r["gk"] = want
                else:
                    r.pop("gk", None)
    merged = sum(1 for idx in groups.values() if len({base_key(items[i]) for i in idx}) > 1)
    return changed, merged


def group_key(r):
    return r.get("gk") or base_key(r)


if __name__ == "__main__":
    path = sys.argv[1] if len(sys.argv) > 1 else os.path.join(os.path.dirname(__file__), "..", "releases.json")
    data = json.load(open(path, encoding="utf-8"))
    changed, merged = assign_group_keys(data)
    if changed:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=1)
    print(f"group keys: {merged} zusammengefasste Gruppen, {changed} Einträge geändert")
