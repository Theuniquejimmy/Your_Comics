![splash_art](https://github.com/user-attachments/assets/18acda18-0bef-4b5b-8942-f6dfc28ecbfe)

# Your Comics! 🦸

A full-featured desktop comic book manager built with Python and PyQt6. Organize, tag, read, and discover your comic collection — all in one app.

---

## Requirements

- Python 3.10+
- PyQt6, PyQt6-WebEngine
- `requests`, `edge-tts`, `markdown`, `patoolib`, `google-genai`
- A free [Comic Vine API key](https://comicvine.gamespot.com/api/) for metadata
- A free [Google Gemini API key](https://aistudio.google.com/) for AI features
- WinRAR / UnRAR for CBR support (optional)

---

## Features at a Glance

<img width="1628" height="1228" alt="image" src="https://github.com/user-attachments/assets/ec4d33ab-ff1c-41da-b27b-1a97f2442377" />
### Local Details Tab
Your main reading view. Select any comic from the tree and see:

- **Large cover image** on the left
- **Full metadata panel** on the right — series, issue, publisher, year, summary, creators, story arcs, characters, teams, and locations
- **Navigation row** with Prev/Next issue buttons and folder-jump arrows (`«` / `»`) that step through your entire library folder by folder in natural sort order
- **AI Chat button** that drops you straight into a chat about the open comic
- **Convert/Tag button** that opens the ComicVine Cover Matcher dialog so you can match, preview, and inject metadata into any CBZ or convert a CBR on the spot
- **More Info / Edit button** (when ComicInfo.xml is present) — opens a full scrollable dialog showing all 35 ComicInfo fields, lets you edit any of them, and saves directly back into the CBZ

---

<img width="2560" height="1390" alt="image" src="https://github.com/user-attachments/assets/9eb3445f-900e-4871-981b-8c39e6c47e7b" />
### Local Grid Tab
A visual grid browser for your collection.

- **Adjustable grid size** — slider from 80 to 360px wide; covers re-render at full quality as you drag
- **Folder stack tiles** — folders show a stacked-covers preview that scales with the slider
- **CBL reading list tiles** — `.cbl` files appear as distinct amber 📋 tiles with optional custom covers
- **Hover summary popup** — hover any comic or folder tile for 2.5 seconds to see the series title and plot summary pulled live from the embedded ComicInfo.xml
- **Search** — full-text search across all your libraries returns comics, folders, and CBLs in the grid, all properly rendered and clickable
- **Right-click context menu** on any item:
  - Smart-Link Comic(s) — match missing files in a CBL reading list
  - Send to Tagger
  - Go to File Location — expands and highlights the item in the left-panel tree
  - Change Cover — pick an internal page, another comic's cover, or a custom image
  - Pick Comic as Cover / Reset to Default Cover
  - Hide Item

---

<img width="2560" height="1390" alt="image" src="https://github.com/user-attachments/assets/23e3d940-a602-456c-8efd-4e05fb867a7e" />
### Comic Finder Tab
Search Comic Vine for any volume and browse its issues.

- Dual-endpoint volume search (`/api/volumes/?filter=name:` for breadth + `/api/search/` for precision) returns up to 75 results merged and deduplicated
- Results sorted by issue count descending so the main run always appears first
- "The" prefix handling — `Sensational She-Hulk` automatically also searches `The Sensational She-Hulk`
- Click any volume to load its full issue list with cover thumbnails, dates, and story arcs
- Select an issue to preview the Comic Vine cover and inject metadata

---

<img width="2560" height="1390" alt="image" src="https://github.com/user-attachments/assets/59bd2262-b076-4ba5-9af3-6334f5b8739e" />
### Comic Chat Tab
Talk to an AI about any comic in your collection.

- Powered by Google Gemini 2.5 Flash with Google Search grounding
- Reads the comic's existing metadata as context
- **Text-to-speech playback** via Microsoft Edge TTS — choose from 9 voices (US, British, Australian) and set playback speed
- Full conversation history with a scrollable dark chat bubble UI
- Pause / resume / stop playback controls

---

<img width="2560" height="1390" alt="image" src="https://github.com/user-attachments/assets/714815de-cb24-4706-9881-b65d3a8aab51" />
### Batch Tagger Tab
Tag your entire collection automatically.

- **Drop folders or individual files** — supports CBZ and CBR
- **Interactive mode** — shows a side-by-side cover matcher dialog for each file so you confirm every match before writing
- **Auto mode** — runs silently, writes metadata immediately, then opens a post-run Review dialog

**Smart filename parser** understands:
- Zero-padded reading-order prefixes (`008 Batman 021` → series: Batman, issue: 21)
- Bare issue numbers (`Batman 021`)
- Volume/TPB notation (`Batman v08 - Superheavy`, `Saga Vol 01`, `100 Bullets - Book 01`)
- Omnibus/Deluxe edition hints in brackets (`Gantz v02 (Omnibus Edition)`)
- Issue numbers inside brackets (`Darkstars, 1994-04-00 (_21)`)
- Embedded date strings (`1994-04-00`)
- Underscored filenames (`Batman_-_Legends_of_the_Dark_Knight_002`)

**Three-pass volume search** for every file:
1. Broad filter (`/api/volumes/?filter=name:`) — up to 50 results
2. Exact search (`/api/search/?resources=volume`) — precision top matches
3. "The" variant pass — catches series like `The Sensational She-Hulk`
4. Subtitle/deluxe/omnibus passes for TPBs and collected editions

**Smart volume scoring** picks the right run using: name similarity (colon/dash normalised), proximity year scoring (prefers `Batman (2011)` over `Batman (1940)` for a 2013 issue), English publisher preference, issue count, and issue-number containment.

**Smart issue scoring** promotes: results from the matched volume, exact issue number match, year match, language (penalises non-English editions by −80 pts), subtitle match for TPBs, and page count > 100 for collected editions.

**Checkboxes:**
- **Interactive Mode** — confirm each match manually
- **Overwrite Existing Metadata** — re-tag files that already have ComicInfo.xml
- **AI Summaries** — when enabled, if Comic Vine has no plot summary for a matched issue, Gemini searches the web and writes one automatically; if Comic Vine finds no match at all, Gemini does a full AI tag from the filename

**Force Volume URL** — paste any Comic Vine volume URL to force the tagger to look there first; useful for obscure series or variant editions

**Post-run Review Dialog** (auto mode):
- Side-by-side: your file's cover vs. the Comic Vine matched cover
- Back/Next to step through every tagged file
- Re-search button — pre-fills a smart query from the filename and auto-triggers the search
- Select any result from the list and click **Overwrite File** to re-tag instantly with a deep metadata fetch

---

<img width="2560" height="1390" alt="image" src="https://github.com/user-attachments/assets/10c63897-724f-401c-8daa-d296bec2e3ad" />
### Getcomic.info Tab
An embedded browser pointed at GetComics.info for finding download links.

- Full navigation bar with back, forward, and URL input
- Downloads are intercepted and saved automatically

---

<img width="2560" height="1390" alt="image" src="https://github.com/user-attachments/assets/fceea31a-0657-43b5-9c88-1ca2b99aedf1" />
### List Maker Tab
Build `.cbl` comic reading lists.

- Drag and drop comics onto the list
- Load existing `.cbl` files
- **AI List Generator** — describe what you want (`"Best Batman stories featuring Ra's al Ghul"`) and Gemini searches your library and Comic Vine to build a curated reading list
- **DieselTech CBL Browser** — browse and download reading lists from the DieselTech GitHub repository directly inside the app; double-click any folder to navigate, double-click any `.cbl` to queue it for download
- Save lists as `.cbl` files compatible with other readers

---

<img width="1628" height="1103" alt="image" src="https://github.com/user-attachments/assets/5c3d8c0e-1354-4d7d-a0e2-b803054969b1" />

### New Releases tab 
-Lets you browse weekly comic releases from [GetComics](https://getcomics.org/), follow series you care about, and track what you’ve downloaded—all in one place.
The tab pulls release data from the GetComics sitemap, groups entries by publisher, and shows them as cards with covers, release dates, and action buttons. You can navigate by week, follow individual releases or entire collection types, and keep a personal watch list.
- Clicking **⬇ Download** on a release opens the **GetComics** tab and loads that article.
- When a download finishes in the GetComics tab, the release is marked as downloaded and gets a green check in New Releases.
- ### Per-release follow
- Each card has a **Follow** checkbox. When checked, the release is added to your **Watched** list and saved across sessions.
### Follow all Collections
-The checkbox **📚 Follow all Collections** auto-follows all collection-type releases (omnibus, TPB, compendium, etc.). When enabled, new collection posts in the current week are added to Watched automatically. Turning it off removes only collection-type follows; single-issue follows stay.
**Hint:** Right-click on the Download button to copy the page link (for JDownloader, etc.).
## Watched Tab
-The Watched tab shows everything you follow. You can filter it with **Watched: All / Issues only / Collections only.
-Entries are sorted by date (newest first), with “outside week” items at the end.
-If you follow a series (e.g. *Radiant Black*), future releases that match that series key (title normalized, without issue number or year) are automatically added to Watched when they appear in the feed.
-A green check (✓) in front of a title means it’s marked as downlaoded.


---

<img width="2560" height="1390" alt="image" src="https://github.com/user-attachments/assets/5fb213a8-22db-412c-8e28-6e86c262968a" />
### Settings Tab
- Comic Vine API key
- Google Gemini API key
- YACReader (or any reader) executable path
- Comic Chat voice and speed settings

---

## Library Management

The **left panel tree** shows your full library with a file system view.

- Add multiple library root folders — they all appear merged in the tree
- **Filter bar** — live-filters the tree as you type
- **Hidden items** — right-click anything to hide it from both tree and grid; unhide all from the grid's empty-area context menu
- CBL files appear in the tree and are openable directly

---

## Cover Customisation

Any item in the grid (comic, folder, or CBL file) can have a custom cover:

- **Pick an internal page** from inside the comic
- **Pick another comic's cover** — extracts the first page from any CBZ/CBR
- **Pick a custom image** — any PNG/JPG/WebP
- **Reset to default** — removes the override and regenerates from the comic itself

Custom covers are stored in a local cache keyed by file path and survive app restarts. Cache is stored at 600×900px so covers look sharp at any grid size.

---

## File Format Support

| Format | Read | Write | Notes |
|--------|------|-------|-------|
| CBZ | ✅ | ✅ | Native ZIP-based format |
| CBR | ✅ | ✅ | Converted to CBZ on tag |
| PDF | ✅ | — | Browse only |
| CBL | ✅ | ✅ | Reading list format |

---

## Metadata Standard

All metadata is written as **ComicInfo.xml** (ComiCRack standard) embedded inside the CBZ. Fields written include:

Series, Number, Title, Publisher, Imprint, Format, AgeRating, Year, Month, Day, Summary, PageCount, Web, Writer, Penciller, Inker, Colorist, Letterer, CoverArtist, Editor, StoryArc, AlternateSeries, AlternateNumber, AlternateCount, Characters, Teams, Locations, ScanInformation, SeriesGroup, LanguageISO, BlackAndWhite, Manga, PlayCount, and more.

---

## Tips

- **Auto mode is fastest** — turn off Interactive Mode, enable AI Summaries, and let the batch tagger run overnight on your whole collection
- **Force a volume URL** when the tagger picks the wrong run — paste the Comic Vine volume URL into the Force URL box
- **CBL files in the grid** support custom covers too — right-click and pick any image or comic cover
- **Hover summary popups** work on folder tiles too — it reads the first issue's summary from inside the folder
- **Re-search in the review dialog** auto-fires immediately when you click the button, using a clean parsed query — no need to hit Search again


