# docs/gamemode/BMW-BENCH.md — Black Myth: Wukong measured on the G14
# [CHANGE: claude-code | 2026-09-20]
Run 2026-09-20 via Lutris (game id 4), GE-Proton11-6, umu/steamrt4, MangoHud logging.
Companion to IGPU-BENCH.md. First real-game numbers on this box.

---

## 1. "It's running on older drivers and things are messed up" — it isn't

Checked end to end. **Nothing is broken and the drivers are current:**

| | |
|---|---|
| running kernel module | 610.57.04 |
| `modinfo nvidia` | 610.57.04 |
| `nvidia-utils` / `nvidia-open-dkms` | 610.57.04-1 |
| DKMS | `nvidia/610.57.04, 7.0.5-arch1-1: installed` |
| kernel | 7.0.5-arch1-1 |

No mismatch anywhere. `~/.config/lutris/system.yml` is present and **byte-identical to
`config/lutris-system.yml`**, so DECISION 90's `prefix_command: dgpu-exec-v2 --` is intact
and the game reaches the 4050. Confirmed live: 1.8-5.2 GB VRAM on the NVIDIA card,
2200-2500 MHz, 93% utilisation.

⚠️ **The thing that *looks* broken and is not:** plain `vulkaninfo` as shawn lists only the
780M, and `nvidia-smi` says "Insufficient Permissions". That is DECISION 25's gate doing its
job — `/dev/nvidia*` is `root:dgpu 0660` and shawn is deliberately not in `dgpu`. Through
`dgpu-exec-v2` both work instantly. **Do not "fix" this.** Anyone diagnosing a GPU problem
on this box must test through the gate or they will misdiagnose it. (This document's author
misdiagnosed exactly that before checking `system.yml`.)

## 2. The settings it was actually running — this is the real story

From `~/Games/umu/umu-default/drive_c/users/steamuser/AppData/Local/b1/Saved/Config/Windows/GameUserSettings.ini`:

| setting | value | meaning |
|---|---|---|
| `ResolutionSizeX/Y` | **2880x1800** | output at native panel res |
| `sg.ResolutionQuality` | **50** | **internal render is 50% = ~1440x900** |
| `QualityLevel` / all `sg.*` | **1-2** | **Medium** |
| `Dlss` | 1 | DLSS on |
| **`InsertFrame`** | **1** | **FRAME GENERATION IS ON** |
| `Rtx` / `sg.RayTracingQuality` | **0** | **RAY TRACING IS OFF** |
| `r.RayTracing.EnableInGame` | **False** | confirmed off |
| `Dx12` | **0** | **running DX11 (DXVK), not DX12/VKD3D** |
| `FrameRateLimit` / `Vsync` | 0 / off | uncapped |

## 3. Measured — steady-state gameplay only (menu and loading excluded)

| | |
|---|---|
| **average FPS** | **53.6** |
| median | 51.0 |
| **1% low** | **37.9** |
| 5% low | 42.3 |
| min / max | 15.4 / 70.1 |
| frametime avg | ~19 ms |
| frametime 99th | ~30 ms |
| frametime worst | **~70 ms** (a visible hitch) |
| dGPU | 5.2 GB / 6.1 GB VRAM, 93% util, 2200-2500 MHz, **55 W, 86 C** |
| iGPU during play | 800 MHz, 10-12% busy — compositing only |

**Read that average carefully: 53.6 fps is WITH frame generation on.** Real rendered frames
are roughly half that — **~27 fps of actual rendering**, interpolated up.

## 4. What this settles

1. 🔴 **The stated target — 60 fps, high/max, ray tracing, no frame generation — is dead for
   this class of title on this hardware.** Measured reality is Medium preset, RT *off*,
   900p internal, frame-gen *on*, DX11, and it still only averages 53.6 with 1% lows of 38.
   Every one of those is a concession the target explicitly refused. This is no longer an
   estimate from published benchmarks (IGPU-BENCH §5) — it is this laptop, this week.
2. 🔴 **VRAM sits at 5.2 of 6.1 GB (85%) with ray tracing OFF and on DX11.** DX12 + DXR under
   VKD3D-Proton roughly doubles VRAM (vkd3d-proton #1874). There is no headroom to turn RT on.
   6 GB is the wall, exactly as FEASIBILITY predicted.
3. 🟢 **The dGPU had 2 MiB used before launch.** The desktop is entirely off the 4050 —
   DECISION 25's gate already gives games effectively the whole 6 GB. **So the "move the
   compositor to the iGPU to free VRAM" idea, argued in the two-GPU discussion, wins
   nothing here. Luminos already does it.** That reasoning needs retiring.
4. 🔴 **The real constraint is SYSTEM RAM, not VRAM.** Baseline desktop: 10.1 GB of 15.2 GB
   used before the game started. During play: **13.2 GB used, ~2 GB available, and 11.5 GB
   pushed to swap.** The 15.4 fps minimum and the 70 ms frametime spikes are consistent with
   swap stalls, not GPU limits — the GPU was at a steady 93% with stable clocks throughout.
   **This is the strongest measured argument for the new OS so far, and it is not the one
   the project was founded on.** A gaming-only OS cannot add VRAM or shader power, but it
   can trivially hand back ~8-10 GB of system RAM, and on this title that is where the
   stutter is coming from.

## 5. Gotcha for next time

**MangoHud logged the iGPU's counters, not the 4050's** — the CSV reports 800 MHz core,
0.4 GB VRAM and 10% load while `nvidia-smi` simultaneously showed 2300 MHz, 5.2 GB and 93%.
FPS and frametime in the log are correct; every GPU hardware column is the wrong device.
Pin it with `pci_dev=0000:01:00.0` in the MangoHud config on any future run, or read the
hardware counters from `dgpu-exec-v2 nvidia-smi` in parallel as was done here.

Also: the first 40 s of any log is menu + shader compile + level load (127 fps menu, 0.7 fps
loading hitches). Slice `elapsed >= 40` or the averages are meaningless.

## 6. Not established

- Performance with frame generation OFF (the actual apples-to-apples number).
- Performance with the desktop shut down / RAM freed — the direct test of §4.4.
- Whether `sg.ResolutionQuality=50` was chosen by the game's auto-detect or set by hand.
