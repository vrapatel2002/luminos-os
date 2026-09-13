# HANDOFF.md — continue-from-here note (single source, overwritten in place)
Last updated: 2026-09-13 — Response 5

> The gaming/dGPU goal is **complete**; its detail is at `git show b08c3904:HANDOFF.md`.
> The `org.luminos.style` QML note is at `git show 4273ed7e:HANDOFF.md`.
> Read either before resuming those; do not reconstruct from memory.

## Goal (the durable end objective)
**Widened 2026-09-13 on Shawn's instruction.** Previously: make the two own pages look
designed. **Now: every page of the media server's web surface, rebuilt from zero**, so the
whole journey feels like one product — with full creative freedom on colour, type, motion and
3D — without loosening a single security property from DECISION 62 / 84 / 90 / 91 / 93.

His words: *"redesign every page from zero … give it every freedom … go out of the box …
using 3d object and more"*, and on process, *"let it research and think"* but *"do not ask
for my suggestion — point it to the luminos folder"*.

## ⚠️ THE SPEC MOVED TO v2 WHILE A v1 BUILD WAS AT STEP 2 OF 6. Read this before continuing.

`server/docs/WEB_UI_PROMPT.md` was rewritten to **v2** on 2026-09-13. **v1 is at
`git show 304e28a7:server/docs/WEB_UI_PROMPT.md`.** Do not merge them; v2 supersedes v1
completely and has absorbed everything from the v1 build that was worth keeping.

**Nothing already deployed was reverted, and nothing needs to be.** Steps 1–2 of the v1 build
are live and approved, and v2 §2b-bis carries them forward explicitly as work not to redo.

**The one thing v2 genuinely reopens** is the aesthetic. Shawn approved "instrument panel"
with a frozen token table and said "YES GO"; v2 asks the implementing agent for three fresh
directions. The conflict is resolved in v2 by making the approved direction **the incumbent** —
a new direction only wins if the agent can argue in writing that it is clearly better, and if
it cannot, the incumbent stands. The deployed fonts survive either way unless a winning
direction genuinely needs different faces.

## Aim right now
Hand **v2** to the implementing agent as its entire prompt. Its first deliverable is
`server/docs/WEB_UI_FINDINGS.md` — research, screenshots of every page, three art directions
scored against the incumbent, and the reasoning for the pick. **Nothing gets built before
that file exists.**

## Process / approach being used
v2 imposes its own order: **Phase 0 research** (read the repo and the live box; design
questions to Shawn are forbidden) → **Phase 1 concept** (three directions vs the incumbent,
self-chosen, justified in writing) → **Phase 2 build** (design system → landing → space →
offline → Jellyfin theme).

Shawn reviews from pictures, not descriptions, and has rejected batched visual changes twice
(DECISION 71, 72). He wants to be informed, not consulted — decisions stated in one line,
questions reserved for security tradeoffs, irreversible deletion, or money.

**This file doubles as the build log.** AGENTS.md §0.2 forbids a second handoff file, so no
separate `BUILD_LOG.md` was created.

## What v2 changes, beyond scope
- **Three tiers by how much control actually exists.** Tier 1 ours, total freedom. Tier 2
  **Jellyfin** — 10.11.11 has a real server-side Custom CSS branding field, and it is where
  Shawn actually spends time. Tier 3 Jellyseerr / *arrs / NZBGet.
- **Tier 3 cannot be reskinned, verified not assumed.** `caddy list-modules` on the box has
  **no `replace` / `sub_filter` handler**; theme.park-style injection would need Caddy rebuilt
  via `xcaddy` — swapping the binary that terminates TLS for all eight site blocks, to change
  a colour scheme. **Rejected in the brief.** The answer given instead is architectural:
  **stop linking out, start absorbing** — first-party pages for the one or two things each app
  is actually opened for, admin panels demoted to rare link-outs.
- **Artwork exists and nobody uses it** — the largest free visual win available.
  `/var/lib/{radarr,sonarr}/MediaCover/<id>/` holds posters, fanart, banners and clearlogos at
  three sizes each, `0664 <app>:media`, and **`luminoshub` is in group `media`** — readable
  with no privilege change, 28.5 MB over ~16 titles. ⚠️ The obvious route fails:
  `GET /MediaCover/…` with a valid `X-Api-Key` **302s to `/login`** (session-cookie route, not
  an API route), so an agent testing via the API concludes there is no artwork. **Read from
  disk**, through an allowlisted route (§6.9) modelled on the existing `/fonts/` whitelist.
- **3D is permitted.** v1 banned it on faulty reasoning — "the server is a weak i5" — but
  **3D renders on the client**; the server only ships bytes. Real constraints are payload over
  Tailscale, phone battery, and the no-CDN rule meaning the library is vendored. Required:
  progressive enhancement, static fallback, and a hard "must still be good with WebGL off".
- **Security went from nine invariants to twelve**, each with a verification command in §8 —
  adding: do not rebuild Caddy, do not touch nftables or unit `User=`, leave the API-facing
  Python alone, and path-traversal tests on the new artwork route.

## State — what is DONE

**Step 1 — brief written back and accepted.** Aesthetic is "instrument panel". Tokens,
type scale and both typefaces are frozen (table below). Shawn said "YES GO".

**Step 2 — tokens + type on the hub, deployed and verified.** The DOM was not touched;
only the `STYLE` constant, plus the new font route.

- `server/assets/fonts/` created: four subset `.woff2` files, **37,968 bytes total**
  against a 60 KB budget. Sources and SHA-256 of each are in that folder's `README.md`.
- `luminos-hub` gained `FONT_DIR` / `FONTS`, a `_send_font()`, a `/fonts/<name>.woff2`
  route, and a `cache` parameter on `_send()`.
- Live on the box. Rollback copy at `/usr/local/bin/luminos-hub.bak-2026-09-13`.
- Fonts installed to `/usr/local/share/luminos/fonts/` (0644, root).

Verified on the box after deploy:

| check | result |
|---|---|
| API keys (32-hex) in rendered HTML | **0** |
| Off-box hosts referenced in HTML | **none** |
| `http://192.168.2.61:8100/` | **connection refused** (loopback only holds) |
| `/fonts/archivo-800.woff2` | 200, `font/woff2`, `max-age=31536000, immutable` |
| `/fonts/../../../etc/passwd` | **404** |
| `/fonts/nope.woff2` | **404** |
| hub page weight | 9,300 bytes |

## State — what is IN PROGRESS
Nothing mid-flight. Awaiting Shawn's look at the step-2 screenshot before starting step 3.

## Next steps (ordered)
1. **Phase 0 + 1 of v2** — the implementing agent researches the repo and the live box,
   screenshots every page, and produces `server/docs/WEB_UI_FINDINGS.md` with three art
   directions scored against the incumbent. Nothing is built before that file exists.
2. **Phase 2 build**, in v2's order: shared design system (`/app.css`) → landing page →
   `luminos-space` → `/offline` → Jellyfin Custom CSS theme → whatever absorbing tier 3
   turns out to justify. Run §8 verification in full and paste the output.
3. The three unfixed findings below are **build work, not research** — fold them in, do not
   defer them. The free-space bug in particular is a wrong number on the live page today.
4. Unrelated and still outstanding: **reboot** (glibc + systemd upgraded, running system is
   on the old ones), then confirm a Lutris game renders on the dGPU with
   `dgpu-exec-v2 -- nvidia-smi`.

## Key decisions & constraints so far

**Frozen token set** — every colour and size in the finished CSS resolves to one of these:

| token | value | token | value |
|---|---|---|---|
| `--bg` | `#0F0D0B` | `--accent` | `#FF7A18` |
| `--surface` | `#17140F` | `--ok` | `#3FBF6A` |
| `--line` | `#2A2520` | `--warn` | `#E8C547` |
| `--text` | `#F2EDE4` | `--danger` | `#FF4D3D` |
| `--muted` | `#8C8279` | `--r` | `4px` |

Type: `--t-display clamp(52px,15vw,76px)` / `--t-head 15px` / `--t-body 15px` /
`--t-mono 14px` / `--t-caption 12px`. Spacing `--s1..--s6` = 4/8/12/16/24/40 px.
Faces: **Archivo** 500+800 (display/UI), **JetBrains Mono** 400+800 (all numbers, all
release names). Accent is deliberately a hue-step away from `--warn` so the two never read
as the same signal.

**`/app.css` and `/app.js` on port 8099 will NOT require the token.** Decided 2026-09-13,
Shawn deferred the call. They are static constants with no library data and no secrets,
byte-identical to what the hub already serves unauthenticated. Putting the token in a
`<link href>` would spread it into a second URL and into browser error reports for no gain.
Every route returning library data or performing a delete keeps `compare_digest` unchanged.

**Fonts are a whitelist, not a path join.** `FONTS` is a fixed tuple and the route tests
membership, so directory traversal is impossible by construction rather than by correct
escaping. Verified with `/fonts/../../../etc/passwd` → 404.

## Three findings from reading the code — all still to be acted on in step 3

1. **The hub is reporting the wrong free space, and has been.** `build_summary()` calls
   `shutil.disk_usage("/srv/media")` and nothing else, so `/srv/external` is invisible.
   Live: sda3 876G (283G free) + sdb1 458G (398G free). The page says ~268 GB free when
   the true figure is ~681 GB, and shows 62.6% used when the pool is ~46%. **Only
   `luminos-space` has a `disks` array — the hub does not.** WEB_UI_PROMPT §3(b) assumes it
   does. Fix: mirror `live_disks()` from `luminos-space` into the hub, `ismount()` check
   included (without it an unplugged USB reports root's space as library space).
2. **`luminos-space` sends no security headers of its own** — no CSP, no `nosniff`, no
   `Referrer-Policy`, no `Cache-Control`; `_send()` sets none. The token is protected from
   referrer leakage *only* by Caddy's `(proxy)` snippet today, so one Caddyfile edit
   silently un-protects a delete-everything URL. Set them at the app level too in step 5.
3. **The hub serves pre-formatted strings** (`"282.7 GB"`), not numbers, so values cannot
   be animated between polls (§7). Add raw byte fields alongside `human()`; do not change
   `human()` itself.

## Gotchas / dead-ends / things NOT to redo
- **Font weight lives in the hinting and ligature tables, not the glyphs.** A naive
  Latin-1 subset of JetBrains Mono Regular is 29,348 bytes; `--no-hinting` plus dropping
  `liga`/`calt` gives the same coverage in 7,884. Do not re-derive this.
- **Keep `tnum`.** Tabular figures are the entire reason JetBrains Mono carries the numbers.
- **Subset range is Latin-1 + Latin Extended-A, not ASCII.** ASCII is ~3 KB smaller per
  file and wrong — the library holds titles like `Amélie`, and a missing glyph falls back
  to a system font mid-word.
- **Screenshot through Caddy, never `127.0.0.1`.** Hitting the loopback port skips the
  proxy, the TLS and the token injection. Working command:
  `chromium --headless --disable-gpu --no-sandbox --ignore-certificate-errors
  --window-size=412,1400 --force-device-scale-factor=2 --virtual-time-budget=9000
  --hide-scrollbars --screenshot=/tmp/x.png "https://192.168.2.61/"`
  (412 px is the Pixel 9 CSS width; `--ignore-certificate-errors` is required because the
  IP addresses can only ever use Caddy's local CA.)
- **Emoji tile glyphs look actively broken against this palette** — confirmed in the step-2
  screenshot, not predicted. They are already scheduled for replacement by inline SVG in
  step 3.
- **`server/SPEC.md` is a different project** (the LLM prefill work). It is not this build's
  spec. The spec for this build is `server/docs/WEB_UI_PROMPT.md`.
- **MCP `mempalace` and `code-review-graph` are not connected in this Cowork session.**
  AGENTS.md §6 requires noting that rather than skipping silently.
- Repo and installed copies of both scripts were **md5-identical** before this work, so
  there is no pre-existing drift to untangle (contrast the usual `/usr/local/bin` divergence).

## Files touched / relevant files
**Repo:**
- `server/scripts/luminos-hub` — `STYLE` replaced; `FONT_DIR`/`FONTS`, `_send_font()`,
  `/fonts/` route, `cache` param on `_send()`
- `server/assets/fonts/` — **new**: 4 × `.woff2` + `README.md` (sources, SHA-256, method)
- `HANDOFF.md` — this file

**Live system (not in the repo):**
- `/usr/local/bin/luminos-hub` — updated
- `/usr/local/bin/luminos-hub.bak-2026-09-13` — rollback copy
- `/usr/local/share/luminos/fonts/` — **new**, 4 files, 0644 root

**Untouched on purpose:** `luminos-space` (step 5), the `/offline` page body (step 6), and
all Python that talks to the Sonarr/Radarr/NZBGet APIs — that code encodes about a dozen
hard-won facts about how those services lie, and WEB_UI_PROMPT §10 forbids tidying it.
Also still unexplained: the initramfs-looking untracked tree at the repo root (`init`,
`kernel/`, `usr/`, `etc/`, `lib`, `sbin`, `hooks/`). **Find out what it is before anyone
commits or deletes it.**

---

## CORRECTION 2026-09-13 — tier 3 apps CAN be reskinned. The brief said they could not.

`server/docs/WEB_UI_PROMPT.md` §4 previously claimed Radarr/Sonarr/Prowlarr/NZBGet could not
be reskinned. **That was wrong.** The owner challenged it; he was right. What had actually
been proved was only that *proxy-level body rewriting* is unavailable in stock Caddy — that
much still holds — and it was then over-generalised to "cannot be reskinned at all". The
on-disk route was never checked. It was checked today and it works.

Verified on the box:
- `/usr/lib/{radarr,sonarr,prowlarr}/bin/UI/index.html` — plain static file, `root:root 0644`.
- `curl http://127.0.0.1:7878/Content/styles.css` → `200 text/css`. `Content/` is served raw,
  so `Content/luminos.css` + one `<link>` in `index.html` is a complete reskin. This is
  theme.park's documented *native* install method. **Caddy is not involved.**
- **NZBGet is the easiest of the five, not the hardest** — `/usr/share/nzbget/webui/` with
  plain `index.html`, `style.css`, `dark-theme.css`, `light-theme.css`.
- **Jellyseerr is the only genuinely hard one** — Next.js SSR, no `.html` anywhere under
  `.next/server`, CSS in content-hashed chunks whose names change on every upgrade. It got
  its own tier 4 in the brief: leave stock, absorb the request flow instead.
- Free win nobody spent: Radarr/Sonarr/Prowlarr have a `theme` field on `/api/v3/config/ui`
  (`/api/v1/` on Prowlarr), currently `"auto"`.
- **The real cost:** `pacman -Qii radarr-bin` → `Backup Files : None`. Every upgrade silently
  overwrites these files. Mitigation specified in the brief: repo-owned skins under
  `server/assets/skins/`, an idempotent `server/scripts/luminos-skin-apply`, and a
  PostTransaction pacman hook in `server/config/`.

Brief sections changed: §4 tier 3 (rewritten), new §4 tier 4 for Jellyseerr, deliverable 15,
the "stop linking out" block (skinning and absorbing are now stated as both-not-either),
§8 checks 10–12, and three new §9 DO NOTs (no `.js` edits, nothing under `/var/lib/<app>/`,
no hand-edit without the hook).

**Steps 1–2 already shipped are unaffected** — none of this touches `luminos-hub`. Tier 3
skinning is new work that slots in after step 6.
