/build  luminos-focus — only what I'm looking at gets compute.

Read first, fully: AGENTS.md, HANDOFF.md, docs/focus/DESIGN.md (measurements, design, done-means, order), and
docs/sleep/BUILD_LOG.md for how the last build was run (spec → contracts → checker → parallel Opus workers → independent
Fable review against real source → live A/B). Follow AGENTS.md strictly (Response N, HANDOFF, doc triggers, §9 for any
/etc change, MemPalace wing luminos_os).

Goal: at system level, the app on screen gets the CPU/GPU; everything hidden or idle drops to the minimum, except apps
playing audio/video or doing work I asked for. One continuous dial, no modes. Prove every step with measured A/B
numbers. Build in the order in DESIGN.md: (1) measure the minimize/suspended path for Chrome + Claude, (2) wallpaper
follows the focus truth + 30 fps cap, (3) per-app cgroup CPU limits with exceptions, (4) only then a small KWin patch
so fully covered windows get `suspended`. Ask me before installing the KWin patch or anything needing a reboot.
