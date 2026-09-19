# Verifying the live wallpaper — brief for a Claude Code session on the G14
<!-- [CHANGE: claude-code | 2026-09-19] -->

A Cowork session can read and write this repo but **cannot run anything in the desktop
session** — no `qml6`, no `plasmashell`, no audio, no `git push` (the remote is SSH). This
file exists so a Claude Code session running **on the box** can close that gap without
anyone copying terminal output back and forth.

## The one command

```bash
~/luminos-os/scripts/luminos-wallpaper-selftest
```

It writes `docs/wallpaper/SELFTEST.log` and exits with the number of failed checks. The
Cowork session reads that file directly, so **the log is the handoff** — nothing needs
pasting.

## What is being verified, and what "working" means

| # | Section | Passing looks like |
|---|---------|--------------------|
| 1 | the package | every file installed, and the installed copy `diff -rq` clean against the repo |
| 2 | scene settings (SPEC §3.2) | `Spectrum.qml` and the sample shader both return `OK {…}`. **`NONE` for Spectrum is a failure** — it ships six controls |
| 3 | runtime shaders (SPEC §3.4) | `qsb` present, the sample shader compiles, the `.qsb` really lands in `~/.cache/luminos/wallpaper-shaders/` |
| 4 | QML contracts | `audio_contract` 22 checks, `props_contract` 21 checks, `editor_contract` 6 checks (does a settings row actually RENDER a control — BUG-173), all exit 0 |
| 5 | the running wallpaper | Chromium **not** mapped into plasmashell. `libcava` mapped only when an audio scene is selected |
| 6 | the journal | no `[LUMINOS-WP]` lines. Any that appear name the real fault — they are worth reading, not filtering |

## Restart plasmashell after EVERY deploy — before any eyes-on check
<!-- [CHANGE: claude-code | 2026-09-19] BUG-171 -->

```bash
systemctl --user restart plasma-plasmashell
```

Not once at the start of the session — **after every single deploy.** `QQmlEngine` caches
compiled components by URL for the life of the engine and never re-stats the file, and
plasmashell is one long-lived engine. So a `diff -rq` clean install is **not** a loaded
install: the config dialog keeps re-using the component it compiled the first time it was
opened. BUG-171 cost a whole eyes-on session this way — three fixes were "tested" against
the buggy code they had already replaced, with nothing anywhere saying so.

The tell, if you ever doubt it: **compare a `[LUMINOS-WP]` line in the journal against the
source on disk.** If the wording differs, the process is running something else. Section [6]
of the self test prints `installed files last written <ts>` for exactly this.

## What still needs a pair of eyes

The self test cannot see the screen. These three need a person, once:

0. **Keep the desktop visible while you look.** `ObscurePolicy=2` (the default) freezes the
   wallpaper whenever a maximized window covers the desktop, and a frozen audio scene shows
   flat bars by design (BUG-172). Un-maximize, or set **Stop rendering when hidden:** to
   *Never — keep rendering even when hidden*, before deciding the audio path is broken.
1. **Native QML → Spectrum**, with music playing in any player — the bars should move, the
   backdrop should swell on bass, and there should be a faint flash on the beat.
2. **Scene settings** at the bottom of the wallpaper settings dialog. **Labels with no
   controls beside them is BUG-173** — `editor_contract.qml` now catches that without a
   person, so check the self test first. Sensitivity, Bars,
   Bar bottom, Bar top, Flash on beat. Changing Bars to 128 should visibly change the
   wallpaper, and the value should survive closing and reopening the dialog.
3. **Shadertoy sample (audio-reactive)** from the Scene list — rings pulsing from the
   cursor, and a *different* settings panel (Speed, Tint) because it comes from that
   shader's own `properties.json`.

## Things that are already known — please do not re-diagnose them

- **Qt 6.11 blocks `XMLHttpRequest` on local files** (BUG-170). Do **not** fix anything by
  setting `QML_XHR_ALLOW_FILE_READ=1`: it is per-process and would give every QML object
  in plasmashell arbitrary local file reads. The reader is `contents/tools/luminos-wallpaper-props`.
- **`.qsb` files are not byte-reproducible.** Never md5 one to decide whether a shader
  changed — diff `qsb --dump` output instead.
- **Never `git add -A` in this repo.** There is an unpacked initramfs and a `_to_delete/`
  untracked at the root. Stage named files only.
- `pytest` and `hypothesis` are **not** installed on this machine, and installing them is a
  Python package action that AGENTS.md rules 5–6 gate behind `luminos-brain safe`. The
  Python suite runs in the build container; only the `qml6` tests run here.

## If something fails

Write what happened into `docs/wallpaper/SELFTEST.log` (the script already does) and, if you
fix it, follow AGENTS.md §13: `luminos-notes.sh add`, the doc triggers, and a commit with an
`Agent:` line. The Cowork session will pick the log up from the repo.

There are also several commits waiting that this session could not push, because the remote
is SSH and the bridge has no key:

```bash
git -C ~/luminos-os push origin main
```
