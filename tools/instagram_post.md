# Instagram – tägliche Vorschau und Posting von «Today's Digs» und Karussell «Fresh today» (@monthlyvinyl)

Einzige Quelle für die tägliche Instagram-Aufgabe. Sprache gegenüber dem Nutzer: Deutsch, Schweizer
Schreibweise (ss statt ß), kurz und sachlich.

**Grundregel: Nie posten ohne ausdrückliches OK des Nutzers.**

**Zweite Grundregel: Nur Platten posten, die auf monthlyvinyl.net unter «Fresh today» stehen** – also
`first_seen` = heute in `releases.json` (frühestes Datum über alle Shops). Die automatischen Videos halten das
ein; bei allem, was von Hand gewählt wird (Nutzerwunsch), vor dem Posten prüfen. Eine Platte, die
Besucher auf der Startseite nicht finden, wird nicht gepostet (27.10.26: TRANSPAC war seit dem 4.10. bei Redeye). Zuerst immer eine Vorschau
(Video, Caption, Markierungen) schicken. Gepostet wird erst, wenn er in derselben Unterhaltung
zustimmt. Änderungswünsche zuerst umsetzen und neu vorlegen.

**Dritte Grundregel: Respekt vor dem Cover.** Das Artwork gehört Artist, Label und Designer. Darum:
- Das Cover wird nicht verfremdet, sondern unverändert gezeigt.
- Ist der Cover-Designer bekannt (Bandcamp-Credits, Discogs «Artwork By»/«Design»), kommt eine Zeile
  `Cover art: <Name>` bzw. `Cover art: @handle` (Handle nur verifiziert, siehe Schritt 2) in die Caption.
- Bittet jemand (Artist, Label, Designer) darum, ein Video zu löschen: sofort entfernen, ohne Diskussion, freundlich
  bestätigen und dem Nutzer melden.

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

**Keine Show-Case-Reels (Einzel-Reels) mehr (seit 30.10.26).** Sie brachten kaum Views und Reaktionen;
der Nutzer hat sie gestoppt. Die Action rendert sie eventuell weiter (`reels` in `history.json`,
`caption_reel_*.txt`): ignorieren, nicht vorlegen, nicht posten. Genre weglassen, wenn sich die Shops beim
Genre widersprechen.

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
- **So viele Markierungen wie möglich (Standard seit 4.11.26):** mehr Markierungen bringen mehr Reichweite.
  Für jede Platte gründlich suchen (Artist, Label, Remixer, Cover-Designer, Shop) und das Maximum von 20
  pro Post möglichst ausschöpfen. Nur das Kriterium «eindeutig» bleibt: lieber eine Markierung weniger als
  ein falsches Konto.
- Maximal 20 Markierungen pro Post.

## 3. Vorschau schicken (SendUserMessage + SendUserFile)

- Video als Datei
- Caption im Wortlaut (Codeblock)
- Liste der Markierungen: @handle, wer das ist, Follower, Quelle der Prüfung
- Cover-Designer (gefunden oder nicht)
- Auffälligkeiten (fehlendes Format, Pre-order, unsichere Handles)
- Frage: «Soll ich posten?»

## 4. Nach dem OK posten

1. `INSTAGRAM_POST_IG_USER_MEDIA`: `ig_user_id: "me"`, `media_type: "REELS"`, `share_to_feed: true`,
   `video_url` = Video-URL, `cover_url` = Startbild-URL (.jpg), `caption` = caption.txt,
   `user_tags` = `[{"username": "..."}]` (ohne x/y bei Reels).
2. `INSTAGRAM_POST_IG_USER_MEDIA_PUBLISH` mit der `creation_id`, `max_wait_seconds: 240`.
3. Mit `INSTAGRAM_GET_IG_USER_MEDIA` (limit 1) prüfen, dass der Post live ist; Link (permalink) melden.
Nie Erfolg melden, ohne den Post gesehen zu haben.

## 5. Karussell «Fresh today» (täglich, seit 2.11.26)

Zweiter Post jeden Tag, **nach** Today's Digs: **10 weitere Platten** von heute («Fresh today», Standard seit
4.11.26 = Instagram-Maximum; mehr Releases = mehr Reichweite; `n: 10` in `tools/genre_carousel.json`, weniger
nur, wenn es nicht genug frische Platten gibt), die nicht im Digs-Video sind, je eine Video-Slide (4:5, 30 s, eigene Hörprobe). Gleiche Grundregeln wie oben (OK des
Nutzers, nur Fresh today, Respekt vor dem Cover). Digs-Vorschau und Karussell-Vorschau dürfen in derselben
Nachricht kommen; das OK muss klar sagen, was gepostet werden soll (z. B. «beide», «nur Digs»).

**Ist es fertig?** Die Action «Genre carousel» (`tools/genre_carousel.py`, Modus `fresh` in
`tools/genre_carousel.json`) läuft automatisch nach jedem Today's-Digs-Lauf. Release `carousel`:
`https://github.com/newvinyl/newvinyl.github.io/releases/download/carousel/carousel.json` muss
`date` = heute haben und `digs_keys` = `keys` des heutigen Eintrags in `92h6fy/history.json`. Sonst bis zu
45 Minuten warten; dann Action von Hand starten (workflow_dispatch `genre_carousel.yml`) oder dem Nutzer melden.
Slides: `…/download/carousel/slide-01.mp4` … `slide-04.mp4` (Anzahl = `slides` in carousel.json),
Standbilder `slide-01.jpg` … ansehen: Cover sauber, richtige Platte, Typo lesbar.
Jede Platte gegen `releases.json` prüfen (`first_seen` = heute, nicht in `tools/not_ours.json`).

**Caption** (aus carousel.json bauen, Format wie bisher):
```
Fresh today: <n> new records, swipe to listen →

1. Artist – Title (@label oder Label)
2. …

Artists: @artist1 · @artist2
Available at @shop (1), @shop2 (2–3) and Shop ohne Handle (4, pre-order)

Previews and prices for all new releases: monthlyvinyl.net

#newvinyl #<genre> … #monthlyvinyl
```
Label nur in Klammern, wenn bekannt; Pre-order beim Shop vermerken; Hashtags aus den Genres (ohne Dubletten,
Genre weglassen bei Widerspruch). `Cover art: …` je Platte, wenn bekannt (Grundregel 3).
**Markierungen:** wie Schritt 2 (Shops, Artists, Labels, max. 20), neue Handles in `artist_instagram.json`.
Bei Karussells kommen die `user_tags` an die einzelnen Slides (die Platte, zu der das Konto gehört).

**Vorschau:** die Slides als Dateien, Caption im Codeblock, Markierungen pro Slide, Auffälligkeiten, «Soll ich posten?».

**Posten nach dem OK:**
1. Pro Slide `INSTAGRAM_POST_IG_USER_MEDIA`: `ig_user_id: "me"`, `video_url` = Slide-URL, `is_carousel_item: true`,
   `user_tags` = `[{"username": "..."}]` (nur username, Video-Items lehnen x/y ab). `creation_id`s merken.
   Dann ca. 60 s warten, bis die Items verarbeitet sind (2.11.26 so erfolgreich gepostet).
   Wenn ein Item mit Tags scheitert: ohne Tags neu anlegen und die Konten in der Caption erwähnen.
2. `INSTAGRAM_CREATE_CAROUSEL_CONTAINER` bzw. `INSTAGRAM_POST_IG_USER_MEDIA` mit `media_type: "CAROUSEL"`,
   `children` = die IDs in Reihenfolge, `caption`.
3. `INSTAGRAM_POST_IG_USER_MEDIA_PUBLISH` (`max_wait_seconds: 240`), dann mit `INSTAGRAM_GET_IG_USER_MEDIA` den
   Post prüfen und den Link melden.

**Erfahrung 4.11.26 (10 Video-Slides):** Den Karussell-Container erst anlegen, wenn alle Items `FINISHED` sind.
Items aus einem gescheiterten Karussell-Container nicht wiederverwenden (der nächste scheitert auch), immer neu anlegen.
10 Video-Items mit Markierungen (16 Tags) führten zum ERROR, 5 markierte Items und 10 Items ohne Markierungen gingen:
bei 10 Slides die Items ohne `user_tags` anlegen und die Konten in der Caption erwähnen.
