# HANDOFF.md — continue-from-here note (single source, overwritten in place)
Last updated: 2026-07-25 — Response 9

## FIRST ACTION IN A NEW CHAT — settle the one open question (hook liveness)
Everything else in thread 4 is done and verified. **One thing could not be tested from the session
that fixed it**, because it can only be answered by a *fresh* session. Do this before anything else:

```bash
~/luminos-os/scripts/luminos-verify --mcp
```

Expected today: `PASS — 1 warning(s), 0 failures`. Read that one warning:

| What you see | What it means | What to do |
|---|---|---|
| The warning is **gone** (`0 warning(s)`) | User-scope hooks **do fire inside Cowork**. `SessionStart` ran and wrote to `~/.luminos-hooks.log`. | Nothing. Close the question in BUG-087 and drop the "unproven" caveat from AGENTS.md §6 and DECISION 34. |
| `hooks are configured but have NEVER run — no /home/shawn/.luminos-hooks.log` | Cowork **does not execute hooks at all**. The graph will never refresh by itself in this host. | Build the fallback: a **systemd path unit** (below). |
| `hook(s) PostToolUse … configured but never observed running` (SessionStart present, PostToolUse absent) | SessionStart fires, PostToolUse does not. Partial. | Same fallback — the graph is the part that needs freshness. |

**Why this test is trustworthy:** `~/.luminos-hooks.log` was deliberately **cleared** at the end of
Response 8, so any line in it now was written by *this* session. The log is appended to by
`scripts/luminos-hook-session-check` (SessionStart) and `scripts/luminos-hook-crg-update`
(PostToolUse); both write their trace line *before* their gate, so a line appears even when the
hook correctly no-ops outside a repo.

**Do NOT try to short-circuit this with `claude -p`.** Hooks do not run in headless mode at all —
this was controlled for across `--setting-sources` unset / `user` / `user,project` and fired in
none of them. A negative from `-p` proves nothing.

**Fallback if hooks are dead here:** a systemd **path** unit (`--user`) watching
`/home/shawn/luminos-os` and running
`~/.code-review-graph-venv/bin/code-review-graph update --skip-flows --repo /home/shawn/luminos-os`.
An update takes ~1.1 s. Use a path unit, not a timer, so it stays idle when nothing changes.
Pattern to copy: `systemd/luminos-theme-sync.path` + `.service` already in the tree (untracked).

## READ THIS FIRST — where MCP config actually lives (BUG-087)
**Claude Code reads `~/.claude/settings.json` (USER scope) — not the repo's `.mcp.json`.**
Cowork / Claude Desktop launches Claude Code with `--setting-sources=user`, so anything in
`~/luminos-os/.mcp.json` or `~/luminos-os/.claude/settings.json` is **never loaded there**. It still
works from a terminal, which is why this went unnoticed: the config looks right and simply never
runs. `.mcp.json` is now intentionally empty and says so — do not re-add servers to it.
Claude Desktop and Antigravity have their own configs and their own registrations; that is correct,
not duplication. The invariant is **one binary**, not one file. Run `luminos-verify --mcp`.

**BUG-086 (OpenRouter key) is CLOSED/WONTFIX** — user dropped that account on 2026-07-25. Do not
re-raise rotation. The second dead OpenRouter key that was pinning `ANTHROPIC_BASE_URL` in user
scope has been removed, because it would have broken plain `claude` in a terminal.

## Goal (the durable end objective)
Four threads:
1. **Make the desktop feel fast again.** DONE for the wallpaper (BUG-083 / DECISION 32) — it must
   never spend CPU/iGPU on frames nobody can see, nor be encoded above the panel resolution.
2. **BUG-084 — stop the crash handler from taking the machine down.** This turned out to be the
   *actual* cause of the reported freeze. Cleared by hand; the durable cap is NOT applied yet.
3. **"Pseudo-unified memory architecture"** — the user's clarified ask: *"24/7 unified memory across
   the CPU and dGPU, as the dGPU will be mostly not used, so it's CPU/iGPU only regardless of what
   we are doing, HIVE or not."* i.e. always-on and general-purpose, NOT a HIVE-session-scoped thing.
   NOT STARTED — there is a hard hardware constraint to resolve with the user first (below).
4. **Stop the agent MCP tooling from silently rotting, everywhere it runs.** DONE (BUG-085 +
   BUG-087 / DECISIONS 33 & 34) — see below. Now reaches Claude Code, Claude Desktop and Antigravity.
   The user's ask was *"we have mempalace and code review graph but we add some new things it breaks
   its environment and it stops working — how to solve it once and for all."*

## Aim right now
Thread 4 is **done and verified across all three MCP clients**. One open question, deliberately not
claimed as solved: whether a *user-scope hook* actually fires inside Cowork. See **FIRST ACTION IN A
NEW CHAT** at the top — that is the next thing to do, and it takes one command.
Thread 1 done. Thread 2 awaiting a yes/no on the `MemoryMax` drop-in. Thread 3: the hardware
constraint has been explained to the user (Response 3) — **dGPU VRAM cannot be made into general 24/7
system memory on this box**, and trying would destroy the true-0W idle work. Awaiting their direction;
the real lead is the iGPU carve-out, not the dGPU.

## State — what is DONE (thread 4, BUG-085 / DECISION 33 — MCP tooling)
**Key insight: neither tool was crashed.** Both answered an MCP handshake the whole time, which is
exactly why this rotted unnoticed for months. Every *dependency* was a moving target and every
failure was silent. Six defects, all fixed:
1. **Both hooks had never run, ever.** `.claude/settings.json` called bare `code-review-graph`;
   hooks run in a **non-interactive shell** with `PATH=/usr/local/bin:/usr/bin`, and `~/.local/bin`
   is added only by `~/.zshrc` line 33. → `command not found`, silently, every time. The 30 s
   timeout was never the problem: a real update takes **1.1 s**.
2. **MemPalace registered TWICE under one name** — `.mcp.json` (pyenv, pinned v3.3.1) vs
   `~/.claude.json` local scope (uv venv, **editable**, v3.1.0). Local scope wins, so the live
   server was v3.1.0 while AGENTS.md §6 documented the other one.
3. **That install was editable** → a `git pull` in `~/mempalace` silently changed the running
   server. This is the literal mechanism behind the user's complaint.
4. **A THIRD MemPalace** lived in `~/.local/lib/python3.14/site-packages` — a shared **301-package**
   user-site on Arch's *rolling* python. All three copies wrote one 2.0 GB store.
5. **`code-review-graph` shebang was `#!/usr/bin/python3`** — one pacman python bump from vanishing.
   Notes show it already bit once: `2026-05-07 | Removed all references to code-review-graph … to
   stop startup errors.`
6. **5,951 stale locks** in `~/.mempalace/locks` (oldest 2026-04-22).

**Fix:** one tool = one **pyenv 3.12.13** venv, pinned, never editable
(`~/.code-review-graph-venv`, `==2.3.1`, **no extras** — the `all` extra pulls `ollama`, Rule 9);
`.mcp.json` is the single authoritative registration; hooks use absolute paths + `--repo`;
`~/.local/bin/mempalace` CLI symlinked to the same venv so CLI and MCP cannot disagree;
locks 5951 → 0.

**Why it can't silently rot again:** `scripts/luminos-verify` gained **section [5] + `--mcp`**, wired
to the SessionStart hook. It performs a **real MCP `initialize` handshake** per server and hard-fails
on: duplicate registration · `/usr/bin/python*` interpreter · interpreter outside `~/.pyenv` ·
any editable install · missing binary · starts-but-returns-nothing. **Each was negative-tested by
deliberately reintroducing the fault.** Also fixed `--quiet`, which printed *nothing at all* — a FAIL
was indistinguishable from a PASS, which would have rebuilt the silent-rot disease inside the check
meant to catch it.

**Verified functionally, not just by handshake:** MemPalace 29 tools,
`mempalace_search("dGPU power gating RTD3")` → 15 hits; code-review-graph 24 tools,
`list_graph_stats_tool` → 259 files / 3161 nodes / 21658 edges,
`query_graph_tool(callers_of, setEPPAfterAsusctl)` → 4 callers. Full `luminos-verify` → PASS.

**Committed locally as `a9df5ec9`** (7 files, +587/−14: `.claude/settings.json`, `AGENTS.md`,
`HANDOFF.md`, `LUMINOS_DECISIONS.md`, `LUMINOS_STATUS.md`, `docs/BUGS.md`, `scripts/luminos-verify`).
Staged **by name, not `git add -A`** — the tree still holds unrelated parked work (`share/`, the
wine and ubuntu-look scripts, `systemd/luminos-theme-sync.*`, the `cmd/luminos-power` conductor
edits, three dirty `research/turboquant` submodules) that must NOT ride along. **Not pushed** —
`git push` remains on hold by explicit user decision, and pushing now would also re-publish the
BUG-086 key situation without it being addressed.

## Why / motivation (context a newcomer would be missing)
The user reported "Chrome and the OS are actually not responding" and suspected the live wallpaper.
The wallpaper *was* a genuine chronic cost — and for a non-obvious reason: it lands on the **iGPU
(renderD129)**, the *same* device KWin composites on and Chrome renders on. But it was **not** the
freeze. Mid-session the box went into a real **memory stall** (BUG-084) and that is what the user
was feeling. Both were worth fixing; do not conflate them.

## Process / approach being used
Measure first, then change, then re-measure the same counter. The counter used throughout is
`awk '{print $14+$15}' /proc/$(pgrep -x plasmashell)/stat` (utime+stime jiffies) sampled twice N
seconds apart, plus `/sys/class/drm/card2/device/gpu_busy_percent` and RSS.

## State — what is DONE (thread 1, BUG-083 / DECISION 32)
- **`PauseWhenObscured` (bool) → `ObscurePolicy` (int)** in `contents/config/main.xml`:
  `0` never freeze · `1` freeze only under a **fullscreen** window · `2` freeze whenever the desktop
  is hidden (fullscreen **or** maximized) — **default 2**.
- Per-window cover is now **graded** (`fullscreen=2`, `maximized=1`, `minimized/normal=0`) and the max
  across windows is **debounced 400 ms** (`coverDebounce`) so alt-tab does not stop-start the decoder.
  The old code OR-ed `IsMaximized || IsFullScreen` into one bool, so the two cases were indistinguishable.
- `config.qml`: the checkbox became a 3-option combo + an explanatory caption.
- **Video right-sized**: `3840×2160 → 2880×1620` H.264 CRF 20, `-an` (it is muted anyway). Panel is
  2880×1800, so the 4K source was decoding 8.3 MP per frame to fill 5.2 MP. **4K original kept.**
- Live config switched (desktop `ObscurePolicy=2`, lock screen deliberately `0`), plugin deployed,
  plasmashell restarted, loads with **zero QML errors**.
- **Measured** (plasmashell, one core):
  | State | CPU | RSS | iGPU |
  |---|---|---|---|
  | 4K, always render (before) | 240/10s (24%) | 810 MB | 16–18% |
  | 2880×1620, always render | 128/10s (12%) | 589 MB | 12% |
  | 2880×1620, hidden (now, default) | **1/10s (~0%)** | 617 MB | — |
  | 2880×1620, desktop visible | 61/6s (~10%) | — | — |
- **Resume verified**, not assumed: minimize Chrome via a KWin script → 61 jiffies/6s, restore → 0.
- Docs written: BUG-083, DECISION 32, LUMINOS_STATUS.md row, luminos-notes, luminos-brain.

## State — what is DONE (thread 2, BUG-084 — the actual freeze)
Diagnosed and cleared live, fully written up in `docs/BUGS.md` BUG-084. Summary:
- KDE **DrKonqi** launched `gdb ... --init-eval-command=set debuginfod enabled on` on a **364 MB
  Filelight core**. gdb reached **7.4 GB RSS / 16.3 GB VSZ at 70% CPU, still running after 12 min**,
  with **five** `drkonqi-coredump-launcher@*` units active at once.
- Peak: RAM **13 of 14 GiB used**, **zram swap 100% full (80 KiB free of 8 GiB)**, `pswpout` 2.47 M
  pages, **PSI memory `full` avg10 = 7.85%** while **CPU PSI stayed ~1%** — a *memory* stall, not a
  CPU shortage. That asymmetry is the fingerprint; check it first next time.
- Cleared with `systemctl --user stop 'drkonqi-coredump-launcher@*.service'` → RAM 13 → 5.6 GiB,
  swap 8 GiB full → 1.6 GiB, PSI memory full **7.85% → 0.08%**. Cores kept, nothing lost.
- **Durable cap NOT applied** — it will recur on the next app crash.

## State — what is IN PROGRESS
Nothing half-built. Thread 3 has **no code written** — deliberately.

## Thread 3 — the constraint, and the answer to "why do we need the dGPU to use VRAM?"
The user asked for "24/7 unified memory across the CPU and dGPU", then asked directly:
*"cant we access the vram without using the dgpu, why in the first place do we need dgpu to use?"*
**This was answered in Response 3. Do not re-litigate it — record the reasoning here so a future
session does not redo the investigation.**

The premise is **half right**: the CPU *can already address VRAM*. Measured from sysfs this session
(`/sys/bus/pci/devices/0000:01:00.0`, deliberately without touching `nvidia-smi`):
```
BAR0 = 16 MB   BAR1 = 8192 MB @ 0x7c00000000   BAR3 = 32 MB   BAR5 = 128 B
resource0_resize / resource1_resize / resource3_resize present  → Resizable BAR ENABLED
```
So the full 6 GB VRAM aperture is mapped into CPU physical address space, no 256 MB window bouncing.
The address works. Four separate reasons it still does not give us system memory:

1. **The GPU die *is* the memory controller.** The GDDR6 chips are wired to exactly one thing — the
   GPU's memory controller. There is no board trace from the CPU to those chips. Every access is
   CPU → root complex → PCIe link → GPU endpoint → GPU fabric → GPU memory controller → GDDR6. The
   BAR is a doorway, not the room.
2. **GDDR6 is dynamic RAM — it forgets.** Capacitors leak and need refresh thousands of times per
   second, and only the GPU's memory controller issues those refreshes. Even *parking* idle data
   there needs the GPU powered. It is not passive storage.
3. **D3cold cuts the power rails.** `d3cold_allowed=1`, and measured
   `runtime_suspended_time = 34,627,852 ms` vs `runtime_active_time = 4,365,730 ms` → **asleep ~89%
   of uptime**. VRAM contents are saved/restored *through system RAM* by the driver on each
   transition. Using VRAM 24/7 drives suspended_time to 0 → ~8 W constant draw, undoing BUG-047,
   DECISION 25 and the `DPM=0x02` tuning. **The dGPU's memory is free precisely because the dGPU is
   asleep** — the user's own reason for wanting it is the reason it is currently free. Rule 11 conflict.
4. **Even awake, the performance shape is wrong, and there is no kernel path.** BAR1 is MMIO —
   uncached / write-combining. Writes stream fine; CPU *reads* are microsecond PCIe round trips vs
   ~80 ns for DRAM, with no caching and no prefetch. Swap-in is a read — the exact worst direction.
   zram already achieves ~4:1 (7.9 GB of data in 1.9 GB) at DRAM speed, so VRAM-as-swap is a
   downgrade on a workload we already handle. And Linux only hot-adds device memory as a NUMA node
   over *coherent* interconnects (CXL, NVLink-C2C on Grace-Hopper); plain PCIe device memory is
   `DEVICE_PRIVATE` (not CPU-accessible) or `DEVICE_COHERENT` (needs coherent interconnect we lack).
   Userspace routes (FUSE `vramfs`, NBD) cannot safely host swap.

**Useful side finding: ReBAR being enabled with an 8 GB BAR1 is a real win for DECISION 23** —
host→VRAM weight streaming can map the full 6 GB in one shot, no window juggling. Worth exploiting
when HIVE weight streaming is built.

### System memory ceiling — measured (2026-07-24)
`dmidecode -t memory` on this board (`ROG Zephyrus G14 GA403UU`):
```
4 × Micron MT62F1G32D2DS-026 WT   LPDDR5, 4 GiB each  (16 GiB total, 15.6 GiB visible)
Channels A / B / C / D            Data Width 32 bits each  → 128-bit total bus
Form Factor: Other                → SOLDERED BGA, there is no SO-DIMM slot
Rated 7500 MT/s   Configured 6400 MT/s   0.5 V   Rank 1   ECC: None
BIOS: AMI GA403UU.306, 2024-06-05.  Secure Boot disabled, no kernel lockdown, no /dev/mtd.
```
- **15.6 GiB is the ceiling for all current planning.** Treat it as fixed. But see the CORRECTION
  below — "physically impossible to upgrade" is **wrong**, and an earlier version of this file said so.
- **Total memory bandwidth = 128 bits × 6400 MT/s ÷ 8 = 102.4 GB/s, SHARED with the 780M iGPU.**
  The iGPU has no private VRAM — the 512 MB "vram" is a BIOS carve-out of this same LPDDR5. So
  zero-copy between CPU and iGPU is genuinely free, but **bandwidth is the contended resource, not
  capacity**. BUG-083's 4K wallpaper was spending this budget, not a separate GPU one. **A RAM
  upgrade would NOT relieve this** — doubling capacity leaves bandwidth at ~102.4 GB/s.

### CORRECTION (2026-07-24, Response 6) — soldered LPDDR5 upgrade IS possible
An earlier version of this section claimed RAM here is "not upgradable on this machine, at all."
**That was overstated, and one of its four supporting reasons was factually false.** Evidence: the
user surfaced dosdude1, "ASUS ROG Ally 32GB RAM Upgrade" (2025-06-28, youtu.be/KbYfhzZzNJg), a
completed and verified 16 → 32 GiB soldered-LPDDR5 upgrade. Full transcript pulled and read.

**The claim that was outright wrong:** *"each channel is a single rank with no spare chip-select."*
LPDDR5 defines **two** ranks per channel and the CS1 line is already routed on these boards — it is
simply unused because the fitted packages are single-rank. That idle second rank is exactly what the
mod turns on. Do not repeat this claim.

**What the mod actually is** (directly applicable — the Ally has the *same* topology as us: 4 × 32 Gbit
Micron packages, 16 GiB, single rank, 128-bit, 6400 MT/s, same AMD platform generation):
1. Board preheater at 250 °C, hot air at 330 °C; desolder all four packages, fit 4-die dual-rank
   replacements (Samsung `K3LKCKC0BM-MGCP`, ~$100 AliExpress — same parts used for Steam Deck upgrades).
2. It boots but still reports 16 GiB. The memory controller does **not** interrogate the chips; it
   trusts SPD data baked into the BIOS image.
3. Desolder the SPI EEPROM, dump it, locate the `APCB` blocks, and edit **two SPD bytes**:
   - **byte 6** (SDRAM package type): 2 dies/package → 4 dies/package — `0x95` → `0xB5`
   - **byte 12** (organization): 1 package rank → 2 package ranks — `0x02` → `0x0A`
   Then copy the edited SPD record over **every** SPD entry in the image (board strap config selects
   among them and will otherwise pick a stock Micron profile), fix the APCB checksum with
   `github.com/95JakeHex/APCB_ROG_Ally` → `Man_edit_apcb_checksum_fix.py`, reflash, re-solder.
4. Result: 32 GiB, still 6400 MT/s, stable. Windows Update must be blocked from flashing BIOS or the
   edit is reverted (he disabled the "System Firmware" device in Device Manager).

### BIOS IMAGE ANALYSED (2026-07-24, Response 7) — no signing, and 32 GiB SPD profiles already shipped
Downloaded the exact installed firmware and parsed it byte-for-byte. This answers both open gates.

**Provenance.** `https://dlcdnets.asus.com/pub/ASUS/GamingNB/Image/BIOS/117008/GA403UUAS306.zip`
→ `GA403UUAS.306`, 33,556,480 bytes. That is 32 MiB **plus a 2048-byte ASUS/AMI update capsule**
(GUID `4A3CA68B-7723-48FB-803D-578CC1FEC44D`, header size `0x0800`, version `0x00010000`, then RSA
signature bytes). Stripping those 2048 bytes yields the raw 32 MiB flash image. **That capsule
signature is checked by EZ Flash / WinFlash only — it does not live on the flash chip, so an external
programmer writing the raw image bypasses it entirely.** No firmware tooling was installed (flashrom,
UEFITool, psptool, amdfwtool are all absent); parsing was done with throwaway Python.

**Layout found.** AMD Embedded Firmware Structure magic `0x55AA55AA` @`0x20000`;
`psp_directory = 0x121000`, second pointer `0x122000`. Valid directories: `$PSP` @`0x121000` (2),
`$PSP` @`0x122000` (2), `$PL2` @`0x125000` (45), `$BL2` @`0x524000` (36), and a full mirrored copy at
+`0x48F000` (`$PL2` @`0x5b4000`, `$BL2` @`0x9b3000`). Eight `APCB` blocks: `0x12f928`, `0x525000`,
`0x528000`, `0x531100` and their four mirrors.

**GATE 1 — Platform Secure Boot: NOT enabled in this image.** Both `$PL2` directories contain only
type `0x00` AMD public key (`0x440` @`0x800`), type `0x0b` soft fuse chain, type `0x50` key database
(`0x2680` @`0x195900`), type `0x51` token unlock (`0x2480` @`0x198000`). **Type `0x05` (OEM BIOS
public key), type `0x07` (BIOS RTM signature) and type `0x0A` (OEM public key) are all ABSENT.** With
no OEM key and no RTM signature there is nothing for the PSP to verify the BIOS region against — the
APCB is protected by a plain checksum, not a cryptographic signature. Caveat that cannot be closed
from the image alone: PSB enforcement ultimately depends on **CPU fuse state**, and fuses are not
readable from firmware bytes. Evidence is strongly favourable, not a proof.

**GATE 2 — the SPD edit is UNNECESSARY here. ASUS already ships 32 GiB profiles.** The big APCB
(`0x528000`, size `0x16f8`) holds a `MEMG` group with **seven SPD records, stride `0x150`**, SPD data
starting at `0x5280f0`, part-number string at record offset `+0xe1`:

| SPD @ | part | byte 6 | dies/pkg | byte 12 | ranks | density/die | total |
|---|---|---|---|---|---|---|---|
| `0x5280f0` | `MT62F2G32D4DS-026 WT` | `0xB5` | 4 | `0x0A` | 2 | 16 Gb | **32 GiB** |
| `0x528240` | `MT62F1G32D2DS-026 WT` | `0x95` | 2 | `0x02` | 1 | 16 Gb | 16 GiB ← **fitted** |
| `0x528390` | `K3KL9L90CM-MGCT` (Samsung) | `0xB5` | 4 | `0x0A` | 2 | 16 Gb | **32 GiB** |
| `0x5284e0` | `K3KL8L80CM-MGCT` (Samsung) | `0x95` | 2 | `0x02` | 1 | 16 Gb | 16 GiB |
| `0x528630` | `H58G66BK7BX067` (SK Hynix) | `0xB5` | 4 | `0x0A` | 2 | 16 Gb | **32 GiB** |
| `0x528780` | `H58G56BK7BX068` (SK Hynix) | `0x95` | 2 | `0x02` | 1 | 16 Gb | 16 GiB |
| `0x5288d0` | `MT62F512M32D2DR-031` | `0x95` | 2 | `0x02` | 1 | 8 Gb | 8 GiB |

The exact byte values dosdude1 had to hand-edit (`byte 6 = 0xB5`, `byte 12 = 0x0A`) are **already
present, unedited, in three shipping profiles** — one per DRAM vendor. Vendor JEDEC IDs confirm at
record offset `+0xd6`: `0x2C` Micron, `0xCE` Samsung, `0xAD` SK Hynix. Three vendors × two capacities
in one image is the signature of a BIOS written to cover multiple factory RAM SKUs.

### SELECTION MECHANISM RESOLVED (2026-07-24, Response 8) — BoardMask, not chip interrogation
Parsed the APCB group/type headers properly. Every APCB type header carries a 16-bit **BoardMask**
at offset +14, and the seven SPD entries each have a *different, single-bit* mask — a clean 1:1
mapping onto six factory board variants:

| BoardMask | part | capacity |
|---|---|---|
| `0x0002` (bit 1) | `MT62F2G32D4DS-026 WT` Micron | **32 GiB** |
| `0x0004` (bit 2) | `MT62F1G32D2DS-026 WT` Micron | 16 GiB ← **this board** |
| `0x0008` (bit 3) | `K3KL9L90CM-MGCT` Samsung | **32 GiB** |
| `0x0010` (bit 4) | `K3KL8L80CM-MGCT` Samsung | 16 GiB |
| `0x0020` (bit 5) | `H58G66BK7BX067` SK Hynix | **32 GiB** |
| `0x0040` (bit 6) | `H58G56BK7BX068` SK Hynix | 16 GiB |
| `0xffff` (any) | `MT62F512M32D2DR-031` Micron | 8 GiB |

**Every other type in the image is `BoardMask=0xffff`** — PSPG, GNBG, FCHG, TOKN and the remaining
MEMG types (0x31/0x35/0x36/0x38/0x40/0x50/0x52/0x53/0x5f/0x99/0x9a/0x9b), plus both small
token-only APCBs at `0x525000` and `0x531100`. So board ID gates **nothing except which SPD profile
is used.** Changing it has no other side effect anywhere in this firmware.

Board ID comes from PSPG type `0x0060` (BoardIdGettingMethod, `BoardMask=0xffff`, data at
`0x5280a0`):
```
03 00 03 00 00 0b 00 00 0c 01 00 ff ff ff 07 00
01 07 01 02 07 02 03 07 03 04 07 04 05 07 05 06
```
The tail is unambiguous — six 3-byte tuples `(mask=0x07, value=N, boardId=N+1)` for N = 0..5, i.e. a
**3-bit value mapped to board IDs 1-6**, and `BoardMask = 1 << boardId`. **The transport is NOT
confirmed.** Method id is `0x0003`; `0c 01 00 ff ff ff` looks like a six-slot pin list with three
used (pins 12, 1, 0). Tested that hypothesis against live FCH GPIO state via
`/sys/kernel/debug/gpio` (`#0` reg `0x081578e3` → high, `#1` reg `0x00150000` → high, `#12` reg
`0x00040000` → low; bit 16 is PIN_STS). Best-fit decode gives value `0b011` = 3 → board ID 4 →
**Samsung 16 GiB** — which contradicts the Micron parts actually fitted, so **the pin-list reading is
wrong.** Also `#0` has an interrupt with debounce configured, i.e. it is a live in-use pin, not a
strap. Do not repeat the GPIO claim. Transport remains open; it does not block the plan.

### The patch this enables — smaller than the Ally edit
Because selection is by BoardMask, the SPD *contents* never need touching. Promoting the Micron
32 GiB profile to match all boards is enough, and it is first in the list so it wins on order:

```
0x5280de:  02 00  ->  ff ff     BoardMask, Micron MT62F2G32D4DS entry
0x528010:  94     ->  98        APCB checksum byte
0x9b70de:  02 00  ->  ff ff     same, mirrored firmware copy at +0x48F000
0x9b7010:  94     ->  98        same
```
**APCB checksum rule verified empirically:** the sum of every byte in the APCB, checksum byte
included, is `0x00`. Confirmed on all four blocks (`0x525000` ck `0x72`, `0x528000` ck `0x94`,
`0x531100` ck `0x72`, `0x9b7000` ck `0x94`) — all currently sum to zero. Recomputed values above are
verified to restore that. No external checksum tool needed; `github.com/95JakeHex/APCB_ROG_Ally` is
not required.

Two bytes plus one checksum byte, twice. Offsets are into the **raw 32 MiB flash image**, i.e. the
ASUS file minus its leading 2048-byte capsule. Still needs the SPI flash off the board (no
`/dev/mtd`), and still needs the four DRAM packages replaced with `MT62F2G32D4DS-026 WT`.

**Remaining real risks:** four BGA reworks with a 250 °C preheater and 330 °C hot air; sourcing parts
matching footprint, pinout and speed grade (ours are rated 7500 MT/s); a dead mainboard rather than a
dead module if it goes wrong; warranty void.

**Bottom line for planning:** keep designing against 15.6 GiB. Honest framing is now "four BGA
reworks plus a three-byte firmware patch at known offsets" — not "impossible," and not gated on PSP
verification.

### dGPU VRAM upgrade — assessed 2026-07-24, Response 8
`10de:28e1` rev `a1`, subsystem `1043:3398` = **AD107M, RTX 4050 Laptop**, read from sysfs without
waking the device (`power_state = D3cold` throughout). 6 GB on a **96-bit bus = three 32-bit
channels = three 2 GB (16 Gbit) GDDR6 packages**, soldered to the same mainboard as everything else.

Three routes, all blocked for *specific* reasons — record these so this is not re-litigated:
1. **Denser packages.** Needs 32 Gbit GDDR6 to double. Mainstream GDDR6 tops out at 16 Gbit; 24 Gbit
   parts exist (Samsung) and would give 3 × 3 GB = 9 GB, a non-power-of-two config on 96 bits.
2. **More packages (wider bus).** AD107 also ships as RTX 4060 Laptop / RTX 2000 Ada Laptop at
   8 GB / 128-bit — but that is a fourth *channel*, needing a fourth set of routed traces that a
   96-bit board does not have, and a different fused device ID.
3. **Clamshell** (second package on the reverse side sharing the channel) needs back-side pads
   designed into the PCB. Not present on a 3-package 96-bit layout.

**The real gate is the VBIOS.** Since Turing, NVIDIA VBIOS is cryptographically signed and verified
by on-die secure boot — a hand-edited image is rejected. Every *working* community mod
(2080 Ti 11→22 GB, 3070 8→16 GB, 3080 10→20 GB) works because the **same die already shipped in a
higher-VRAM SKU**, so a *stock signed* VBIOS describing that config exists: TU102 → Quadro RTX 6000
24 GB, GA104 → RTX A4000 16 GB, GA102 → RTX A5000. This is structurally the identical trick to the
BoardMask finding above — you don't forge the config, you select one the vendor already shipped.
**For AD107 no such SKU exists.** Its maximum anywhere is 8 GB, and only on 128-bit. There is no
signed NVIDIA firmware anywhere that describes an AD107 with more than 8 GB.

So: unlike system RAM — where the win came from ASUS having already shipped the config we want —
here nobody shipped it, so there is nothing to select. That is a hard blocker, not a hand-wave.
Failure mode is also worse: the GPU is soldered to the same board as CPU, RAM and SPI flash, so a
botched GPU rework kills the machine, whereas a modded desktop card is a replaceable part.

**Priority note:** 16 → 32 GiB system RAM is both more achievable and worth more to HIVE than
6 → 9 GB of VRAM would be, since it also raises the 780M's GTT ceiling and CPU-side model headroom.

**Confirmed from the full video transcript — SPD was the ONLY thing changed.** No power delivery, no
VRM, no resistor straps, no other hardware modification anywhere in the procedure. Two bytes and a
checksum. Tooling he used: TL866 / XGecu (Xgpro) programmer; **the EEPROM runs at 1.8 V**, so a
3.3 V-only programmer needs a level shifter or it can damage the chip; `MX25U25645G` chosen as a
near-match definition with "check ID" unchecked; SOIC adapter socket; leaded solder on reinstall for
easier future rework; SPD located by searching `02 00 04 80 00 00 0`; checksum script run under
`python` (v2), not `python3`.
- **Total memory bandwidth = 128 bits × 6400 MT/s ÷ 8 = 102.4 GB/s, SHARED with the 780M iGPU.**
  The iGPU has no private VRAM — the 512 MB "vram" is a BIOS carve-out of this same LPDDR5. So
  zero-copy between CPU and iGPU is genuinely free, but **bandwidth is the contended resource, not
  capacity**. BUG-083's 4K wallpaper was spending this budget, not a separate GPU one.
- **Open question, not yet investigated:** parts are rated 7500 MT/s but configured at 6400 — ~17%
  of bandwidth unused. Unknown whether that is BIOS conservatism, an AMD-validated ceiling for this
  SKU, or a power/thermal decision. Worth a look ONLY if measurement shows bandwidth is the binding
  constraint. Do not assume it is free performance.

- **The genuinely unified half already exists and is measurable.** Live readings this session:
  `mem_info_vram_total = 512 MB` with **501 MB used (98% full)**, `mem_info_gtt_total = 7633 MB` with
  1218 MB used. The 512 MB is the BIOS UMA carve-out for the 780M; everything beyond it spills to
  GTT. That carve-out being pinned at 98% on a 2880×1800 HiDPI desktop is the most concrete
  unified-memory lead we have, and it is on the CPU/iGPU side the user says they actually live on.
- Suggested first move, pending user agreement: **characterise the iGPU VRAM/GTT split under real
  load** (idle vs Chrome vs wallpaper vs HIVE) before proposing any allocator. Measure, then design.

## Next steps (ordered)
0. **BUG-086 — ROTATE THE OPENROUTER KEY.** See the banner at the top of this file. Order matters:
   (a) revoke/rotate at openrouter.ai — this is the only step that actually kills the credential;
   (b) `git rm --cached .claude/settings1.json` — a plain `.gitignore` edit will NOT untrack it;
   (c) commit. Purging it from history needs `git filter-repo` + a **force-push to a shared
   remote** — destructive, user's decision only, and worthless before the key is revoked.
1. **BUG-084 durable fix** — user go-ahead for a systemd drop-in on
   `drkonqi-coredump-launcher@.service` with `MemoryMax=`/`MemoryHigh=`, so a runaway backtrace is
   OOM-killed in its own cgroup. Optionally also blank `DEBUGINFOD_URLS` for drkonqi and serialise
   the launchers. Until this lands, every app crash can repeat the stall.
2. Separately: **`kscreen-doctor` SIGABRTs reliably on this box** (three times in 24 h) and each crash
   arms another launcher. Fix or avoid it.
3. **Thread 3** — the dGPU-VRAM constraint has now been explained to the user (Response 3); awaiting
   their direction. Next concrete move: measure the iGPU VRAM/GTT split under load (idle / Chrome /
   wallpaper / HIVE) before writing any allocator code.
   Cache-theory mapping to reuse when it does get built: L1 dGPU VRAM 4.6 GB / L2 system RAM 16 GB
   (already genuinely unified with the iGPU — zero-copy there, only the dGPU needs a PCIe transfer) /
   L3 zram / L4 NVMe. Weights are **read-only → clean lines → eviction is free, no write-back**; KV
   cache is read-write → pin or write back. The replacement policy already exists in-tree:
   **luminos-ram's LIRS/IRR + HotSet**. Prefetch = the layer N+1 double-buffer (DECISION 23).
   "Way-locking" = resident weights/KV/embeddings/output head that must never be evicted.
4. Optional wallpaper follow-up: detect **session locked / DPMS-off** and freeze then too. Today the
   lock greeter is not a window in `TasksModel`, so `coverLevel` stays 0 and the desktop copy keeps
   decoding behind the lock screen if no maximized window is up.
5. `git push` is **on hold by explicit user decision** — commit locally, do not push yet.

## Key decisions & constraints so far
- **DECISION 32 amends DECISION 31.** The session-wide `QTWEBENGINE_CHROMIUM_FLAGS` anti-throttle is
  **kept** — it removes the *involuntary* Chromium/KWin throttle, which is what makes `ObscurePolicy=0`
  work at all. The plugin's policy is now the **authority**; the flags are the enabler.
- Default `2` is a deliberate trade: a *maximized* window stops the wallpaper. Anyone wanting motion
  behind a maximized window sets `1` or `0` and pays ~12% of a core.
- Rule recorded in DECISION 32: **never encode a wallpaper above the panel resolution** — the extra
  pixels are decoded and then thrown away by the scaler.

## Gotchas / dead-ends / things NOT to redo
- **Never `os.path.realpath()` a venv's `bin/python` to find its site-packages.** It resolves the
  symlink *out* of the venv into `~/.pyenv` or `~/.local/share/uv`, so you inspect the wrong tree.
  An early version of `luminos-verify` section [5] did this and reported a clean **PASS for a
  known-editable install**. Derive the venv from the **configured** command path instead. This is
  why the negative tests exist — the check was wrong and only the negative test caught it.
- **pip and uv mark editable installs differently**: pip writes `<dist-info>/direct_url.json` with
  `{"dir_info":{"editable":true}}`; uv drops a bare `_<pkg>.pth`. Check both or you miss half.
- **`luminos-brain safe` blocked this work twice with `NO: ML/AI always use pyenv 3.12.13` — for a
  plan that WAS pyenv 3.12.13.** It is keyword-matching, not reasoning. Proceeded via
  `--reason` with explicit user authorization. Live instance of open task 0b.
- **Do not "fix" MemPalace by retiring it again.** LUMINOS_STATUS.md used to list it as deprecated
  with "hnswlib crash" while AGENTS.md made it mandatory. The crash was the *CLI* resolving to a
  different install on Arch's rolling python — not MemPalace. That contradiction is now corrected.
- **`git add -A` is how the API key got published.** `.claude/` is not gitignored. Stage by name.
- **The running wallpaper loads from the INSTALLED copy**
  (`~/.local/share/plasma/wallpapers/org.luminos.livewallpaper/`). Editing the repo source alone does
  nothing — run the deploy recipe below + restart plasmashell. (This already cost a wasted test during
  BUG-082.)
- **KWin's "Show Desktop" does NOT set `IsMinimized`**, so it does not change `coverLevel`. It is
  useless as a test of the occlusion guard — use a real minimize or unmaximize.
- The jank was **not** a fault. Do not go looking for amdgpu hangs/OOM again: journal is clean, PSI is
  0, 8.5 GB available. It is contention.
- iGPU busy stays at ~12–21% even with the wallpaper fully frozen — that residue is Chrome / Claude /
  KWin, **not** the wallpaper. Do not attribute it to the wallpaper.
- **The wallpaper was not the freeze.** It was a real chronic cost (24% of a core, forever) and worth
  fixing, but the unresponsiveness was BUG-084. Do not let the wallpaper fix "explain" a future stall
  — check `/proc/pressure/memory` `full` vs `/proc/pressure/cpu` first. Memory-full high + CPU-some
  low = a memory stall, and something is eating RAM.
- **`ps --sort=-rss | head` found it in one command.** Reach for that before any deep GPU forensics.
- **NOT pushed to origin** (user's explicit decision this session). Committed locally only.
  `git add -A` would sweep in files the previous
  session explicitly parked as "awaiting user OK" (`scripts/luminos-ubuntu-persist`,
  `systemd/luminos-ubuntu-look.service`, `share/`, the wine scripts) — stage by name, never `-A`.
- Still unverified from the previous session: BUG-082's real suspend/resume cycle (close lid, wait
  ~10 s, reopen). A plasmashell restart does not test that path.

## Files touched / relevant files
- `src/wallpapers/org.luminos.livewallpaper/contents/config/main.xml` — `ObscurePolicy` replaces `PauseWhenObscured`
- `src/wallpapers/org.luminos.livewallpaper/contents/ui/main.qml` — graded `cover`, `coverDebounce`, `notVisible`, `shouldPlay`
- `src/wallpapers/org.luminos.livewallpaper/contents/ui/config.qml` — 3-option combo + caption
- `docs/BUGS.md` (BUG-083), `LUMINOS_DECISIONS.md` (DECISION 32), `LUMINOS_STATUS.md`
- Live config (not in repo): `~/.config/plasma-org.kde.plasma.desktop-appletsrc`,
  `~/.config/kscreenlockerrc` — backups `*.bak-wallpaper-20260724`
- Video: `~/Videos/4K Video Downloader+/Sabrina Carpenter Kissing Screen Wallpaper (2880x1620 h264).mp4`
  (4K original kept next to it)
- Relevant for thread 2: `LUMINOS_DECISIONS.md` DECISION 23, `cmd/luminos-ram/main.go`,
  `docs/LUMINOS_RAM_ARCHITECTURE.md`, `scripts/hive-daemon.py`

### Deploy / reload recipe
```
SRC=~/luminos-os/src/wallpapers/org.luminos.livewallpaper
DST=~/.local/share/plasma/wallpapers/org.luminos.livewallpaper
rm -rf "$DST"; mkdir -p "$DST"; cp -r "$SRC/." "$DST/"
mkdir -p "$DST/contents/samples"; cp ~/luminos-os/src/wallpapers/samples/*.html "$DST/contents/samples/"
systemctl --user restart plasma-plasmashell.service
```
