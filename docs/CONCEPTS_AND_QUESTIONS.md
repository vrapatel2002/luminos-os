# Concepts & Questions
# [CHANGE: claude-code | 2026-08-27]

Questions Shawn has actually asked, and the answers, kept here rather than left in a chat log that
disappears. Written to be read cold, months later. If a question turned out to rest on a wrong
assumption, the wrong assumption is stated plainly — that is the useful part.

---

## Q1 — "the game was running on 3gb vram, why? where is the rest? things should be using all the VRAM no matter what."

Asked 2026-08-27, about 007 First Light on the RTX 4050 (6141 MiB).

### The premise is wrong, and it is worth being precise about why

A program does not take all the VRAM because there is VRAM to take. It allocates **what the scene
in front of you needs** — the textures, meshes, shadow maps and render targets actually being
drawn — and nothing more. Unused VRAM is not wasted; it is headroom.

The comparison that makes this click: system RAM behaves the same way. A text editor on a 64 GB
machine does not use 64 GB. Nobody finds that alarming.

**Where the intuition comes from, and where it is right:** on consoles, and in some engines,
there *is* a texture-streaming pool sized to fill available memory, because unused VRAM genuinely
buys nothing. That is a **quality setting**, not automatic behaviour, and it is set from inside the
game's own graphics menu. If you want the card fuller, that is the lever — and the payoff is
sharper textures, not more frames.

### What was actually measured, 2026-08-27

| moment | VRAM used | note |
|---|---|---|
| before launch | 3 MiB of 6141 | card idle, 5798 free |
| game at title screen | 3047 MiB | first reading |
| +2 min | 3071 MiB | climbing — streaming in, not pinned |
| +5 min, steady | 3093 MiB | flat at the menu |

**3 GB was the title screen.** A menu with one character model and a background does not need level
geometry. It is not the gameplay figure, and it is not a ceiling.

Evidence that nothing was capping it:
- `~/re/007/dxvk.conf` contains two lines, `dxgi.hideNvidiaGpu` and `dxgi.nvapiHack`. **No memory
  cap.**
- No `DXVK_*` or `VKD3D_*` memory limit in the launcher.
- 3048 MiB sat free and unclaimed the whole time. A capped allocator does not leave the card half
  empty; it presses against its limit.

### "I think it's Dolphin holding the rest — why is it not getting kicked off? We coded that way."

**Dolphin was not on the card at all.** Verified three independent ways on every launch:

- `luminos-gpu-yield` printed `no model on the card - nothing to park`.
- `nvidia-smi --query-compute-apps` returned an empty list before launch.
- 5798 of 6141 MiB were free before Proton started.

The arbiter was not failing to kick Dolphin off. It had nothing to kick — **HIVE loads models
lazily**, only when someone actually sends a message, precisely so the dGPU can runtime-suspend
instead of being held awake (BUG-103). If nobody has chatted, no model is resident.

So the code works. It just had nothing to do, and reported exactly that.

### The real gap the question exposed

The instinct behind the question was sound even though the specific suspicion was not. The arbiter
parks a model when a game **launches** and is never consulted again — so nothing prevented a model
loading *during* a game. Chatting from the phone mid-session would have tried to fit ~5718 MiB into
the 2708 MiB the game left.

Closed as **BUG-143**: `hive-start-model.sh` now checks free VRAM before loading and refuses,
naming whatever holds the card. See `docs/BUGS.md`.

**Takeaway:** the 3 GB was never the bug. The question found a different, real one.
