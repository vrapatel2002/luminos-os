# vram-probe — does NVIDIA/Linux have a usable system-memory heap for graphics?
# [CHANGE: claude-code | 2026-09-20]
Answer: YES. See ../../docs/gamemode/WALL3-BREACHED.md

    gcc -O2 probe.c  -lvulkan -o probe  && dgpu-exec-v2 ./probe    # enumerate + host-import test
    gcc -O2 probe2.c -lvulkan -o probe2 && dgpu-exec-v2 ./probe2   # tiled image in sysmem + render + capacity
    glslc -O bw.comp -o bw.spv
    gcc -O2 probe3.c -lvulkan -o probe3 && dgpu-exec-v2 ./probe3 NVIDIA <memtype>   # bandwidth per memory type

Must run through `dgpu-exec-v2` or the NVIDIA device is not visible (DECISION 25 gate).
