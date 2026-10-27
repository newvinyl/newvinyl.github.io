#!/usr/bin/env python3
import os, urllib.request
UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_5) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0 Safari/537.36"
os.makedirs("probe", exist_ok=True)
for i, u in enumerate(["https://cdn-next.dancingvinyl.com/catalog/products/cmto4hdpp01w6cof7ol7l7qil/supplier/51d268253a2aae9a6cccfe09a017cad9c08edd36ff68af321d66c214de09f642.jpg",
                       "https://cdn-next.dancingvinyl.com/catalog/products/cmto4hdpp01w6cof7ol7l7qil/supplier/5e2e9274e669871334177c0533d9aa5a99a17d7cc21fb14e4d9d65da8acc0065.jpg"]):
    try:
        open("probe/dv%d.jpg" % i, "wb").write(urllib.request.urlopen(urllib.request.Request(u, headers={"User-Agent": UA}), timeout=30).read())
    except Exception as e:
        print(i, e)
