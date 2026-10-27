#!/usr/bin/env python3
"""One-off: download today's covers (records with previews), rank by 'graphic-ness' (few dominant colours, flat areas),
save top covers at 1080 px + their first preview + a contact sheet into pick/."""
import io, json, os, sys, urllib.request
import numpy as np
from PIL import Image
UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_5) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0 Safari/537.36"
def get(u, n=30):
    return urllib.request.urlopen(urllib.request.Request(u, headers={"User-Agent": UA}), timeout=n).read()
d = json.load(open("releases.json")); day = d["updated"]
cands = []
for S in d["shops"]:
    for x in S.get("items") or []:
        want = sys.argv[1].lower() if len(sys.argv) > 1 else None          # optional: only this artist/title (any day)
        hit = (want in (x["a"] + " " + x["t"]).lower()) if want else (x.get("first_seen") == day)
        if hit and x.get("cover") and any(t.get("u") for t in x.get("tr") or []):
            cands.append(dict(x, shop=S["shop"]))
os.makedirs("pick", exist_ok=True)
res = []
for x in cands[:160]:
    try:
        im = Image.open(io.BytesIO(get(x["cover"]))).convert("RGB")
    except Exception as e:
        continue
    if min(im.size) < 500:
        continue
    sm = np.asarray(im.resize((96, 96))).reshape(-1, 3).astype(int)
    q = (sm // 48)                                          # coarse colour bins
    keys, cnt = np.unique(q[:, 0] * 100 + q[:, 1] * 10 + q[:, 2], return_counts=True)
    top = np.sort(cnt)[::-1]
    share3 = top[:3].sum() / cnt.sum()                       # how much of the cover is covered by 3 colours
    sat = np.asarray(im.resize((96, 96)).convert("HSV"))[..., 1].mean() / 255
    res.append({"a": x["a"], "t": x["t"], "shop": x["shop"], "cover": x["cover"], "url": x["url"], "share3": round(float(share3), 3),
                "sat": round(float(sat), 3), "tr": [t for t in x["tr"] if t.get("u")][:3], "l": x.get("l"), "g": x.get("g"), "im": im})
res.sort(key=lambda r: -(r["share3"] + 0.25 * r["sat"]))
sheet = Image.new("RGB", (6 * 220, 6 * 250), (20, 20, 20))
from PIL import ImageDraw
dr = ImageDraw.Draw(sheet)
for i, r in enumerate(res[:36]):
    sheet.paste(r["im"].resize((210, 210)), ((i % 6) * 220 + 5, (i // 6) * 250 + 5))
    dr.text(((i % 6) * 220 + 5, (i // 6) * 250 + 218), "%d %s" % (i, r["a"][:26]), fill=(230, 230, 230))
    r["im"].resize((1080, 1080), Image.LANCZOS).save("pick/c%02d.jpg" % i, quality=93)
    try:
        open("pick/a%02d.mp3" % i, "wb").write(get(r["tr"][0]["u"], 60))
        for k, t in enumerate(r["tr"][1:3], 1):
            open("pick/a%02d_%d.mp3" % (i, k), "wb").write(get(t["u"], 60))
    except Exception:
        pass
sheet.save("pick/sheet.jpg", quality=85)
json.dump([{k: v for k, v in r.items() if k != "im"} for r in res[:36]], open("pick/pick.json", "w"), indent=1)
print(len(cands), len(res), file=sys.stderr)
