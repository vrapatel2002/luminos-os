# BUILD_LOG — strong sleep
- 2026-11-06 16:40 Spec + contracts written from measurements (stack trace /var/tmp/sleeptest/stack-162739.txt,
  wakeup_sources mmc0=3, ACAD=2). Budgets in CONTRACTS.md. Plan: 4 workers in parallel (W1 nvsleep patch Opus, W2 its
  tests Opus, W3 lid/hook/wake-policy Opus, W4 their tests Opus), then Fable review, then PM installs non-reboot parts,
  live-tests them, asks Shawn for the one reboot for the NVIDIA module.
- 17:05 Round 1: W1 REJECTED (correct: HDMI-audio device link = third wake path) and all 4 workers were confined to docs/sleep by the monitor's cwd → nothing written. Re-plan 1 in CONTRACTS.md; respawning all 4 from the repo root, same models.
- 17:20 W3 done (B–E written, static OK, nothing run as root). Re-plan 2: wait on suspend_stats before retry; reset backoff after a real sleep; start = resume. Sent back to W3 (resume); W4 told to cover it.
- 17:30 PM edit (one word): luminos-lid start banner now 'v3 watching …' so live.sh can tell v3 from v2.
- 17:50 nvsleep static ALL PASS incl. compile (0 new warnings). tests/sleep/static.sh all pass (30 pytest). Fable review1 (patch, with real v7.0 PM source in docs/sleep/ksrc) + review2 (lid/wake/sd/installer) running.
- review2 (Fable): 1 HIGH (sdreader ejects inserted card), 2 MEDIUM (root hubs disabled → kbd wake lost; installer no liveness check), 7 LOW. Re-plan 3; fixes to W3, test updates to W4.
- review1 (Fable, against real v7.0 source): patch sound (stock/hibernate/race/locks confirmed). BLOCKING was in D (bridge wakeup change re-wakes dGPU) → Re-plan 4. HIGH test threshold (dep-1 events). MEDIUM may_skip_resume guard. Sent to W1, W2; W3 after its round 4.
- PM one-word fix (W4 finding): sdreader ': >' → 'true >' (special builtin redirect failure killed the hook).
- B–E installed (`luminos-strong-sleep --install`), tests/sleep/live.sh ALL PASS. Real RTC test sleep: first attempt
  succeeded, sdreader unbound/rebound, lid v3 saw the resume and (lid open) did nothing. S0i3 23.7/30 s (entry still
  slow: NVIDIA module not yet loaded).
- nvsleep installed via `luminos-nvidia-defer --install`: dkms build+sign OK, mkinitcpio OK, --check: source has both
  patches, initramfs nvidia.ko == dkms module, modinfo shows nv_sleep_skip_idle + nv_sleep_skipped. Needs ONE reboot.
  Backup /boot/initramfs-linux.img.pre-nvsleep. NEXT: reboot → `sudo bash tests/nvsleep/live.sh` (detached).
- 17:47 POST-REBOOT live test, idle run: nv_pm_notifier 2352 ms → 0.041 ms, entry 1.7 s, S0i3 88 %, skipped +1. BUT
  after resume the card was left in D0/active and BROKEN ("Unable to determine the device handle … Unknown Error",
  NVRM status 0x11 on every ACPI event) → needs a reboot to recover. Cause (trace /var/tmp/nvsleep-live/20261106-174705/):
  the port 00:01.1 noirq resume re-powers the slot (722 ms) and pci_resume_bus queues runtime resumes of its children;
  the audio function (syscore, runtime PM still ENABLED) resumed from a kworker at dpm_complete → rpm_get_suppliers →
  RM runtime resume on a card whose slot the kernel had power-cycled behind RM's back. Second waker found:
  luminos-brightness.service (undocumented, /etc) writes nvidia_0 brightness after every wake → wakes the dGPU, fails
  (EINVAL), and also forces amdgpu_bl2 to 399000 = 100 % brightness on every wake.
- Mitigation now: nv_sleep_skip_idle=0 at runtime + /etc/modprobe.d/luminos-nvsleep-off.conf + mkinitcpio -P (stock
  path on next boot). Test killed before the busy/control runs. NOTE: pkill -f with a pattern from my own command line
  killed my shell — use PIDs.
- Re-plan candidate 5: skip path must also leave the PARENT PORT 00:01.1 untouched (syscore + runtime disabled for the
  whole subtree: port, card, audio) so the slot is never re-powered behind RM; disable runtime PM on the audio function
  for the window. Needs a new review round before any install.
- Re-plan 5 = nvsleep v2 design (docs/sleep/DESIGN-NVSLEEP-V2.md): whole dGPU subtree (port 00:01.1 + all descendants) syscore during skipped s2idle; v1 pmops/flags removed; race guard via pm_system_wakeup; brightness unit → save/restore hook. Design review (Fable xhigh) BEFORE implementation.
- 18:36 design review (Fable xhigh) stopped: Claude 5-hour usage limit on the laptop CLI, resets 21:20. Session kept for --resume.
- 21:30 limit reset; Shawn rebooted ~19:10 (dGPU back, suspended, nvsleep param 0). review3 resumed. Re-plan 6 (brightness hook) → W3 + W4 in parallel.
- review3 (design, Fable xhigh): mechanism right; 2 BLOCKING (target-state check can't work in notifier; ACPI notifies → RM on a runtime-PM-disabled card = dead GPU, e.g. charger plug during sleep), 2 MEDIUM. Folded as v2.1 into DESIGN-NVSLEEP-V2.md. Next: W1 fresh rewrite on Fable xhigh (hardest module), W2 tests.
- PM one-line fix (W4 finding): brightness restore() skips nvidia-driven records.
- 21:45 v2.1 written (W1v2 Fable xhigh): 187 added lines, nv.c+nv-acpi.c, static+compile ALL PASS (PM re-ran). W2 live.sh rewritten with safety interlock. Brightness hook installed + live PASS (old unit disabled). Code review4 (Fable high) running.
- review4 (code, Fable high): VERDICT safe to install; 2 MEDIUM (procfs resume double-unlock; nv_indicate_not_idle relies on RM), 6 LOW → back to W1v2.
- 22:07 v2.1 installed (v1 source restored by hand from its .nvsleep-orig copies, then --apply). --check OK, initramfs matches, off-switch in initramfs. AGENTS §9 + DECISION 173 amendment + HANDOFF updated. Waiting for Shawn's reboot.
- 23:10-23:16 LIVE v2.1 (/var/tmp/nvsleep-live/20261106-231031): card WORKED after all 5 sleeps (nvidia-smi rc 0,
  log clean, back to D3cold), interlock never tripped. Idle x3: zero dep-0 wakes of port/card/audio, no port noirq
  resume, card D3cold after, notifier 0.05-0.08 ms (was 2352 ms), skipped +1 each. Entry 1.8-1.9 s vs stock 4.2 s
  (control run); resume 0.83 s vs stock 1.23 s. Busy + control runs correct (stock path, card fine).
  Non-safety FAILs explained: aplay not installed (HDMI card present in /proc/asound/cards); LNXPOWER:00 on right
  after resume = wireplumber opening the HDMI PCM (azx_pcm_open → audio → port runtime resume, normal path, card stayed
  off); idle2 entry 8.3 s / S0i3 67 % = sdreader unbind waiting for the reader's own 7 s "stuck busy" re-init loop.
- Made permanent: /etc/modprobe.d/luminos-nvsleep-off.conf removed (copy in /var/tmp), mkinitcpio -P. Re-plan 7
  (sdreader deferred re-bind) → W3/W4.
