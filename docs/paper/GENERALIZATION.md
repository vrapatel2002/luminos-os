# Does the 007 work generalize? — findings + resume point
# [CHANGE: claude-code | 2026-08-20]

**Status: IN PROGRESS, stopped 2026-08-20. Paper itself is DONE (19 pages).**

The question asked: *"we did it one game good but now real question is it
applicable to any or all other?"*

Answer so far, with evidence. Some of it **contradicts the paper** and the paper
needs a correction pass.

---

## The control we found: Black Myth Wukong

A second, fully installed title on `/mnt/win-os/Games/Black Myth - Wukong`
(140 GB). Same distributor (`FitGirl-Launcher.exe` is present). **Has Denuvo.**
This is the control §4 needed and never had.

Built `~/re/tools/drmcheck.py` — the whole §4 procedure as one reusable tool.
Negative-tested it against 007 first: it reproduces every number in the paper's
Table (64,228,744 B, md5 `3e0c3e10…`, 43 windows, 5.906–6.700, mean 6.505, 0
windows ≥ 7.5, stock sections). So the instrument is sound.

### Result on both titles

| Test | 007 (no Denuvo) | Wukong (Denuvo) | Discriminates? |
|---|---|---|---|
| Authenticode digest | **VALID** | **VALID** | **NO** |
| Windowed entropy ≥7.5 | 0 of 43 | **1 of ~680** | **NO** |
| Import table size | 52 DLLs / 753 syms | **56 DLLs / 1178 syms** | **NO** (backwards) |
| Non-standard sections | none | **10** | **YES** (with caveat, Finding 5) |
| `.text` section present | yes | **absent** | **YES** |
| RWX section | none | **`.xtls`, 198 MB** | **YES** |
| Protection strings | none | **`DENUVO`** | **YES** |
| File size | 64 MB | **728 MB** | **YES** |

Two titles, six tests each. **Three of the six discriminate cleanly; the other
three do not.** The three that survive are the ones the corrected §4 should lean
on: missing `.text`, an RWX section, and protection strings — plus size as a soft
prior.

### Finding 1 — the entropy test FAILED on a real Denuvo binary

Per-section, across 695 MB of a known-Denuvo executable, **exactly one 1 MiB
window out of ~680 crosses 7.5**. That is noise.

```
Wukong  .shared  263.2 MB  X  entropy 6.443  win>=7.5: 0
        .code    199.8 MB  -  entropy 6.031  win>=7.5: 1
        .xtls    198.0 MB  X  entropy 6.761  win>=7.5: 0
```

**§4 currently claims:** *"Had a virtualising layer been present, it would appear
as a contiguous run of windows well above 7.5."* **That is now empirically
false.** Denuvo's VM is ordinary x86 that interprets — it is not compressed and
not encrypted at rest, so it is not high-entropy. The `sokpacker` false-negative
caveat the paper cites turns out to apply directly to the one case that mattered.

→ **ACTION: demote entropy in §4 from "corroborating" to "was tried, did not
discriminate," and add this control table.** This makes the paper stronger, not
weaker — it is a measured negative result on a real protected binary.

### Finding 2 — the signature test answers a different question than §4 implies

Wukong's exe is **also** a valid, unmodified publisher build. The signature
validates. And Denuvo is right there in it.

So "signature valid" means **"nothing was removed"** — it does *not* mean
"unprotected." §4's chain of reasoning is:

> signature valid → nothing removed → if protection is not visible now, it was
> never there

That is still **logically sound**, but the load-bearing clause is *"if protection
is not visible now"* — which depends entirely on the **weak** tests, and one of
those two weak tests (entropy) just failed. The paper currently presents the
signature as sufficient on its own. It is not. It is necessary, and it needs a
*working* visibility test beside it.

→ **ACTION: rewrite the "Why this settles the question" block in §4 to make the
visibility test explicit, and cite Wukong as the case that proves the signature
alone is not enough.**

### Finding 3 — why the signature survives on a cracked Denuvo game

Because the crack never touches the exe. Wukong's countermeasure is the
hypervisor (§4 contrasting case), which sits *below* the game. 007's is a Steam
API DLL replacement, which sits *beside* it. Neither modifies the binary.

→ Useful generalisation: **repack cracks in this family are non-invasive to the
main executable.** That is why the signature method works at all on repacks, and
it is worth stating.

### Finding 4 — the import-table claim is backwards

**§4 currently claims:** *"a protected binary usually cannot afford a full static
import table."* Measured, that is the wrong way round:

```
Wukong (Denuvo)   56 DLLs / 1178 symbols
007    (clean)    52 DLLs /  753 symbols
```

The protected binary imports **more**, not fewer. Denuvo does not hide the game's
imports — it adds its own on top. So a small import table is not evidence of
protection and a large one is not evidence of its absence.

What *is* interesting is **which** symbols only appear on the protected side:

```
AddVectoredExceptionHandler   RtlAddFunctionTable      RtlDeleteFunctionTable
VirtualProtect                FlushInstructionCache    GetNativeSystemInfo
GetVolumeInformationW         GetAdaptersInfo          GetComputerNameW
RegCreateKeyExW  RegSetValueExW  RegDeleteKeyW  RegDeleteValueW
GetNamedSecurityInfoW         SetNamedSecurityInfoW
TerminateThread  OpenThread   CreateToolhelp32Snapshot  Process32NextW
```

That reads as: install exception handlers and unwind tables for the VM, flip page
protections and flush I-cache after writing code, fingerprint the machine
(volume serial + MAC + computer name), persist under a registry key with an ACL
on it, and enumerate/kill other processes. That is a **behavioural** signature and
it is worth more than the counting test.

Equally important, these appear in **both** binaries and therefore discriminate
nothing: `IsDebuggerPresent`, `DebugBreak`, `SetUnhandledExceptionFilter`,
`VirtualAlloc`, `VirtualQuery`, `GetSystemInfo`, `SuspendThread`,
`TerminateProcess`, and all four timing APIs. Ordinary games use every one of
them.

→ **ACTION: delete the import-count claim from §4. Replace it with the
Denuvo-only symbol list above, marked as suggestive rather than conclusive
(n=2).**

### Finding 5 — the section-name test false-positives on clean software

`drmcheck.py` was run over a wider control set on `/mnt/win-os/Program Files`.
Non-standard section names are **common in legitimate shipped software**:

- Microsoft Excel — `.detourc`, `.c2r`, `sdmprc`
- RadeonSoftware — `.qtversi`
- CrashReportClient — 1 odd section

None of these is protected. Odd section *names* are a weak prior only. What none
of the clean controls had is the combination the corrected test should use:

> **no `.text` at all** + **a section that is simultaneously writable and
> executable**.

Five clean controls, **zero** RWX sections. Wukong has a 198 MB one.

→ **ACTION: in §4, downgrade "non-standard section names" to a prior and promote
"missing `.text` + RWX section" to the primary structural test.**

### Finding 6 — how Denuvo actually integrates (measured, not described)

Useful for the paper and worth recording independently, since it explains *why*
the surviving tests survive.

```
b1-Win64-Shipping.exe   728,458,376 B   md5 c7dae1acb6df82a1d591bd13ca1a9154

  .shared  263.2 MB  executable        <- real code lives here
  .code    199.8 MB  INITIALISED DATA  <- flagged NON-executable = VM bytecode
  .xtls    198.0 MB  R+W+X             <- the runtime container
  .text    ABSENT
```

- **Entry point relocated.** Clean 007 enters at rva `0x02a0a4a4` inside `.text`.
  Wukong enters at rva `0x2918eb40` inside `.xtls` — i.e. control lands in
  Denuvo's container, not in the game.
- **6 TLS callbacks** vs 007's 2. TLS callbacks run *before* the entry point, so
  Denuvo is alive before `main`:
  `[0] 0x21395c70 .xtls`, `[1] 0x26e639bd .xtls`, `[2] 0xff52344 .shared`,
  `[3] 0xff524dc .shared`, `[4] 0xf232ed0 .shared`, `[5] 0x29bc4ae0 .xtls`.
  The TLS directory sits in `.code` and the callback array in `.00cfg`.
- **Strings**, all inside `.xtls`: `DODENUVO` at `0x2534d8f4`, `denuvo_atd` at
  `0x2a43bca0` beside UTF-16 `antitamperdiagnosis` / `tamperdiagnosis`.
- **`.code` being flagged as data is the tell.** 199.8 MB of non-executable
  content in a game executable is not data the game reads — it is a program the
  interpreter in `.shared` walks. That is the virtual machine, and it is why the
  entropy test fails: interpreted x86-like bytecode is *not* compressed or
  encrypted at rest, so its entropy looks like ordinary code.

### Finding 7 — the hypervisor crack, verified rather than assumed

The Wukong repack ships its own countermeasure. It was inspected rather than
taken on trust.

```
b1/Binaries/Win64/Simplesvm.sys           18,680 B   (AMD)
_AMD CPU/b1/Binaries/Win64/Simplesvm.sys  18,680 B
_INTEL CPU/b1/Binaries/Win64/hyperkd.sys  11,984 B
```

`Simplesvm.sys` is **PE machine 8664, subsystem 1 = native kernel driver**. It
imports **`ntoskrnl.exe` only, 47 functions**. Grouped by what they are for:

| Purpose | Imports |
|---|---|
| Build nested page tables by hand | `MmAllocateContiguousNodeMemory`, `MmFreeContiguousMemory`, `MmGetPhysicalAddress`, `MmGetVirtualForPhysical` |
| Bring the hypervisor up on every core | `KeQueryActiveProcessorCountEx`, `KeGetProcessorNumberFromIndex`, `KeSetSystemGroupAffinityThread`, `KeRevertToUserGroupAffinityThread`, `KfRaiseIrql`, `KeLowerIrql`, `KeGetCurrentIrql` |
| SVM MSR / IOIO permission bitmaps | `RtlInitializeBitMap`, `RtlClearAllBits`, `RtlSetBits` |
| Double-map pages into the target process | `PsSetCreateProcessNotifyRoutine`, `PsLookupProcessByProcessId`, `KeStackAttachProcess`, `KeUnstackDetachProcess`, `IoAllocateMdl`, `MmProbeAndLockPages`, `MmMapLockedPagesSpecifyCache` |
| Anti-analysis | `KdDebuggerNotPresent`, `KeBugCheck` |

Disassembled with `objdump -D -b binary -m i386:x86-64 -M intel` (capstone and
ndisasm are both absent on this machine). The AMD-V instruction set is present
and unambiguous: `vmsave`×3, `vmload`×3, `vmrun`×1, `stgi`×1, plus `rdmsr`×12,
`wrmsr`×9, `cpuid`×9, `sgdt`×5, `sidt`×1, `xgetbv`×1. The first 16 bytes of
`.text` are the launch loop itself:

```asm
mov  rsp, rcx
mov  rax, [rsp]
vmload            ; 0f 01 da
vmrun             ; 0f 01 d8
vmsave            ; 0f 01 db
sub  rsp, 0x190
push rax / rcx / rdx / rbx / -1 / rbp / rsi / rdi
```

`.rdata` still carries `@SimpleSvm` and an unstripped `SimpleSvm.pdb` path — the
name matches a well-known open-source educational AMD hypervisor.

**The mechanism is split-view paging (EPT on Intel, NPT on AMD).** One virtual
address gets two backing pages: instruction fetch is served the patched page,
data read is served the original. Denuvo's own `sha256(code pages)` integrity
check therefore reads clean bytes while the CPU executes modified ones.
**Normal x86 paging cannot express execute-without-read** — that split exists
only in EPT/NPT, which is exactly why a hypervisor is mandatory here and why no
user-mode patch would do.

Two verbatim confirmations from the repack's own files:

> `VBS.cmd` — *"This script disables the Windows hypervisor, Virtualization-based
> Security (VBS) and its dependent features including Memory Integrity,
> Credential Guard, System Guard and the Windows Hello protection."*
> …and *"On older Intel CPUs (and rarely, older AMD CPUs), KVA Shadow will also
> be disabled as it conflicts with our syscall hook implementation."*

That is proof that two hypervisors cannot co-own the CPU — it has to evict
Microsoft's before installing its own.

> `HV-StartGame_INFO.txt` — *"Detects which CPU you have (AMD/INTEL) / Perform the
> creation, installation, and initialization of the hypervisor service. / Start
> the game. / Once the game is closed, HV-StartGame performs a cleanup procedure
> to stop and remove the hypervisor service and its associated files."*

`HV-StartGame.ini`: `TargetExe=steamclient_loader_x64.exe,Game1.exe,Game2.exe`,
`ServiceName=denuvo`, `InstallPath=C:\Drivers`.

**Why this matters for generalization:** Denuvo has two layers. Layer 1 is the VM
and nobody attacks it. Layer 2 is ordinary licence/activation code, and that is
what gets patched. Layer 1's job is to notice the Layer 2 patch. The hypervisor's
only job is to make that one ordinary patch invisible to Layer 1. **It is
concealment, not injection.**

### Finding 8 — Wukong ships no anti-cheat (negative result, measured)

Checked because it would have changed the Proton assessment if true. It is not.

`find` for anticheat / easyanti / battleye / eac / vanguard / xigncode across the
whole 140 GB install returned nothing. The only `.sys` files present are the
crack's three. String counts inside the 728 MB executable:

```
EasyAntiCheat 0   BattlEye 0   Vanguard 0   XIGNCODE 0   anticheat 0
AntiCheat 1       nProtect 7
```

All 8 hits were checked by byte-context and all 8 are false positives:
`SampleCollectionProtectTime`, `NormalProtectTime`, `TrainProtect`,
`isNonProtectedInternal`, `ActiveDirectoryConnectionProtection`, `OnProtected`,
and `bAntiCheatProtected` sitting beside `bDedicatedServer` / `bUsesStats` —
which is a stock Unreal session-settings field, present in every UE title.

Compare the real signal in the same binary: `DENUVO` 1, `denuvo_atd` 1,
`antitamperdiagnosis` 1.

→ Method note worth keeping: **a string match is not a finding until the bytes
around it are read.** Same discipline as the malware triage in §3.

### Correction to an earlier claim of my own — "impossible" was too strong

I previously wrote that the Linux crack path is *structurally impossible*. That
is wrong and it was challenged. The accurate statement:

- The **existing tool** cannot work on Linux. `Simplesvm.sys` is a Windows kernel
  PE importing `ntoskrnl.exe`. Wine translates Windows *programs* in user space;
  a kernel driver is not a program and there is no Windows kernel underneath it
  to load into.
- A **Linux equivalent is conceivable.** You would not write a driver — you would
  patch KVM's NPT fault handler, since the machine already has the hardware
  (`svm` flag present, `kvm_amd` + `kvm` + `irqbypass` loaded, `/dev/kvm` at
  `10,232` mode `crw-rw-rw-`, `/sys/module/kvm_amd/parameters/nested` = `1`).
- It has not been built because of the **stack above it**, not the hypervisor:
  running the game inside a VM makes the fingerprint the VM's, invites
  VM-in-a-VM detection, and RTX 4050 passthrough fails on this muxless Optimus
  G14 anyway. And the audience for the tool is on Windows.

→ **The honest phrasing, which is what should go in the paper: hard and unbuilt,
not physically impossible.**

### Also fixed: a real bug in my own instrument

`drmcheck.py` originally hardcoded `.text` for the entropy profile. Wukong has
**no `.text` section at all** — its code is in `.code`/`.shared`/`.xtls`. The
entropy test silently did not run and printed nothing. Now falls back to the
largest `IMAGE_SCN_MEM_EXECUTE` section. Same class of silent failure as
everything in the paper's Table XV.

---

# THIRD TITLE EXECUTED — *Returning to Mia* (2026-08-20)

The test deferred in the previous session was run end to end. It is the first
time the method has been executed against a title it was not derived from, and
it changes four rows of the table below from *reasoned* to *measured*.

Specimen: `Returning to Mia`, FitGirl repack, 14 GB, Ren'Py 8.3.3 visual novel
(GOG build). Maximally unlike 007: no Unreal, no D3D12, no Denuvo.

### Finding 9 — §3 triage generalizes at the TOOLCHAIN level, not the title level

The repack payload is **not** title-specific. Comparing Mia's extracted
installer payload against the known-clean 007 payload:

| Result | Count | Files |
|---|---|---|
| byte-identical (md5) | **11 of 11** comparable | `ISDone.dll` `unarc.dll` `idp.dll` `hosts.exe` `CallbackCtrl.dll` `botva2.dll` `cls-lollypop.dll` `cls-srep_x64.exe` `cls-magic2_x64.exe` `facompress.dll` `razor.dll` |
| new in Mia | 3 | `InnoCallback.dll`, `bass.dll`, `precomp.exe` |
| `host.cmd` | identical | same FitGirl anti-impersonation host redirect, same IP `109.94.209.70` |
| `arc.ini` | 2 lines differ | both cosmetic: a section alias, and `fgrplc` placeholder vs a resolved `15` |

All three new files were attributed by reading context, not by string matching:
`precomp.exe` carries an embedded text dictionary (source of ~40 junk
`http://...` fragments) and a genuine credit line for packJPG's author;
`hosts.exe` carries a .NET manifest. Zero real network indicators beyond the
known FitGirl redirect.

→ **This is the strongest generalization result in the whole exercise.** Triaging
a FitGirl repack is a **delta problem**: hash the payload against a known-clean
one and triage only what is new. §3's full procedure needs to be run once per
*toolchain version*, not once per game.

### Finding 10 — §4's strong test is simply unavailable on a repack's installer

`setup.exe` has **no Authenticode signature at all** — not an invalid one, none.
The decisive test in §4 therefore cannot run on the artefact a user actually
executes first. Weak evidence only, all clean: entropy 6.482 flat (0 windows
≥ 7.5), **0 RWX sections**, no protection strings, `.text` present.

Also: `drmcheck.py` flagged `.itext` as a non-standard section name. It is
ordinary Delphi/Inno Setup. **Another false positive for Finding 5's pile.**

### Finding 11 — §5's preconditions are present, its fixes apply, and the installer still fails

Everything §5 asks for was verified present and then applied:

- **Precondition confirmed by measurement.** Creator `cls-srep_x64.exe` contains
  `Global\`; opener `CLS-srep.dll` does not. Same for the lollypop pair.
  `cls-magic2{,l}.dll` carry their own copy and so already agree — the exact
  asymmetry §5 describes, in binaries that are byte-identical to 007's, at
  **identical patch offsets** (`cls-magic2.dll` offset 1651, the number recorded
  in `clspatch.py`'s 007-era comment).
- **FIX 1 applied live.** `clspatch.py` caught **10 runtime-extracted helpers**
  in a fresh temp dir seconds after launch — independently confirming §5's
  "the payload is re-materialised at runtime, static patching is bypassed" claim
  on a second title.
- **FIX 2 applied.** `c:\arc.ini` staged at the system drive root.
- **Payload proven intact first.** All 7 containers md5-match the shipped
  `fitgirl-bins.md5` (14 GB verified), so the stall is not corrupt data.
- **Config proven correct.** `{app}` substituted to the real target; the runtime
  `CLS.ini` matches 007's working one (007's only edit redirected temp to a
  separate dir — a disk-space convenience, not a fix).
- **Prefix proven equivalent.** Fresh `win64` prefix; the only delta against the
  007 sandbox is four NVIDIA DLLs, irrelevant to extraction.

**Result: the installer still stalls.** 25 minutes, **zero bytes** into the
`.rpa`, 3.0 MB of redist — reproducing the pre-existing failed install's exact
signature in a clean prefix, so the failure is deterministic rather than
environmental damage.

### Finding 12 — the stall is a THIRD failure mode; §5's differential table is incomplete

§5 offers two shapes and a table to tell them apart. This is neither:

| | §5 Failure 1 (modal) | §5 Failure 2 (config) | **Mia (new)** |
|---|---|---|---|
| CPU | 0% | one core busy | **one core pinned 100%** |
| Child process | helper alive | none | **none ever spawned** |
| Bytes written | partial | zero | **zero** |
| Time to fail | never | ~2 s | **never** |

Measured directly rather than inferred:

- read offset on `fg-01.bin` frozen at **byte 31** — the ArC header — for minutes
  (`/proc/<pid>/fdinfo`, which is the real progress indicator, not output size)
- RSS **perfectly flat** at 80,508 kB while burning a full core → not decompression
- main thread blocked in `NtWaitForSingleObject`
- worker thread: **every** stack sample lands in `NtFreeVirtualMemory` — a tight
  alloc/free retry loop, `wchan=0`, no syscalls, pure userspace spin
- **no `cls-*` helper process was ever spawned**

→ §5 needs a **third row**: *spins at 100% forever, no helper, zero bytes*. Its
current table would misdiagnose this as "one core busy" → Failure 2 → "missing
config file", which is wrong; the config was present and correct.

### Finding 13 — §6 is not a fallback, it is the primary method

Driving `unarc.dll` directly via `arcx32.exe`, bypassing `setup.exe` entirely:

| Container | Result | Note |
|---|---|---|
| fg-01 | **rc=0**, 17.2 GB `.rpa` in 5 m 20 s (~50 MB/s) | `CLS-srep_x64.exe` **did spawn** here |
| fg-02…fg-07 | **rc=0** each | complete game tree, 18 GB total |

Output validated structurally, not assumed: the archive opens with `RPA-3.0` and
`Made with Ren'Py.`

The single sharpest observation: **the srep helper spawns under the direct path
and never spawns under the installer.** Same binaries, same patches, same
`arc.ini`, same prefix — so the defect lives in the ISDone/Inno layer above
`unarc`, not in the compressor stack §5 spends its time on.

→ In the paper, §6 is framed as the emergency route taken because 007's
`setup.exe` was missing. On Mia `setup.exe` is present, is used, and **fails** —
while §6 succeeds. **That inverts the framing: skip the installer by default.**

### Finding 14 — §7–§12 are unnecessary here, not merely untested

The Windows repack ships a **native Linux build**: `ReturningToMia.sh` plus a
full `lib/py3-linux-x86_64/` (`librenpython.so`, etc.). It was run:

```
Ren'Py 8.3.3.24111502 — "Returning to Mia"
Loading script took 1.23s ... Index archives took 0.00s
Initializing gl2 renderer:
Renderer: AMD Radeon 780M Graphics (radeonsi, phoenix, ACO)
Version: 4.6 (Compatibility Profile) Mesa 26.1.6-arch1.1
```

No `traceback.txt`, no `errors.txt`. No Wine, no Proton, no vkd3d-proton, no
Optimus divide-by-zero, no dGPU at all. (Two benign non-fatal notes: the GOG
build's `libsteam_api.so` is a stub, and PulseAudio was unavailable in the test
environment.)

→ **Generalization lesson the paper does not contain: look for a shipped native
build before doing any graphics work.** 007 had none, so the case study never had
occasion to check, and §7–§12 read as though the Wine graphics path is mandatory.
For this title the entire second half of the paper is skippable.

### What the third title cost, and what it bought

Two new tools, both generalized from 007-specific scripts by removing hardcoded
paths — nothing else had to change, which is itself evidence the method is
engine-level:

- `~/re/tools/fginstall.sh` — from `install007.sh`; applies both §5 fixes and
  carves `arc.ini` out of any installer automatically
- `~/re/tools/fgextract.sh` — from `extract007.sh`; the §6 direct-`unarc` path
  against any repack

---

## Generalizability by layer — current assessment

| Paper section | Generalizes to | Confidence | Evidence |
|---|---|---|---|
| §3 malware triage | any Inno Setup installer | **High, measured on 2 repacks** | 11/11 payload files byte-identical 007↔Mia; Finding 9 |
| §3 script carving | any Inno Setup installer | **High, measured on 2 repacks** | `innoextract` carved Mia's script first try |
| §4 signature test | any **signed** PE | **High** — but see Findings 2 and 10 | tested on 2 titles; **unavailable** on Mia's unsigned `setup.exe` |
| §4 entropy | — | **Rejected** | failed on the one control |
| §4 import-table size | — | **Rejected** | backwards; Finding 4 |
| §4 odd section *names* | any PE | **Low** — weak prior only | false-positives on Excel/Radeon; Finding 5 |
| §4 missing `.text` + RWX | any PE | **High** | 5 clean controls have zero RWX |
| §4 protection strings/size | any PE | **High** | clean on both titles |
| §5 `Global\` namespace fix | all ISDone/unarc repacks | **Necessary, NOT sufficient** | applies cleanly to Mia (10 helpers, identical offsets) — installer still fails; Finding 11 |
| §5 `c:\arc.ini` fix | all ISDone/unarc repacks | **Necessary, NOT sufficient** | same run; Finding 11 |
| §5 failure taxonomy | — | **Incomplete** | Mia is a third failure mode neither entry describes; Finding 12 |
| §5 installer path overall | — | **1 of 2 titles** | 007 n/a (no `setup.exe`), Mia **fails** |
| §6 reassembly method | all FitGirl repacks | **High, measured on 2 titles** | Mia: 7/7 containers rc=0, 18 GB, validated; Finding 13 |
| §6 vs §5 ordering | all FitGirl repacks | **§6 first** | it is the path that works; Finding 13 |
| pre-§7 native-build check | any title | **High** | Mia shipped a Linux build; §7–§12 moot; Finding 14 |
| §7 Optimus divide-by-zero | every D3D12 game on any Optimus laptop | **High** | hardware topology, nothing to do with 007 |
| §8 EGL vendor pin | this machine's config | **Low** (specific); class is general | — |
| §11 vkd3d-proton 3.0.1 | **every D3D12 game on NVIDIA under Proton** | **High by construction** | see below |
| §9 dialog-enumeration diagnosis | any Wine hang | **High** | technique, not fix |

### The graphics fix is game-agnostic by construction

Verified `~/re/tools/007-mkproton.sh` touches **nothing game-specific**. It
clones a Proton dir with `cp -al` and replaces exactly two files —
`d3d12.dll`, `d3d12core.dll` — in four arch directories. No 007 files, no
prefix contents, no per-title config. The name `007-` on the script is
misleading.

→ Therefore the fix applies to **any** D3D12 title that hits the same NVIDIA
SPIR-V compiler fault. Whether other titles *hit* that fault is untested —
we have no second D3D12 game installed on the Linux side.

→ **ACTION: rename `007-mkproton.sh` → `mkproton.sh`, it is a general tool.**

---

## The third title — EXECUTED 2026-08-20

**Status: done.** This section was written as a proposal; it is kept because the
specimen description is still the record of what was tested, but the test itself
is no longer pending. Results are Findings 9–14 above. One-line verdict:

> §3 generalizes at the toolchain level; §4's strong test was unavailable; **§5
> failed**; **§6 succeeded and produced a working 18 GB game**; §7–§12 turned out
> to be unnecessary because the title ships a native Linux build.

The specimen, as found on disk 2026-08-20 and verified the same day:

```
/home/shawn/Downloads/New Folder/Returning_to_Mia_--_fitgirl-repacks.site_--_
  fg-01.bin  13,144,054,789        setup.exe   5,393,864   <- PRESENT
  fg-02.bin     793,894,366        MD5/
  fg-03.bin     589,848,556        Verify BIN files before installation.bat
  fg-04.bin     121,167,209
  fg-05.bin      47,620,375
  fg-06.bin      31,200,257
  fg-07.bin      25,807,318        (14 GB total)
```

Why it was a good control — and it earned every one of these in the event:

- **Same distributor, same repack engine** (FitGirl / ISDone / unarc), so §5 and
  §6 apply directly. Confirmed: 11/11 helper binaries byte-identical to 007's.
- **`setup.exe` is present.** 007's was missing, which is why §6 had to
  reassemble by hand. Here the normal path could be tried first — and the manual
  path was still available as a fallback, which made this a clean A/B of the two
  methods. **The A/B is the single most valuable thing this title produced: the
  supposedly-normal path lost.**
- **Maximally unlike 007.** Ren'Py indie visual novel vs AAA Unreal. If the
  installer fixes held across that gap they would be genuinely engine-level.
  They did not hold — but §6 did, across the same gap, which is the stronger
  result because §6 is the harder claim.
- **It already failed in the documented way.** A previous install attempt left:

```
/home/shawn/Games/Returning to Mia/
  1,515,889  unins000.exe
  1,104,818  _Redist/fitgirl.md5
    299,864  _Redist/dxwebsetup.exe
    103,424  _Redist/QuickSFV.EXE
     95,749  unins000.dat
        155  _Redist/QuickSFV.ini
          0  game/00110001_01101100.rpa    <- STALLED AT ZERO BYTES
```

  Installer ran, wrote its redist payload, created the target file, then produced
  nothing. That looked like precisely the ISDone/unarc stall §5 diagnoses — so it
  was a live test of the `Global\` namespace fix and the `c:\arc.ini` fix rather
  than a hypothetical one. **It reproduced exactly in a clean prefix with both
  fixes armed** (25 min, 0 bytes), which is what turned it from a re-run into
  Finding 12.

**Limits of this control, as anticipated and as they played out:** `.rpa` means
Ren'Py, which is Python + SDL. It exercised §3, §4, §5 and §6. It did **not**
exercise §7–§12 — no D3D12, no Optimus divide-by-zero, no vkd3d-proton path. The
graphics rows stay untested until a second D3D12 title is installed on the Linux
side. What was *not* anticipated is that §7–§12 would be moot rather than merely
skipped: the title ships a native Linux build (Finding 14).

---

## Resume point — what to do next

0. ~~Test on `Returning to Mia`~~ — **DONE 2026-08-20.** Findings 9–14.
1. **Correct §4 of the paper** with Findings 1, 2, **4, 5 and 10**, and add the
   control table. Three claims in §4 are falsified by measurement, and Finding 10
   adds a fourth limitation: the signature test is not merely weak, it is
   *unavailable* on unsigned installers, which is the exact class of file §3 and
   §4 are pointed at. This is still the highest-value paper work: it turns a
   single-case study into a case study with two controls.
2. **Correct §5 and §6 of the paper.** New, and arguably now more urgent than
   step 1 because it changes what a reader is told to *do*, not just what to
   believe:
   - §5's failure table is incomplete — add Finding 12's third mode.
   - §5 must stop being presented as the default path and §6 as the fallback.
     Measured record across three titles: §5 usable **zero** times, §6 usable
     **twice**. Recommend §6 first.
   - Add the "check for a native Linux build before §7" step (Finding 14). It is
     five seconds of `ls` and it deleted six sections of work.
3. Add a short **"Generalization" section** (would become §13) covering the table
   above, honestly marking which rows are measured and which are reasoned.
   Include the corrected "hard and unbuilt, not impossible" wording — do not
   leave the overstatement on the record.
4. Rebuild: `cd docs/paper && pdflatex main && pdflatex main`
   (currently 19 pages, 0 undefined refs, 5 minor overfull boxes).
5. Root-cause the Mia installer spin, if it is ever worth it. Characterised but
   not fixed: main thread parked in `NtWaitForSingleObject`, a worker spinning in
   `NtFreeVirtualMemory`, srep helper never spawned, read offset frozen at byte
   31 of `fg-01.bin`. The defect is in the ISDone/Inno layer *above* unarc —
   proven because the identical `unarc.dll` and the identical helpers work fine
   when driven directly by `arcx32.exe`. Low priority: §6 already gets the game.
6. Optional, cheap, high value: run `drmcheck.py` over more PEs to widen the
   control set — `HV-StartGame.exe` (the hypervisor loader), the Steam DLLs, and
   anything under `/mnt/win-os/Program Files`. Every clean PE added strengthens
   the "zero RWX sections in clean software" claim, which is now the primary
   structural test.
7. Optional, expensive: install a second D3D12 title on the Linux side to test
   whether the vkd3d-proton 3.0.1 result reproduces. This is the only way to
   move the §11 row from "high by construction" to "measured."

**Standing constraint:** do not write new `.tex` prose until the user says so.
The corrections above are recorded here on purpose, staged and ready, not folded
into the paper yet.

### Tools
- `~/re/tools/drmcheck.py` — §4 procedure on any PE. `drmcheck.py <exe> [exe…]`
- `~/re/tools/fginstall.sh` — **NEW.** Game-agnostic §5 installer path. Both
  fixes applied automatically; `arc.ini` carved out of the installer itself.
  `fginstall.sh -s <setup.exe> -t <target-dir>`. Generalized from `install007.sh`.
  *Works as designed; the underlying method does not — see Finding 11.*
- `~/re/tools/fgextract.sh` — **NEW.** Game-agnostic §6 direct-unarc path, which
  is the one that works. `fgextract.sh -r <repack-dir> -o <out-dir> 01 02 …`
  Stages the repack's **own** helpers so the test stays honest.
- `~/re/tools/clspatch.py` — the live `Global\` patcher. Must run concurrently.
- `~/re/tools/arcx32.exe` — 32-bit `LoadLibrary` harness for `unarc.dll`.
- `~/re/tools/007-mkproton.sh` — Proton variant builder (game-agnostic)
- `~/re/tools/pescan.py` — older sections/entropy/imports dump

**Technique note — measuring progress.** Output file size is a *useless* signal
for unarc: it creates the target at full or zero size and fills it out of order.
The true signal is the read offset on the input container,
`/proc/<pid>/fdinfo/<fd>` for the fd pointing at `fg-01.bin`. That is what
exposed Mia's freeze at **byte 31**. Flat RSS plus `wchan` of `0` distinguishes a
spin from slow work. `eu-stack -p <pid>` needs `sudo` on this machine —
`/proc/sys/kernel/yama/ptrace_scope` is `1`.

**Missing on this machine:** `capstone` (Python) and `ndisasm`. Disassembly was
done with `objdump -D -b binary -m i386:x86-64 -M intel` over a raw extracted
section blob. That works but linear-sweeps, so it can misdecode mid-stream —
trust it at a known-good boundary (offset 0 of `.text`) and not in the middle.

### Specimens
- `/mnt/win-os/007 First Light/Retail/007FirstLight.exe` — clean baseline,
  64,228,744 B, md5 `3e0c3e10a9fdb15397f5bc50aeb5e09b`
- `/mnt/win-os/Games/Black Myth - Wukong/b1/Binaries/Win64/b1-Win64-Shipping.exe`
  — Denuvo control, 728,458,376 B, md5 `c7dae1acb6df82a1d591bd13ca1a9154`
- `/home/shawn/Downloads/New Folder/Returning_to_Mia_--_fitgirl-repacks.site_--_`
  — third title, 14 GB, `setup.exe` present, **tested 2026-08-20**. All 7 bins
  md5-verified intact before any conclusion was drawn about the installer.
- `/mnt/win-os/miaraw` — the §6 output, 18 GB, the working game. Contains the
  native Linux build under `lib/py3-linux-x86_64`.
- `/mnt/win-os/Games/ReturningToMia` — the **failed** §5 output, 3.0 MB, with a
  0-byte `.rpa`. Keep it: it is the evidence for Finding 11/12, not junk.

### Files
- `docs/paper/main.tex` + `sec1..sec13` — the paper, builds clean
- `docs/paper/007-first-light-linux-case-study.pdf` — 19 pages
