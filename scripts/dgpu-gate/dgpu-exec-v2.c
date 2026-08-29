/* dgpu-exec-v2 — setgid(dgpu) launcher that grants dGPU device access, and MAKES IT STICK.
 * [CHANGE: claude-code | 2026-08-05] BUG-102 follow-up. Successor to dgpu-exec.c.
 * [CHANGE: claude-code | 2026-08-28] BUG-145 — also hand the target the NVIDIA vendor
 *          environment, because v2 stopped inheriting it by accident. See part two below.
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
 *
 * PART TWO — BUG-145: fixing AT_SECURE broke NVIDIA, and that is not a contradiction.
 * ----------------------------------------------------------------------------------
 * /etc/environment pins every process on this box to the Mesa EGL vendor:
 *     __EGL_VENDOR_LIBRARY_FILENAMES=/usr/share/glvnd/egl_vendor.d/50_mesa.json
 * That pin is the BUG-046c / BUG-050 fix: it stops NVIDIA claiming EGL for the whole
 * desktop and holding the dGPU awake on a laptop whose panel is wired to the 780M.
 *
 * libglvnd reads that variable with secure_getenv(3), which returns NULL when
 * AT_SECURE is set. So:
 *     v1  -> AT_SECURE=1 -> the Mesa pin is IGNORED -> libglvnd scans the directory,
 *            finds 60_nvidia.json, and NVIDIA works.
 *     v2  -> AT_SECURE=0 -> the Mesa pin is OBEYED  -> only the Mesa vendor loads.
 *
 * NVIDIA's Vulkan ICD lives inside libGLX_nvidia.so.0, a glvnd-managed library. With
 * only the Mesa vendor loaded it cannot initialise, so vk_icdGetInstanceProcAddr
 * returns NULL, the loader discards nvidia_icd.json, and you get:
 *     loader_scanned_icd_add: Could not get 'vkCreateInstance' ... for ICD libGLX_nvidia.so.0
 *     vkCreateInstance: Found no drivers!  /  ERROR_INCOMPATIBLE_DRIVER
 * Measured through the probe in tmp-probe/, 2026-08-28:
 *     no gate: AT_SECURE=0 gid=1000/1000/1000 -> AMD only
 *     v1:      AT_SECURE=1 gid=1000/948/948   -> AMD + RTX 4050
 *     v2:      AT_SECURE=0 gid= 948/948/948   -> AMD only, NVIDIA ICD discarded
 * The env var is present in the target's environ in ALL THREE cases — the kernel does
 * not strip it. It is libglvnd's secure_getenv that ignores it. That is the whole bug.
 *
 * So v1 never "supported NVIDIA properly". It worked by being privileged enough that
 * the system's own graphics policy did not apply to it. That is an accident, and a bad
 * one: the same accident is what made v1 silently deliver the iGPU to shell-launched
 * apps. DO NOT "FIX" THIS BY REVERTING TO V1.
 *
 * The right fix is for the gate to say out loud what it was previously getting by
 * accident: this binary exists to run things on the dGPU, so it sets the NVIDIA vendor
 * environment itself, after the credential change. A value that already names nvidia is
 * left alone (so a caller can pick a different vendor JSON, and re-entry is idempotent);
 * a value naming Mesa, or no value at all, is replaced. `--keep-env` opts out entirely.
 *
 * If the NVIDIA vendor JSON is missing — the window after an nvidia-utils upgrade and
 * before the nvidia-egl-priority.hook renames 10_nvidia.json to 60_nvidia.json — we
 * UNSET the variable rather than point it at a file that is not there. Unset means
 * libglvnd scans the directory, which is the safe behaviour; a dangling path means no
 * EGL at all.
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
#include <sys/stat.h>
#include <fcntl.h>
#include <dirent.h>
#include <grp.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <errno.h>
#include <sys/auxv.h>

/* Candidates in preference order; first one that exists wins. 60_ is where our pacman
 * hook parks it, 10_ is where nvidia-utils drops it before the hook has run. */
static const char *const EGL_NVIDIA_JSON[] = {
    "/usr/share/glvnd/egl_vendor.d/60_nvidia.json",
    "/usr/share/glvnd/egl_vendor.d/10_nvidia.json",
    NULL
};
static const char *const VK_NVIDIA_ICD = "/usr/share/vulkan/icd.d/nvidia_icd.json";

/* Replace `name` with `want` unless it is already set to something naming nvidia.
 * Leaving an existing nvidia-ish value alone keeps the call idempotent and lets a
 * caller choose a different vendor JSON on purpose. */
static void force_nvidia_var(const char *name, const char *want) {
    const char *cur = getenv(name);
    if (cur && *cur && strstr(cur, "nvidia")) return;   /* caller already chose NVIDIA */
    setenv(name, want, 1);
}

static const char *find_egl_nvidia_json(void) {
    for (int i = 0; EGL_NVIDIA_JSON[i]; i++)
        if (access(EGL_NVIDIA_JSON[i], R_OK) == 0) return EGL_NVIDIA_JSON[i];
    return NULL;
}

static void apply_nvidia_env(void) {
    const char *egl = find_egl_nvidia_json();
    if (egl) {
        force_nvidia_var("__EGL_VENDOR_LIBRARY_FILENAMES", egl);
    } else {
        /* No NVIDIA vendor JSON on disk. Unsetting restores libglvnd's directory scan;
         * pointing at a missing file would kill EGL outright. */
        const char *cur = getenv("__EGL_VENDOR_LIBRARY_FILENAMES");
        if (cur && *cur && !strstr(cur, "nvidia")) {
            unsetenv("__EGL_VENDOR_LIBRARY_FILENAMES");
            fprintf(stderr, "dgpu-exec-v2: warning: no NVIDIA EGL vendor JSON found; "
                            "cleared the Mesa pin and left libglvnd to scan.\n");
        }
    }

    /* Vulkan. VK_DRIVER_FILES is the current name and overrides the legacy one, so if
     * it is set to something non-NVIDIA it has to be corrected too or it wins. */
    if (access(VK_NVIDIA_ICD, R_OK) == 0) {
        force_nvidia_var("VK_ICD_FILENAMES", VK_NVIDIA_ICD);
        if (getenv("VK_DRIVER_FILES")) force_nvidia_var("VK_DRIVER_FILES", VK_NVIDIA_ICD);
    }

    /* GLX + PRIME offload. Harmless for CUDA-only callers such as nvidia-smi. */
    force_nvidia_var("__GLX_VENDOR_LIBRARY_NAME", "nvidia");
    setenv("__NV_PRIME_RENDER_OFFLOAD", "1", 0);
}

/* ---- --check: say what the target would actually see, in plain words ------------
 * This exists because BUG-145 took two sessions to find, and every fact needed to
 * spot it in seconds is printed below. Run it AFTER the credential change so it
 * reports the target's view, not the caller's. */

static const char *runtime_power_state(char *buf, size_t n) {
    DIR *d = opendir("/sys/bus/pci/drivers/nvidia");
    if (!d) return NULL;
    struct dirent *e;
    const char *out = NULL;
    while ((e = readdir(d))) {
        if (strncmp(e->d_name, "0000:", 5) != 0) continue;
        char path[512];
        snprintf(path, sizeof path,
                 "/sys/bus/pci/drivers/nvidia/%s/power/runtime_status", e->d_name);
        FILE *f = fopen(path, "r");
        if (!f) continue;
        if (fgets(buf, (int)n, f)) { buf[strcspn(buf, "\n")] = 0; out = buf; }
        fclose(f);
        break;
    }
    closedir(d);
    return out;
}

static int check_mode(void) {
    int problems = 0;   /* things that stop the target reaching the dGPU */
    int leaks = 0;      /* things that let others reach it WITHOUT the gate */
    gid_t gr, ge, gs;
    getresgid(&gr, &ge, &gs);
    struct group *g = getgrgid(ge);

    printf("dgpu-exec-v2 --check\n\n");

    printf("identity\n");
    printf("  real/effective/saved gid : %d/%d/%d\n", (int)gr, (int)ge, (int)gs);
    printf("  effective group name     : %s\n", g ? g->gr_name : "(unknown)");
    /* Our OWN AT_SECURE is always 1 — we were exec'd setgid, that is the point. What
     * matters is the TARGET's, and the target inherits rgid==egid from the setresgid
     * above, so its exec is unprivileged and AT_SECURE will be 0. Report both; showing
     * only our own would be actively misleading. */
    printf("  AT_SECURE (this gate)    : %ld  (expected 1 — the setgid bit)\n",
           (long)getauxval(AT_SECURE));
    printf("  AT_SECURE (target, pred.): %d%s\n", gr == ge ? 0 : 1,
           gr == ge ? "  -> it WILL read __EGL_VENDOR_LIBRARY_FILENAMES"
                    : "  -> libglvnd will IGNORE __EGL_VENDOR_LIBRARY_FILENAMES");
    if (gr != ge) {
        printf("  !! real != effective — shells will drop the group (BUG-102)\n");
        problems++;
    }

    printf("\ndevice nodes\n");
    static const char *const nodes[] = { "/dev/nvidiactl", "/dev/nvidia0",
                                         "/dev/nvidia-modeset", "/dev/nvidia-uvm", NULL };
    int opened_any = 0;
    for (int i = 0; nodes[i]; i++) {
        struct stat st;
        if (stat(nodes[i], &st) != 0) { printf("  %-22s absent\n", nodes[i]); continue; }
        struct group *ng = getgrgid(st.st_gid);
        int fd = open(nodes[i], O_RDONLY);
        if (fd >= 0) { opened_any = 1; close(fd); }
        int world = (st.st_mode & 07) != 0;
        int wrong_group = !ng || strcmp(ng->gr_name, "dgpu") != 0;
        printf("  %-22s %04o %s  %s%s\n", nodes[i], st.st_mode & 07777,
               ng ? ng->gr_name : "?", fd >= 0 ? "OPEN" : "DENIED",
               (world || wrong_group) ? "   <- LEAK" : "");
        /* DECISION 25 is default-deny: every node must be root:dgpu 0660. A node that
         * is world-accessible or owned by another group is reachable WITHOUT the gate,
         * which silently defeats the whole policy. */
        if (world || wrong_group) leaks++;
    }
    if (!opened_any) { printf("  !! could not open any NVIDIA node\n"); problems++; }
    if (leaks) printf("  !! a node marked LEAK is reachable without this gate (DECISION 25)\n");

    printf("\nEGL vendor (libglvnd)\n");
    const char *ev = getenv("__EGL_VENDOR_LIBRARY_FILENAMES");
    printf("  __EGL_VENDOR_LIBRARY_FILENAMES = %s\n", ev && *ev ? ev : "(unset -> directory scan)");
    if (ev && *ev && !strstr(ev, "nvidia")) {
        printf("  !! pinned to a non-NVIDIA vendor. NVIDIA's Vulkan ICD lives in\n"
               "     libGLX_nvidia.so.0, so this ALSO kills Vulkan, not just EGL. (BUG-145)\n");
        problems++;
    }
    DIR *d = opendir("/usr/share/glvnd/egl_vendor.d");
    if (d) {
        struct dirent *e;
        printf("  available vendors        :");
        while ((e = readdir(d))) if (e->d_name[0] != '.') printf(" %s", e->d_name);
        printf("\n  (lower filename sorts FIRST and claims the display)\n");
        closedir(d);
    }

    printf("\nVulkan ICD\n");
    const char *vk = getenv("VK_DRIVER_FILES");
    const char *vk2 = getenv("VK_ICD_FILENAMES");
    printf("  VK_DRIVER_FILES   = %s\n", vk && *vk ? vk : "(unset)");
    printf("  VK_ICD_FILENAMES  = %s\n", vk2 && *vk2 ? vk2 : "(unset)");
    for (int i = 0; i < 2; i++) {
        const char *p = i ? vk2 : vk;
        if (p && *p && access(p, R_OK) != 0) {
            printf("  !! %s does not exist. This is an OVERRIDE, not a hint: a missing\n"
                   "     file yields \"Found no drivers!\", it does not fall back. (BUG-144)\n", p);
            problems++;
        }
    }

    printf("\npower\n");
    char pbuf[64];
    const char *ps = runtime_power_state(pbuf, sizeof pbuf);
    printf("  dGPU runtime_status      : %s\n", ps ? ps : "(unknown)");
    if (ps && strcmp(ps, "suspended") == 0)
        printf("  (suspended is CORRECT at idle — it wakes on device open)\n");

    /* Two independent questions, deliberately not merged: "can my app use the dGPU"
     * and "can apps that did NOT come through here use it". A leak does not cause an
     * iGPU fallback, so reporting them as one number would send the reader hunting
     * for the wrong fault. */
    printf("\nverdict\n");
    printf("  access : %s\n", problems == 0
           ? "OK — a target launched through this gate should see the RTX 4050."
           : "BROKEN — the target will most likely fall back to the iGPU.");
    printf("  gate   : %s\n", leaks == 0
           ? "OK — the dGPU is reachable only through this binary."
           : "LEAKING — see the nodes marked LEAK above. The gate still blocks real use\n"
             "           if nvidiactl and nvidia0 are tight, but this contradicts DECISION 25.");
    return (problems || leaks) ? 1 : 0;
}

int main(int argc, char **argv) {
    int keep_env = 0;
    int check = 0;
    int i = 1;

    /* Only LEADING options belong to the gate; the first non-option is the command and
     * everything after it is the command's own. `--` ends gate options explicitly, for
     * the case where the command itself starts with a dash. */
    for (; i < argc; i++) {
        if (strcmp(argv[i], "--keep-env") == 0)      { keep_env = 1; continue; }
        if (strcmp(argv[i], "--check") == 0)         { check = 1; continue; }
        if (strcmp(argv[i], "--") == 0)              { i++; break; }
        break;
    }

    if (i >= argc && !check) {
        fprintf(stderr,
            "usage: dgpu-exec-v2 [--keep-env] [--check] [--] <command> [args...]\n"
            "  --keep-env  do not set the NVIDIA vendor environment (see BUG-145)\n"
            "  --check     report what a target would see, then exit\n");
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

    /* Must happen after the credential change: the point is that the TARGET execs with
     * AT_SECURE=0 and will therefore actually read these. See BUG-145 in the header. */
    if (!keep_env) apply_nvidia_env();

    if (check) return check_mode();

    execvp(argv[i], &argv[i]);
    fprintf(stderr, "dgpu-exec-v2: cannot exec %s: %s\n", argv[i], strerror(errno));
    return 127;
}
