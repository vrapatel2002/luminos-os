/* dgpu-exec-v2 — setgid(dgpu) launcher that grants dGPU device access, and MAKES IT STICK.
 * [CHANGE: claude-code | 2026-08-05] BUG-102 follow-up. Successor to dgpu-exec.c.
 *
 * WHY THIS EXISTS — the v1 gate was defeated by any launcher written in shell.
 * ---------------------------------------------------------------------------
 * v1 relies purely on the setgid bit, which raises only the EFFECTIVE gid and leaves
 * the REAL gid at the caller's (shawn, 1000). That looked fine in the one test anyone
 * ever ran (`dgpu-exec nvidia-smi` — a direct ELF exec) but it silently fails for the
 * common case, because a raised-egid-only process is "privileged" in three ways that
 * bite:
 *
 *   1. bash/sh RESET egid -> rgid at startup as setuid/setgid protection, unless
 *      invoked with `-p`. Chrome is launched through TWO bash wrappers
 *      (/usr/bin/google-chrome-stable -> /opt/google/chrome/google-chrome -> chrome),
 *      so the dgpu group was dropped at the very first link and the browser that
 *      finally started had no access at all. This affects EVERY app whose launcher is
 *      a shell script, not just Chrome.
 *
 *   2. access(2) — which the shell tests `[ -r ]` / `[ -w ]` call — consults the REAL
 *      gid. So any permission check written the obvious way reports DENIED even when
 *      the device opens fine. A check that consults the wrong identity is worse than
 *      no check.
 *
 *   3. The kernel sets AT_SECURE=1 on a setgid exec. Chrome's setuid-root helper
 *      /opt/google/chrome/chrome-sandbox reacts to that privileged state by refusing
 *      to start: "Running as root without --no-sandbox is not supported."
 *
 * THE FIX — setresgid(g, g, g) makes the dgpu gid REAL as well as effective, before
 * exec. Real == effective means the process is no longer privileged, so all three
 * problems disappear at once: bash keeps the group, access(2) tells the truth, and
 * AT_SECURE is not set so chrome-sandbox is happy.
 *
 * Verified 2026-08-05, side by side:
 *     v1: rgid 1000 egid 948   | via bash: DENIED | direct ELF: chrome-sandbox refuses
 *     v2: rgid  948 egid 948   | via bash: OPEN   | direct ELF: starts normally
 *     no gate:                   DENIED  <- the gate itself is still intact
 * And end to end: Chrome's GPU process held /dev/nvidia0 (20 fds), /dev/nvidiactl and
 * /dev/nvidia-modeset, loaded libnvidia-glcore + libGLX_nvidia with ZERO Mesa/radeon
 * libs, and the card's own process table (nvidia-smi) listed it.
 *
 * SECURITY NOTE — this does not widen the gate. An app still has to be launched
 * through this binary to get anything; apps that are not stay denied by the 0660
 * root:dgpu device nodes. The only change is that the grant now survives the exec
 * chain instead of evaporating at the first shell. If anything the posture improves,
 * because v1's failure mode was SILENT: it announced NVIDIA and delivered the iGPU.
 *
 * SCOPE — installed alongside v1 as `dgpu-exec-v2`, wired into `chrome-luminos` only.
 * `dgpu-exec` (v1) is still what `luminos-gpu-launch` and everything else calls. Once
 * the other gated apps have been re-verified against v2, this should replace v1
 * outright and the -v2 name should go away.
 *
 * Build/install (also done by install-dgpu-gate.sh):
 *     cc -O2 -Wall -o dgpu-exec-v2 dgpu-exec-v2.c
 *     sudo install -o root -g dgpu -m 2755 dgpu-exec-v2 /usr/local/bin/dgpu-exec-v2
 * NOTE: the setgid bit is ignored on nosuid mounts — /tmp is nosuid on this box, so
 * a binary built and left in /tmp reports egid=1000 and looks broken. Build elsewhere.
 */
#define _GNU_SOURCE
#include <unistd.h>
#include <sys/types.h>
#include <stdio.h>
#include <string.h>
#include <errno.h>

int main(int argc, char **argv) {
    if (argc < 2) {
        fprintf(stderr, "usage: dgpu-exec-v2 <command> [args...]\n");
        return 2;
    }

    /* egid is dgpu, courtesy of the setgid bit. Make it real too, so the grant
     * survives shell wrappers and does not mark us AT_SECURE. See header. */
    gid_t g = getegid();
    if (setresgid(g, g, g) != 0) {
        fprintf(stderr, "dgpu-exec-v2: setresgid(%d) failed: %s\n",
                (int)g, strerror(errno));
        return 126;
    }

    execvp(argv[1], &argv[1]);
    fprintf(stderr, "dgpu-exec-v2: cannot exec %s: %s\n", argv[1], strerror(errno));
    return 127;
}
