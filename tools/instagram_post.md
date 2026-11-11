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

**Vierte Grundregel: Keine Releases, bei denen Sony Music die Rechte hält (seit 10.11.26).** Instagram sperrt
solche Reels in 9 Regionen, u. a. USA. `tools/digs.py` (auch Karussell, Wochenrückblick) filtert über
`tools/rights_block.json` (Sony-Labels wie Columbia, Epic, RCA, Arista, Legacy, Ministry Of Sound, Deconstruction,
Ultra, The Orchard, AWAL …, dazu Artists und Titel). Zusätzlich in der Vorschau jede Platte prüfen: Reissues,
Edits, Remixe und Bootlegs bekannter Hits → Rechteinhaber des Originals suchen (Discogs «Phonographic Copyright ℗»,
«Licensed From», «Copyright ©»). Gehört er zu Sony: nicht vorlegen, sondern ersetzen (bei Digs `92h6fy/reel_request.json`,
beim Karussell neu rendern) und den Fall in `rights_block.json` ergänzen. Meldet der Nutzer eine Sperre, den Release
dort sofort eintragen.

## 1. Ist das Video von heute fertig?

- Repo `newvinyl/newvinyl.github.io` (Branch `main`) holen bzw. `git pull`.
- `92h6fy/history.json`, erster Eintrag: `date` muss heute sein (Europe/Zurich) und `dv` muss dem
  `DIGS_V` in `tools/digs.py` entsprechen. Sonst prüfen, ob die Action «Today's Digs» (`digs.yml`) heute
  schon läuft oder in der Warteschlange ist (GitHub MCP `actions_list`, `list_workflow_runs`, `digs.yml`).
  **Läuft keine, sie sofort selbst starten** (`actions_run_trigger`, `run_workflow`, `digs.yml`, ref `main`;
  geht das nicht: Zeile in `tools/digs_request.txt` anhängen, committen, pushen). Nicht nur warten: der
  grosse Push des Daily Updates startet die Action nicht von selbst (10.11.26 deshalb ohne Video bis Mittag).
  Voraussetzung: `releases.json` hat `updated` = heute; sonst läuft das Daily Update noch, dann warten.
  Das Rendern dauert ca. 30–45 Minuten; bis zu 60 Minuten warten und erneut prüfen. Ist es dann immer noch
  nicht da, dem Nutzer kurz melden (PushNotification) und aufhören.
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
- **Reihenfolge der Priorität (Nutzer, 11.11.26), für alle Beiträge und Reels:** 1. Artists (inkl. Remixer,
  Aliase), 2. Labels, 3. Shops. Reicht das Limit von 20 nicht, zuerst Shop-Markierungen streichen (Shop dann nur
  als @Erwähnung in der Caption), danach Labels; Artists zuletzt. In der Vorschau und in `user_tags` die Konten in
  dieser Reihenfolge auflisten (Artists zuerst).

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

**Auswahl nach Markierbarkeit (Nutzer, 11.11.26, Pflicht):** Von 10 Platten müssen **mind. 8 einen markierbaren
Artist** (geprüftes öffentliches Konto) haben **und mind. 8 ein markierbares Label**. Bei weniger Slides anteilig
(aufgerundet, `ig.need` in carousel.json). `genre_carousel.py` wählt darum zuerst Platten, deren Artist und Label in
`tools/artist_instagram.json` ein Konto haben (Stufe 0), dann eines von beiden (1), dann ungeprüfte (2), zuletzt ohne
Konto (3); `carousel.json` enthält pro Slide `ig_a`, `ig_l`, `ig_todo` und gesamt `ig` (`artist_ok`, `label_ok`, `need`).
Ablauf jeden Morgen, bevor die Vorschau rausgeht:
1. `ig` in carousel.json prüfen. Reicht `artist_ok` oder `label_ok` nicht: `python3 tools/ig_handles.py` listet alle
   frischen Platten von heute (ohne Digs) mit Status; Zeilen mit `TODO` = Artist/Label noch nicht recherchiert.
2. Die TODO-Namen der bestplatzierten Platten (Stufe 1, dann 2) wie in Schritt 2 recherchieren und prüfen, Ergebnis
   in `artist_instagram.json` (Handle oder `null`), committen, pushen – so lange, bis mind. 10 Platten Stufe 0 sind
   bzw. die 8/8-Regel erfüllbar ist.
3. Action «Genre carousel» von Hand starten (workflow_dispatch `genre_carousel.yml`, ref `main`), ca. 30–45 Min.
   warten, carousel.json erneut prüfen. Erst dann die Vorschau schicken.
4. Ist die Regel auch so nicht erfüllbar (zu wenige frische Platten mit Konten): mit weniger Slides posten, sodass
   die Regel stimmt (`n_by_date` in `genre_carousel.json`), und das in der Vorschau sagen.
In der Vorschau die Zählung angeben: «Artists markierbar: x/10, Labels markierbar: y/10».

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
Bei Karussells kommen die `user_tags` an die einzelnen Slides (die Platte, zu der das Konto gehört): pro Slide
Artist(s) + Label + Shop, soweit geprüft – Priorität Artists > Labels > Shops (siehe Schritt 2): wird es über 20,
zuerst wiederholte bzw. alle Shop-Tags streichen, dann Labels. **Pflicht seit 10.11.26** – die Karussells vom 4.–10.11. gingen ganz ohne
Markierungen raus, und nachträglich lassen sich Markierungen und Caption über die API NICHT ändern (nur von Hand in
der App). Private Konten (z. B. trinidadiandeep) lassen sich nicht markieren: nur als @Erwähnung in die Caption,
immer mit «@». In der Vorschau pro Slide die Markierungen auflisten.

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
**Test 10.11.26:** 10 Video-Items mit 15 `user_tags` (1–2 pro Slide) → alle Items und der Karussell-Container
`FINISHED`. Also: Items MIT Markierungen anlegen, ca. 60–90 s warten, Status aller Items prüfen
(`INSTAGRAM_GET_MULTIPLE_NODES`, fields `status_code`), dann Container anlegen und dessen Status prüfen, erst dann
publizieren. Nur wenn ein Item oder der Container `ERROR` meldet: neue Items anlegen, zuerst mit weniger Tags
(max. 2 pro Slide), erst als letzte Möglichkeit ohne Tags – und das dem Nutzer melden.

## 5b. Wochenrückblick (jeden Sonntag 16:00, seit 8.11.26)

Ein Reel, **eine Platte pro Wochentag** (Montag–Sonntag der laufenden Woche), je 6 s Hörprobe, 42 s.
Design (vom Nutzer am 8.11.26 abgenommen): **gelber Hintergrund, schwarze Typo**, reduziert – Wochentag gross
(MONDAY …), Cover unverändert, Artist fett, Titel, klein monthlyvinyl.net. Soll sich klar von Digs und Karussell
abheben (nicht das Digs-Layout verwenden).
**Titelbild** (abgenommen 8.11.26, `"intro": 2.0` in weekly_recap.json, Stil `row`): klein «WEEKLY» / «WEEK NN»,
riesiges «RECAP», alle 7 Covers nebeneinander von Rand zu Rand (keine Wochentag-Labels), klein Datum und
«7 RECORDS». Es läuft 2 s am Anfang des Reels und ist das Startbild (`cover_url` = `weekly-recap-week-NN-title.jpg`).
Erster Rückblick: KW 45, gepostet 8.11.26 um 16:55.

**Ablauf (Sonntag, Vorschau ca. 14:30):**
1. Insights der Woche holen (`INSTAGRAM_GET_IG_USER_MEDIA` ab Montag 00:00, dann `INSTAGRAM_GET_IG_MEDIA_INSIGHTS`
   mit views, reach, likes, comments, saved, shares, total_interactions, ig_reels_avg_watch_time) und kurz auswerten
   (Tabelle pro Tag: Digs-Reel und Karussell).
2. Pro Wochentag eine Platte aus dem Digs des Tages wählen (`92h6fy/history.json`): stärkste/bekannteste, **echtes
   Cover in guter Auflösung** (kein Mockup, keine schwarze Hülle, kein kleines Label-Foto), noch in `releases.json`.
3. `tools/weekly_recap.json` schreiben (`week`, `range`, `seg`, `picks` mit day/artist/title/show_artist/show_title),
   committen und pushen → Action «Weekly recap» rendert (`tools/weekly_recap.py`, nur dort sind die Shops erreichbar)
   und lädt `weekly-recap-week-NN.mp4/.jpg` + `recap.json` ins Release `recap`. `recap.json` zeigt Cover-Quelle und
   -Grösse; unter ~500 px lieber eine andere Platte des Tages nehmen.
4. Vorschau (Video, Übersicht, Caption, Markierungen, Auswertung), «Soll ich posten?». Posten erst nach OK des
   Nutzers **in seiner eigenen Nachricht** (eine geplante Erinnerung zählt nicht als OK), wie Today's Digs als
   REELS mit `user_tags` (max. 20). GitHub-Release-Downloads können scheitern (8.11.26: 504): dann Video kurz unter
   `ig/<yymmdd>/` auf GitHub Pages legen, `https://monthlyvinyl.net/ig/...` verwenden und danach wieder löschen.

**Caption:**
```
Week <NN> in 7 records – one dig for every day (<range>) 🎧

Monday – Artist – Title (@label) · @shop
…
Artists: @a · @b

Previews and prices for all new releases: monthlyvinyl.net

#newvinyl #vinylrecords #weeklydigs #<genres> #monthlyvinyl
```

## 6. Stories (nur auf Wunsch des Nutzers, seit 4.11.26)

**Nicht automatisch und nicht geplant** – nur wenn der Nutzer Stories verlangt (4.11.26: «nicht planen, zu aggressiv»).
**Höchstens 5 Stories** pro Tag, gepostet **zwischen 13:00 und 22:45** (Europe/Zurich). Nur nach
Today's Digs und dem Karussell (beide müssen gepostet sein). Gleiche Grundregeln (OK des Nutzers, nur Fresh today,
Respekt vor dem Cover).

**Bauen:** `python3 tools/stories.py --date <heute> --work <tmp> --out stories/<yymmdd>` holt Digs-Video und
Karussell-Slides aus den Releases (kein Shop-Zugriff nötig) und wählt die 5 Platten mit den meisten geprüften
Handles (Digs bei Gleichstand zuerst). Design (vom Nutzer am 4.11.26 abgenommen): reduziert, Cover gross, Artist fett,
Titel, monthlyvinyl.net, gelb auf Schwarz; @handles (Shop, Label, Artist, nur aus `shop_instagram.json` und
`artist_instagram.json`) als Typewriter-Sticker, weiss auf schwarzem Kasten, leicht schräg, auf einer Kante des Covers,
jedes Mal an einer anderen Stelle. Ton: Hörprobe (Digs 10 s, Karussell 15 s). Ergebnis: `story-01.mp4` … und
`stories.json` (Datei, Handles).

**Vorschau:** Übersichtsbild + die Videos, Handles pro Story, «Soll ich posten?».

**Posten nach dem OK** (nur zwischen 13:00 und 22:45):
1. Dateien in `stories/<yymmdd>/` committen und pushen (GitHub Pages, ca. 1 Min.), URL
   `https://monthlyvinyl.net/stories/<yymmdd>/story-NN.mp4`.
2. Pro Story `INSTAGRAM_POST_IG_USER_MEDIA`: `ig_user_id: "me"`, `media_type: "STORIES"`, `video_url`,
   `user_tags` = `[{"username": "..."}]` (wie in stories.json; am 4.11.26 so akzeptiert).
3. In der Reihenfolge `INSTAGRAM_POST_IG_USER_MEDIA_PUBLISH` (`max_wait_seconds: 240`), dann mit
   `INSTAGRAM_GET_IG_USER_STORIES` prüfen und die Links melden.
4. `stories/<yymmdd>/` wieder löschen, committen, pushen.
