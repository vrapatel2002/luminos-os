# HANDOFF.md — continue-from-here note (single source, overwritten in place)
Last updated: 2026-09-13 — Response 1 (new chat; the previous chat ended at Response 6)

> Previous goals, complete, do not reconstruct from memory:
> gaming/dGPU → `git show b08c3904:HANDOFF.md` · `org.luminos.style` QML → `git show 4273ed7e:HANDOFF.md`
> web-surface redesign → the version of this file at `git show fa8c1bf2:HANDOFF.md`

## Goal (durable)
Keep Luminos OS working as a daily-driver Windows replacement — the G14 desktop/AI stack and the
separate media server — fixing what Shawn reports, and never leaving a change undocumented.

## Aim right now
**Nothing is mid-flight.** The PS5-controller task below is finished and verified. Pick up from
"Still outstanding".

## State — what is DONE

### ✅ 2026-09-13 — PS5 controller in Lutris (BUG-156 / DECISION 101)
Reported as *"the ps5 controller is not supported"*. Two separate defects, both fixed and
verified live as the normal user.

1. **`/dev/hidraw3` was `root:root 0600`** because Arch's `steam-devices` udev rules were not
   installed. Everything *else* about the pad was already perfect — `hid-playstation` had it,
   and `event18`/`js0` both had `uaccess` ACLs — which is exactly why this is easy to
   misdiagnose. That one node decides whether SDL uses its **HIDAPI PS5** driver (rumble, light
   bar, gyro, touchpad, correct map) or falls back to generic **evdev**, which enumerates
   cleanly and throws no error. Fixed with `pacman -S steam-devices`.
2. **Black Myth Wukong's `sdl_gamecontrollerconfig` override was dead and wrong.** GUID product
   field `e60e` (`0x0EE6`, not a Sony product) vs the real `e60c` (`0x0CE6`) — one transposed
   character, so it never matched. The body was a DualShock-3 map anyway (digital triggers,
   rotated face buttons). Deleted; SDL's built-in mapping is correct.
   Backup: `~/.config/lutris/games/black-myth-wukong-1788815087.yml.bak-ps5-20260913`.

Verified as `shawn`, no sudo: HIDAPI driver active, rumble **OK** (felt), LED **OK** (light bar
went orange), gyro/accel/touchpad all present.

### ✅ earlier — the web-surface redesign (DECISION 99)
All eight surfaces on one token set. Brief `server/docs/WEB_UI_PROMPT.md` **v3** (v2/v1 are
superseded — **do not merge them**); full research trail, art directions and screenshots in
`server/docs/WEB_UI_FINDINGS.md`. Budgets all held.

| tier | what | how |
|---|---|---|
| 1 | `luminos-hub` `/` + `/offline`, `luminos-space` | ours, rebuilt from zero on `/app.css` |
| 2 | Jellyfin | Custom CSS via its own API — **ElegantFin removed** |
| 3 | Radarr, Sonarr, Prowlarr, NZBGet, **Bazarr** | skinned on disk + pacman hook |
| 4 | Jellyseerr | cannot be skinned — request flow **absorbed** as a first-party page |

## ⚠️ Read these before touching the web surface

1. **There are FIVE tier-3 apps, not the four the brief lists.** Bazarr arrived the same day the
   brief was written (DECISION 98). It is in `TIER3`, in the hook, and skinned.
2. **`login.html` is skinned too**, so `pacman -Qkk` reports **2** altered files per Servarr app,
   not the 1 that §8 check 10 calls "the ONLY acceptable result". Deliberate — all three run
   `AuthenticationMethod=Forms`, so it is the only page a logged-out browser sees. **Do not "fix"
   it back.**
3. **The pacman hook is proven live on NZBGet only.** The other four are not in
   `/var/cache/pacman/pkg/`, so the version-identical reinstall could not be run. If you want
   that proof it needs a re-download — ask first.
4. **`<Theme>dark</Theme>` is a write under `/var/lib/<app>/`**, which §6.13 otherwise forbids.
   It is the "free win" §4 instructs; Servarr persists that API field to `config.xml`, not its
   database. Flagged, not hidden.

## Still outstanding (ordered)
1. **Reboot** — glibc + systemd were upgraded and the running system is still on the old ones.
   Then confirm a Lutris game renders on the dGPU with `dgpu-exec-v2 -- nvidia-smi`.
   *(The controller fix needs no reboot — udev rules in `/usr/lib` apply at boot and the running
   node was already re-triggered.)*
2. ⚠️ **`server/config/Caddyfile` in the repo is STALE — missing the Bazarr `:8450` block that is
   live on the box.** DECISION 98 added it to `/etc/caddy/Caddyfile` on 2026-09-13 17:51 and never
   mirrored it back. Restoring the repo copy onto the box today would silently drop Bazarr's front
   door. Deliberately not fixed inside the redesign commit (§8 check 13 requires that diff to be
   empty, and mixing the two makes config drift indistinguishable from a redesign change).
   **Mirror it back as its own change.** The one *other* difference is intentional and must stay:
   the repo redacts the `luminos-space` token, the live file has the real one.
3. **`luminos-brain safe` has now returned a false `NO` four times** by matching the bare word
   "install" — the newest instance is DECISION 101. **Its rule scope needs narrowing.** Until then
   the documented escape is `luminos-brain safe "<action>" --reason "<why it is not ML/venv>"`,
   which logs `OVERRIDE LOGGED`. Also still open: 0b, make a `NO` print its actual reason instead
   of unrelated canned incident lines.
4. Bazarr has **pre-existing** errors from its fresh install, unrelated to the skin:
   `KeyError: 'audio_only_include'`, a `FOREIGN KEY constraint failed` on a Solo Leveling episode,
   and Sonarr sync timeouts. All timestamped before that work — see `WEB_UI_FINDINGS.md` §10.2 so
   they are not misread as fallout.
5. `/etc/nftables.conf` was rewritten at 17:51 the same day, with a `.bak-20260913` alongside.
   **Checked, not assumed:** `policy drop` still holds and every `accept` is restricted by source
   address or interface — the only unrestricted ones are ICMP. Nothing is open to the internet.
6. **Still unexplained: the initramfs-looking untracked tree at the repo root** (`init`, `kernel/`,
   `usr/`, `etc/`, `lib`, `sbin`, `hooks/`, `early_cpio`, `buildconfig`, `keymap.bin`,
   `consolefont.psfu`). Plus an untracked `_to_delete/`. **Find out what these are before anyone
   commits or deletes them.**

## How to change a skin
Edit `server/assets/skins/<app>/luminos.css`, then:

```
rsync -a server/assets/skins/ <box>:/tmp/skins/
sudo rsync -a /tmp/skins/ /usr/local/share/luminos/skins/
sudo luminos-skin-apply --check     # dry run, exits 1 if anything would change
sudo luminos-skin-apply             # apply
```

Comments and indentation are stripped at install time (that is how the 8 KB budget is met), so the
repo copy stays readable and `diff`ing installed-vs-git still works line by line. A colour-only
change never restarts a service; only inserting the `<link>` does, because `index.html` is cached
at process start while the stylesheet is re-read per request.

## Key decisions & constraints

**Frozen token set** — every colour and size in the finished CSS resolves to one of these:

| token | value | token | value |
|---|---|---|---|
| `--bg` | `#0F0D0B` | `--accent` | `#FF7A18` |
| `--surface` | `#17140F` | `--ok` | `#3FBF6A` |
| `--line` | `#2A2520` | `--warn` | `#E8C547` |
| `--text` | `#F2EDE4` | `--danger` | `#FF4D3D` |
| `--muted` | `#8C8279` | `--r` | `4px` |

Type: `--t-display clamp(52px,15vw,76px)` / `--t-head 15px` / `--t-body 15px` / `--t-mono 14px` /
`--t-caption 12px`. Spacing `--s1..--s6` = 4/8/12/16/24/40 px. Faces: **Archivo** 500+800
(display/UI), **JetBrains Mono** 400+800 (all numbers, all release names). Accent is deliberately a
hue-step away from `--warn` so the two never read as the same signal.

**`/app.css` and `/app.js` on port 8099 do NOT require the token.** Static constants, no library
data, no secrets, byte-identical to what the hub already serves unauthenticated. Putting the token
in a `<link href>` would spread it into a second URL and into browser error reports for no gain.
Every route returning library data or performing a delete keeps `compare_digest` unchanged.

**Fonts are a whitelist, not a path join.** `FONTS` is a fixed tuple and the route tests membership,
so traversal is impossible by construction rather than by correct escaping. Verified with
`/fonts/../../../etc/passwd` → 404.

## Gotchas / dead-ends / things NOT to redo

**Controllers**
- **`getfacl /dev/hidraw*` is the first check for any "controller not supported" report**, not
  `/dev/input`. evdev/joydev get `uaccess` from stock systemd rules and will look healthy while
  hidraw is locked and every real feature is missing.
- **Do not hand-write a udev rule or an `sdl_gamecontrollerconfig` for a pad.** DECISION 101 has
  the reasoning: the package is maintained, covers ~240 devices, and is not an `/etc/` file.
- **`SDL_GameControllerRumbleTriggers` returning "not supported" on a DualSense is correct** —
  that is the Xbox trigger-rumble API. Adaptive triggers use `SDL_SendGamepadEffect`.
- **No 32-bit SDL on this box, and none is needed.** `sdl2-compat` is 64-bit only, Arch has no
  `lib32-sdl2-compat`; system `wine`'s `winebus.so` links `libudev` and not SDL, and Proton /
  GE-Proton ship their own. Installing one fixes nothing.

**Web surface**
- **Font weight lives in the hinting and ligature tables, not the glyphs.** A naive Latin-1 subset
  of JetBrains Mono Regular is 29,348 bytes; `--no-hinting` plus dropping `liga`/`calt` gives the
  same coverage in 7,884. Do not re-derive this.
- **Keep `tnum`.** Tabular figures are the entire reason JetBrains Mono carries the numbers.
- **Subset range is Latin-1 + Latin Extended-A, not ASCII.** ASCII is ~3 KB smaller per file and
  wrong — the library holds titles like `Amélie`, and a missing glyph falls back mid-word.
- **Screenshot through Caddy, never `127.0.0.1`.** The loopback port skips the proxy, the TLS and
  the token injection. Working command:
  `chromium --headless --disable-gpu --no-sandbox --ignore-certificate-errors
  --window-size=412,1400 --force-device-scale-factor=2 --virtual-time-budget=9000
  --hide-scrollbars --screenshot=/tmp/x.png "https://192.168.2.61/"`
  (412 px is the Pixel 9 CSS width; `--ignore-certificate-errors` is required because the IP
  addresses can only ever use Caddy's local CA.)
- **`server/SPEC.md` is a different project** (the LLM prefill work). The spec for the web build is
  `server/docs/WEB_UI_PROMPT.md`.
- **Tier-3 apps CAN be reskinned** — the brief once claimed otherwise and was wrong. What was
  actually proved is only that *proxy-level body rewriting* is unavailable in stock Caddy. The
  on-disk route works and is theme.park's documented native method. The portable lesson, now
  written into the brief's Phase 0 step 5: **"I tested route A and it failed" is not "the thing is
  impossible."** Enumerate every route per app and record the command behind each verdict.
- **NZBGet is the HARDEST of the five, not the easiest** — Bootstrap 2, no custom properties, so
  ~120 selectors by hand and its packaged `dark-theme.css` misses 45 light surfaces. Bazarr is the
  easiest (Mantine 7, real token layer, 2322 B).

**Process**
- **MCP `mempalace` and `code-review-graph` are NOT connected in Cowork sessions.** AGENTS.md §6
  requires saying so rather than skipping silently. Confirmed again this session — fell back to
  `luminos-notes.sh search` + `luminos-brain query`.

## Files touched this session
- `docs/BUGS.md` — BUG-156 added
- `LUMINOS_DECISIONS.md` — DECISION 101 added
- `AGENTS.md` §9 — `steam-devices` row added
- `HANDOFF.md` — this file
- **Live system, not in the repo:** package `steam-devices` installed;
  `~/.config/lutris/games/black-myth-wukong-1788815087.yml` (+ `.bak-ps5-20260913`)
