#!/usr/bin/env python3
"""Instagram handles of artists and labels from tools/artist_instagram.json (verified by hand, see tools/instagram_post.md).

Rule (user, 11.11.26): pick releases by whether artist and label can be tagged on Instagram –
of 10 carousel records at least 8 with a taggable artist and at least 8 with a taggable label.

    status(artist, label) -> {"a": [handles], "l": handle or None, "a_unknown": [names not yet checked], "l_unknown": bool}

CLI (for the daily research before the preview):
    python3 tools/ig_handles.py [YYYY-MM-DD]   lists today's fresh records (not in Today's Digs) with handle status,
                                               names still to research first."""
import json, os, re, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_DB = None
SPLIT = re.compile(r"\s+(?:/|&|\+|x|vs\.?|feat\.?|ft\.?|featuring|and|with|pres\.?|presents)\s+|\s*,\s*|\s*/\s*", re.I)
VARIOUS = {"various", "various artists", "va", "v/a", "v.a.", "unknown artist", "unknown"}
SUFFIX = re.compile(r"\s+(records|recordings|music|discos|disques|label|rec\.?)$", re.I)

def db():
    global _DB
    if _DB is None:
        _DB = json.load(open(os.path.join(ROOT, "tools", "artist_instagram.json"), encoding="utf-8"))
    return _DB

def _n(s):
    return re.sub(r"\s+", " ", (s or "").lower().strip())

def lookup(name):
    """(found, handle): found=False → not checked yet; handle None → checked, nothing to tag"""
    d, k = db(), _n(name)
    for key in (k, SUFFIX.sub("", k), k + " records"):
        if key in d:
            v = d[key]
            return True, (v.get("handle") if isinstance(v, dict) else v)
    return False, None

def artists(a):
    a = _n(re.sub(r"\(.*?\)|\[.*?\]", "", a or ""))
    if not a or a in VARIOUS:
        return []
    found, _ = lookup(a)
    if found:                       # duo names like "fk + dfp" may be an entry of their own
        return [a]
    return [p for p in (x.strip() for x in SPLIT.split(a)) if p and p not in VARIOUS]

def status(a, l):
    ha, unk = [], []
    for p in artists(a):
        found, h = lookup(p)
        if not found:
            unk.append(p)
        elif h and h not in ha:
            ha.append(h)
    lf, lh = lookup(l) if _n(l) else (True, None)
    return {"a": ha, "l": lh, "a_unknown": unk, "l_unknown": not lf}

def tier(a, l):
    """0 = artist and label taggable, 1 = one of them, 2 = artist or label still unchecked, 3 = nothing taggable"""
    s = status(a, l)
    ok = bool(s["a"]) + bool(s["l"])
    if ok == 2:
        return 0
    if ok == 1:
        return 1
    return 2 if (s["a_unknown"] or s["l_unknown"]) else 3

def main():
    sys.path.insert(0, os.path.dirname(__file__))
    import digs
    data = json.load(open(os.path.join(ROOT, "releases.json"), encoding="utf-8"))
    day = sys.argv[1] if len(sys.argv) > 1 else data["updated"]
    hist = json.load(open(os.path.join(ROOT, "92h6fy", "history.json"), encoding="utf-8"))
    dk = set(next((e.get("keys", []) for e in hist if e.get("date") == day), []))
    seen = set(k for e in hist if e.get("date") != day for k in e.get("keys", []))
    rows, done = [], set()
    for c in digs.candidates(data, day, seen):
        if c["key"] in dk or c["key"] in done:
            continue
        done.add(c["key"])
        x = c["feat"]
        s = status(x["a"], x.get("l"))
        rows.append((tier(x["a"], x.get("l")), -c["score"], x["a"], x["t"], x.get("l") or "", x["shop"], s))
    rows.sort(key=lambda r: (r[0], r[1]))
    for t, _, a, ti, l, shop, s in rows:
        print("T%d | %s – %s | %s | %s | artist %s%s | label %s" % (
            t, a, ti, l, shop, ",".join("@" + h for h in s["a"]) or "-",
            (" | TODO " + ", ".join(s["a_unknown"])) if s["a_unknown"] else "",
            ("@" + s["l"]) if s["l"] else ("TODO" if s["l_unknown"] and l else "-")))
    print("%d fresh records, %d with artist+label taggable" % (len(rows), sum(r[0] == 0 for r in rows)))

if __name__ == "__main__":
    main()
