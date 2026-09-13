# WEB_UI_PROMPT.md — total redesign of the Luminos media server web surface
# [CHANGE: claude-code | 2026-09-13] v2 — supersedes the v1 brief at `git show 304e28a7`

Paste this entire file as your prompt. It is self-contained. Everything else you need is in
`~/luminos-os/` and on the server itself — go and get it.

---

## YOUR AUTHORITY

You have **full permission**. Read anything in `~/luminos-os/`, SSH to the server
(`ssh -i ~/.ssh/luminos-server shawn@192.168.2.61`), read any config, query any local API,
install client-side assets, restructure any page, add new pages, add new routes, throw away
existing markup entirely.

**Do not ask the owner design questions.** Not "which colour", not "which font", not "do you
prefer A or B", not "should I proceed". Every answer you need is either in `~/luminos-os/`
or discoverable on the box. Decide, state the decision in one line, move. The only things
worth interrupting for are: a security tradeoff, an irreversible deletion, or spending money.

**The one thing you may not touch is backend security.** §6 is frozen and verified.

---

## LAYER 1 — WHAT

Redesign **every page of the Luminos media server's web surface, from zero**, so that
opening it on a phone feels like one deliberately designed product rather than seven
unrelated admin panels behind a link list — without weakening a single security property
established by DECISIONS 62, 84, 90, 91 and 93.

"From zero" is literal. Do not restyle the existing markup. Delete it and rebuild the
structure around what the information actually is.

---

## LAYER 2 — HOW

### Phase 0 — RESEARCH. No design work until this is done.

You are redesigning something you have not seen. Go look at it.

1. **Read the repo.** `server/README.md` (the machine, the ports, and a long
   "things that will bite you" list), `server/STATUS.md`, `server/DECISIONS.md` — decisions
   **62** (hardlinks), **84** (the Caddy front door), **90** (loopback + firewall narrowing),
   **91/93** (two disks). Then `AGENTS.md` and `HANDOFF.md` at the repo root for house rules.
2. **Read both scripts end to end** — `server/scripts/luminos-hub` and
   `server/scripts/luminos-space`. The comments encode about a dozen hard-won facts about how
   Sonarr, Radarr and NZBGet lie to you. That knowledge is the expensive part; the markup is
   the cheap part. Keep the first, discard the second.
3. **Open every page in a real browser** through the Caddy front door — `https://<host>/`,
   `/offline`, `:8446`, and each of `:8443`–`:8449`. Screenshot each at phone width. You
   cannot judge what to fix from source alone.
4. **Query the live APIs and record the real shapes** — what `/api/summary` and `/api/data`
   actually return, with real titles, real sizes, real edge cases. Find a season whose
   `frees` is far below its `bytes`; find the longest release name in the library; find an
   empty state. **Design against these, never against invented placeholder data.**
5. **Enumerate what is themeable per app** and write down the verdict with evidence. §4 has
   the answers I already verified — confirm them, extend them, correct me if I am wrong.
6. **Write the findings to `server/docs/WEB_UI_FINDINGS.md`** before continuing. Include the
   screenshots. This is the deliverable of Phase 0.

### Phase 1 — CONCEPT

7. **Generate three genuinely distinct art directions.** Each gets: a name, a one-sentence
   visual thesis (mood, material, energy), a named font pairing, a five-colour palette with
   hex values, one layout concept, and one idea for what the signature moment of the page is.
   They must differ in *kind*, not in accent colour.
8. **Pick one yourself and commit to it completely.** Write a paragraph on why it beats the
   other two *for this content specifically* — a machine reporting on itself, viewed on a
   phone, in the dark, by one person. Record all three in
   `server/docs/WEB_UI_FINDINGS.md`; the two rejected ones are the audit trail.
9. **Lock design tokens before any layout.** CSS custom properties for the full palette, a
   type scale, a spacing scale, radii, elevation, motion durations and easings. Every value
   in the finished CSS must resolve to a token. A raw hex in a rule means the token set is
   incomplete — extend it rather than writing the hex.

### Phase 2 — BUILD, in this order

10. **The design system first**, as `/app.css` served by `luminos-hub`, shared by every
    first-party page. One stylesheet, one vocabulary.
11. **The landing page** (`luminos-hub` `/`) — the surface that matters most.
12. **The library and downloads tool** (`luminos-space`), reusing the identical tokens.
13. **`/offline`**, which is mostly typography.
14. **The Jellyfin theme** (§4 tier 2), so the place people spend the most time stops looking
    like a different product.
15. **The seam** — whatever §4 tier 3 turns out to allow, applied consistently.

---

## LAYER 2b — WHAT YOU ARE REDESIGNING

Three tiers, by how much control you actually have. **I verified these on the box on
2026-09-13. Confirm, do not assume.**

### Tier 1 — ours. Total freedom, rebuild from nothing.
| page | process | reached at |
|---|---|---|
| landing | `luminos-hub` | `https://<host>/` |
| offline how-to | `luminos-hub` | `/offline` |
| library + downloads | `luminos-space` | `:8446/?token=…` |
| **anything new you invent** | either | — |

Both are single Python 3 files, **stdlib only**, serving HTML/CSS/JS from string constants.
Move the CSS and JS out into real served routes (§6.8). You may add as many first-party
pages as the design calls for.

### Tier 2 — Jellyfin. Themeable properly, and this is the big win.
Jellyfin **10.11.11** exposes a server-wide **Custom CSS** field (Dashboard → General →
Branding) plus a login disclaimer and splashscreen. That is a supported feature, not a hack.
Jellyfin is where the owner actually spends time. A redesign that makes the hub beautiful and
leaves Jellyfin stock has redesigned the lobby and not the building.

### Tier 3 — Jellyseerr, Radarr, Sonarr, Prowlarr, NZBGet. **Verified constraint, read carefully.**
Reskinning these from a proxy needs response-body rewriting. **Stock Caddy cannot do it.**
`caddy list-modules` on the box returns `http.handlers.templates` and the encoders — there is
**no `replace` / `sub_filter` handler**. Getting one means rebuilding Caddy with `xcaddy` and
swapping the binary that terminates TLS for all eight site blocks. That is a change to the
security front door to alter a colour scheme. **Do not do it.**

So solve it the other way, and this is the central architectural idea of the redesign:

> **Stop linking out. Start absorbing.**
>
> Most of those seven apps are visited to do one or two simple things. Jellyseerr is
> "search a title, press request". NZBGet is "what is downloading, pause it". Sonarr is
> "is this show monitored". Each of those is a first-party page you can build properly
> in tier 1, talking to the same local APIs the hub already talks to. The full admin
> panels stay as link-outs — clearly marked as the deep, rare, unstyled machine room —
> and stop being the front door for everyday tasks.
>
> Decide how far to take this. Absorbing the whole of Sonarr is wrong. Absorbing "request
> a film" and "what is downloading" is almost certainly right. Justify where you drew the
> line in your findings doc.

**The constraint on absorbing:** a first-party page that *performs an action* must sit behind
the `luminos-space` token, never on the unauthenticated hub. See §6.5 — that is not
negotiable and it is the reason the split exists.

---

## LAYER 2b-bis — WORK ALREADY DONE AND DEPLOYED. Read before you touch anything.

A previous session executed **steps 1–2 of the v1 brief** and the result is **live on the
box, approved by the owner**. This is not a draft you may discard. Details, verification
tables and the full build log are in `HANDOFF.md` at the repo root — **read it first**.

**Already shipped and verified — do not redo, do not break:**
- `server/assets/fonts/` — four subset `.woff2`, **37,968 bytes total**, sources and SHA-256
  recorded in a README beside them. Installed to `/usr/local/share/luminos/fonts/`.
- `luminos-hub` has a working `/fonts/<name>.woff2` route: `FONT_DIR`/`FONTS`,
  `_send_font()`, a `cache` parameter on `_send()`. **`FONTS` is a fixed tuple and the route
  tests membership** — traversal is impossible by construction, not by escaping. Reuse this
  pattern for the artwork route in §6.9.
- Rollback copy at `/usr/local/bin/luminos-hub.bak-2026-09-13`.
- Repo and installed copies were md5-identical before that work, so there is no pre-existing
  `/usr/local/bin` drift to untangle.

**An aesthetic was already chosen and approved** — "instrument panel", with a frozen token
table (`--bg #0F0D0B`, `--accent #FF7A18`, Archivo 500/800 + JetBrains Mono 400/800, full
scale in `HANDOFF.md`). **Treat it as the incumbent, not as settled.** Phase 1 still requires
three fresh directions — but the incumbent is the fourth entry, and a new direction only wins
if you can argue in writing that it is *clearly* better for this content. If it cannot beat
the incumbent, keep the incumbent and say so. Do not churn an approved decision for novelty.
Whatever wins, the deployed fonts stay unless the winning direction genuinely requires
different faces — in which case re-subset with the same method and update the README.

**Three findings from that session, all still unfixed — fold them into your build:**

1. ⚠️ **The hub reports the wrong free space and always has.** `build_summary()` calls
   `shutil.disk_usage("/srv/media")` and nothing else, so `/srv/external` is invisible. Live
   figures: sda3 876 G (283 G free) + sdb1 458 G (398 G free). The page claims **~268 GB free
   when the truth is ~681 GB**, and 62.6% used when the pool is ~46%. **Only `luminos-space`
   has a `disks` array — the hub does not.** Mirror `live_disks()` across, `ismount()` check
   included; without it an unplugged USB reports root's space as library space.
2. **`luminos-space` sends no security headers of its own** — no CSP, no `nosniff`, no
   `Referrer-Policy`, no `Cache-Control`. Its `_send()` sets none. The token is protected
   from referrer leakage *only* by Caddy's `(proxy)` snippet today, so a single Caddyfile edit
   would silently un-protect a delete-everything URL. Set them at the app level as well.
3. **The hub serves pre-formatted strings** (`"282.7 GB"`), not numbers, so values cannot be
   animated between polls. Add raw byte fields alongside `human()`; do not change `human()`.

**Gotchas from that session — do not re-derive:**
- **Font weight lives in hinting and ligature tables, not glyphs.** A naive Latin-1 subset of
  JetBrains Mono Regular is 29,348 bytes; `--no-hinting` plus dropping `liga`/`calt` gives
  identical coverage at 7,884. Keep `tnum` — tabular figures are the entire point.
- **Subset Latin-1 + Latin Extended-A, not ASCII.** ASCII saves ~3 KB per file and is wrong:
  the library holds titles like `Amélie`, and a missing glyph falls back mid-word.
- **Emoji tile glyphs look actively broken against this palette** — confirmed in a screenshot,
  not predicted. Replace with inline SVG.
- **Working headless screenshot command** (412 px is the Pixel 9 CSS width;
  `--ignore-certificate-errors` is required because the bare IPs can only use Caddy's local CA):
  `chromium --headless --disable-gpu --no-sandbox --ignore-certificate-errors --window-size=412,1400 --force-device-scale-factor=2 --virtual-time-budget=9000 --hide-scrollbars --screenshot=/tmp/x.png "https://192.168.2.61/"`
- **`server/SPEC.md` is a different project** (LLM prefill work). Your spec is this file.

---

## LAYER 2c — FIVE FACTS THAT CHANGE THE DESIGN

I checked these so you do not spend a day rediscovering them.

**1. There is artwork, and nobody is using it.** This is the single largest visual upgrade
available and it is free. Radarr and Sonarr keep full artwork on disk:

```
/var/lib/{radarr,sonarr}/MediaCover/<id>/
  poster.jpg  poster-500.jpg  poster-250.jpg
  fanart.jpg  fanart-360.jpg  fanart-180.jpg
  banner.jpg  banner-70.jpg   banner-35.jpg   clearlogo.png   (sonarr)
```

Files are `0664 <app>:media` and **`luminoshub` is in the `media` group** — so the hub can
read them directly with no privilege change. 28.5 MB total across ~16 titles; the pre-scaled
`-250`/`-180` variants are what you want on a phone.

⚠️ **The obvious route does not work.** `GET /MediaCover/1/poster.jpg` with a valid
`X-Api-Key` returns **302 → `/login`** — it is a session-cookie route, not an API route. An
agent who tries the API and stops will wrongly conclude there is no artwork. **Read from
disk.** Serve it through a first-party route that maps an id to a file, validates the id is an
integer, and never lets a path fragment through — see §6.9.

**2. `frees` and `size` are different numbers and the gap is the whole point.** Sonarr and
Radarr import by hardlink, so a 47 GB season in the library is usually the *same inode* as a
copy under `/srv/media/downloads`. Deleting the library name frees **zero bytes**. On this box
that affects ~370 GB. `luminos-space` already computes both. The current UI puts the real
figure in small grey text. **Make it the loudest thing on the page.** If anyone ever deletes
something believing they reclaimed 47 GB when they reclaimed nothing, the redesign failed no
matter how it looks.

**3. There are two disks and a pooled bar lies.** `/srv/media` (1 TB internal) and
`/srv/external` (500 GB USB — **no readable SMART, expected to fail without warning**,
DECISION 91). `luminos-space` returns a `disks` array; **the hub does not, and is actively
reporting the wrong number because of it** — see §2b-bis finding 1. Show the split, and let
the external drive read as the less trustworthy thing it is.

**4. NZBGet's `Status` lags up to 16 seconds** and `PausedSizeMB > 0` is the par2 repair set,
not a pause flag. The progress bar's byte-delta is *more truthful* than the status string.
Never render a status chip that can visibly contradict the bar beside it.

**5. Every title is hostile input.** They are Usenet release names —
`Show.S01E02.2160p.WEB-DL.DV.HDR-GROUP` — untrusted, long, ugly, dot-separated. Escape them
(§6.6) and design for them honestly. Mono type earns its place here: these are machine
identifiers and reading them as machine identifiers is correct, not decorative.

---

## LAYER 2d — CREATIVE MANDATE

Free hand. Colour, type, layout, motion, 3D, illustration, sound — your call. The brief is
"make it genuinely, memorably good", and the failure mode to design against is **converging on
the statistically safe centre**: Inter on near-black, a purple-blue gradient, a centred hero
above three rounded cards. That is what a model produces when it is not steered. Steer.

Go and build taste first. The owner's research note on this lives at
`~/Downloads/website_prompt.md` — read it; it is the source of this brief's method. Study
Awwwards, Godly, SiteInspire, Typewolf. Name your references in the findings doc.

**Typography.** Two faces maximum. **Never Inter, Roboto, Arial, Helvetica, `system-ui`, or
Space Grotesk** — that last one is where models land *after* being told to avoid the first
four. Use the full range: weight extremes, a 3×+ jump between display and body. Self-host,
always (§6.2) — vendor subset `.woff2` into `server/assets/fonts/` and record source + SHA-256
in a README beside them.

**Colour.** One dominant field doing most of the work, one accent carrying every live/actionable
signal, and a separate rationed vocabulary for machine state that never appears as decoration.
The current `#1f6feb` is default-admin-panel blue; purple-on-anything is the banned default.
Go somewhere neither. When everything is fine, the page should be nearly monochrome — that is
what makes a warning mean something.

### On 3D — permitted, and here is the honest reasoning

The previous version of this brief banned WebGL because "the server is a weak i5". **That was
wrong, and the correction matters:** 3D renders on the *client*. The server only ships bytes.
The real constraints are payload size over Tailscale on mobile data, phone battery and thermals,
and the no-CDN rule (§6.2) meaning you vendor the library yourself.

So: **3D is allowed. It must earn its place.**

The bar it has to clear: *does this communicate something a 2D treatment communicates worse?*
Some things here genuinely pass — physical storage across two unequal drives, one of which is
dying, is a **volume** problem and reads better as volume than as two flat bars. A wall of
posters is a spatial object. Some things obviously fail — a download queue is a list; a list
in 3D is a list you made harder to read.

If you use it:
- Vendor the library into `server/assets/` (Three.js is the sane default; be honest about
  whether you can justify its weight). No CDN, ever.
- **Progressive enhancement is mandatory, not optional.** Detect capability, and on a low-end
  device, a `prefers-reduced-motion` user, or a failed context, **do not mount the canvas at
  all** — render a pre-generated static poster that is genuinely good on its own.
- Cap `devicePixelRatio` (2 desktop / 1.5 mobile), pause the render loop when offscreen via
  `IntersectionObserver`, no post-processing on mobile.
- **The page must be fully usable with WebGL disabled.** Test it that way.

**Motion.** One orchestrated page-load with staggered reveals beats a dozen scattered
micro-interactions. Compositor-only properties (`transform`/`opacity`). Live values transition
between states rather than snapping. Everything non-essential wrapped in
`@media (prefers-reduced-motion: reduce)` showing final states.

**Also consider, rather than defaulting past:** artwork-driven backgrounds pulled from the
fanart you now know exists; a page that looks different at 2am than at 2pm; ambient colour
extracted from the poster of whatever is currently downloading; the library as something with
shape rather than a list. Propose at least two ideas nobody asked for.

---

## LAYER 3 — GUARDRAILS

## 6. SECURITY — FROZEN. Each item exists because of a specific incident.

1. **Both processes stay bound to `127.0.0.1`.** Caddy on 8443–8449 is the only way in
   (DECISION 90). Do not add a `--bind 0.0.0.0` convenience or change the default.
2. **Zero third-party network requests.** No CDN, no Google Fonts, no analytics, no
   `<link>` or `fetch()` to a host you do not control. This box is reachable only on a LAN and
   a tailnet; an outbound asset fetch makes a private page depend on the internet *and* tells a
   third party each time it is opened. Self-host everything — fonts, libraries, all of it.
3. **No API key reaches the browser, ever.** The hub holds the Sonarr/Radarr/Prowlarr/NZBGet
   keys server-side and serves computed answers only. Verified once as "zero 32-hex strings in
   the rendered HTML"; keep it true.
4. **The `luminos-space` token stays exactly as it is** — query string, injected by Caddy,
   `secrets.compare_digest` on the server. Do **not** convert it to a cookie, `localStorage`,
   or a login form. That is a security change wearing a UX costume and it is out of scope.
   Keep `Referrer-Policy: no-referrer`; never write the token into the DOM, a log, or any
   `href` pointing off-box.
5. **The hub stays read-only and unauthenticated. Those two facts are the same fact.** It has
   no auth precisely because it exposes nothing but summary data. Any new page that writes,
   deletes, requests, pauses or mutates goes behind the `luminos-space` token — no exceptions,
   no "just this one convenience button".
6. **Escape everything, and prefer a structure where you cannot forget to.** Today's code does
   `innerHTML` concatenation with an `esc()` helper: correct now, one careless edit from not
   being. Since you are rebuilding anyway, construct nodes and set `textContent`. Then an
   escaping bug is structurally impossible rather than merely absent.
7. **Destructive actions get harder, not easier.** Delete is irreversible; there are no
   snapshots. A prettier, larger tap target must not also be lower-friction. Keep an explicit
   confirmation naming the title and the **real freed bytes**, not dismissible by a stray
   backdrop tap. Pause / resume / move-to-top are reversible and may stay one tap. Cancel and
   delete may not.
8. **Add a Content-Security-Policy — make security stronger here.** Serving CSS and JS from
   real routes instead of inline blocks lets you send:
   `default-src 'none'; style-src 'self'; script-src 'self'; font-src 'self'; img-src 'self' data:; connect-src 'self'; form-action 'none'; frame-ancestors 'none'; base-uri 'none'`
   No `unsafe-inline`. If a 3D library needs a blob worker, widen that one directive
   explicitly and say why — never fall back to `unsafe-eval`. Keep the existing
   `X-Content-Type-Options: nosniff`, `Referrer-Policy: no-referrer`, and `Cache-Control:
   no-store` on API responses.
9. **The artwork route is a file-serving route, which means it is a path-traversal surface.**
   Accept an integer id and a fixed variant name from a hard-coded allowlist. Build the path
   yourself; never join user input into it. Reject anything else before touching the
   filesystem. Serve `image/jpeg`/`image/png` with `nosniff` and a long `Cache-Control` —
   artwork is the only genuinely cacheable thing on the site.
10. **No new server-side dependencies.** Python stdlib only. Client-side vendored assets are
    fine (§6.2). No npm in the deploy path, no build step required to run the thing, no
    bundler, no CSS preprocessor. Deployment stays "copy files to the box".
11. **Do not rebuild or reconfigure Caddy**, do not touch `nftables.conf`, do not change any
    service unit's `User=`, and do not alter the token, the ports, or the firewall.
12. **Leave the API-facing Python alone.** The functions that talk to Sonarr/Radarr/NZBGet
    encode facts learned from specific failures. Read them, reuse them, do not "tidy" them.
    Your work lives in the templates, the new routes, the assets, and the handler.

## 7. PERFORMANCE BUDGET

Client is usually a phone on mobile data over Tailscale. Server is an i5-10210U that is often
transcoding at the same time.

- **Zero third-party requests.** Every byte comes from this box.
- First-party CSS ≤ 24 KB, first-party JS ≤ 20 KB, hand-written, uncompressed.
- Fonts ≤ 80 KB total, Latin subset, `woff2` only.
- Any vendored 3D library is **lazy-loaded, on capable devices only**, and never blocks first
  paint. Budget it honestly in the findings doc and justify the number.
- Artwork: serve the pre-scaled variants, `loading="lazy"` below the fold, explicit
  `width`/`height` so nothing shifts.
- **Do not increase poll frequency.** Hub stays 15s, space stays 5s, the hub's 10s server-side
  cache stays. To feel more live, animate between polls — do not poll harder.
- Do not re-render whole lists into `innerHTML` on each tick. Update changed nodes. A full
  repaint steals focus, kills a mid-tap, loses expanded rows, and burns CPU during a transcode.
  `luminos-space` already keeps an `open` Set to preserve expansion — do not regress it, and
  extend the same care to scroll position.
- LCP under 2.5s throttled-mobile, CLS under 0.1. Reserve space for values arriving from the
  API so the page does not jump when they land.

## 8. VERIFICATION — run these, paste the output, never assert without them

```bash
# 1. no API key reached the browser — must print 0
curl -s http://127.0.0.1:8100/ | grep -coP '[0-9a-f]{32}'

# 2. no third-party host referenced in any served asset
for p in / /app.css /app.js /offline; do curl -s http://127.0.0.1:8100$p; done \
  | grep -oP 'https?://[^"'"'"' )]+' | sort -u        # expect nothing off-box

# 3. still loopback only — both must refuse
curl --max-time 3 http://192.168.2.61:8100/ ; curl --max-time 3 http://192.168.2.61:8099/

# 4. headers present on every HTML route
curl -sI http://127.0.0.1:8100/ | grep -iE 'content-security-policy|nosniff|referrer'

# 5. token still enforced — must be 403
curl -s -o /dev/null -w '%{http_code}\n' http://127.0.0.1:8099/api/data

# 6. artwork route rejects traversal — all must be 4xx, none 200
for u in '../../etc/passwd' '1/../../../etc/passwd' 'abc' '1%2f..%2f..%2fetc%2fpasswd'; do
  curl -s -o /dev/null -w "$u -> %{http_code}\n" "http://127.0.0.1:8100/art/$u"; done

# 7. weights
curl -s http://127.0.0.1:8100/app.css | wc -c ; curl -s http://127.0.0.1:8100/app.js | wc -c

# 8. client JS parses — this has caught a shipped syntax error before (DECISION 93)
curl -s http://127.0.0.1:8100/app.js > /tmp/a.js && node --check /tmp/a.js

# 9. every remaining innerHTML must be static markup with no interpolation
grep -n 'innerHTML' server/scripts/luminos-hub server/scripts/luminos-space
```

Then load every page in a real browser **through the Caddy front door** — not against
`127.0.0.1`, which skips the proxy, the TLS and the token injection Caddy alone performs.
Screenshot each at phone width. Re-test with WebGL disabled and with `prefers-reduced-motion`
forced. Confirm the `frees < size` case against a **real** hardlinked season, not an imagined one.

Before overwriting a live script, copy it to `/usr/local/bin/<name>.bak-<date>`, the way
DECISION 93 did.

## 9. DO NOT

- Centred hero above three feature cards. A uniform grid of equal-weight rounded cards.
- Inter, Roboto, Arial, Helvetica, `system-ui`, Space Grotesk.
- Purple or blue-violet gradients. Glassmorphism. Neumorphism. Default shadcn look.
- Emoji as iconography, or any icon font / icon library. Draw inline SVG.
- A CDN link of any kind, for anything, ever.
- A light theme or a theme toggle. Nobody asked; it doubles the surface.
- Lorem ipsum or invented titles. Develop against the live API.
- A framework, bundler, `package.json`, CSS preprocessor, or utility-class library.
- A login form, session cookie, or any change to how auth works.
- A mutating endpoint on the unauthenticated hub.
- Rebuilding Caddy with plugins to inject CSS into third-party apps.
- Skeleton loaders that shift layout when real content lands.
- A stack of corner toasts. There is one `say()` message bar and it is the right pattern for
  one-action-at-a-time.
- 3D as decoration on content that is a list.

## 10. LITMUS CHECKS — self-critique against these, then revise, before declaring done

- Open the landing page on a phone. **Within two seconds, without reading a label, is it clear
  whether the machine is busy or idle and whether it is running out of room?**
- Remove every shadow, gradient and border-radius. Does it still look deliberate? If it
  collapses, the hierarchy was carried by decoration.
- Cover the accent colour. Is the hierarchy still legible in greyscale?
- Put a season that frees 0 bytes beside one that frees 40 GB. **Can you tell them apart from
  arm's length, before tapping?** This is the most important check in the document.
- Turn WebGL off. Is the page still good — not "still functional", *still good*?
- Go from the landing page into Jellyfin. Does it feel like the same product, or like clicking
  a bookmark?
- Could you name the job of each section in three words?
- Does anything move that does not carry information?
- Screen-read a download row. Does the accessible name include the title, or just "delete"?
- Would a stranger guess this was designed on purpose, or generated?

## 11. DONE MEANS

`server/docs/WEB_UI_FINDINGS.md` exists with the research, the three directions and the
reasoning for the one chosen. Every tier-1 page is rebuilt on one shared token set. Jellyfin
carries a matching theme. Every command in §8 has been run with its output pasted. Phone-width
screenshots of every page exist, including WebGL-off and reduced-motion variants. Changed files
carry `[CHANGE: claude-code | <date>]` tags, `server/STATUS.md` and `server/DECISIONS.md` are
updated, and the work is committed with **named files** — never `git add -A`, because there is
an untracked initramfs tree at the repo root that must not be committed.
