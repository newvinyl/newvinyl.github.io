# Instagram – tägliche Vorschau und Posting von «Today's Digs» und drei Einzel-Reels (@monthlyvinyl)

Einzige Quelle für die tägliche Instagram-Aufgabe. Sprache gegenüber dem Nutzer: Deutsch, Schweizer
Schreibweise (ss statt ß), kurz und sachlich.

**Grundregel: Nie posten ohne ausdrückliches OK des Nutzers.** Zuerst immer eine Vorschau
(Video, Caption, Markierungen) schicken. Gepostet wird erst, wenn er in derselben Unterhaltung
zustimmt. Änderungswünsche zuerst umsetzen und neu vorlegen.

## 1. Ist das Video von heute fertig?

- Repo `newvinyl/newvinyl.github.io` (Branch `main`) holen bzw. `git pull`.
- `92h6fy/history.json`, erster Eintrag: `date` muss heute sein (Europe/Zurich) und `dv` muss dem
  `DIGS_V` in `tools/digs.py` entsprechen. Sonst bis zu 45 Minuten warten und erneut prüfen
  (GitHub Action «Today's Digs» rendert nach dem täglichen Update). Ist es dann immer noch nicht da,
  dem Nutzer kurz melden und aufhören.
- Video: `https://github.com/newvinyl/newvinyl.github.io/releases/download/digs/todays-digs-<yymmdd>.mp4`
- Startbild: gleiche URL mit `.jpg` statt `.mp4`
- Caption: `92h6fy/caption.txt` (genau so übernehmen)

Video herunterladen, die Bilder bei 0 s, 3 s, 18 s und 33 s ansehen und prüfen: kein schwarzes
Startbild, Titel lesbar, Cover sauber (kein Aufkleber/Mockup, richtige Platte), Shop-Zeile vorhanden.
Fehler dem Nutzer melden statt zu posten.

**Zusätzlich drei Einzel-Reels (seit 27.10.26).** `92h6fy/history.json`, erster Eintrag, Liste `reels`
(je `title`, `video` = `reel-<yymmdd>-1.mp4` … `-3.mp4`, `look`). Startbild: gleiche URL mit `.jpg`.
Captions: `92h6fy/caption_reel_1.txt` … `caption_reel_3.txt`. Format 9:16: das Cover läuft oben und unten in
seiner eigenen Fläche weiter, Form- und Farb-Loop (`tools/shapeloop.py` / `tools/poster916.py`), gelbe Typo
unter dem Cover (Artist, Titel, Label · Shop, monthlyvinyl.net). Prüfen: Bilder bei 0 s, 4 s, 20 s, 40 s –
Cover erkennbar, nichts zerrissen, Typo vorhanden. Beginnt `look` nicht mit «poster916», war kein grafisches
Cover dabei (alter Effekt-Look): in der Vorschau als Ausnahme kennzeichnen.
Für jedes Reel gelten die Schritte 2–4 (eigene Markierungen: Artist, Label, Shop; eigene Vorschau; eigener
Post nach dem OK). Reihenfolge: Today's Digs zuerst, dann Reel 1–3. Genre weglassen, wenn sich die Shops
beim Genre widersprechen. Fehlt ein Reel (Liste kürzer), nur die vorhandenen vorlegen und es erwähnen.

## 2. Markierungen recherchieren

Für jede der drei Platten: Shop, Artist(s), Label.

- **Shops:** `tools/shop_instagram.json` (geprüft). `null` = nicht markieren.
- **Artists/Labels:** zuerst `tools/artist_instagram.json` (Schlüssel = Name klein geschrieben).
  Fehlt ein Eintrag: Handle über offizielle Quellen suchen (Bandcamp, eigene Website, Linktree,
  Resident Advisor, Discogs «Sites», Booking-Agentur) mit WebSearch/WebFetch. Suchtreffer-Titel allein
  reichen nicht.
- Jeden neuen Handle mit `SCRAPECREATORS_GET_INSTAGRAM_PROFILE` (über den Instagram-Konnektor /
  Composio, `cache_max_age: "30d"`) prüfen: öffentlich, Name/Bio passen, verlinkt die richtige Seite.
  Kostet ca. 0,001 $ pro Abfrage.
- **Nur markieren, wenn eindeutig.** Bei Zweifel (Allerweltsname, unpassende Bio) weglassen und in der
  Vorschau erwähnen.
- Gefundene und geprüfte Handles in `tools/artist_instagram.json` ergänzen (auch `null`, wenn sicher
  kein Konto existiert) und committen/pushen.
- Der Nutzer will gezielt auch kleine, aktive Konten pushen: grosse Konten sind kein Muss.
- Maximal 20 Markierungen pro Post.

## 3. Vorschau schicken (SendUserMessage + SendUserFile)

- Video als Datei
- Caption im Wortlaut (Codeblock)
- Liste der Markierungen: @handle, wer das ist, Follower, Quelle der Prüfung
- Auffälligkeiten (fehlendes Format, Pre-order, unsichere Handles)
- Frage: «Soll ich posten?»

## 4. Nach dem OK posten

1. `INSTAGRAM_POST_IG_USER_MEDIA`: `ig_user_id: "me"`, `media_type: "REELS"`, `share_to_feed: true`,
   `video_url` = Video-URL, `cover_url` = Startbild-URL (.jpg), `caption` = caption.txt,
   `user_tags` = `[{"username": "..."}]` (ohne x/y bei Reels).
2. `INSTAGRAM_POST_IG_USER_MEDIA_PUBLISH` mit der `creation_id`, `max_wait_seconds: 240`.
3. Mit `INSTAGRAM_GET_IG_USER_MEDIA` (limit 1) prüfen, dass der Post live ist; Link (permalink) melden.
Nie Erfolg melden, ohne den Post gesehen zu haben.
