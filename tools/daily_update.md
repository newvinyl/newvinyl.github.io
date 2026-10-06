# Daily update – Monthly Vinyl (monthlyvinyl.net)

This file is the single source of truth for the daily update task. The scheduled task only says
"follow tools/daily_update.md". To add or change a shop, edit this file (commit to main); no change
to the scheduled task is needed.

Reply to the user in German (Swiss spelling, "ss" not "ß"), one short final message.

The site runs in two places with the same data file: the live website https://monthlyvinyl.net
(GitHub Pages, repo newvinyl/newvinyl.github.io, branch main) and a preview artifact
https://claude.ai/artifact/MYi1YSiJFww9TC4v8payVT. It lists new vinyl releases from several online
shops in these genres (all subgenres): House (deep, tech, minimal, acid, Chicago, Detroit …), Techno
(dub, minimal, acid, deep …), Electro, Balearic / Downtempo, Ambient, Disco / Nu-Disco / Disco Edits,
Italo Disco / Cosmic. Skip drum & bass, jungle, UK hardcore, dubstep, UK garage, hip hop, reggae, pop,
rock, jazz, soundtracks, CDs, cassettes, merchandise, books. The page's genre filter offers House,
Deep House, Tech House, Minimal, Techno, Dub Techno, Electro, Acid House, Balearic, Ambient, Disco and
Italo Disco; always tag a release with the most specific of these subgenres the shop names, so every
filter has records.

Your job: add today's new releases to releases.json, make sure as many as possible can be listened to,
and publish it to both places. Do not change the page design or code by hand (never edit index.html
yourself; only tools/build_static.py may regenerate parts of it). Other automation also commits to
this repo (GitHub Actions "Today's Digs" and "Preview check"); always pull/rebase before pushing.

## 1. Data sources to start from

Read the artifact with the Artifact tool (action "read", url above) so the publish is allowed and you
get the saved page file. Then read its data file: Artifact action "read" with the same url and path
"releases.json". Load it as JSON. Also load <dir>/releases.json from the repo. Merge both (union by
shop + url) so no item is lost; for shop-level fields (where, country, cur, blocked, note) the repo
version wins. Use the newer "fx".

## 2. Data format of releases.json

{"updated":"YYYY-MM-DD","fx":{"CHF":1,"EUR":rate,"GBP":rate,"USD":rate,"date":"YYYY-MM-DD"},"shops":[{"shop":"Hardwax","where":"Berlin","country":"DE","cur":"€","date":"new wk 40","items":[ITEM,...]}, ..., {"shop":"OYE Records","country":"DE","where":"Berlin","blocked":true,"note":"..."}]}

"country" is the ISO code of the shop's home country (CH, DE, NL, FR, UK …) and "where" its city; keep
both on every shop. "fx" = value of 1 unit of each currency in CHF.

ITEM = {"a":artist,"t":title,"l":label,"cat":catalog number or "","f":format like "12\"" / "LP" / "2×12\"","p":price number or null,"g":genre string in English using " / " between genres and " · Reissue" / " · Repress" when relevant (use these names where they fit: House, Deep House, Tech House, Minimal, Minimal House, Acid House, Chicago House, Detroit House, Techno, Dub Techno, Minimal Techno, Acid Techno, Deep Techno, Electro, Breakbeat, Balearic, Downtempo, Ambient, Disco, Italo Disco, Cosmic, Edits; never use "Lo-Fi House" — use House instead),"m":"YYYY-MM" month it first appeared,"first_seen":"YYYY-MM-DD","url":product page URL,"cover":cover image URL,"tr":[TRACK,...],"d":optional release date / week text,"st":optional stock status "in" | "low" | "pre" | "out" (only if the shop page states it: in stock / low stock or "last copies" / pre-order / sold out),"bpm":optional number,"mk":optional musical key text like "Am" or "8A"}

Only fill "st", "bpm" and "mk" when the shop page shows them; never guess. Never use a field named
"key" in items (the page uses that name internally).

TRACK is one of: {"s":side like "A1","n":track name,"u":direct mp3 preview URL} (preferred) or
{"s":..,"n":..,"yt":YouTube video id} or {"s":"","n":"Whole EP on YouTube","ytl":YouTube playlist id}
or {"s":..,"n":..,"page":product URL} (last resort, not playable on the page).

Keep every existing item (never delete; the start page shows this month and last month, older months
are on the "Past" page). Keep shop order. The same record may appear in several shops — keep each
shop's item; the page merges them into one card with a price comparison, so keep artist and title
spelled as the shop does. Keep any extra fields other automation added to items (e.g. preview-check
fields); do not remove them.

## 3. Exchange rates

Look up today's EUR→CHF, GBP→CHF and USD→CHF rates (WebSearch, e.g. "EUR CHF exchange rate today"; a
central bank or major financial site). If you find clear current values, update "fx" with them and
today's date; otherwise leave "fx" unchanged.

## 4. Shops

For each shop that is not "blocked", read its new-release pages with WebFetch. Ask WebFetch for
compact JSON lines copied exactly from the page and to use null for anything missing. Follow "next
page" links while the releases are still new (this week / last 7 days), max 3 pages per list.

- Hardwax (Berlin, DE): https://hardwax.com/this-week/ and ?page=2, ?page=3. Direct mp3s at
  media.hardwax.com/audio/ID_SIDE.mp3 (use the vinyl links, not "_clip"). Price €.
- Rush Hour (Amsterdam, NL): https://www.rushhour.nl/ (new releases with week numbers; prices usually
  not shown → null; store the week as "d"; pre-orders → "st":"pre"; skip pre-orders dated "W 52",
  which is a placeholder). Rush Hour only tags coarse genres; use its Disco / Italo / Electro /
  Ambient / Balearic tags where given. Each product page has direct mp3s on
  objectstore.true.nl/rushhourrecords:files/tracks/… — fetch the product page and ask only for those
  mp3 URLs; stop fetching product pages if the site answers 429.
- Decks.de (DE): https://www.decks.de/decks/workfloor/lists/list.php?wo=ten&now_Sub=zh&now_Was=news&now_Date=nodate&aktuell=0
  (house) and the same with now_Sub=zz (techno); the page sometimes breaks after one entry — take what
  is there.
- Deejay.de (Wiesbaden, DE): https://www.deejay.de/m_House/sm_News and
  https://www.deejay.de/m_Techno/sm_News (page 1; /page_2 only if still needed). Take only releases
  whose shown date is yesterday or today (Europe/Zurich); skip later pre-order dates. Price €. Style
  tags: House+Deep → Deep House, House+Minimal → Minimal House, House+Tech → Tech House, House alone
  → House, Techno → Techno (Techno+Minimal without House → Minimal Techno), Electro → Electro, Disco
  → Disco, Breaks → Breakbeat; join several with " / "; add " · Reissue" if tagged Classics. Format
  "12inch"/"excl" → 12", "2x12inch" → 2×12", "LP" → LP. "In Stock" → "st":"in"; "ships from …" or
  "collecting" → "st":"pre". No direct mp3s: store tracks as {"s":side,"n":name,"page":product URL}
  and let step 6 find previews. The shop entry must not carry "blocked"/"note".
- Clone (Rotterdam, NL): https://clone.nl/all/new and ?page=2. Also the subgenre lists (sorted newest
  first, with release dates; take releases dated within the last 7 days or upcoming, page 1 only):
  https://clone.nl/all/tag/Dub+Techno (→ "Dub Techno"), https://clone.nl/all/tag/Minimal (→
  "Minimal"), https://clone.nl/all/tag/Tech+House (→ "Tech House"), https://clone.nl/all/tag/Italo
  (→ "Italo Disco"), https://clone.nl/all/tag/Ambient (→ "Ambient"), https://clone.nl/all/genre/Electro
  (→ "Electro"), https://clone.nl/all/genre/Disco (→ "Disco", skip soul/funk),
  https://clone.nl/all/genre/Acid (→ "Acid House" if house-based, "Acid Techno" if techno-based). Put
  the list's subgenre into "g" (join several with " / "); future release dates → "st":"pre". Direct
  mp3s follow https://clone.nl/platen/mp3/ITEMID/<track label as listed, e.g. "1 Meteora">.mp3
  (URL-encode the label; ITEMID is the number in itemNNNNN.html).
- Phonica (London, UK): https://www.phonicarecords.com/new-releases and /new-releases/18 (price £;
  genre pages are blocked by robots, do not use them; skip merchandise). No direct mp3s.
- Redeye Records (London, UK): https://www.redeyerecords.co.uk/house-disco/new-releases,
  https://www.redeyerecords.co.uk/techno-electro/new-releases,
  https://www.redeyerecords.co.uk/balearic-and-downtempo/new-releases (→ "Balearic" / "Downtempo")
  and https://www.redeyerecords.co.uk/experimental/new-releases (only its ambient releases →
  "Ambient") (price incl. VAT £; only in-stock → "st":"in"). One direct preview per release:
  https://sounds.redeyerecords.co.uk/IMAGEID.mp3 where IMAGEID is the number in the cover URL
  /imagery/IMAGEID-2.jpg → track {"s":"","n":"Preview","u":…}.
- Yoyaku (Paris, FR): https://yoyaku.io/releases/ (genres listed per release; skip items whose image
  upload path is older than the current year unless clearly a current-year reissue). No direct mp3s.
  Use the product page links containing "/release/", never add-to-cart links.
- Kompakt (Cologne, DE): https://kompakt.fm/releases and https://kompakt.fm/releases?page=2 — take
  product URLs, covers, artist, title, label, cat no., format and € price from the list; assign genres
  only if the page or the product page names them, otherwise use the label's known style
  conservatively (e.g. Kompakt → Techno / Minimal) or skip the item. Skip CDs and merchandise.
- Juno Records (London, UK): https://www.juno.co.uk/house/this-week/, /techno/this-week/,
  /disco/this-week/, /downtempo/this-week/, /ambient-drone/this-week/, and the subgenre pages
  https://www.juno.co.uk/deep-house/this-week/, https://www.juno.co.uk/tech-house/this-week/,
  https://www.juno.co.uk/minimal-tech-house/this-week/, https://www.juno.co.uk/electro/this-week/,
  https://www.juno.co.uk/balearic-downtempo/this-week/ (direct mp3s at juno.co.uk/MP3/…). Pages are
  very long and may be cut off; take only releases you can actually see with full data. If a URL does
  not exist or shows no listings, skip it.

Blocked shops stay blocked: OYE Records Berlin (product links and covers on its new-releases page
cannot be read). Swiss shops were checked (Plattfon Basel blocks automated reading; Six Pack, Sihl
Records, Panthera, Zero Zero, Ex Libris, cede.ch have no readable list of new house/techno records) —
do not add them unless one clearly offers a readable new-releases list; if so, add it as a new shop
with "country":"CH".

Only use data that is actually on the pages; never invent prices, dates, tracks, genres or URLs. If a
WebFetch answer looks inconsistent (old years like 2020, empty urls), discard it. If a site refuses
automated access or fails (including 403 or rate limits), skip it for today, leave its items as they
are and do not retry that page. Do not work around a blocked site.

## 5. New vs. existing

A release is new if no existing item in that shop has the same url or the same artist + title. For
each new one add an ITEM with "m" = current month (YYYY-MM, Europe/Zurich) and "first_seen" = today.
For existing items you see again today, update "p" and "st" if the page shows new values (a pre-order
whose release date has passed and is shown as available → "in"), and refine "g" if the shop now names
a more specific subgenre (keep " · Reissue" / " · Repress").

## 6. Make releases listenable

For every item (new or existing, current month first) that has no track with "u", "yt" or "ytl":
(a) if the same artist + title exists in another shop with playable tracks, copy those tracks;
(b) otherwise search YouTube with WebSearch (allowed_domains ["youtube.com"], query "<artist> <title>"
plus label if helpful) and use a result only if its title clearly names this artist and this release
or one of its tracks. Use youtube.com/watch?v=ID as {"yt":ID} and official album playlists
(list=OLAK5uy_… or a label playlist named after this release) as {"ytl":ID}. Never guess IDs. Do at
most 40 YouTube searches per run; new items first.

## 7. Write

Set "updated" to today's date (YYYY-MM-DD). Write releases.json (valid JSON, UTF-8, indent=1,
ensure_ascii=False). Check it parses (python3 -m json.tool) before publishing.

## 8. Publish to the live website

Inside <dir>: copy your releases.json over <dir>/releases.json, run `python3 tools/build_static.py`
(regenerates the crawlable list in index.html, genre pages, /r/ release pages, sitemap.xml, llms.txt).
Do not change any other file by hand; never delete CNAME, .nojekyll, favicon-32.png,
apple-touch-icon.png, og-image.png, robots.txt, BingSiteAuth.xml or tools/. If the build script
fails, still publish releases.json alone and report the error. If nothing changed, skip this step.
Otherwise `git add -A`, commit with author name "Claude" and email "noreply@anthropic.com" and the
message "Daily update YYYY-MM-DD: N new releases", `git pull --rebase origin main` (rerun the build
script and recommit if releases.json changed in the rebase), then `git push origin main` (GitHub
Pages publishes only from main). If the push fails, retry once. Then verify: `git fetch origin` and
check that origin/main contains your commit. If it does not, say so clearly in the final message —
never report success without this check.

## 9. Republish the preview artifact

Artifact publish with url https://claude.ai/artifact/MYi1YSiJFww9TC4v8payVT, file_path = the saved
page file from step 1 (unchanged), and files = {"releases.json": "<path to your updated
releases.json>"}. Do not pass capabilities. If the publish reports a conflict, re-read and merge,
then publish again.

## 10. Final message (German)

One short line: new releases per shop, how many items became playable, whether fx was updated,
whether the website push succeeded (verified), and which shops were skipped and why.
