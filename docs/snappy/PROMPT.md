/build  Find out why Luminos felt faster/snappier after the 2026-11-06 test sleeps, and make that state permanent.

Read first: AGENTS.md, HANDOFF.md, docs/sleep/SESSION-2026-11-05-06.md (everything that was touched — all reverted —
and the "New lead" section), docs/focus/BUILD_LOG.md last entry (idle 11-12 W, VDDNB 835 mV vs 8-9 W / 714 mV on 11-05).
Follow AGENTS.md strictly (Response N, HANDOFF, doc triggers, §9, MemPalace wing luminos_os).

Method — measure, don't guess (Shawn's rule: prove, don't assert):
1. Baseline now: 10 min idle (RAPL package W, amdgpu_pm_info SoC W / VDDNB / MCLK / SCLK / GPU load, Tctl, fans, per-process
   CPU with a correct LC_ALL=C sort, interrupt + wakeup rates, psr_state, kwin supportInformation, compositor fps).
2. One 30 s RTC test sleep (/var/tmp/sleeptest/run.sh 30 — the nvsleep v2.1 + strong-sleep stack is live and safe).
3. Same 10 min idle again. Diff every number. Repeat on another day to see if it drifts back up with uptime.
4. If a resume resets something: find exactly which knob (DPM level, fabric clock, a driver state, an app leak, kwin) and
   fix the cause so the good state holds without sleeping — never "suspend periodically" as the fix.
Do not change anything before step 3 has numbers.
