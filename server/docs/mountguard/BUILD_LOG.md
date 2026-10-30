# BUILD_LOG — mountguard (2026-10-10)
- Spec written by PM (SPEC.md); implementer = claude-fable-5-1 high via bm.py, tools Read + Bash(ssh:*) only.
- Run 1 killed at 14:08 by the PM's own host-shell timeout (worker was a child of that shell). Server untouched.
  Fix: relaunch with `setsid nohup ... & disown`, `--resume 69f85b74-...` (kept its context).
- Run 2 finished 14:16: fstab +x-systemd.automount, chattr +i on bare /srv/external via bind mount of /,
  NZBGet RequiredDir=/srv/external/usenet, nzbget restarted while idle. One justified deviation: had to stop
  srv-external.mount once before starting the automount ("already a mount point").
- PM re-verified C1–C5 independently (exit codes/output), incl. live "disk gone" simulation: nzbget write
  → Operation not permitted, 0 entries on bare dir; automount reconnects /dev/sdb1 on access.
- Separate reviewer (step 8) skipped: no code, 2 config lines + 1 attribute, every property checked mechanically.
- Worker's first run put the NZBGet API password on an ssh command line (LAN-only, already in nzbget.conf);
  run 2 read it server-side. Noted, not rotated.
