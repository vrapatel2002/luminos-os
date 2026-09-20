# gamemode-bench — iGPU throughput harness
# [CHANGE: claude-code | 2026-09-20]

Self-contained Vulkan compute microbenchmarks. No package install required —
builds against the vulkan headers + glslc already on the box (luminos-brain safe
returned NO for installing vkpeak/clpeak, so these were written instead).

    glslc -O fma.comp -o fma.spv && gcc -O2 bench.c -lvulkan -o bench && ./bench 780M
    glslc -O bw.comp  -o bw.spv  && gcc -O2 bw.c    -lvulkan -o bw    && ./bw 780M

bench = FP32 FMA throughput (8 independent accumulators, so RDNA3 VOPD dual-issue
can fire). bw = vec4 read-modify-write over a 256MB buffer = achieved bandwidth.

IMPORTANT: `bench` defaults to RUNS=20 which is only ~145ms of load. That is far too
short to measure power or thermal behaviour — sampling hwmon over such a run reads
mostly idle. Rebuild with RUNS=2000 for sustained numbers. This mistake was made and
caught during the first measurement session; see docs/gamemode/IGPU-BENCH.md.
