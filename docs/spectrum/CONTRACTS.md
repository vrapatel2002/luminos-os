# CONTRACTS — spectrum (frozen; change only by re-plan)
# [CHANGE: claude-code | 2026-10-15]

## spectrum.go (package main, imports only "math")
Exactly the API of DESIGN.md §4:
type Params struct { TickS, PminW, PmaxAcW, PmaxBatHiW, PmaxBatLoW, PmaxDgpuW, ThiAcC, ThiBatC, ThiDgpuC,
    T0C, RthCPerW, KpWPerC, KiWPerCS, IminW, ImaxW, IleakS, TauTempS, TauDemandS, TauGpuS, D0, D1,
    SlewUpWS, SlewDownWS, SlewDownHotWS, WriteDeadbandW, RefreshS float64
    FreqBatFloorKHz, FreqBatCeilKHz, FreqSlewKHzS, FreqDeadbandKHz, HwMaxKHz int; EPP string }
type Inputs struct { DT, UtilAvg, UtilMax, IGPUBusy, TempC, SOC float64
    OnAC, DGPUBusy, PPTOwnerExternal, ProfileChanged, Resumed bool }
type State struct { TempS, Demand, I, Gpu, P, SinceRefreshS float64; F, PptWritten, FreqWritten int; Seeded bool }
type Outputs struct { Level, TargetTempC, PmaxW, Demand float64; PptW, FreqCapKHz int; EPP, Binding string
    WritePPT, WriteFreq, WriteEPP bool }
func DefaultParams(hwMaxKHz int) Params      // constants = DESIGN §3.4 table
func Step(p Params, s State, in Inputs) (State, Outputs)
Semantics = DESIGN §3.4 steps 0–9 exactly. Binding ∈ {"demand","thermal","battery","dgpu"}.
Clarifications (binding):
- C1 dt = clamp(in.DT, 0.5, 3). Step 0 seeding sets F = p.HwMaxKHz when !Seeded.
- C2 Level uses the FIXED scale (P − PminW)/(PmaxAcW − PminW), clamped to [0,1].
- C3 On battery the freq target uses PmaxSrc (the battery top) as the denominator; if PmaxSrc − PminW < 0.5 W,
  Ftarget = FreqBatFloorKHz. F is clamped to [FreqBatFloorKHz on battery else 0, HwMaxKHz].
- C4 Outputs.PptW = round(P); Outputs.FreqCapKHz = F; Outputs.EPP = p.EPP; Outputs.PmaxW = Pmax (blended);
  Outputs.TargetTempC = Thi (blended); Outputs.Demand = state Demand.
- C5 "force" = !Seeded (before seeding) || in.Resumed.
- C6 Under in.PPTOwnerExternal, WritePPT=false and PptWritten/SinceRefreshS are NOT updated (so a re-assert
  happens as soon as ownership returns: next tick with PPTOwnerExternal=false must WritePPT=true).

## main.go ↔ spectrum boundary
- main.go owns ALL I/O; spectrum.go owns ALL decisions. main.go never computes a watt/frequency/EPP value itself.
- Loop: time.Ticker(1 s) → read Inputs → Step → apply writes the Outputs flag → update status snapshot → WATCHDOG=1.
- Writers: PPT → the three asus-nb-wmi ppt_* files, same value, order pl1, pl2, fppt; freq → scaling_max_freq of all
  policies; EPP → all cpus. Never: platform_profile, asusctl, fan curves, nvidia-smi (except the offload_* socket path).
- PowerState JSON: keep every existing key; add level, ppt_w, ppt_target_w, pmax_w, temp_target_c, demand, binding,
  freq_cap_khz, dgpu, ppt_owner, wmi_writes_total (DESIGN §3.10).
- Log line every 30 s + on events: `spectrum: level=..% ppt=..W tgt=..W pmax=..W temp=..C thi=..C demand=.. binding=..
  dgpu=.. profile=.. epp=.. ac=. writes=..` (keeps `profile=` for the Plasma widget).

## Files and owners
| file | owner |
|---|---|
| cmd/luminos-power/spectrum.go | core implementer |
| cmd/luminos-power/spectrum_test.go | test writer |
| cmd/luminos-power/main.go, delete conductor.go + fan_control.go, systemd/luminos-power.service | integrator |
| scripts/luminos-fan-curve-install, tests/spectrum/load/*, scripts/spectrum-ab.sh | tools worker |
No worker edits another's files. Nobody runs systemctl, writes sysfs, installs binaries, or touches /etc — PM only.

## Rulings (PM, 2026-10-15, after core + tests landed — both workers converged independently)
- R-C6: while PPTOwnerExternal, PptWritten is untouched and SinceRefreshS is parked at ≥ RefreshS (refresh due), so the
  first tick with PPTOwnerExternal=false always has WritePPT=true. This replaces "SinceRefreshS NOT updated".
- R-P5: idle never integrates (I only decays, τ = IleakS = 300 s); "|I| ≤ 1e-3" holds after ~4 300 idle seconds, not 120.
  P == PminW after 120 idle steps is unchanged.
- R-P9: on a Resumed tick, steps 2 and 6 still run after the reset: Demand == that tick's raw demand, |I| ≤ one
  integration step; with idle inputs both are exactly 0.
- R-plant: the 180 s settle rule applies where heat binds (AC, no dGPU); on battery / dGPU the model never reaches Thi,
  so zero overshoot is asserted instead. Measured in sim: 3.11 °C overshoot, settle 168 s (limits 4 °C / 180 s).
- R-tick (PM, after review): the loop period is FIXED at Params.TickS = 1 s. `poll_interval_secs` in config.toml is
  ignored (it defaulted to 2 in internal/config and silently halved the loop rate). Logged once if set.
- R-retry: a failed ppt_* write forces a retry on the next tick (I/O layer resets PptWritten); never counted as success.
