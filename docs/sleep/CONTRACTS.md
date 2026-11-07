# CONTRACTS — strong sleep (frozen; change only via re-plan logged in BUILD_LOG.md)
# [CHANGE: claude-code | 2026-11-06]
Repo: ~/luminos-os. All paths below relative to it unless absolute.

## A. NVIDIA patch "nvsleep" (owner: W1 implementer)
- Source: /usr/src/nvidia-610.57.04 (nvidia-open-dkms 610.57.04-1), ALREADY carrying patches/nvdefer/nvdefer-610.57.04.patch.
- Work tree: patches/nvsleep/work/ = copy of patches/nvdefer/work/ (nvdefer applied). Never edit /usr/src by hand.
- Patch: patches/nvsleep/nvsleep-610.57.04.patch, unified diff -p1 relative to the source root, applies with
  `patch -p1 -F0` on top of nvdefer. Touches ONLY kernel-open/nvidia/nv.c and kernel-open/nvidia/nv-pci.c. Never src/.
- Module params (nvidia.ko): `nv_sleep_skip_idle` (int, 0644, default 1); `nv_sleep_skipped` (ulong, 0444, count of
  sleeps where the card was left off). Marker comment string `LUMINOS-NVSLEEP` in every changed hunk.
- Behaviour:
  * PM_SUSPEND_PREPARE (standby only; hibernate = stock): if nv_sleep_skip_idle && EVERY nvidia device in
    nv_linux_devices is pm_runtime_suspended(nvl->dev) → record "skipped", still take nv_system_pm_lock for write
    (so no RM API entry can wake the card while the system sleeps), DO NOT call nv_suspend_devices (no nvkms_suspend,
    no UVM suspend, no RM call). Otherwise stock.
  * PM_POST_SUSPEND after a skipped suspend: release the lock, DO NOT call nv_resume_devices. Clear "skipped".
  * Device callbacks (nv_pmops_suspend / resume and any late/noirq ones the driver has) for a device in a skipped
    sleep: if still runtime-suspended → return 0 with no RM call. If it is NOT runtime-suspended any more (raced
    awake) → return -EBUSY from suspend so the system suspend aborts cleanly (and nothing half-suspended is left).
  * nv-pci.c: keep DPM_FLAG_NO_DIRECT_COMPLETE; ADD DPM_FLAG_SMART_SUSPEND (+ DPM_FLAG_MAY_SKIP_RESUME if the kernel
    defines it) under #if defined(...) guards, so the PCI core stops runtime-resuming a D3cold card in pci_pm_suspend.
  * One NVRM info line per skipped sleep and per skipped resume. No new allocations, no new locks besides the use above.
- Script: scripts/luminos-nvidia-defer gains the second patch: --apply applies nvdefer then nvsleep (each idempotent,
  own marker), --revert removes both, --check reports both + both loaded params. Installed patch copy:
  /usr/local/share/luminos/nvdefer/nvsleep-$VER.patch (root-owned, like nvdefer). Hook unchanged.
- Budgets: patch ≤ 120 added lines; any new C function ≤ 40 lines; nesting ≤ 3. Script total ≤ 200 lines.
- Must compile: `make -C patches/nvsleep/work modules` (or the nvdefer build.log recipe) with zero new warnings.

## B. Lid supervisor v3 (owner: W3 implementer) — scripts/luminos-lid (deployed to /usr/local/bin/luminos-lid)
- Python 3 stdlib only, runs as root under the existing luminos-lid.service (unit unchanged unless needed).
- Pure core, importable without side effects (`if __name__ == "__main__": main()`):
    BACKOFF = (2.0, 5.0, 10.0, 30.0); GRACE = 5.0
    @dataclass(frozen=True) class State: closed_since: float|None=None; attempts: int=0; last_try: float|None=None
    class Action(Enum): NONE, LOCK_AND_SLEEP, SLEEP
    def decide(now: float, lid_closed: bool, resumed_at: float|None, st: State) -> tuple[Action, State]
  Rules: lid open → (NONE, State()). Lid closed and now - resumed_at < GRACE → (NONE, st). Lid closed, no attempt yet
  this closure → (LOCK_AND_SLEEP, attempts=1, last_try=now, closed_since=now). Otherwise if now - last_try >=
  BACKOFF[min(attempts-1, 3)] → (SLEEP, attempts+1, last_try=now) else (NONE, st). Times are CLOCK_BOOTTIME seconds.
- I/O shell: lid state by EVIOCGSW ioctl on the 'Lid Switch' evdev node (found by name, as today) — level, not edge.
  Loop: select() on the node with 1 s timeout, drain events, read state, detect resume (BOOTTIME−MONOTONIC grew by
  > 2 s ⇒ resumed_at = now), call decide, act. LOCK_AND_SLEEP = `loginctl lock-sessions` then sleep. SLEEP =
  `systemctl suspend -i` (returns once logind queues it — Re-plan 2 stats wait is what makes it safe). Absolute paths for binaries. One log line per action with reason
  and attempt number. Never exits on a failed suspend.
- Budgets: ≤ 150 lines file; functions ≤ 40 lines; nesting ≤ 3.

## C. SD reader sleep hook (owner: W3) — config/system-sleep/luminos-sdreader → /usr/lib/systemd/system-sleep/
- sh. `pre`: if /sys/bus/platform/drivers/rtsx_pci_sdmmc/rtsx_pci_sdmmc.0 exists → write rtsx_pci_sdmmc.0 to unbind,
  record in /run/luminos/sdreader-unbound. `post`: if the record exists → bind, remove record. Any error → log, exit 0
  (never block sleep). ≤ 30 lines.

## D. Wake policy (owner: W3) — scripts/luminos-wake-policy + config/udev/71-luminos-wake.rules + systemd/luminos-wake-policy.service
- Only lid (PNP0C0D) and power button (PNP0C0C) may wake. Disable power/wakeup on: PCI bridges 0000:00:01.1 (dGPU),
  0000:00:02.2 (Wi-Fi), 0000:00:03.1 (USB4 tunnel); 0000:65:00.5 (audio coprocessor); 0000:67:00.5 (USB4 NHI); the
  AC adapter (ACPI0003 / ACAD power_supply device); every USB device whose idVendor != 0b05. Keep xHCI controllers
  and internal 0b05 keyboard as-is.
- `--apply` (writes, idempotent), `--check` (exit 0 only if every target reads disabled and lid+power button read
  enabled; prints a table), `--revert` (sets the original values saved at first apply in /var/lib/luminos/wake-policy.orig).
- udev rule: USB device add with idVendor != 0b05 → power/wakeup=disabled. Service: oneshot `--apply` at boot after
  udev settle. Budgets: script ≤ 120 lines.

## E. Installer (owner: W3) — scripts/luminos-strong-sleep --install | --check | --revert
- Copies B/C/D into place (backup of the old /usr/local/bin/luminos-lid to /usr/local/bin/luminos-lid.pre-v3),
  daemon-reload, restarts luminos-lid, enables+starts luminos-wake-policy, udevadm reload. ≤ 80 lines.
  It does NOT touch the NVIDIA patch (that is luminos-nvidia-defer --install, run by the PM).

## Tests (owners: W2 = nvsleep tests, W4 = B–E tests). Testers never edit sources; implementers never edit tests/.
- tests/nvsleep/static.sh: patch applies -F0 on top of nvdefer to a pristine copy; budgets; markers; params
  declared 0644/0444; flags guarded by #if defined; compiles (exit 0). tests/nvsleep/live.sh (run by PM after reboot):
  test sleep 30 s via RTC with ftrace rpm events → zero rpm_resume 0000:01:00.0 between PM_SUSPEND_PREPARE and
  thaw; notifier < 200 ms; S0i3 residency > 80 %; after resume card returns to D3cold ≤ 60 s; `dgpu-exec-v2 nvidia-smi`
  works; second run with the card held busy (`dgpu-exec-v2 nvidia-smi -l 1` in background) still suspends (or aborts
  cleanly + retry) and the card works after; `nv_sleep_skipped` incremented only in the idle run.
- tests/sleep/test_lid.py (pytest + hypothesis, venv ~/.local/share/luminos/coder-venv): properties of decide().
- tests/sleep/static.sh: syntax (bash -n, sh -n, py_compile), udevadm verify on the rule, budgets, installer --check
  exit codes. tests/sleep/live.sh (PM): wake-policy --check, sdreader hook pre/post round trip (driver re-bound).

## Re-plan 1 (2026-11-06 17:05, after W1 REJECTED)
- W1 found a third wake path: 0000:01:00.1 (HDMI audio, snd_hda_intel) is a runtime-PM CONSUMER of 0000:01:00.0
  (/sys/class/devlink/pci:0000:01:00.0--pci:0000:01:00.1, runtime_pm=1). snd_hda_intel has no SMART_SUSPEND, so the
  PCI core runtime-resumes the audio function in pci_pm_suspend → rpm_get_suppliers → wakes the card (trace lines
  131-149). With contract A as written every idle sleep would abort.
- Change: in the SKIPPED path only, the nvsleep patch may mark the sibling function(s) of the NVIDIA device (same bus/
  slot, other function numbers, found via pci_get_slot / pci_get_domain_bus_and_slot) with
  dev_pm_syscore_device(dev, true) IF that function is pm_runtime_suspended at PREPARE time, and MUST clear it
  (dev_pm_syscore_device(dev, false)) at PM_POST_SUSPEND (which the PM core also delivers after an aborted suspend).
  Reference counts from pci_get_* must be dropped (pci_dev_put). If a sibling is NOT runtime-suspended → do not skip
  (stock path). The race (sibling or card wakes after PREPARE) must still end in a clean -EBUSY abort.
- Patch budget raised to 150 added lines. Files allowed unchanged (nv.c, nv-pci.c).
- Tests (W2) add: after resume 0000:01:00.1 power/runtime_status returns to suspended, `aplay -l` still lists the
  NVIDIA HDMI card, no syscore flag left set (best effort: a second test sleep with nv_sleep_skip_idle=0 behaves stock).
- Workers now run with cwd /home/shawn/luminos-os (the first round was confined to docs/sleep and could not write).

## Re-plan 2 (2026-11-06 17:20, after W3's report) — section B only
- decide(): when resumed_at is not None and last_try is not None and resumed_at > last_try → a sleep actually happened:
  treat as attempts=1 (backoff restarts at 2 s) after the GRACE window. Lid open still resets everything.
- I/O shell: after issuing a sleep, WAIT until /sys/power/suspend_stats/success or /fail changes, or 60 s pass, before
  the next decide() may act (a pending attempt is never doubled up while the system is still entering sleep).
- At service start treat resumed_at = now (so boot / restart with the lid shut waits GRACE before sleeping).
- File budget for scripts/luminos-lid raised to 170 lines.

## Re-plan 3 (after review2) — B–E fixes
- C: hook `pre` does nothing if a card is present (any mmc_host/*/mmc*:* child) — never eject a mounted card; record
  is written BEFORE unbind and removed if unbind fails.
- D: root hubs (idVendor 1d6b) are NOT targets (keep as-is, like xHCI) — internal keyboard keeps manual-sleep wake.
  BAT0 stays untouched (verify with a charger test later).
- E: installer verifies luminos-lid is still active 2 s after restart, else exit 1.
- B: run() returns success; give_up armed only when systemctl accepted; lid open clears give_up/stats wait.
  Wording: `systemctl suspend -i` returns once logind queues the request (not blocking) — the stats wait is required.

## Re-plan 4 (after review1, Fable) — supersedes D's PCI list and A's test threshold
- D: do NOT touch any PCIe bridge (0000:00:01.1, 0000:00:02.2, 0000:00:03.1). Changing a runtime-suspended bridge's
  power/wakeup makes acpi_pci_need_resume() true → PCI core runtime-resumes the port at dpm_suspend → wakes the dGPU
  (00:01.1) → every nvsleep attempt aborts. Remaining D targets: 0000:65:00.5, 0000:67:00.5, ACAD, non-0b05/non-1d6b USB.
- A patch: in the STOCK branch of nv_pmops_suspend_late set dev->power.may_skip_resume = false (as pci-driver.c:971 does)
  so MAY_SKIP_RESUME can never leave an RM-active GPU marked runtime-suspended. Script: when nvsleep fails after a clean
  dry-run, still dkms_rebuild + initramfs for the nvdefer-only source before exit 1.
- A tests: rpm_resume events with dep-1 (disable_depth>0, returns -EACCES, nothing resumes) are NOT counted; the count
  is of real resumes (dep-0) of 0000:01:00.0. Document that the port 00:01.1 noirq resume still re-powers the slot
  (0.6 s, kernel-side, not fixable in nvidia) — resume gain = skipped RM resume only.

## Re-plan 6 (2026-11-06 21:30) — section F: brightness across sleep (owner W3, tests W4)
- Replace /etc/systemd/system/luminos-brightness.service (2026-05-08, undocumented: forces amdgpu_bl2=399000 = 100 %
  and writes nvidia_0 after EVERY wake → wakes the dGPU, EINVAL) with config/system-sleep/luminos-brightness (sh,
  /usr/lib/systemd/system-sleep/). `pre`: for each /sys/class/backlight/* whose device is NOT driven by nvidia
  (readlink device/driver ≠ …/nvidia; in practice amdgpu_bl2), save `brightness` to /run/luminos/brightness-<name>.
  `post`: if the saved value exists and differs from the current one, write it back; remove the record. Never read or
  write any nvidia backlight (reading actual_brightness also goes to RM). Errors → log, exit 0. ≤ 40 lines.
- Installer (scripts/luminos-strong-sleep): installs the hook; `systemctl disable` luminos-brightness.service and
  moves its unit file to /etc/systemd/system/luminos-brightness.service.disabled-by-strong-sleep; --revert restores it.
  Installer budget raised to 95 lines.
- Tests (W4): static (sh -n, budget, never mentions nvidia_ except in an exclusion, exit 0 on unknown args, fake-sysfs
  run of pre/post via env override BACKLIGHT_ROOT if the hook supports it); live.sh: run pre, change brightness, run
  post → value restored; luminos-brightness.service not enabled.

## Re-plan 7 (2026-11-06 23:25) — section C: SD reader re-bind deferred
- Live run 20261106-231031 idle2: `pre` unbind blocked 7.3 s because the reader, re-bound at the previous `post`, was
  still in its "mmc0: Card stuck being busy / error -110" re-init loop (3 × ~2.4 s, no card present).
- Change: `post` does NOT re-bind immediately; it schedules the bind 60 s later in the background
  (`systemd-run --on-active=60 --unit=luminos-sdreader-rebind …` or equivalent, transient, idempotent). `pre`: if the
  reader is already unbound (still within the 60 s, record present) → cancel the pending re-bind and do nothing
  (fast). Card-present guard unchanged. Never blocks sleep; errors → log, exit 0. Budget ≤ 40 lines.

## Re-plan 8 (2026-11-07 00:05) — BUG-199 lock-screen black wallpaper
Evidence (journal 23:53:12): luminos-lid `loginctl lock-sessions` at .262 → its own `systemctl suspend` → logind
PrepareForSleep at .320 (58 ms later) → KWin sends the greeter SIGUSR1 (end grace time, greeter started with
--graceTime 5000) before the greeter has installed its handler → default action kills it (crash log: "killed by signal
SIGUSR1") → KWin restarts the greeter inside the suspend transition → its QtWebEngine GPU init fails ("GPUInfo not
initialized", WebGL VENDOR 0xffff) → three.js wallpaper draws nothing → BLACK until the greeter restarts. Every boot
since 10-14 shows exactly one such crash + one WebGL failure.
### G (owner W3, tests W4) — scripts/luminos-lid: lock, WAIT for the lock, then sleep
- LOCK_AND_SLEEP: `loginctl lock-sessions`, then poll every 100 ms until every session with Type wayland or x11 and
  Class user reports LockedHint=yes (`loginctl show-session <id> -p LockedHint --value`), then wait a further 1.0 s
  settle (greeter finishes start-up and installs its signal handlers), then suspend. Timeout 5 s total → suspend anyway
  (sleep must never be lost; log "lock not confirmed"). If the lid opens during the wait → abort the sleep (decide()
  already resets on open; the wait loop must re-read the lid). SLEEP (retries) unchanged (already locked).
- Pure-core change only if needed; the wait is I/O shell. Budget: luminos-lid ≤ 190 lines.
### H (owner W5, tests W4) — wallpaper never black when WebGL fails
- src/wallpapers/org.luminos.livewallpaper/contents/ui/WebMode.qml (repo copy is canonical; deploy copy
  ~/.local/share/plasma/wallpapers/org.luminos.livewallpaper/ — check how it is installed, e.g. a script under
  scripts/ or kpackagetool6, and use that): on javaScriptConsoleMessage containing "WebGL context could not be
  created" OR "Error creating WebGL context", OR on renderProcessTerminated → show a still poster on top of the web
  view (hide the web view). Poster = `poster.png` next to the page's html if it exists, else the Lively "Thumbnail"
  (LivelyInfo.json) scaled with PreserveAspectCrop, else nothing (bgColor as today). Log once.
- New scripts/luminos-wallpaper-poster <wallpaper-dir> [WxH, default 2880x1800]: renders the page with headless
  Chromium (whatever exists on the box: chromium/google-chrome --headless --screenshot, or node playwright if
  installed — check, do not install anything system-wide) after ~6 s of animation, writes poster.png beside the html.
  Run it for ~/.local/share/luminos/wallpapers/medusae. ≤ 80 lines.
- The lock screen uses the same plugin (kscreenlockerrc Greeter WallpaperPlugin=org.luminos.livewallpaper); DECISION 127
  keys stay as they are.

## Re-plan 9 (2026-11-07 00:20) — supersedes G's lock step
Evidence: on every lid close PowerDevil ALSO requests suspend in the same millisecond (19:37:33 and 23:53:12 journals:
luminos-lid's and org_kde_powerde's requests both at .xx of the same second). Delaying only luminos-lid's suspend
cannot stop PrepareForSleep arriving at once. KWin's own lock-on-sleep (kscreenlockerrc LockOnResume=true) holds a
delay inhibitor and starts the greeter with NO grace time → race-free. The greeter that dies is the one luminos-lid's
`loginctl lock-sessions` started a few ms earlier with --graceTime 5000.
G': LOCK_AND_SLEEP — for every graphical user session (Type wayland|x11, Class user): if its Desktop
(`loginctl show-session <id> -p Desktop --value`) is "KDE", do NOT lock it (KWin locks before sleep itself). If any
graphical session is NOT KDE (e.g. Hyprland): `loginctl lock-session <id>` for those only, then the G wait (LockedHint
on those sessions, +1.0 s settle, 5 s cap). If there is no non-KDE graphical session: suspend at once. Retries
unchanged. Never read files in the user's home. Budget ≤ 190 lines.
G'' (Re-plan 9 addendum, security guard): after every detected resume, 2 s after it (lid open or closed), read
LockedHint of every KDE graphical user session; any that reads "no" → `loginctl lock-session <id>` + log
"WARNING: KDE session <id> was NOT locked after wake — locked it now; check kscreenlockerrc LockOnResume". Budget for
scripts/luminos-lid raised to 205 lines.
