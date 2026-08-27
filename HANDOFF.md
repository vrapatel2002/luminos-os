# HANDOFF — BUG-142 FIXED: the 007 black screen was a leftover process, not a graphics bug
# [CHANGE: claude-code | 2026-08-27] — Response 4
Last updated: 2026-08-27 — Response 4

**Read this whole file before touching anything.**

Per AGENTS.md §0.2 there is exactly **one** HANDOFF.md, overwritten in place. The previous version
(Response 3, BUG-141 / the GPU arbiter) is at `git show HEAD:HANDOFF.md` once this is committed.

---

## Goal, in Shawn's words

> "bro fix this once in for all the game's video is visible its black evey time you fix it i can
> play i restart and it stops working find a permemant cure."

The load-bearing word is **restart**. He had already told us where the bug was; it took two
sessions to hear it.

---

## What it actually was

**A leftover `explorer.exe /desktop` from the previous run.** Not vkd3d, not the swapchain, not the
virtual desktop size, not the KWin rule, not VRAM, not DLSS.

Measured, 2026-08-27:

- `explorer.exe /desktop` does **not** reliably exit when the game does. pid 127547 started 17:19,
  its game was killed at ~17:20, and it was still alive at 17:36 owning a fullscreen X window
  titled `Wine Desktop`, class `steam_proton`.
- The next launch creates a **second** window with the same title and class.
- KWin ends up holding `_NET_ACTIVE_WINDOW` on a window it keeps unmapped. From then on every
  launch comes up with `_NET_WM_STATE_HIDDEN` — **including launches made after the stale process
  has been killed**, because the wedged state lives in KWin, not in Wine.
- The game was always fine. It renders, audio plays, the GPU sits at 99%. Its window is
  `Unviewable` because its **parent is `Unmapped`**, so not one frame ever reaches the screen:

  ```
  0x4600068  Unviewable  2880x1800                    <- the Vulkan surface
  0x5200001  Unviewable  2880x1800  007 First Light
  0x1e00007  Unmapped    2880x1800  Wine Desktop      <- the parent. nothing under it is visible
  0x359      Viewable    2880x1800                    <- root
  ```

That is why it looked intermittent for two sessions: whether a run is black depends on what the
**previous** run left behind, and nothing — not the log, not the run, not any tool — records that.
It is also why every earlier "fix" appeared to work. Each one happened to involve a teardown or a
long enough gap.

---

## The one command that tells the two apart

```bash
xprop -id <win> _NET_WM_STATE
```

| outcome   | `_NET_WM_STATE` |
|-----------|-----------------|
| rendering | `MAXIMIZED_VERT, MAXIMIZED_HORZ, FULLSCREEN, FOCUSED` |
| black     | **the same list plus `_NET_WM_STATE_HIDDEN`** |

**KWin's scripting API lies about this.** For a window the X server reports as `Unmapped`, KWin
reports `minimized=false fullscreen=true active=true hidden=false`, and neither setting
`w.minimized = false` nor sending a `_NET_ACTIVE_WINDOW` client message recovers it. Trust `xprop`
and `XGetWindowAttributes`, not the KWin script view.

`xwininfo`, `xdotool` and `wmctrl` are **not installed** on this box. `xprop` is. Two throwaway
ctypes/libX11 helpers were used for the parent-chain and map-state walks; they are in `/tmp` and
are not worth keeping — `xprop` covers the check that matters.

---

## The fix — `~/re/tools/007-run.sh`, installed to `/usr/local/bin/007`

1. **`wine_teardown()` — `wineserver -k` on the prefix before AND after every attempt.** Never
   start on top of an old session, never leave one behind. *This is the cure. The rest is safety
   net.* It declines to act while a game is actually running, so it cannot shoot a live session.
2. **`black_watchdog()`** polls `_NET_WM_STATE` during the run and ends the attempt in ~40 s if the
   desktop is wedged, instead of leaving a black window up forever. It waits 30 s before it starts
   looking and needs three readings in a row, so a momentary state during map/unmap is not fatal.

   **This watchdog was itself a bug on its first draft, and the trap is easy to fall back into.**
   It tested `_NET_WM_STATE_HIDDEN` on its own and killed a game that was rendering perfectly,
   three attempts running, all the way down to the iGPU fallback — because `HIDDEN` is *also* what
   KWin sets when another window is in front, and the screenshot tool used to check on the game
   took focus. As written it would have killed the game every time Shawn alt-tabbed.

   The signature is the **contradiction — `FOCUSED` and `HIDDEN` together.** Nothing healthy
   produces that: if you hold the focus, nothing is on top of you. A wedged KWin does exactly that,
   holding `_NET_ACTIVE_WINDOW` on a window it will not map. Alt-tab gives `HIDDEN` without
   `FOCUSED` and is ignored. Re-verified live: six deliberate focus-steals over 13 minutes, state
   never left `MAXIMIZED_VERT, MAXIMIZED_HORZ, FULLSCREEN, FOCUSED`, zero fires.
3. **Attempt 2 is a clean restart.** Measured to work: a black run and the rendering run right
   after it differed by nothing else.
4. **Attempt 3 is the 780M.** RADV has never shown this. Slower, but it renders — which beats a
   black screen. The BUG-141 model-restore runs *before* the fallback, via `give_back()`, so the
   card goes back to Dolphin rather than sitting idle. The iGPU branch is no longer `exec`, or the
   trap would not survive.
5. **`VKD3D_DEBUG=err` is always on now.** Not a debug flag — vkd3d ships with its log off, which
   is the only reason the second mechanism below stayed invisible for two sessions.

### The second, rarer mechanism — also real, also proven today

`vkCreateSwapchainKHR` returns `VK_ERROR_UNKNOWN` (`vr -13`) inside
`dxgi_vk_swap_chain_recreate_swapchain_in_present_task`, and vkd3d retries it ~100×/second for as
long as the game runs. **There is no give-up path in vkd3d**, so the first failure is fatal and the
run only *looks* alive. The watchdog greps for it as well as checking the window state.

---

## Verification (all screenshotted, pixel-checked, not inferred)

| run | condition | result |
|-----|-----------|--------|
| 17:30 | stale `explorer.exe` present | **ALL BLACK** (5,184,000 pure-black pixels) |
| 17:38 | stale process killed, KWin still wedged | **ALL BLACK** |
| 17:41 | clean teardown, KWin rule **off** | renders — "PRE-LOADING SHADERS 96%" |
| 17:44 | clean teardown, KWin rule **on** | renders |
| ×3    | back-to-back quit → relaunch, no cleanup | renders, renders, renders |
| final | **stale session deliberately planted first** | teardown killed it, **renders** |
| 19:18–19:31 | corrected watchdog, 6 deliberate focus-steals | renders throughout, **0 watchdog fires**, 0 swapchain errors |

Last frame captured: the title screen, "Press [F] to play".

A pure-black 2880x1800 capture is ~20 KB; a rendering one is 130 KB–2.4 MB. Do not judge by file
size alone — check the pixels:
```bash
python3 -c "from PIL import Image; im=Image.open('x.png').convert('RGB'); print(im.getcolors(20))"
```

Headless screenshot recipe (the session env has to be lifted from plasmashell):
```bash
P=$(pgrep -x plasmashell|head -1)
eval "$(sudo tr '\0' '\n' < /proc/$P/environ | grep -E '^(WAYLAND_DISPLAY|XDG_RUNTIME_DIR|DBUS_SESSION_BUS_ADDRESS)=' | sed 's/^/export /;s/=/="/;s/$/"/')"
spectacle -b -n -f -o /tmp/shot.png
```

---

## Ruled out by direct experiment. Do not spend another session on these.

NVIDIA Streamline/DLSS/NVAPI (`PROTON_DISABLE_NVAPI=1` moved VRAM 3304→2669 MiB, so it took
effect; the screen stayed black) · the game's saved settings and profile (whole `remote/` removed →
worked; restored → still worked) · the `vkd3d-proton.cache` · driver/kernel-module mismatch (they
match; no package upgrades since Aug 24) · winewayland vs winex11 (`winex11.drv` confirmed loaded)
· **the virtual desktop size** · **the BUG-138 KWin fullscreen rule** · suspend/resume ·
NVIDIA's ability to present an xcb swapchain at 2880x1800 (`vkcube --wsi xcb` works; the flag is
`--wsi xcb`, not `--xcb`).

**This corrects BUG-138.** Its stated cause — "asking for a virtual desktop larger than KWin will
give you" — did not survive testing: 2880x1800 renders with the fullscreen rule *disabled*, and
2560x1440 has gone black with it *enabled*. The size is not the deciding variable.

---

## Still open / next agent picks this up

- **`~/re/tools/007-run.sh` lives outside git.** It is the source of `/usr/local/bin/007` and the
  cure is in it. A home-directory loss takes the cure with it. Ask Shawn before copying it into the
  repo — two sources of truth for an installed binary is its own bug.
- **`luminos-game-mode`'s revert is defective.** It restored `platform_profile=quiet` instead of the
  recorded `balanced` and left `nvidia-powerd` active, and it leaves `game-mode.state` behind when
  it half-finishes. Its watcher was found inactive with the machine still in performance mode; it
  has been re-armed against the correct saved values, but the script itself is unfixed.
- **`luminos-train-mode` still watches with `pgrep -f`**, whose pattern is in its own argv, so it
  self-matches, never fires, and leaves the fans pinned and `nvidia-powerd` unmasked forever.
- **`007 --igpu` has not been re-verified** since the BUG-138 work. It is now attempt 3 of the
  fallback chain, so it matters more than it did.
- **The BUG-138 KWin rule lives only in `~/.config/kwinrulesrc`**, which a Plasma profile reset
  would silently delete. It is no longer load-bearing (see above) but it is still there.
- **Two commits are unpushed.** `git push` has never been authorised in this repo — ask first.
- `/tmp/007-remote.aside` and `/tmp/007-remote.fresh-working` are copies of his 007 save data,
  kept deliberately. `/tmp` clears on reboot; the originals are in place and verified working.

---

## REPLY TO MANAGEMENT

BUG-142 is fixed and verified on the screen, not inferred. The black screen was never a graphics
fault — it was an `explorer.exe /desktop` surviving the previous run and wedging KWin, which is
exactly why it came back "every time you fix it, I restart and it stops working". The launcher now
tears the Wine session down on both sides of every run, notices within ~40 s if the window comes up
hidden, restarts itself once, and falls back to the 780M rather than ever handing him a black
screen again. Six consecutive launches render, including three back-to-back restarts and one with a
stale session planted on purpose.

Two corrections to the record: BUG-138's stated root cause (virtual desktop size) is wrong, and
KWin's scripting API cannot be trusted to report whether a window is on screen.
