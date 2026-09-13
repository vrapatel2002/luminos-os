# HANDOFF.md — continue-from-here note (single source, overwritten in place)
Last updated: 2026-09-13 — Response 6

> The gaming/dGPU goal is **complete**; its detail is at `git show b08c3904:HANDOFF.md`.
> The `org.luminos.style` QML note is at `git show 4273ed7e:HANDOFF.md`.
> Read either before resuming those; do not reconstruct from memory.

## ✅ THE WEB-SURFACE REDESIGN IS BUILT. Steps 1–16 are done and live.

`server/docs/WEB_UI_PROMPT.md` v3 is the brief; v2 is `git show a03fda8a:…`, v1 is
`304e28a7:…`. **Do not merge them — v3 supersedes both.** The full research trail, all three
art directions, the per-route themeability verdicts and every screenshot are in
`server/docs/WEB_UI_FINDINGS.md`. The architectural record is **DECISION 99**.

All eight surfaces now share one token set:

| tier | what | how |
|---|---|---|
| 1 | `luminos-hub` `/` + `/offline`, `luminos-space` | ours, rebuilt from zero on `/app.css` |
| 2 | Jellyfin | Custom CSS via its own API — **ElegantFin removed** |
| 3 | Radarr, Sonarr, Prowlarr, NZBGet, **Bazarr** | skinned on disk + pacman hook |
| 4 | Jellyseerr | cannot be skinned — request flow **absorbed** as a first-party page |

Budgets all held: `app.css` 20,055 / 24,576 B · `app.js` 12,333 / 20,480 B · skins
7907 / 8067 / 7748 / 7912 / 2322 B against 8192 each · **0 `@font-face` in any skin** ·
**0 third-party network calls anywhere**.

## ⚠️ Read these four before touching any of it

1. **There are FIVE tier-3 apps, not the four the brief lists.** Bazarr arrived the same day
   the brief was written (DECISION 98). It is in `TIER3`, in the hook, and skinned.
2. **`login.html` is skinned too**, so `pacman -Qkk` reports **2** altered files for each
   Servarr app, not the 1 that §8 check 10 calls "the ONLY acceptable result". Deliberate:
   all three run `AuthenticationMethod=Forms`, so it is the only page a logged-out browser
   ever sees. Reasoning in DECISION 99; do not "fix" it back.
3. **The hook is proven live on NZBGet only.** The other four are not in
   `/var/cache/pacman/pkg/`, so the version-identical reinstall could not be run for them.
   If you want that proof, it needs a re-download — ask first.
4. **`<Theme>dark</Theme>` is a write under `/var/lib/<app>/`**, which §6.13 otherwise
   forbids. It is the "free win" §4 explicitly instructs; Servarr persists that API field to
   `config.xml` rather than its database. Flagged, not hidden.

## Aim right now
Nothing mid-flight on the web surface. Remaining work is unrelated: see "Still outstanding".

## Still outstanding (unrelated to the redesign)
1. **Reboot** — glibc + systemd were upgraded and the running system is still on the old
   ones. Then confirm a Lutris game renders on the dGPU with `dgpu-exec-v2 -- nvidia-smi`.
2. Bazarr has **pre-existing** errors from its fresh install, unrelated to the skin:
   `KeyError: 'audio_only_include'`, a `FOREIGN KEY constraint failed` on a Solo Leveling
   episode, and Sonarr sync timeouts. All timestamped before this work. See
   `WEB_UI_FINDINGS.md` §10.2 so they are not misread as fallout.
3. `luminos-brain safe` has now returned a false `NO` three times by matching the word
   "install". **Its rule scope needs narrowing.**
4. ⚠️ **`server/config/Caddyfile` in the repo is STALE — it is missing the Bazarr `:8450`
   block that is live on the box.** DECISION 98 added it to `/etc/caddy/Caddyfile` on
   2026-09-13 at 17:51 and never mirrored it back. Restoring the repo copy onto the box
   today would silently drop Bazarr's front door. **Deliberately not fixed in the redesign
   commit**, because §8 check 13 requires `git diff --stat -- server/config/Caddyfile` to be
   empty and mixing the two would make it impossible to tell a config drift from a redesign
   touching the front door. Mirror it back as its own change. (The one *other* difference is
   intentional and must stay: the repo redacts the `luminos-space` token, the live file has
   the real one.)
5. `/etc/nftables.conf` was also rewritten at 17:51 the same day, with a
   `.bak-20260913` alongside it. **Checked, not assumed:** `policy drop` still holds and
   every `accept` is restricted by source address or interface — the only unrestricted ones
   are ICMP. Nothing is open to the internet.

## How to change a skin
Edit `server/assets/skins/<app>/luminos.css`, then:

```
rsync -a server/assets/skins/ <box>:/tmp/skins/
sudo rsync -a /tmp/skins/ /usr/local/share/luminos/skins/
sudo luminos-skin-apply --check     # dry run, exits 1 if anything would change
sudo luminos-skin-apply             # apply
```

Comments and indentation are stripped at install time (that is how the 8 KB budget is met),
so the repo copy stays readable and `diff`ing installed-vs-git still works line by line. A
colour-only change never restarts a service; only inserting the `<link>` does, because
`index.html` is cached at process start while the stylesheet is re-read per request.

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

## Three findings from reading the code — ✅ all three fixed in the build, verified live

Verified 2026-09-13 against the running services, not assumed:

```
$ curl -s http://127.0.0.1:8100/api/summary        # hub now has BOTH disks, and raw bytes
"disks":[{"name":"internal","total":940017598464,…,"freeh":"271.2 GB"},
         {"name":"external","total":491106508800,…,"freeh":"397.8 GB"}]

$ curl -s -D- -o /dev/null http://127.0.0.1:8099/  # space sets its own headers now
Content-Security-Policy: default-src 'none'; style-src 'self'; script-src 'self'; …
X-Content-Type-Options: nosniff
Referrer-Policy: no-referrer
Cache-Control: no-store
```

Finding 1 fixed (the hub gained the `disks` array with the `ismount()` guard), finding 2 fixed
(headers set at the app level, so the token no longer depends on Caddy's snippet alone), and
finding 3 fixed in the same change — raw `total`/`used`/`free` sit **alongside** `totalh`/
`usedh`/`freeh`, so values can animate between polls and `human()` was left untouched.

The original text is kept below because it is the only record of what the numbers were wrong
*by*:

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
- ~~**NZBGet is the easiest of the five, not the hardest**~~ — **this turned out to be wrong
  too, and is corrected in `WEB_UI_FINDINGS.md` §9.3.** Its files are indeed plain, but it is
  Bootstrap 2 with **no custom properties anywhere**, so there is no token layer to redeclare
  and the skin has to name ~120 selectors by hand. Its packaged `dark-theme.css` is also
  incomplete — 45 light surfaces it never covers. It is the **hardest** of the five. Bazarr,
  which did not exist when this was written, is the easiest: Mantine 7, a real token layer,
  2322 B of skin.
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

### v3 — the correction is now integrated throughout, not bolted on

The first pass only rewrote §4 and left the rest of the brief contradicting it. Fixed:

- Header says v3 and lists exactly what changed from v2.
- §4 heading now says **four** tiers, not three, and carries the `(§4)` anchor the rest of the
  document was already referencing.
- **Phase 0 step 5** now carries the research lesson: *"I tested route A and it failed" is not
  "the thing is impossible."* Enumerate every route per app — proxy, in-app setting, theme API,
  files on disk — and record the command behind each verdict. This is the most portable part
  of the correction and it is why the step exists.
- **Build order gained steps 14–16**: absorbed first-party pages, then Jellyfin, then the
  tier-3 skins *last* — they are the rarest surfaces, the only step writing outside the repo
  and `/usr/local/`, and worthless before the token set is settled.
- **§6 gained item 13**, bounding third-party edits: `.css` plus one `<link>` line, never
  `.js`, never `/var/lib/<app>/`, never a unit file, everything reproducible from the repo.
  §6.1–12 are untouched.
- **§8 checks 10–13 rewritten.** `pacman -Qkk <pkg>` replaces the `find -newer` hack — it
  names exactly which packaged files were altered. Baseline today is `radarr-bin: 583 total
  files, 0 altered files`; afterwards the only acceptable result is `index.html` per app.
  Check 12 now *simulates the upgrade* (`pacman -S --noconfirm radarr-bin`) to prove the hook
  actually fires, rather than trusting that it would.
- **§7** caps each skin at 8 KB and forbids it pulling the fonts in — skins inherit the
  palette, not the whole system.
- **§10** litmus extended: hub → Jellyfin → Radarr → NZBGet must read as one building; and a
  separate check asks whether the everyday path still runs through unskinnable Jellyseerr.
- **§11** now requires the skins, the apply script, the hook, and a DECISIONS entry recording
  that package-owned files are edited on purpose.

**Two things deliberately left open for the implementing agent**, because I did not measure
them: whether the Servarr apps re-read `index.html` per request or cache it at start (decides
whether the apply script needs a `systemctl restart`), and whether an override stylesheet or a
custom-property redeclaration is the upgrade-durable shape. Both are written into §4 tier 3 as
questions, not guesses.
