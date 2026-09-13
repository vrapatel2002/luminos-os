# WEB_UI_FINDINGS.md — Phase 0 research + Phase 1 concept
# [CHANGE: claude-code | 2026-09-13]

Deliverable of Phase 0/1 of `server/docs/WEB_UI_PROMPT.md` (v3). Nothing was built before
this file existed. Every verdict below carries the command that produced it.

Screenshots of every page at 412 px (Pixel 9 CSS width) are in `server/assets/screenshots/`,
prefixed `before-`.

---

## 0. Headline — five things that contradict the brief

The brief asked to be corrected where wrong. It is wrong in five places, two of them
load-bearing.

| # | The brief says | Reality | Impact |
|---|---|---|---|
| 1 | Tier 3 needs `index.html` + a CSS drop | `Content/styles.css` is **271 bytes** and re-read **per request**. Replace *it*. `index.html` is **cached in memory** and would need a restart. | Skin gets simpler *and* stops needing a `<link>` edit or a restart |
| 2 | Jellyfin is stock, apply our theme | Jellyfin already carries **74 KB of ElegantFin** in `/etc/jellyfin/branding.xml` | Not a blank canvas. Backed up before touching |
| 3 | ~370 GB has `frees` far below `bytes` | **Zero rows** have `frees < bytes`. The library-wide delta is **exactly 0 bytes** | The signature moment had to be redesigned — see §3 |
| 4 | `/srv/media` has 283 G free | **269 G** free. `sdb1` is 14 % used, not near-empty | Numbers corrected |
| 5 | — (not mentioned) | **The live library page renders no titles at all on a phone.** | Shipped safety bug — see §2 |

---

## 1. The machine

Dell Inspiron 3590, i5-10210U, Arch. `ssh -i ~/.ssh/luminos-server shawn@192.168.2.61`.
Caddy terminates TLS and is the only front door (DECISION 84/90); both first-party services
are loopback-only.

```
/dev/sda3  940,017,598,464 B  /srv/media     68 % used, 288,027,045,888 free   (ismount ✓)
/dev/sdb1  491,106,508,800 B  /srv/external  14 % used, 427,131,486,208 free   (ismount ✓)
pooled     1,431,124,107,264                           715,158,532,096 free
```

The pooled figure reads healthy. The disk NZBGet unpacks to has 269 GiB. Those are different
facts and the current hub shows neither correctly.

### The hub's free-space bug, measured

`build_summary()` calls `shutil.disk_usage("/srv/media")` and nothing else.

```
$ curl -s http://127.0.0.1:8100/api/summary | python3 -m json.tool
"disk": {"total": "875.5 GB", "used": "562.7 GB", "free": "268.2 GB", "pct": 64.3}
```

`/srv/external` is invisible. Two errors compound:

- **Wrong disk set.** Claims 268 GB free when the pool has 715 GB.
- **Wrong unit.** `human()` divides by 1024 and labels the result `GB`. `875.5 GB` is
  875.5 **GiB**. Every number on the page is mislabelled by 7.4 %.

`luminos-space` has `live_disks()` with the `ismount()` guard and gets this right. The fix is
to mirror it, not to invent it.

---

## 2. ⚠️ The live library page shows no titles on a phone

Not predicted — seen in `before-space.png`. The rows render a disclosure caret, a progress
bar, a size and a **delete button**, and no title.

`.row` is a flexbox of fixed columns with `.name{flex:1;min-width:0}`:

```
$ python3 -c "print(412 - 44 - (13+170+86+132) - 10*4)"
-73
```

412 px viewport − 44 px body padding = 368 px of content. The fixed columns and gaps demand
441 px. The title column is therefore crushed to **zero width**, and the row still overflows
by 73 px.

**This is a safety bug, not a cosmetic one.** The page exists to decide what to delete. On the
device it was built for, it offers a delete button on a row the user cannot identify. It alone
justifies rebuilding rather than restyling.

---

## 3. Hardlinks — the brief's central premise does not hold as stated

The brief says to make `frees` vs `bytes` the loudest thing on the page, on the basis that
~370 GB diverges. Measured on the box, **nothing diverges**:

```
files scanned            20,072
inodes with nlink > 1        26
bytes in those inodes   284,355,523,674   (284.36 GB)

library bytes           632,067,501,306
library frees           632,067,501,306
delta                                 0
```

Every row reports `frees == bytes` exactly. This is **correct**, and the reason is in the code:
`weigh()` counts a file as freed when `st_nlink <= 1 + len(twins found in the downloads tree)`,
and `delete_season()` then calls `drop_twins()` to unlink the twin as well. So `frees` honestly
means *"what a delete through this tool recovers"* — and because the tool deletes both names,
that is the full size.

### What is actually true, and is still dangerous

284.36 GB — **45.0 % of the library** — is House of Cards, held as **two names for one inode**:

```
/srv/media/downloads/House.of.Cards.2013.S01...NOGRP[rartv]/...S01E01....mkv
/srv/media/tv/House of Cards (US)/Season 1/House of Cards (US) - S01E01 - ....mkv
    same inode, st_nlink=2, st_size=13,450,191,034
```

Deleting the library name **in Sonarr's own UI, or with `rm`, frees zero bytes.** Deleting it
in `luminos-space` frees all of it. Same title, same screen, two utterly different outcomes
depending on which tool you used.

**So the signal to design against is not `frees < bytes`. It is `twins > 0`.** That is the fact
that separates "one copy" from "two names for one copy", and it is the fact that makes the
difference between our tool and every other route to the same deletion.

### Two real defects found while proving this

**(a) `twins` is missing from the rows that have the delete buttons.** It exists only on
`movies[]` and on `series[].seasons[].eps[]` — not on season or series rows. A season row
cannot state its own twin count without summing its episodes. Rolling it up is this build's job.

**(b) A genuine `frees = 0` case exists and is invisible by construction.** `twin_map()` walks
only `DOWNLOADS = /srv/media/downloads`. NZBGet actually writes to
`/srv/media/usenet/complete` (`DestDir` in its config), and both arrs have
`copyUsingHardlinks = true`. Confirmed from a real import record:

```
droppedPath : /srv/media/usenet/complete/tv/[Moozzi2] Ore dake Level Up na Ken-12 .../....mkv
importedPath: /srv/media/tv/Solo Leveling/Season 1/Solo Leveling - S01E12 - ....mkv
```

Same filesystem, so that import was a hardlink. In the window between import and NZBGet's
cleanup the file is `nlink=2` with its twin in a tree the scan never walks — so `weigh()` sees
`nlink(2) > 1 + 0` and reports **`frees = 0` against a full-size `bytes`**. That is *correct*
(the tool would not delete the usenet copy) and it is the real "frees far below bytes" row.
Both usenet dirs are empty right now, which is why it cannot be photographed today.

**The UI must render that row properly even though it cannot be produced on demand.**

---

## 4. Themeability — every route, every app, with the command

Baselines first. All four tier-3 packages are clean, and none uses pacman `backup`:

```
$ for p in radarr-bin sonarr-bin prowlarr-bin nzbget; do pacman -Qkk $p; done
radarr-bin    583 total files, 0 altered files      Backup Files : None
sonarr-bin    546 total files, 0 altered files      Backup Files : None
prowlarr-bin  571 total files, 0 altered files      Backup Files : None
nzbget        110 total files, 0 altered files      Backup Files : None
```

| App | Route | Verdict | Command | Evidence |
|---|---|---|---|---|
| **Jellyfin** 10.11.11 | server-wide Custom CSS | **works** | `curl -s http://127.0.0.1:8096/Branding/Configuration` | `{"CustomCss":"/* ElegantFin v26.06.06 …` — **already populated** |
| Jellyfin | `/Branding/Css` delivery | **works** | `curl -sI http://127.0.0.1:8096/Branding/Css` | `200`, **73,708 bytes** — no practical size cap |
| Jellyfin | store location | — | `sudo cat /etc/jellyfin/branding.xml` | `/etc/jellyfin/branding.xml`, 74,363 B. **Not** under `/var/lib/jellyfin/` |
| Jellyfin | static files on disk | works, unneeded | `pacman -Ql jellyfin-web \| head -3` | hashed chunks; route above is strictly better |
| **Radarr/Sonarr/Prowlarr** | in-app custom-CSS setting | **no** | `curl -H "X-Api-Key: …" …/config/ui` | no CSS field in the response |
| ″ | `theme` API field | **works, useless for skinning** | `curl …/api/v3/config/ui` | `"theme":"auto"` on all three; accepts only `auto`/`dark`/`light` |
| ″ | **replace `Content/styles.css`** | **works — chosen** | `curl -sI http://127.0.0.1:7878/Content/styles.css` | `200 text/css`, **271 B**. `File.OpenRead` per request — **no restart** |
| ″ | new file in `Content/` + `<link>` | works, **needs restart** | upstream `HtmlMapperBase.GetHtmlText()` | `if (IsProduction && _generatedContent != null) return _generatedContent;` — index.html is cached |
| ″ | Caddy `handle` + `file_server` | works — **forbidden by brief** | `caddy list-modules \| grep file_server` | present. See §4.1 |
| ″ | Caddy body rewrite | **no** | `caddy list-modules \| grep -i replace` | only `caddy.logging.encoders.filter.replace` |
| **NZBGet** 26.2 | in-app theme switcher | works, **browser-local only** | `grep -n theme-btn /usr/share/nzbget/webui/index.js` | `Util.getFromLocalStorage('Theme')` — not server-side |
| NZBGet | replace `dark-theme.css` | **works — chosen** | `ls -la /usr/share/nzbget/webui/` | `dark-theme.css` 15,780 B, root:root 0644 |
| NZBGet | `combined.css?a+b` concatenator | works | `grep -n combined.css …/index.html` | server concatenates arbitrary named webui files |
| **Jellyseerr** 3.4.1 | custom-CSS setting | **no — definitively** | `sudo grep -rl customCss /usr/lib/jellyseerr --exclude-dir=node_modules` | empty; also absent from the 225 KB OpenAPI spec |
| Jellyseerr | theme API field | **no** | `curl -s …/api/v1/settings/public` | 32 keys, none theme- or CSS-related |
| Jellyseerr | HTML on disk | **none** | `sudo find …/.next/server -name '*.html' \| wc -l` | `0` — SSR confirmed |
| Jellyseerr | append to hashed CSS chunk | works, **dies on upgrade** | `sudo find …/.next -name '*.css'` | `0hpyc1253dhc8.css`, content-hashed name |

### 4.1 The Caddy route works, and I am not taking it

The research turned up a route the brief did not list: Caddy has stock `file_server` and
`handle`, so it could intercept exactly `/Content/styles.css` per app and serve a replacement
with **zero packaged files touched** and no upgrade exposure at all. Engineering-wise it is
the better answer.

**Rejected, because the brief forbids it three times** — §6.11 ("do not rebuild or reconfigure
Caddy"), §9 ("the front door is never touched to change a colour"), and §8 check 13, which
requires `git diff --stat -- server/config/Caddyfile` to come back **empty**. The on-disk route
is taken instead, with the pacman hook as the mitigation, exactly as specified.

**Flagging it because it is a real option the owner may prefer.** It trades "an upgrade can
clobber the skin, and a hook re-applies it" for "one Caddyfile edit per app, forever". Not my
call to make unilaterally against an explicit instruction.

### 4.2 How the Servarr skin actually has to work

`Content/styles.css` declares **no variables at all**. Its entire body is 271 bytes:

```css
html, body { height: 100%; }
body { overflow: hidden; background-color: var(--pageBackground); }
@media only screen and (max-width: 768px) { body { overflow-y: auto; } }
```

The real sheet is `Content/527-daac9c32834ddf9a1b61.css` (248 KB). It *consumes* **136 named
variables** (`--pageBackground`, `--textColor`, `--borderColor`, `--primaryBackgroundColor`,
`--sidebarBackgroundColor`, `--linkColor`, …) and declares almost none of them — **the JS sets
them as inline styles on `<html>`** via `document.documentElement.style.setProperty()`.

That matters for one reason: a normal stylesheet rule loses to an inline style. An author
`!important` declaration beats a non-`!important` style attribute, so:

```css
:root { --pageBackground: #0F0D0B !important; }
```

wins. **This is the durable route, not the fragile one** — `!important` lands on ~35 variable
declarations, never on layout selectors, so a Radarr upgrade that reshuffles its compiled
class names cannot break it. Comfortably inside the 8 KB budget (271 B original + ~35
overrides ≈ 2–3 KB).

Free win taken first: set `theme` to `dark` via the API on all three, so the ~100 variables we
*don't* override start from the dark palette instead of `auto`.

### 4.3 Jellyseerr — leave stock, absorb the flow

Confirmed hard. No setting, no API field, no HTML on disk, CSS in content-hashed chunks that
rename on upgrade. Not chased further, per the brief.

One extra trap worth recording: **`pacman -Qkk jellyseerr` is useless as a change detector** —
it reports `67,952 total files, 67,935 altered files` because the package chowns the tree to
`jellyseerr:media` at install. Check 10 is meaningful for the other four only.

---

## 5. Real data shapes

### What the library actually is

Four rows. That is the whole library.

| kind | title | bytes | frees | twins |
|---|---|---:|---:|---|
| series | House of Cards (US) | 284,355,523,674 | 284,355,523,674 | **26/26 episodes twinned** |
| series | Ozark | 258,272,487,982 | 258,272,487,982 | 0/20 |
| series | Solo Leveling | 31,941,811,589 | 31,941,811,589 | 0/12 |
| movie | Quantum of Solace (2008) | 57,497,678,061 | 57,497,678,061 | 0 |

**A design for "a list of many things" is the wrong design.** Four rows, one of which is
45 % of the library and is secretly doubled. Two of the three series have exactly two seasons.

### Titles are hostile, and the hub truncates them wrongly

224 unique release names across Sonarr + Radarr history:

```
min 34   p50 66   mean 68.9   p90 95   p99 112   MAX 117
```

Worst case, 117 chars:

```
A.Knight.of.the.Seven.Kingdoms.S01E05.In.the.Name.of.the.Mother.2160p.HMAX.WEB-DL.DDP5.1.Atmos.DoVi.HDR.H.265-playWEB
```

Nastiest to lay out is not the longest — it mixes spaces, dots and brackets, so it wraps
completely differently from a dot-name:

```
www.1TamilMV.reisen - The Odyssey (2026) HQ PreDVD - 1080p - x264 - [Tam + Hin + Eng] - HQ Clean - AAC - 3GB.mkv
```

**The hub cuts at `sourceTitle[:70]` with no ellipsis — that fires on 125 of 224 names (56 %)**
and removes exactly the quality information that distinguishes two releases of one episode:

```
full (117): A.Knight.of.the.Seven.Kingdoms.S01E05.In.the.Name.of.the.Mother.2160p.HMAX.WEB-DL.DDP5.1.Atmos.DoVi.HDR.H.265-playWEB
hub  ( 70): A.Knight.of.the.Seven.Kingdoms.S01E05.In.the.Name.of.the.Mother.2160p.
```

NZBGet's own names run longer still — median 83, max 117. **The download panel is the tightest
layout in the product.**

### Everything is idle, and failure is normal

```
NZBGet listgroups        []
Sonarr /queue            totalRecords: 0
hub /api/summary         "queue": [], "speed": "idle"
NZBGet history (188)     SUCCESS 72 · FAILURE 114 · DELETED 2
```

**61 % of all downloads on this box fail.** Sonarr agrees — of 500 history records,
`downloadFailed: 161` against `grabbed: 229`. Failure is not an exceptional state here and must
not be styled as one. `ServerStandBy: true` is NZBGet's honest idle flag and neither service
currently uses it; both infer idle from `DownloadRate == 0`.

### Artwork — exists, and mostly belongs to things that aren't there

```
/var/lib/radarr/MediaCover/   9 ids   6 variants each   19,178,827 B
/var/lib/sonarr/MediaCover/   7 ids  10 variants each    9,721,125 B
                             16 ids  124 files          28,899,952 B  (27.56 MB)
```

Sonarr carries four variants Radarr does not — `banner-35`, `banner-70`, `banner`, and
`clearlogo.png` (the only PNG in the tree). A shared image helper must not assume a uniform set.

Phone budget is cheap: **all 16 `poster-250` total 262,327 B (256 KB)**; all 16 `fanart-180`
total 420,397 B. A single full `fanart.jpg` can be 2.2 MB — never served.

Permissions confirm the brief:

```
$ id luminoshub
uid=956(luminoshub) gid=956(luminoshub) groups=956(luminoshub),965(media)
-rw-rw-r-- radarr media  poster-250.jpg
```

Read as `luminoshub`: **succeeds.** No privilege change needed.

⚠️ **But only 4 of the 16 ids correspond to a row in `/api/data`.** Twelve posters belong to
titles that are tracked with zero files — True Detective, The Sopranos, Better Call Saul, A
Knight of the Seven Kingdoms, and 8 Radarr movies. `gather()` drops them (`if not files:
continue`).

**A poster wall would therefore be 75 % things you cannot watch.** That single fact killed art
direction C — see §6.

---

## 6. Three art directions, and the incumbent

The incumbent is **"Instrument panel"** — approved by the owner, deployed, tokens frozen in
`HANDOFF.md`: `--bg #0F0D0B`, `--accent #FF7A18`, Archivo 500/800 + JetBrains Mono 400/800.

### A — "Drafting table"
*Thesis: the machine as an engineering drawing — hairline rules, dimensioned leaders, nothing
filled, everything measured.*
Fonts: **Radio Grotesk** + **Berkeley Mono**. Palette `#0C1116` ground, `#E8EDF2` ink,
`#5A6B7A` graphite, `#00C2A8` live, `#FF5E4D` alarm.
Layout: a single measured elevation — the two disks drawn as dimensioned rectangles with
leader lines carrying exact byte figures into the margin.
Signature: the dimension line itself animating to its measured length on load.

**Rejected.** Hairlines are the failure mode of a phone in the dark — at 412 px and low
brightness a 1 px `#5A6B7A` rule on `#0C1116` is invisible, and the whole direction is
hairlines. And `#00C2A8` on `#0C1116` is one hue-step from the `#1f6feb` admin blue the brief
bans; it looks like a monitoring dashboard because it is built like one.

### B — "Shelf"
*Thesis: the library as physical objects — poster board, paper warmth, things with weight and
edges rather than rows.*
Fonts: **GT Sectra** display + **JetBrains Mono**. Palette `#12100E` ground, `#EDE4D3` paper,
`#8A7B66` shelf, `#C2410C` spine, `#4D7C2F` shelved.
Layout: poster-led — a wall of `poster-250` artwork, machine data demoted to the margins.
Signature: the twin/hardlink relationship as a literal doubled card — one poster casting a
second identical poster behind it, offset.

**Rejected on a measured fact.** §5 found that **12 of 16 posters belong to titles with zero
files**. A poster-led design is 75 % pictures of things you cannot watch — the aesthetic is
directly contradicted by the inventory. It would also make the page heavy for a phone on
mobile data, to display absence.

**Its best idea was kept:** the doubled card for twinned content is exactly right and is
carried into the chosen direction as the signature moment.

### C — "Night watch"
*Thesis: an instrument that is quiet when all is well — near-total monochrome, colour rationed
so hard that any colour at all means something.*
Fonts: **Söhne Breit** + **Söhne Mono**. Palette `#0A0A0B`, `#D6D6D8`, `#5B5B60`, one signal
`#E4572E`, one alarm `#C1121F`.
Layout: a vertical stack with no containers at all — hierarchy entirely from type scale and
whitespace.
Signature: the page being almost empty when idle, which it is 95 % of the time.

**Rejected as a replacement — absorbed as a discipline.** The "nearly monochrome when fine"
rule is correct and the brief already demands it, but as a whole direction it has no answer
for the one genuinely loud thing on this box (the doubled 284 GB) and it deletes the
containers that make a delete confirmation feel heavy enough. Removing all structure from a
page whose job includes an irreversible action is the wrong trade.

### ✅ Chosen — "Instrument panel" (the incumbent stands)

**It wins for this content specifically, and the research is why.**

This is a machine that is **idle 95 % of the time**, holds **four things**, on **two unequal
disks**, and whose most dangerous act is deleting one of 26 files that are secretly two names
for one inode. That is not a browsing problem and it is not a monitoring problem — it is a
**readout** problem. The one question on opening the page in the dark is *"is it doing
anything, and is it running out of room"*, and a readout answers that in one glance where a
poster wall (B) buries it and a drawing (A) makes you read it.

The warm near-black `#0F0D0B` beats the cold grounds of A and C for the actual viewing
condition — a phone at 2am — because a blue-black screen at low brightness reads as a
*device*, and a warm black reads as *unlit*. `#FF7A18` is a hue that neither A, B nor C offered
and that the brief's banned list does not contain: not admin blue, not violet, and a
deliberate hue-step from `--warn #E8C547` so an alarm never reads as an accent.

And JetBrains Mono with `tnum` is not decoration here: **every important string on this box is
a machine identifier** — 117-character dot-separated release names and tabular byte counts.
Setting them in a mono with tabular figures is reading them as what they are.

None of A, B or C is *clearly* better. The brief says the incumbent then stands, and it does.
**No churn: the deployed fonts stay, the 37,968 bytes stay, the token table stays.**

### What changes, since the tokens are not the problem

The direction survives; the *page* does not. The current landing page is a **uniform grid of
eight equal-weight rounded tiles with emoji glyphs** — explicitly banned by §9, and the
screenshot confirms the emoji look broken against this palette. What gets rebuilt:

- Eight equal tiles → a weighted structure where "is it busy / is it full" is the page, and
  navigation is subordinate.
- Emoji → inline SVG.
- One pooled disk bar → two disks with the USB reading as the less trustworthy thing it is.
- `frees` in small grey text → `twins` as the loudest signal on any deletable row.

### Two ideas nobody asked for

1. **The doubled card.** A row whose content is twinned is drawn as two offset stacked cards —
   one object, two names, visible from arm's length before tapping. Inherited from direction B,
   and it is the answer to the brief's most important litmus check.
2. **Tracked-but-empty as a real state.** The 12 titles with artwork and no files are currently
   invisible everywhere. They are the honest answer to "what is this machine for" when the
   queue is empty 95 % of the time — the library is not four things, it is four things and
   twelve intentions.

### 3D: yes — and without WebGL

Two unequal disks, one expected to fail without warning, is a **volume** problem and the brief
is right that it reads better as volume than as two flat bars.

**Three.js is not justified.** The smallest honest build is ~150 KB against a 20 KB JS budget,
for one static object, on a phone on mobile data — and it drags in vendoring, capability
detection, `devicePixelRatio` capping, an `IntersectionObserver`, and a pre-rendered fallback
poster, all to draw two boxes.

**Two isometric solids in hand-written SVG cost under 1 KB, need no library, no canvas, no
context loss, no fallback path, and are identical with WebGL disabled** — which also means the
brief's "must still be good with WebGL off" is satisfied by construction rather than by a
second code path. Volume is kept; the 150 KB is not spent.

Budget: **0 bytes of vendored 3D library.**

---

## 7. References

Studied for structure rather than for surface, per the brief's method note
(`~/Downloads/website_prompt.md`): **Teenage Engineering** product pages (readout-as-interface,
type doing the hierarchy with no containers); **Berkeley Graphics** (dimensioned technical
drawing — the source for direction A, rejected but the measuring discipline kept);
**Linear's changelog** (mono for identifiers, prose for meaning); **Typewolf** for the
Archivo/JetBrains pairing precedent; **Awwwards** and **Godly** surveyed mainly as a list of
what to avoid — the centred hero over three cards that §9 bans is the modal result on both.

---

## 8. Where the line was drawn on absorbing

**Absorbed** (built first-party, on our tokens):
- *"What is downloading, pause it"* — already in `luminos-space`; kept and rebuilt.
- *"Request a title"* — Jellyseerr's one useful function, behind the `luminos-space` token
  because it mutates. This is the highest-value absorption precisely because §4 proves
  Jellyseerr cannot be skinned, so it is the only way that flow stops looking foreign.

**Not absorbed** (skinned link-outs):
- Radarr / Sonarr / Prowlarr admin, NZBGet admin, Jellyfin playback. Absorbing Sonarr's
  monitoring UI would mean reimplementing season/episode monitoring state, which is a second
  source of truth for something Sonarr already owns. The skin closes the seam instead.

The test used: **absorb a flow if it is one action against an API the hub already holds a key
for; skin it if it needs the app's own state model.**
