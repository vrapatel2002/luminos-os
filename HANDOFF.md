# HANDOFF.md — continue-from-here note (single source, overwritten in place)
Last updated: 2026-08-02 — Response 6 (Cowork session; sleep/suspend — **FIX LANDED**, awaiting one physical lid close)

## FIRST ACTION IN A NEW CHAT
Read this file, then `cat ~/luminos-os/AGENTS.md`. The **active thread is sleep/suspend** (below) and
it is essentially **done** — only a physical lid-close confirmation from the user is outstanding.
Everything under "Settled — do not re-litigate" is closed knowledge; do not redo that work.

---

# ACTIVE THREAD — sleep on lid close and on idle — FIXED 2026-08-02

## Goal (the durable end objective)
User report 2026-08-02: *"this laptop g14 is not going to sleep when lid is closed or after certain
time of inactivity. can you fix it?"*

User's three answers (asked and answered the same day):
1. **Lid close = sleep, always** — on battery **and** on AC. This deliberately reverses their own
   2026-06-03 decision.
2. **Live `rtcwake` suspend test — authorised**, and it was run.
3. **Idle timer = "whatever is the system default"** — so the defaults had to be *determined*, not
   invented. They were read out of the PowerDevil binary (see below).

## Status: DONE and VERIFIED END TO END
| Item | State |
|---|---|
| Suspend path itself | ✅ Proven working *before* any change — see "Problem B was wrong" |
| Lid close → sleep (AC + battery) | ✅ **Verified in the wild 2026-08-03** — see below. Not inferred |
| Idle → sleep (900/600/300 s) | ✅ Configured. Still no D-Bus readback; the lid close beat the idle timer to it, so this specific path is still unobserved |
| logind fallback (SDDM / TTY / logged out) | ✅ `suspend` on AC and battery, `ignore` when docked |
| `/etc/systemd/sleep.conf` noise | ✅ Dead `SuspendMode=` line removed |
| Docs (AGENTS.md §9, DECISION 38, BUG-091, LUMINOS_STATUS.md) | ✅ Written |

**The real-world proof** (the user closed the lid unprompted ~2 min after the fix landed):
```
Aug 02 00:50:11  systemd-logind: Lid closed.
Aug 02 00:50:11  systemd-logind: suspend requested from client PID 27911 ('org_kde_powerde')
Aug 02 00:50:11  systemd-logind: The system will suspend now!
        ... 40 hours in s2idle ...
Aug 03 16:56:23  systemd-logind: Lid opened.
Aug 03 16:56:24  kernel: PM: suspend exit          # session intact
```
`suspend_stats`: success 2 / fail 1.

⚠️ **Reading that journal is itself a trap.** There are ~41 `Timekeeping suspended for ~3600 s`
lines **all sharing one wallclock timestamp** (`Aug 03 16:56:23`). They are *not* 41 suspends. The
kernel ring buffer only drains to journald at full resume, so a whole night's worth of messages get
stamped at the same instant. They are the hourly s2idle re-arm cycles
(`PM: Triggering wakeup from IRQ 9` → `ACPI: PM: Rearming ACPI SCI for wakeup`). **Count
`PM: suspend entry` / `PM: suspend exit` — exactly one each.** Misreading this is almost certainly
what produced the old, wrong "Problem B".

## Residual: the FIRST lid close failed to suspend (minor, self-recovering, NOT fixed)
```
PM: Wakeup pending, aborting suspend
PM: active wakeup source: mmc0
systemd-sleep: Failed to put system to sleep. System resumed again: Device or resource busy
```
The **empty SD card reader** (`rtsx_pci_sdmmc`) raised a spurious wakeup 600 ms into device suspend.
PowerDevil retried 11 s later and that attempt held for 40 h — so the user sees a working laptop,
but roughly the first attempt can be lost.

- The PCI device's `power/wakeup` **already reads `disabled`** — so this is *not* a PCI PME wake and
  toggling PCI wakeup will not silence it. It is a kernel wakeup source registered by the mmc core
  (card detect). `/sys/kernel/debug/wakeup_sources`: `mmc0  active_count 2  prevent_suspend_time 3295248`.
- Same device already logs ~12 errors per boot **with no card inserted**.
- **Not applied — needs a user decision**, because the plausible fixes (blacklisting / constraining
  `rtsx_pci_sdmmc`) cost the SD reader entirely. Any such change is `/etc/` → Rule 10.

## THE DIAGNOSIS — what was actually wrong

### Problem A — sleep was deliberately switched off, in three places (CONFIRMED, and it was the whole story)
**Not a fault.** Built on purpose, commit `f8e00ab0` (2026-06-03), task line verbatim:
*"keep all processes running on lid close, screen off only."*

| Layer | Was | Now |
|---|---|---|
| `/etc/systemd/logind.conf.d/luminos-nolidsleep.conf` | `HandleLidSwitch`/`ExternalPower`/`Docked` = `ignore` | **Deleted**; replaced by `luminos-lidsleep.conf` → `suspend` / `suspend` / `ignore` (docked) |
| PowerDevil lid action | `lidAction=0` (do nothing) | `LidAction=1` (Sleep) on **AC, Battery and LowBattery** |
| Idle suspend | **no setting at all**, either profile | `AutoSuspendAction=1` + `AutoSuspendIdleTimeoutSec` 900 / 600 / 300 |
| `/etc/udev/rules.d/99-luminos-lid.rules` → `luminos-lid.service` → `kscreen-doctor` panel blank | armed | **Rule deleted**, `udevadm control --reload-rules` run. The `.service` is left installed but is `static` and now unreachable — the udev rule was its only entry point |
| logind `IdleAction` | `ignore` | **left `ignore` on purpose** — KDE owns the idle path; two idle timers would fight |

### Problem B — "it bounces straight back out" — ❌ DISPROVEN, do not chase it
The previous handoff called this "the real bug". **It was not a bug.** Proven *before* changing
anything, with `sudo rtcwake -m freeze -s 30`:
- slept the **full 30 s**; `Timekeeping suspended for 25.480 seconds`
- `ACPI: \_SB_.PEP_: Successfully transitioned to state lps0 entry`
- `amd_pmc: SMU idlemask s0i3: 0x3ffb3eb5`
- woke on **IRQ 9 (RTC)** — i.e. the alarm we set, nothing spurious
- `suspend_stats`: success 0→1, fail 0

The 2026-08-01 "suspend loop" was `upowerd` firing **critical-battery** suspends while the user kept
**opening the lid**. The final suspend had no exit because **the battery died.** Nothing to fix.

Corollaries that also turned out to be noise, not causes:
- The `\_SB.PCI0.GPP7.CADR` / `ACPI Error: Aborting method \_SB.PEP._DSM` pair fires only on the
  **exit** path and does not prevent s0ix. AMI GA403UU.306 firmware defect. **Benign — leave the
  BIOS alone.**
- `mmc0` / `rtsx_pci_sdmmc` logs ~12 errors per boot with **no card inserted** and fired one wakeup
  event without preventing a full 30 s sleep.

### Problem C — config hygiene — ✅ FIXED
`/etc/systemd/sleep.conf` line 2 (`SuspendMode=s2idle`) was removed from systemd upstream and logged
`Support for option SuspendMode= has been removed` twice per suspend. Line dropped, comment left in
its place. `SuspendState=freeze` is the line that actually selects s2idle.

Rule 10 debt from 2026-06-03 (no §9 rows, no DECISION entry for the lid config) is now cleared.

## ⚠️ THE TRAP THAT COST THIS THREAD ITS TIME — read before touching PowerDevil again
**PowerDevil 6.7 keys live under a *subgroup*, and a wrong group is silently accepted.**

The first fix wrote `LidAction=1` under a bare `[AC]` group in `~/.config/powerdevilrc`. KConfig
parsed it. `inotifywait` proved PowerDevil **opened the file**. It did **nothing**.

- PowerDevil ships **no `.kcfg`** — the schema is compiled in. `ProfileSettings` is a
  `KConfigSkeleton` over **`powerdevilrc`**, group = the bare profile id (`AC`, `Battery`,
  `LowBattery`), and items are registered against **subgroups**:
  `SuspendAndShutdown`, `Display`, `Keyboard`, `Performance`, `RunScript`.
- **The live key is `[AC][SuspendAndShutdown] LidAction`.** Same silent-success shape as
  BUG-088/089.
- `~/.config/powermanagementprofilesrc` is the **legacy Plasma-5** file. It is no longer read for
  these settings. It was **kept, not deleted** (deleting could re-trigger migration) and its
  `lidAction` values were aligned to `1` so a re-migration cannot reimport `0`.
- KConfigXT getters are **inline**, so `nm -D` on the action plugins shows zero ProfileSettings
  imports. Don't read that as "it doesn't use it".

**Verify like this:**
```
qdbus6 org.kde.Solid.PowerManagement \
  /org/kde/Solid/PowerManagement/Actions/HandleButtonEvents lidAction     # → 1 == Sleep
busctl get-property org.freedesktop.login1 /org/freedesktop/login1 \
  org.freedesktop.login1.Manager HandleLidSwitch                          # → "suspend"
```

**⚠️ NEVER use `triggersLidAction()` as the health check.** It returns `true` for *every*
configuration, **including `LidAction=0`**. It reports that PowerDevil owns the lid event, not what
PowerDevil will do. It was caught only because it was deliberately run against a config known to be
wrong. `lidAction()` (int) is the one that tracks config — it was watched moving 1→2→0→1 under test.

## Where the numbers came from (not guessed)
The user asked for "the system default", so it was disassembled out of
`/usr/lib/libexec/org_kde_powerdevil` rather than invented:
- `defaultLidAction()` → `1` on the ordinary-laptop branch
- `defaultAutoSuspendType()` → `mov $0x1,%eax` → `PowerButtonAction::Sleep`
  (enum: `NoAction=0, Sleep=1, Hibernate=2, …`)
- `defaultAutoSuspendIdleTimeoutSec()` → **AC 900 / Battery 600 / LowBattery 300** (non-mobile branch)

These are **written explicitly** into `powerdevilrc` so behaviour cannot drift if upstream changes
its defaults.

## Live config now in place
`~/.config/powerdevilrc`:
```
[AC][SuspendAndShutdown]
AutoSuspendAction=1
AutoSuspendIdleTimeoutSec=900
LidAction=1

[Battery][SuspendAndShutdown]
AutoSuspendAction=1
AutoSuspendIdleTimeoutSec=600
LidAction=1

[LowBattery][SuspendAndShutdown]
AutoSuspendAction=1
AutoSuspendIdleTimeoutSec=300
LidAction=1
```

## Known limits of the verification — state these, do not gloss them
- **The idle timer has no D-Bus readback.** `SuspendSession` exposes only
  `suspendToRam/suspendToDisk/suspendHybrid` plus the `aboutToSuspend`/`resumingFromSuspend`
  signals, and PowerDevil logs no "registering idle timeout" line. Confidence rests on it living in
  the same group that was *proven* live via `LidAction`. Not the same as a direct observation.
- **The physical lid switch was never actuated** — no hinge, no hands. `lidAction()` returning `1`
  says what PowerDevil *will* do, not that it did it.

## Ruled OUT — do not chase these
- **`SYSTEMD_SLEEP_FREEZE_USER_SESSIONS=false` is NOT a Luminos customization.** It ships from
  nvidia-utils at `/usr/lib/systemd/system/systemd-suspend.service.d/10-nvidia-no-freeze-session.conf`.
  Vendor default. The "This is not recommended" log line is nvidia's, not ours.
- **`/sys/power/mem_sleep` = `[s2idle]` only.** There is no `deep`/S3 on this platform. That is
  normal for modern AMD laptops, not a misconfiguration.
- **The forex bot was not a blocker** — `forex-bot.service` was `inactive` (down from BUG-080).
  It **will** matter again once BUG-080 is fixed — it is **live trading**. Re-check `is-active`
  before any future suspend test; do not assume.
- `supergfxctl` is `enabled`/`active` in Hybrid mode; `/etc/modprobe.d/supergfxd.conf` is
  auto-generated and dates to 2026-04-11. Not a new change.

## Gotchas for this thread
- **`systemctl show systemd-logind -p HandleLidSwitch` prints NOTHING** — those are *Manager* D-Bus
  properties, not unit properties, so it silently returns empty rather than erroring. Use `busctl`.
  An empty result reads as "unset" and is a trap.
- **PowerDevil, not logind, owns the lid** while Plasma runs — it holds a **`block`** inhibitor on
  `handle-lid-switch`. The logind drop-in is only the SDDM / bare-TTY / post-logout fallback.
  Changing only logind changes nothing for a logged-in user.
- Kernel timestamps across a suspend are flushed at resume, so freeze→suspend→resume can share one
  timestamp. Bracket with `PM: suspend entry` / `PM: suspend exit`, and cross-check
  `Timekeeping suspended for N seconds`.

## Backups taken
`~/luminos-os/backups/power-2026-08-02/` — `powermanagementprofilesrc`, and
`etc/{luminos-nolidsleep.conf, 99-luminos-lid.rules, sleep.conf}`.
Repo `systemd/`: `luminos-nolidsleep.conf` removed (also `git rm --cached`), `luminos-lidsleep.conf`
added. `99-luminos-lid.rules` and `luminos-lid.service` kept **byte-identical** so the 2026-06-03
behaviour is restorable.

## Next steps
1. **Decide on the `mmc0` residual above** — accept the occasional lost first attempt, or trade the
   SD reader away. User's call.
2. **BUG-082 (video wallpaper freezes on resume) — HALF-verified, do not close it yet.**
   A real 40 h suspend/resume finally happened (2026-08-03 16:56). Confirmed after it: plasmashell
   **never restarted** (`ActiveEnterTimestamp` still 2026-08-01 23:55, elapsed matches uptime), and
   there are zero wallpaper/QML/gstreamer errors in the journal since resume. That is *necessary but
   not sufficient* — plasmashell was at 0.0% CPU, which per BUG-083's `ObscurePolicy` is exactly what
   a correctly-**paused** wallpaper looks like as well as a frozen one. **The remaining check needs a
   human: show the desktop and confirm the video is actually moving.**
3. The **idle** path (900/600/300 s) is configured but has never actually been observed firing —
   the lid close always got there first. Worth catching once in the journal.

---

# Settled — do not re-litigate (condensed from earlier threads)

## MCP tooling (BUG-085 / BUG-087, DECISIONS 33 & 34) — DONE
- **Claude Code reads `~/.claude/settings.json` (USER scope), not the repo's `.mcp.json`.** Cowork /
  Claude Desktop launch it with `--setting-sources=user`, so repo-scoped config is never loaded
  there. `.mcp.json` is intentionally empty. Desktop and Antigravity have their own configs — that
  is correct, not duplication. The invariant is **one pinned binary**, not one file.
- **User-scope hooks do NOT fire in Cowork.** Proven 2026-07-26 with a cleared log: no `SessionStart`,
  no `PostToolUse` after ~15 tool calls. Hooks work in the CLI only. **Consequence: in Cowork the
  code graph never refreshes itself** — check `list_graph_stats_tool`'s `last_updated` before
  trusting "this function has no callers", or call `build_or_update_graph_tool` at session start.
  MemPalace is unaffected (queried on demand).
- One tool = one pyenv 3.12.13 venv, pinned, never editable. `luminos-verify --mcp` does a real MCP
  `initialize` handshake and hard-fails on duplicate registration / rolling-python interpreter /
  editable install / missing binary. Every check was negative-tested.
- **DECISION STILL OPEN:** install a `systemd --user` path unit watching **`~/luminos-os/.git/index`**
  (not the repo directory — path units are **not recursive**) to refresh the graph in Cowork? Or
  just refresh manually each session?

## Theme / Ubuntu (Yaru) look (BUG-088 / BUG-090, DECISION 30) — DONE
- `AutomaticLookAndFeelOnIdle` **defaults to `true`** with a **5 s** idle interval. Writing only
  `AutomaticLookAndFeel=false` leaves the idle path armed and looks like an intermittent bug. Both
  keys are now `false` in `~/.config/kdeglobals`.
- **Never verify a KDE colour scheme by its name.** `plasma-apply-colorscheme` no-ops with exit 0
  when the name already matches, without writing the `[Colors:*]` payload — so the name said Yaru
  while the payload stayed Breeze Dark for four days. Compare an actual colour value.
- GTK is the half that breaks: a Look-and-Feel apply rewrites `~/.config/gtk-{3,4}.0/settings.ini`
  via the `kde-gtk-config` kded module. **`plasma-changeicons Yaru` exits 0 and does NOT fix them.**
- **Never `kwriteconfig6` an `index.theme`** — it sorts groups and buries `[Icon Theme]`, which the
  freedesktop spec requires first. Use `scripts/luminos-icon-inherits.py`.
- **Settled:** dock/launcher icons come from **Papirus** and cannot come from Yaru (Yaru ships no
  `org.kde.dolphin`/`konsole`/`firefox`/`google-chrome` icon; breeze has none either). Changing them
  is a taste decision, not a bug.
- **TRADEOFF ACCEPTED:** KDE automatic light/dark switching is off and cannot coexist with the Yaru
  look. Re-enabling it in System Settings silently undoes DECISION 30.
- **NOT installed:** `systemd/luminos-theme-sync.{path,service}` exist in the repo but were never
  copied to `~/.config/systemd/user/`. Ask before installing.

## Wallpaper (BUG-083 / BUG-082, DECISION 32) — DONE
- `ObscurePolicy` (int: 0 never / 1 fullscreen / 2 desktop-hidden, **default 2**) replaced the old
  `PauseWhenObscured` bool. plasmashell went 24% of a core → ~0 while hidden.
- **Never encode a wallpaper above panel resolution** — 2880×1800 panel was decoding a 4K source.
- **The running wallpaper loads from the INSTALLED copy**
  (`~/.local/share/plasma/wallpapers/org.luminos.livewallpaper/`), not the repo. Deploy recipe at the
  bottom of this file.
- **KWin's "Show Desktop" does NOT set `IsMinimized`** — useless for testing the occlusion guard.
- BUG-082 (video freezes on resume) is **fixed but still never live-verified**. It needed a real
  suspend/resume, which was blocked by the lid/suspend thread — **that block is now gone (2026-08-02).
  Verify it on the next real resume.**

## Memory / hardware ceiling — settled
- **15.6 GiB is the planning ceiling.** 4× soldered Micron LPDDR5, no SO-DIMM. But **"impossible to
  upgrade" is WRONG** — 32 GiB is reachable via 4 BGA reworks + a **three-byte** firmware patch.
  ASUS already ships three 32 GiB SPD profiles unedited; selection is by **BoardMask**, so the SPD
  contents never need editing. Exact offsets, checksum rule (all APCB bytes sum to `0x00`) and the
  PSB analysis (no OEM key, no RTM signature → not signed) are in git history for this file.
- **Bandwidth, not capacity, is the contended resource: 102.4 GB/s shared with the 780M iGPU**, which
  has no private VRAM. A RAM upgrade would not relieve it.
- **dGPU VRAM cannot become 24/7 system memory.** ReBAR is on (BAR1 = 8192 MB) so the CPU *can*
  address it, but: the GPU die is the memory controller; GDDR6 needs refresh; D3cold cuts the rails
  (measured **89% of uptime suspended** — the VRAM is free *because* the dGPU is asleep); MMIO reads
  are µs-scale vs ~80 ns DRAM and swap-in is a read; and there is no kernel NUMA path without a
  coherent interconnect. **The real unified-memory lead is the iGPU 512 MB carve-out (98% full) with
  7633 MB GTT behind it.** Next concrete move if resumed: measure the VRAM/GTT split under load.
- dGPU VRAM upgrade is hard-blocked: **AD107 never shipped above 8 GB anywhere**, so no signed VBIOS
  describing more exists. Unlike the RAM case, there is no vendor config to select.

## Other open items
- **BUG-084 — durable fix NOT applied.** DrKonqi's `gdb` + debuginfod ate 7.4 GB and filled zram;
  cleared by hand. **It will recur on the next app crash.** Needs user go-ahead for a `MemoryMax=`
  drop-in on `drkonqi-coredump-launcher@.service`. Fingerprint to check first next time:
  `/proc/pressure/memory` `full` high while `/proc/pressure/cpu` stays ~1% = memory stall.
  `ps --sort=-rss | head` found it in one command.
- **`kscreen-doctor` SIGABRTs reliably on this box** (3× in 24 h) and each crash arms another
  drkonqi launcher. `luminos-lid` called it on every lid event — **that path was removed 2026-08-02**
  with the udev rule, so this trigger is gone. Others may remain.
- **BUG-086 (OpenRouter key) is CLOSED/WONTFIX** — dead account, user dropped it 2026-07-25.
  **Do not re-raise rotation.**
- **BUG-080 open** — Wine 11.8→11.13 broke the MT5/forex stack. Live-trading infra; needs a
  deliberate window.

## Repo hygiene — READ BEFORE COMMITTING
- **`git push` is on hold by explicit user decision.** 11+ commits unpushed. Commit locally only.
- **Never `git add -A`.** That is how the API key got published, and the tree still holds parked
  work that must not ride along: `share/`, `scripts/luminos-wine-*`, `scripts/luminos-ubuntu-look`,
  `systemd/luminos-theme-sync.*`, `systemd/luminos-ubuntu-look.service`, the `cmd/luminos-power`
  conductor edits, and three dirty `research/turboquant` submodules. **Stage by name.**
- **Luminos scripts have a recurring habit of printing success on a failed path** (BUG-088's
  `Ubuntu (Yaru) look re-affirmed.`, BUG-089's `Note added to $TAG.`). Both hid faults for days.
  **`luminos-brain log` still has it** — avoid apostrophes when calling it. When touching any
  `scripts/` helper, check its "done" message is *conditional*.
- **`luminos-brain safe` keyword-matches, it does not reason** — it has blocked correct plans with an
  unrelated canned reason. That is open task 0b.

## Files relevant to the active thread
- `~/.config/powerdevilrc` — **the live one.** `[<profile>][SuspendAndShutdown]`, subgroup mandatory
- `~/.config/powermanagementprofilesrc` — legacy Plasma-5; kept, values aligned, no longer read
- `/etc/systemd/logind.conf.d/luminos-lidsleep.conf` (repo: `systemd/luminos-lidsleep.conf`)
- `/etc/systemd/sleep.conf` — dead `SuspendMode=` line removed
- `/etc/udev/rules.d/99-luminos-lid.rules` — **deleted** (backed up; repo copy kept for restore)
- `/etc/systemd/system/luminos-lid.service` + `/usr/local/bin/luminos-lid` — still installed,
  now unreachable (`static`, and its only trigger was the deleted udev rule)
- Docs written for this: `AGENTS.md` §9, `LUMINOS_DECISIONS.md` **DECISION 38**, `docs/BUGS.md`
  **BUG-091**, `LUMINOS_STATUS.md`

### Wallpaper deploy / reload recipe
```
SRC=~/luminos-os/src/wallpapers/org.luminos.livewallpaper
DST=~/.local/share/plasma/wallpapers/org.luminos.livewallpaper
rm -rf "$DST"; mkdir -p "$DST"; cp -r "$SRC/." "$DST/"
mkdir -p "$DST/contents/samples"; cp ~/luminos-os/src/wallpapers/samples/*.html "$DST/contents/samples/"
systemctl --user restart plasma-plasmashell.service
```
