# WEB_UI_PROMPT.md — the brief for redesigning the media server's web face
# [CHANGE: claude-code | 2026-09-13]

Hand this whole file to the agent doing the work. It is written to be pasted as-is.
It is a **visual/UX redesign only**. No new capability, no new endpoint, no new exposure.

---

## ROLE

You are a senior frontend engineer and art director who also reads C-level systems code.
You are redesigning the web face of a headless media server. The information is already
correct and hard-won; it is being displayed badly. Your job is the display, and nothing else.

You will be judged on two things at once: whether it looks genuinely, deliberately designed —
and whether every security property listed in §4 is still provable by the commands in §9
when you are done. A beautiful page that widens the attack surface is a failed task.

---

## 1. WHAT THIS IS

A Dell Inspiron 3590 in a cupboard, no monitor, no keyboard, mains only. It runs Jellyfin,
Sonarr, Radarr, Prowlarr, NZBGet and Jellyseerr. Caddy is the single TLS front door.

Two pages are yours. Both are **single Python 3 files, stdlib only**, that embed their own
HTML/CSS/JS as string constants and serve them from `http.server`:

| file | binds | reached at | what it is |
|---|---|---|---|
| `server/scripts/luminos-hub` | `127.0.0.1:8100` | `https://<host>/` | landing page. Read-only. Free space, live download queue, recently imported, tiles out to the seven apps. Plus `/offline` — a three-step how-to for saving a film onto a phone. |
| `server/scripts/luminos-space` | `127.0.0.1:8099` | `https://<host>:8446/?token=…` | the dangerous one. Library by show → season → episode and by movie, with **delete** at every level, plus live NZBGet control (pause / resume / move-to-top / cancel / pause-all). |

Everything else on the box — Jellyfin, Jellyseerr, the *arrs — is a third-party app with its
own UI. **You do not touch those.** The hub links to them; that is the whole relationship.

### Who actually uses this
A phone (Pixel 9), usually over Tailscale on mobile data, often one-handed, sometimes in bed.
Secondarily a laptop browser. The TV is **not** a client — the Roku talks to Jellyfin on `:8096`
directly and never sees these pages. So: **phone-first is not a nicety here, it is the primary
target.** Design the phone layout first and let the desktop be the adaptation.

### Read before you design
- `server/README.md` — the machine, the ports, the long "things that will bite you" list
- `server/DECISIONS.md` — 62 (hardlinks), 84 (the front door), 90 (loopback + firewall), 91/93 (two disks)
- The two scripts themselves. The comments in them explain *why* each shape is what it is.

---

## 2. WHY IT NEEDS THE WORK

The current pages are functional and honest and look like a `README` someone added colours to.
Specifically: default dark-GitHub palette, system font stack, everything at one type size,
data rendered as `<div>` rows of equal weight so nothing has priority, and the single most
important number on the whole site (§3) is a parenthetical in grey text.

It is not ugly. It is undesigned. That is the thing to fix.

---

## 3. THE INFORMATION-DESIGN PROBLEM — read this twice

This is the part a generic "make it pretty" pass will get wrong. Four facts about this data
are more important than any styling choice:

**(a) Size and freed-space are different numbers, and the gap is the whole point.**
Sonarr and Radarr import by hardlink. A 47 GB season in the library is usually the *same
inode* as a copy under `/srv/media/downloads`. Deleting the library name drops the link count
to 1 and frees **zero bytes**. On this box that affects ~370 GB. `luminos-space` already
computes both (`bytes` and `frees`) — the current UI prints the real figure in a small grey
warning. **Make this the loudest piece of information on the page.** A row that will free less
than its apparent size must be unmistakable *before* the finger reaches the button, and the
confirm dialog must lead with the real number. If a user ever deletes something believing they
reclaimed 47 GB when they reclaimed nothing, the redesign has failed regardless of how it looks.

**(b) There are two disks and a merged total lies.** `/srv/media` (1 TB internal) and
`/srv/external` (500 GB USB, no readable SMART, expected to die without warning). The API
already returns a `disks` array. A single pooled bar hides one drive being full. Show the
split, and make the external drive read as the less trustworthy one it is.

**(c) NZBGet's own `Status` field lags up to 16 seconds** and `PausedSizeMB > 0` is the par2
repair set, not a pause. The progress bar's byte-delta is *more truthful* than the status
string. Never render a status chip that can visibly contradict the bar next to it — if they
disagree, the bar wins and the chip goes.

**(d) Every title on these pages is an untrusted string.** They are Usenet release names that
arrived from an indexer: `Show.S01E02.2160p.WEB-DL.DV.HDR-GROUP`. They are hostile input and
they are also *long*, *ugly* and full of dots. Two consequences — escape them properly (§4),
and design for them honestly. Do not truncate the part that carries the meaning. Mono type
earns its place here: these strings are machine identifiers and reading them as machine
identifiers is correct, not decorative.

---

## 4. SECURITY — NON-NEGOTIABLE, AND VERIFIED IN §9

Each of these exists because of a specific incident. Do not relax one for a visual effect.

1. **Both processes stay bound to `127.0.0.1`.** Caddy on 8443–8449 is the only way in
   (DECISION 90). Do not add a `--bind 0.0.0.0` convenience, do not change the default.
2. **Zero third-party network requests. No CDN, no Google Fonts, no analytics, no
   `<link>` or `fetch()` to any host you do not control.** This box is only reachable on a LAN
   and a tailnet; an outbound asset fetch makes a private page depend on the internet *and*
   tells a third party the page was opened. Self-host or do without — see §6 for fonts.
3. **No API key reaches the browser, ever.** The hub holds Sonarr/Radarr/Prowlarr/NZBGet keys
   server-side and serves only computed answers. This was verified once as "zero 32-hex
   strings in the rendered HTML" and must stay true.
4. **The `luminos-space` token stays required on every request**, exactly as it is: query
   string, injected by Caddy, `secrets.compare_digest` on the server. Do **not** "improve" it
   into a cookie, `localStorage`, or a login form — that is a security change wearing a UX
   costume, and it is out of scope. Keep `Referrer-Policy: no-referrer` so it cannot leak
   through an outbound link, and never write it into the DOM, a log line, or an `<a href>`
   that points off-box.
5. **The hub stays read-only.** It has no authentication of its own, on purpose, because
   everything it exposes is summary data. Do not add a single mutating endpoint to it. All
   destructive power stays in `luminos-space`, behind the token.
6. **Escape everything, and prefer not to have to.** Current code does `innerHTML` string
   concatenation with an `esc()` helper. That works today and is one careless edit from not
   working. Where you are rewriting a render function anyway, build nodes and set
   `textContent` — then an escaping mistake becomes structurally impossible rather than
   merely absent. `grep -n innerHTML` on your result should return few lines, and every one
   of them should be provably static markup with no interpolation.
7. **Destructive actions get harder, not easier.** Delete cannot be undone; there are no
   snapshots. A tap target that is prettier and larger must not also be lower-friction. Keep
   an explicit confirm step that states the title and the **real freed bytes**, and make sure
   no confirm can be dismissed by an accidental tap on a backdrop. Pause/resume/move-to-top
   are reversible and may stay one tap. Cancel and delete may not.
8. **Add a Content-Security-Policy — this is the one place you should make security stronger.**
   Move the CSS and JS out of inline `<style>`/`<script>` into two routes the same process
   serves (`/app.css`, `/app.js`), then send:
   `default-src 'none'; style-src 'self'; script-src 'self'; font-src 'self'; img-src 'self' data:; connect-src 'self'; form-action 'none'; frame-ancestors 'none'; base-uri 'none'`
   No `unsafe-inline`. Keep the existing `X-Content-Type-Options: nosniff`,
   `Referrer-Policy: no-referrer` and `Cache-Control: no-store` on the API. This also makes
   the design work easier — you get a real stylesheet instead of a Python string literal.
9. **No new dependencies. No npm, no build step, no framework, no bundler.** Python stdlib on
   the server, vanilla ES on the client. The deploy is `scp` of one file (plus, now, a small
   asset directory). If your design needs a framework, the design is wrong for this box.

---

## 5. AESTHETIC DIRECTION — commit fully to this one

**Name it: "instrument panel".** A machine that reports on itself. Closer to a broadcast
monitoring rack or a film-archive card catalogue than to a SaaS dashboard. Confident,
dense where density is informative, silent where it is not. Nothing decorative that is not
also load-bearing.

Ground rules:
- **The first viewport is a poster, not a document.** On the hub that poster is the *state of
  the machine* — free space, downloading or idle, current rate — set at a size that is
  genuinely large. The numbers are the hero image, because this application has no hero image
  and never will. Do not open with a logo and a row of feature cards.
- **Dominant field, one sharp accent.** A near-black field doing 85% of the work, one accent
  colour carrying every "this is live / this is where you act" signal. Do not distribute
  colour evenly across the interface.
- **Status colour is a separate, rationed vocabulary.** Green / amber / red mean *machine
  state* and nothing else. They never appear as decoration, never as a border on a calm row,
  never in the accent's job. When everything is fine the page should be almost monochrome.
- **Tabular numerals everywhere a number can change.** Free space, percentages, rates, ETAs,
  sizes. A number that jitters while it ticks is the single clearest tell of an undesigned
  dashboard.
- **Dark only.** This is a thing you look at in a dark room at 1am. Do not build a light
  theme, do not add a theme toggle; nobody asked for one and it doubles the surface.

### Tokens — define these as CSS custom properties and use nothing outside them
`--bg`, `--surface`, `--line`, `--text`, `--muted`, `--accent`, `--ok`, `--warn`, `--danger`,
plus a type scale (`--t-display`, `--t-head`, `--t-body`, `--t-mono`, `--t-caption`) and a
spacing scale. Every colour and every size in the finished CSS resolves to one of these. If
you find yourself writing a raw hex in a rule, the token set is incomplete — extend it.

Pick the actual values yourself, but: **the accent is not blue and not purple.** The current
`#1f6feb` is the default-bootstrap-blue of every admin panel ever shipped, and the brief's own
anti-pattern list bans purple gradients outright. A signal amber or a warm sodium-orange suits
a machine that reports its own state, sits well beside green/red status without collision, and
is not what the model reaches for unprompted. Warm the near-black slightly rather than using
pure `#000` or the cool GitHub `#0d1117`.

---

## 6. TYPOGRAPHY

**Two typefaces, maximum. Never Inter, Roboto, Arial, Helvetica, `system-ui`, or Space
Grotesk** — that last one is the default the model converges on *after* being told to avoid
the first four; do not land there by accident.

- **Display / UI:** one variable grotesque with real character at heavy weights.
  Bricolage Grotesque, Archivo, or Cabinet Grotesk are all appropriate and OFL-licensed.
- **Mono:** JetBrains Mono. It carries every number, every release name, every state string —
  which is most of the actual content here.

**Self-hosting is mandatory (§4.2).** Vendor subset `.woff2` files into
`server/assets/fonts/`, commit them, have the Python process serve that directory on a fixed
route with a correct `font/woff2` content type and a long `Cache-Control` (these are the only
cacheable things on the site). Record the source and SHA-256 of each file in a
`server/assets/fonts/README.md` so a future reader knows what the binaries are. Use
`font-display: swap` and a plain system fallback in the stack — the fallback is a fallback,
not the design.

Use the range. Weight extremes and a 3×+ jump between display and body are what make this read
as designed; a uniform 14px/16px everywhere is what makes the current page read as a config
file. Set the release-name mono at a size that is genuinely readable on a phone.

---

## 7. LAYOUT AND MOTION

### Hub (`/`)
Sections, each with exactly one job: **machine state** (the poster) → **go somewhere** (the
app tiles) → **downloading now** → **recently added**. That order is already right — it is the
order of "how is it doing / where am I going / what is happening / what arrived".

The eight tiles are the part most likely to collapse into a generic card grid. They are not
peers: "Find something to watch" (Jellyseerr) and "Watch" (Jellyfin) are what the page is
*for*; Prowlarr is a thing you touch twice a year. Let the hierarchy show. Vary the shape.
Replace the emoji glyphs with inline SVG — emoji render differently on every device and cannot
be coloured with the accent.

Empty states are the *normal* state here. "Nothing downloading" is good news and should look
like calm, not like an error or a missing section.

### Space (`:8446`)
A dense, scannable, hierarchical list — show → season → episode, and movies. This one is
allowed to be much denser than the hub; it is a tool, used seated, with intent.

Two things must survive the redesign because they were built deliberately:
- **Expanded rows stay expanded across a refresh** (there is an `open` Set doing this). Do not
  regress it, and extend the same idea to scroll position.
- **Download rows repaint on a 5s poll.** Do not re-render the whole list into `innerHTML` on
  every tick — update the changed nodes. Re-rendering steals focus, kills a mid-tap, and burns
  CPU on a box that is simultaneously transcoding.

### Motion
One orchestrated page-load — a short staggered reveal down the page, ~0.06s stagger, CSS only,
`transform`/`opacity` only. Plus one continuous signal: the live elements (rate, progress,
free space) should *transition* between values rather than snapping. That is it. No scroll
choreography, no parallax, no GSAP, no WebGL — there is no budget for it and no content that
wants it. Wrap all of it in `@media (prefers-reduced-motion: reduce)` showing final states.

---

## 8. PERFORMANCE BUDGET — these are hard numbers

The server is an i5-10210U that is often transcoding at the same time, and the client is
frequently a phone on mobile data over a VPN.

- **Zero third-party requests. Total requests: HTML + CSS + JS + fonts. Nothing else.**
- CSS ≤ 14 KB, JS ≤ 10 KB, both uncompressed and hand-written.
- Fonts ≤ 60 KB total across both faces, subset to Latin, `woff2` only.
- No images. Icons are inline SVG, drawn by you, no icon library.
- **Do not increase poll frequency.** Hub stays at 15s, space stays at 5s. The 10s server-side
  cache in the hub stays. If you want something to feel more live, animate between polls —
  do not poll harder.
- Every animation is `transform`/`opacity` only. `will-change` sparingly or not at all.
- LCP under 2.5s on a throttled mobile profile, CLS under 0.1 — reserve space for the numbers
  that arrive from `/api/summary` so the page does not jump when they land.

---

## 9. VERIFICATION — run these, paste the output, do not assert without them

Nothing is "done" until these have been run against the actually-running services on the box.

```bash
# 1. no API key reached the browser — must print 0
curl -s http://127.0.0.1:8100/ | grep -coP '[0-9a-f]{32}'

# 2. no third-party host is referenced anywhere in the served assets
for p in / /app.css /app.js /offline; do curl -s http://127.0.0.1:8100$p; done \
  | grep -oP 'https?://[^"'"'"' )]+' | sort -u          # expect nothing off-box

# 3. still loopback only — must be "Connection refused" for both
curl --max-time 3 http://192.168.2.61:8100/ ; curl --max-time 3 http://192.168.2.61:8099/

# 4. headers are present on every HTML route
curl -sI http://127.0.0.1:8100/ | grep -iE 'content-security-policy|nosniff|referrer'

# 5. the token is still enforced — must be 403
curl -s -o /dev/null -w '%{http_code}\n' http://127.0.0.1:8099/api/data

# 6. page weight
curl -s http://127.0.0.1:8100/ | wc -c ; curl -s http://127.0.0.1:8100/app.js | wc -c

# 7. the client JS actually parses (this has caught a shipped syntax error before)
curl -s http://127.0.0.1:8100/app.js > /tmp/a.js && node --check /tmp/a.js

# 8. escaping: every remaining innerHTML must be static markup with no interpolation
grep -n 'innerHTML' server/scripts/luminos-hub server/scripts/luminos-space
```

Then load both pages in a real browser through the Caddy front door — **not** against
`127.0.0.1`, because that skips the proxy, the TLS, and the token injection that only Caddy
does — and take a phone-width screenshot of each. Confirm the `frees < size` case renders
correctly by finding a real hardlinked season in the list, not by imagining one.

Rollback: copy the live file to `/usr/local/bin/<name>.bak-<date>` before overwriting, the way
DECISION 93 did.

---

## 10. DO NOT

- Centered hero + three feature cards. A uniform grid of equal-weight rounded cards.
- Inter, Roboto, Arial, `system-ui`, Space Grotesk.
- Purple or blue-violet gradients. Glassmorphism. Neumorphism.
- Emoji as iconography. An icon font or icon library of any kind.
- A CDN link of any kind, for anything, ever.
- A theme toggle, a light theme, a settings panel, a sidebar nav for four sections.
- Lorem ipsum or invented placeholder titles — develop against the real API output.
- A framework, a build step, a `package.json`, a CSS preprocessor, a utility-class library.
- A login form, a session cookie, or any other change to how auth works.
- Any new endpoint that writes, deletes, or mutates anything.
- Skeleton loaders that shift layout when the real content lands.
- Toast notifications stacked in a corner — there is already a single `say()` message bar and
  it is the right pattern for one-action-at-a-time.
- Renaming, refactoring, or "tidying" the Python that talks to the APIs. That code encodes
  about a dozen hard-won facts about how these services lie (see the comments). Read it,
  leave it. Your changes live in the template constants, the new asset routes, and the
  handler that serves them.

---

## 11. HOW TO EXECUTE — one surface, one step, shown before the next

The owner reviews from pictures, not descriptions, and has explicitly rejected large batched
visual changes twice before. So:

1. **Write the brief back first.** One-sentence visual thesis, the finalised token table with
   real hex values, the two font names, and a one-line note per section on what its job is.
   Nothing else. Stop and show it.
2. **Then tokens + type only**, applied to the hub, nothing else restructured. Screenshot at
   phone width. Stop and show it.
3. **Then the hub's layout** — poster, tiles, queue, recent. Screenshot. Stop and show it.
4. **Then motion + the CSP/asset-route split**, with §9 run in full. Screenshot. Stop.
5. **Then `luminos-space`**, reusing the exact same tokens and stylesheet, with §3(a) — the
   frees-vs-size problem — as the centrepiece of that step. Screenshot. Stop.
6. **Then `/offline`**, which is mostly typography and needs the least.

Decide the small things yourself and state the decision in one line — do not ask which font,
which easing, which radius. Ask only if you hit one of: a security tradeoff, an irreversible
deletion, or something that costs money. Keep the code small enough to read: no speculative
abstractions, no config knobs nobody asked for, no defensive branches for cases that cannot
occur. If a piece of what you wrote cannot be explained back in two plain sentences, it is
too complex — rewrite it rather than commenting it.

---

## 12. LITMUS CHECKS — self-critique against these before declaring done

- Open the hub on a phone. **Within two seconds, without reading a label, is it clear whether
  the machine is busy or idle, and whether it is running out of room?**
- Remove every shadow, border-radius and gradient. Does it still look deliberate? If the
  design collapses without decoration, the hierarchy was carried by decoration.
- Does each section have exactly one job, and could you name it in three words?
- In `luminos-space`, put a season that frees 0 bytes next to one that frees 40 GB. **Can you
  tell them apart from arm's length, before tapping anything?** This is the most important
  check on the page.
- Cover the accent colour. Is the hierarchy still legible in pure greyscale?
- Are the tiles actually necessary as cards, or are they cards because cards are the default?
- Does anything move that does not carry information?
- Screen-read one download row. Does the accessible name include the title, or just "delete"?

---

## APPENDIX — two alternate directions, if "instrument panel" is rejected on sight

Swap §5 for one of these and leave everything else in this file intact.

- **Archive / editorial.** Warm off-black paper tone, a serif display face (Fraunces,
  Newsreader) for section headings, mono for all data, generous vertical rhythm, rules
  instead of cards. Reads like a film-archive index rather than a monitoring tool. Calmer;
  worse at signalling urgency, which matters for the disk-full case.
- **Utility terminal.** Near-monospace throughout, visible grid, boxed regions with rules,
  amber-on-black, near-zero motion, every value in a fixed column. Extremely legible and
  extremely honest about what it is; risks reading as a deliberately retro costume rather
  than a designed interface, which is a real failure mode and not a cheap one to fix late.
