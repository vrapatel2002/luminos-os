/* dgpu-exec — setgid(dgpu) launcher that grants dGPU device access.
 * [CHANGE: claude-code | 2026-07-03] DECISION 25: dGPU access gate (default-deny).
 *
 * Installed setgid: owner root:dgpu, mode 2755. When ANY user execs this binary,
 * the kernel sets egid=dgpu for the new process. It then execs the target command,
 * which inherits egid=dgpu and can therefore open the gated device nodes
 * (/dev/nvidia*, group dgpu, mode 0660).
 *
 * Apps that are NOT launched through this helper keep rgid/egid=<their group> and
 * are denied by the device-node permissions — the default-deny behavior we want.
 *
 * This is the ONLY privileged component of the gate, and it is setGID (not setUID):
 * it can grant the dgpu group and nothing else. It performs no argument parsing and
 * holds no secrets. To bypass the gate entirely: `sudo chmod 0666 /dev/nvidia*`.
 */
#include <unistd.h>
#include <stdio.h>
#include <string.h>
#include <errno.h>

int main(int argc, char **argv) {
    if (argc < 2) {
        fprintf(stderr, "usage: dgpu-exec <command> [args...]\n");
        return 2;
    }
    /* egid is already dgpu (set by the setgid bit on this binary). Exec the target
     * directly so it inherits egid=dgpu and can open the gated dGPU device nodes. */
    execvp(argv[1], &argv[1]);
    fprintf(stderr, "dgpu-exec: cannot exec %s: %s\n", argv[1], strerror(errno));
    return 127;
}
