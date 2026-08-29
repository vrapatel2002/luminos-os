#!/bin/bash
# [CHANGE: claude-code | 2026-08-20] Launcher for the hand-rebuilt 007 First Light.
#
#   007              -> RTX 4050 (default since BUG-137 was fixed; this WORKS).
#                       Parks the HIVE model for the duration and puts it back
#                       when you quit - see "TAKING THE CARD" below.
#   007 --igpu       -> AMD Radeon 780M instead. Also works. Much less power,
#                       and it leaves the HIVE model alone (shared system RAM).
#   007 --keep-model -> do NOT park the HIVE model. Expect a black screen or an
#                       outright failure if it is holding the card.
#   007 --debug      -> full Wine logging instead of WINEDEBUG=-all
#   007 --res=WxH    -> virtual desktop size (default: the desktop WORK AREA from
#                       _NET_WORKAREA - 2760x1800 here, not the panel's 2880x1800.
#                       Asking for more than KWin will give is BUG-138: a black
#                       screen with working audio on NVIDIA. See below.)
#
# BUG-142 - THE BLACK SCREEN THAT KEPT COMING BACK. [2026-08-27]
# It was never a graphics bug. It is a LEFTOVER PROCESS bug.
#
# What is actually happening, measured, not guessed:
#   `explorer.exe /desktop` does not reliably exit when the game does. One was
#   observed alive 17 minutes after its game was gone, still owning a
#   fullscreen X window titled "Wine Desktop", class steam_proton. The next
#   launch makes a SECOND window with the same title and class. KWin ends up
#   with _NET_ACTIVE_WINDOW pointing at a window it keeps unmapped, and after
#   that every launch comes up with _NET_WM_STATE_HIDDEN set - INCLUDING
#   launches made after the stale process has been killed, because the wedged
#   state is in KWin, not in Wine.
#   The game itself is fine. It renders. Audio plays. The GPU is busy. The
#   window it renders into is Unviewable because its parent is Unmapped, so
#   not one frame ever reaches the screen.
#
# That is exactly the reported symptom: "every time you fix it I can play, I
# restart and it stops working". The restart IS the trigger. It also explains
# why it looked intermittent for two sessions - whether a run is black depends
# on whether the PREVIOUS run left explorer.exe behind, which nothing in the
# log or the run itself records.
#
# HOW TO TELL THE TWO APART IN ONE COMMAND - xprop -id <win> _NET_WM_STATE:
#   rendering : MAXIMIZED_VERT, MAXIMIZED_HORZ, FULLSCREEN, FOCUSED
#   black     : the same list PLUS _NET_WM_STATE_HIDDEN
# (xwininfo, xdotool and wmctrl are NOT installed on this box. xprop is.)
#
# THE CURE, in order of importance:
#   1. wine_teardown() before AND after every attempt. Never start on top of an
#      old session, never leave one behind. This is the fix; the rest is net.
#   2. A watchdog that notices _NET_WM_STATE_HIDDEN and ends the attempt in
#      ~40s instead of leaving a black window up forever.
#   3. Attempt 2: a clean restart. Measured to work - a black run and the
#      rendering run right after it differed by nothing else.
#   4. Attempt 3: the 780M, which has never shown this. Slower, renders.
#   5. VKD3D_DEBUG=err always on, so the OTHER way this can go black (a
#      swapchain that never gets created) is in the log instead of invisible.
#
# RULED OUT by direct experiment, do not spend a session on these again:
# NVIDIA Streamline/DLSS/NVAPI; the game's saved settings and profile; the
# vkd3d cache; driver/kernel mismatch; winewayland vs winex11; the virtual
# desktop size (2880x1800 and 2560x1440 both render); the KWin fullscreen rule
# (black WITH it and WITHOUT it, rendering WITH it and WITHOUT it - it is not
# the variable); suspend/resume.
#
# BUG-137 IS FIXED - and the fix is one number. GE-Proton10-34 ships a
# vkd3d-proton that generates SPIR-V which segfaults NVIDIA's shader compiler
# (libnvidia-glvkspirv.so + 0x346fd8, nine threads, one address). vkd3d-proton
# 3.0.1 does not. Same Wine, same DXVK, same prefix, same driver - only the
# D3D12-to-Vulkan translator changed, and the RTX 4050 went from 9 invisible
# assert dialogs at 0% GPU to the game running at 100% and 2070 MiB of VRAM.
#
# So GE below is NOT stock GE-Proton10-34. It is GE-Proton10-34 with vkd3d
# 3.0.1 dropped in, built by ~/re/tools/007-mkproton.sh, and it has its own
# prefix. Both were verified on BOTH GPUs before this file was changed.
#
# Everything below was proven by running it. The four non-obvious parts:
#
#  1. Proton, not system Wine. `wine` 11.14 dies outright on the same fault the
#     Proton build survives; and only Proton's tree has a matching
#     VKD3D-Proton + winevulkan pair. We invoke `proton run`, which needs both
#     STEAM_COMPAT_* variables set or it refuses to start.
#  2. Virtual desktop. On Optimus the dGPU has no monitor attached and DXVK's
#     dxgi divides by zero computing a refresh rate from an empty display mode;
#     the iGPU path needs it too or the game gets no window. Supplied by the
#     prefix registry, NOT the command line - `proton run` has no
#     `explorer /desktop=` equivalent. See PREFIX REGISTRY below.
#  3. One Proton, one prefix, two GPUs. Do NOT point this at
#     ~/re/007/protondata: that prefix belongs to stock GE-Proton10-34 and a
#     Proton prefix upgrade is one-way. Keeping them separate means stock
#     GE-Proton10-34 stays a working fallback that costs nothing.
#  4. radeon_icd.json - NOT radeon_icd.x86_64.json, which does not exist on Arch.
#     luminos-gpu-launch:65 carried that stale path until 2026-08-28; fixed as
#     BUG-144, so this is now a note about why the name matters, not a warning
#     about a live bug elsewhere.
#
# PREFIX REGISTRY - already applied; restore with these two lines if the
# prefix is ever rebuilt:
#   wine reg add 'HKCU\Software\Wine\Explorer'          /v Desktop /d Default   /f
#   wine reg add 'HKCU\Software\Wine\Explorer\Desktops' /v Default /d 1920x1080 /f
#
# UNDO, in one line: set GPU=igpu below, or run `007 --igpu`. To go all the way
# back, set GE to .../GE-Proton10-34 and COMPAT_DATA to ~/re/007/protondata -
# both are untouched and still work.

set -u

GE="$HOME/.local/share/Steam/compatibilitytools.d/GE-Proton10-34-vkd3d301"
GAME_DIR="/mnt/win-os/007 First Light/Retail"
GAME_EXE="007FirstLight.exe"
COMPAT_DATA="$HOME/re/007/pfx-GE-Proton10-34-vkd3d301"
DXVK_CONF="$HOME/re/007/dxvk.conf"
LOG="$HOME/re/007/last-run.log"

# RES is resolved AFTER the graphical session is found - see "virtual desktop
# size" below. It needs DISPLAY, so it cannot live up here.
RES=""

GPU=nvidia
WINEDEBUG_VAL="-all"
KEEP_MODEL=0
for arg in "$@"; do
  case "$arg" in
    --igpu|--amd)  GPU=igpu ;;
    --nvidia)      GPU=nvidia ;;
    --keep-model)  KEEP_MODEL=1 ;;
    --debug)       WINEDEBUG_VAL="" ;;
    --res=*)       RES="${arg#--res=}" ;;
    -h|--help)     sed -n '2,14p' "$0"; exit 0 ;;
  esac
done

die() { echo "007: $*" >&2; command -v notify-send >/dev/null && notify-send "007 First Light" "$*" --icon=dialog-error; exit 1; }

# ---- preflight: fail loudly here rather than silently later ----------------
[ -f "$GAME_DIR/$GAME_EXE" ]   || die "game not found at $GAME_DIR/$GAME_EXE"
[ -x "$GE/proton" ]            || die "GE-Proton10-34 missing at $GE"
[ -d "$COMPAT_DATA/pfx" ]      || die "proton prefix missing: $COMPAT_DATA/pfx"
[ -f "$DXVK_CONF" ]            || die "dxvk config missing: $DXVK_CONF"

# ---- resolve the graphical session ----------------------------------------
# Only if we were not started from inside it (e.g. launched by an agent, a
# systemd unit, or a bare TTY). NEVER trust this script's own inherited env to
# describe the session when the vars are absent - ask the running desktop.
if [ -z "${DISPLAY:-}" ] || [ -z "${XAUTHORITY:-}" ]; then
  for p in $(pgrep -x plasmashell) $(pgrep -x kwin_wayland) $(pgrep -x Hyprland); do
    [ -r "/proc/$p/environ" ] || continue
    while IFS= read -r -d '' kv; do
      case "$kv" in
        DISPLAY=*)          [ -z "${DISPLAY:-}" ]          && export "$kv" ;;
        XAUTHORITY=*)       [ -z "${XAUTHORITY:-}" ]       && export "$kv" ;;
        XDG_RUNTIME_DIR=*)  [ -z "${XDG_RUNTIME_DIR:-}" ]  && export "$kv" ;;
      esac
    done < "/proc/$p/environ"
    [ -n "${DISPLAY:-}" ] && [ -n "${XAUTHORITY:-}" ] && break
  done
fi
# The xauth cookie filename is random per login, so glob for it as a last resort.
if [ -z "${XAUTHORITY:-}" ]; then
  for f in "${XDG_RUNTIME_DIR:-/run/user/$(id -u)}"/xauth_*; do
    [ -f "$f" ] && export XAUTHORITY="$f" && break
  done
fi
[ -n "${DISPLAY:-}" ] || die "no graphical session found - run this from your desktop"

# ---- virtual desktop size --------------------------------------------------
# BUG-138. This MUST be the WORK AREA, not the panel's native mode.
#
# The panel is 2880x1800 physical (KDE scale 2 = 1440x900 logical; XWayland is
# unscaled, so Wine works in physical pixels). But Caelestia's left bar reserves
# an exclusive zone of 60 logical = 120 physical px, so the largest window KWin
# will ever hand out is 2760x1800:
#     xprop -root _NET_WORKAREA         -> 120, 0, 2760, 1800
#     xprop -root _NET_DESKTOP_GEOMETRY -> 2880, 1800
#
# Asking for 2880x1800 anyway used to be merely cosmetic. On NVIDIA it is fatal:
# nvidia reports minImageExtent == maxImageExtent == currentExtent for a surface,
# so the swapchain must match the window EXACTLY. vkd3d-proton creates the
# 2880x1800 swapchain once, then every recreate-in-present fails with
#     Failed to create swapchain, vr -13     (VK_ERROR_UNKNOWN)
# forever - 894 times in 68 seconds - so no frame is ever presented. Audio plays,
# the GPU sits at 100%, the screen is black. RADV does NOT clamp, which is the
# whole reason the --igpu path never showed this.
#
# THE WINDOW IS ALSO WINDOWED WITHOUT HELP. A Wine virtual desktop is a perfectly
# ordinary window: KWin gives it a titlebar and parks it beside the bar. So there
# is a KWin rule to go with this, in ~/.config/kwinrulesrc, matching the window
# TITLE "Wine Desktop" (not wmclass=steam_proton, which would hit every Proton
# game whether or not it wants this):
#     fullscreen=true  fullscreenrule=2      (2 = Force)
#     noborder=true    noborderrule=2
# Reload it with `qdbus org.kde.KWin /KWin reconfigure`.
#
# So: work area or full screen depending on that rule; panel mode as the last
# fallback (Hyprland, bare TTY, no xprop).
# Line 1 of drm/modes is the preferred mode. Test the CONTENT, not the file size:
# every sysfs file reports 4096 bytes whether or not it has anything in it, so
# `[ -s ]` matches the disconnected card1-eDP-1 connector first and yields "".
# Which of the two sizes is right depends on whether the KWin rule below is in
# force. With it, the "Wine Desktop" window is made genuinely fullscreen and gets
# the WHOLE screen (2880x1800) with no titlebar and the bar covered. Without it,
# the window is an ordinary one and the work area is the most it can ever get.
# Ask for the wrong one and you are back in BUG-138, so DETECT it - do not assume:
KWINRULE="Luminos: Wine virtual desktop is fullscreen"
FULLSCREEN_RULE=0
if pgrep -x kwin_wayland >/dev/null 2>&1 &&
   grep -qF "$KWINRULE" "${XDG_CONFIG_HOME:-$HOME/.config}/kwinrulesrc" 2>/dev/null; then
  FULLSCREEN_RULE=1
fi

if [ -z "$RES" ] && command -v xprop >/dev/null 2>&1; then
  if [ "$FULLSCREEN_RULE" = 1 ]; then
    _g=$(xprop -root _NET_DESKTOP_GEOMETRY 2>/dev/null | tr -d ' ' | cut -d= -f2)
    _w=$(echo "$_g" | cut -d, -f1); _h=$(echo "$_g" | cut -d, -f2)
  else
    _wa=$(xprop -root _NET_WORKAREA 2>/dev/null | tr -d ' ' | cut -d= -f2)
    _w=$(echo "$_wa" | cut -d, -f3); _h=$(echo "$_wa" | cut -d, -f4)
  fi
  case "$_w:$_h" in
    [1-9][0-9]*:[1-9][0-9]*) RES="${_w}x${_h}" ;;
  esac
fi
if [ -z "$RES" ]; then
  for _m in /sys/class/drm/card*-eDP-*/modes; do
    _r=$(head -1 "$_m" 2>/dev/null)
    case "$_r" in [0-9]*x[0-9]*) RES="$_r"; break ;; esac
  done
fi
RES="${RES:-1920x1080}"

# ---- keep the virtual desktop in step with --res ---------------------------
set_vdesk() {
  local cur
  cur=$(WINEPREFIX="$COMPAT_DATA/pfx" WINEDEBUG=-all "$GE/files/bin/wine" reg query \
          'HKCU\Software\Wine\Explorer\Desktops' /v Default 2>/dev/null | awk '/Default/{print $3}')
  [ "$cur" = "$1" ] && return 0
  WINEPREFIX="$COMPAT_DATA/pfx" WINEDEBUG=-all "$GE/files/bin/wine" reg add \
    'HKCU\Software\Wine\Explorer' /v Desktop /d Default /f >/dev/null 2>&1
  WINEPREFIX="$COMPAT_DATA/pfx" WINEDEBUG=-all "$GE/files/bin/wine" reg add \
    'HKCU\Software\Wine\Explorer\Desktops' /v Default /d "$1" /f >/dev/null 2>&1
}

# ---- BUG-142: leave no Wine session behind ---------------------------------
# [CHANGE: claude-code | 2026-08-27]
# THIS is the actual cure, and it is a cleanup, not a graphics setting.
# `explorer.exe /desktop` does NOT reliably die when the game does. Verified:
# one lived 17 minutes after its game was gone, still owning a fullscreen
# "Wine Desktop" window. The next launch then creates a SECOND fullscreen
# window with the same title and class, the two fight, KWin ends up with
# _NET_ACTIVE_WINDOW pointing at a window it keeps unmapped, and from then on
# every launch comes up hidden - including launches made after the stale
# process is gone, because the wedged state lives in KWin, not in Wine.
# That is precisely the reported symptom: "every time you fix it I can play, I
# restart and it stops working."
# So: never start a second Wine session on top of an old one, and never leave
# one behind. One line each side.
wine_teardown() {
  pgrep -x '007FirstLight.e' >/dev/null 2>&1 && return 0   # a game is running - hands off
  pgrep -x explorer.exe >/dev/null 2>&1 || pgrep -x wineserver >/dev/null 2>&1 || return 0
  WINEPREFIX="$COMPAT_DATA/pfx" WINEDEBUG=-all "$GE/files/bin/wineserver" -k >/dev/null 2>&1
  sleep 3
}

# Is the Wine desktop window wedged? Measured states, from real runs:
#   rendering : MAXIMIZED_VERT, MAXIMIZED_HORZ, FULLSCREEN, FOCUSED
#   black     : the same list PLUS _NET_WM_STATE_HIDDEN
#   alt-tabbed: HIDDEN, but NOT focused
#
# READ THIS BEFORE "IMPROVING" IT. _NET_WM_STATE_HIDDEN on its own is NOT the
# bug - KWin also sets it whenever another window is in front, which is what
# ALT-TAB does. A first version tested HIDDEN alone and killed a game that was
# rendering perfectly, three attempts running, because the screenshot tool used
# to check on it took focus. Anything that watches for HIDDEN alone will do the
# same to a player who tabs out to Discord.
#
# The signature is the CONTRADICTION: focused and hidden at the same time. A
# healthy compositor cannot produce that - if you have the input focus, nothing
# is on top of you. It is exactly what a wedged KWin does: it holds
# _NET_ACTIVE_WINDOW on a window it is refusing to map.
desktop_wedged() {
  command -v xprop >/dev/null 2>&1 || return 1   # cannot tell -> assume fine
  local w st
  for w in $(xprop -root _NET_CLIENT_LIST 2>/dev/null | sed 's/.*# //; s/,//g'); do
    xprop -id "$w" WM_CLASS 2>/dev/null | grep -q 'steam_proton' || continue
    st=$(xprop -id "$w" _NET_WM_STATE 2>/dev/null)
    case "$st" in *_NET_WM_STATE_HIDDEN*) ;; *) continue ;; esac
    case "$st" in *_NET_WM_STATE_FOCUSED*) return 0 ;; esac
  done
  return 1
}

cd "$GAME_DIR" || die "cannot enter $GAME_DIR"

export STEAM_COMPAT_CLIENT_INSTALL_PATH="$HOME/.local/share/Steam"
export STEAM_COMPAT_DATA_PATH="$COMPAT_DATA"

COMMON=(
  DISPLAY="$DISPLAY"
  XAUTHORITY="${XAUTHORITY:-}"
  XDG_RUNTIME_DIR="${XDG_RUNTIME_DIR:-/run/user/$(id -u)}"
  WINEDEBUG="$WINEDEBUG_VAL"
  DXVK_CONFIG_FILE="$DXVK_CONF"
  # BUG-142. NOT OPTIONAL, NOT DEBUG-ONLY. vkd3d ships with its log off, so when
  # dxgi_vk_swap_chain_recreate_swapchain_in_present_task gets vr -13
  # (VK_ERROR_UNKNOWN) back from vkCreateSwapchainKHR it retries forever and
  # silently. Audio plays, the GPU looks busy, nothing is ever presented, and the
  # log says NOTHING. That invisibility cost two whole sessions. One line of
  # output per failure is a cheap price for never having to guess again - and the
  # watchdog below reads it.
  #
  # MEASURED RATE, 2026-08-29: 13.1 failures/second. This file used to say "~100
  # times a second" - that was a guess, and it was wrong by 8x. It matters: a
  # detector tuned to 100/s would never have fired on the real thing.
  VKD3D_DEBUG=err
)

# ---- BUG-142: never hand the user a silent black screen --------------------
# [CHANGE: claude-code | 2026-08-27]
# The failure: vkCreateSwapchainKHR returns VK_ERROR_UNKNOWN on the NVIDIA
# XWayland surface and vkd3d retries it in the present task for as long as the
# game runs. It cannot recover on its own - there is no code path in vkd3d that
# gives up or tries different parameters - so once the first one fails the run
# is dead and only looks alive. The trigger is transient (it failed six times
# running, then stopped for fourteen launches with nothing changed), so this
# does not pretend to prevent it. It DETECTS it in under 4 seconds, kills the
# dead attempt, retries at the other candidate size, and if that fails too,
# hands the game to RADV, which has never once shown this bug.
# Under NO circumstances leave the user staring at black with working audio.
BLACKFLAG="$HOME/re/007/.swapchain-failed"

# Check (a) is a RATE detector, not a presence test. It used to be
#     grep -qs 'Failed to create swapchain' "$LOG"
# which fires on the FIRST failure ever written. That is wrong, and it was live:
# a single swapchain failure at startup is survivable and happens on healthy
# runs, so the old test would kill a game that was about to render fine. Found
# and measured 2026-08-29.
#
# What a real storm looks like (measured): 13.1 failures/second, sustained, for
# as long as the process lives, because vkd3d has no give-up path. What a
# survivable hiccup looks like: a burst that stops. So the signature is not
# "any failure", it is "failures that keep coming".
#
# The rule, validated against 15 healthy/edge captures with zero false fires and
# a 2.30 s time-to-detect on both a 12.6/s and a 95.8/s storm:
#     250 ms buckets, a 12-bucket (3.0 s) sliding window,
#     fire only when the window holds >= 30 failures AND >= 10 of its 12
#     buckets are non-empty.
# The second half is what rejects bursts: 30 failures in one spike leaves 11
# empty buckets and is ignored; 30 spread evenly cannot be anything but a storm.
#
# KNOWN AND ACCEPTED LIMITS, so nobody has to rediscover them:
#   - a burst with gaps under ~0.4 s will still fire. Judged correct: at that
#     density the run is not recovering either.
#   - a genuine storm slower than 10/s is missed BY DESIGN. The measured real
#     rate is 13.1/s with margin to spare; lowering the floor costs false fires.
SWAP_WINDOW_BUCKETS=12     # 12 x 250ms = 3.0s window
SWAP_MIN_TOTAL=30          # failures required inside the window
SWAP_MIN_ACTIVE=10         # of the 12 buckets, how many must be non-empty

# NOT `grep -c ... || echo 0`. grep -c PRINTS "0" and ALSO exits 1 when it finds
# nothing, so the `|| echo 0` fires too and the function returns two lines -
# "0\n0" - which blows up the very next $(( )) with an arithmetic syntax error.
# That exact bug was written here first and caught by the burst edge-case test.
# grep -c always prints a count when the file is readable; -s means a missing
# file prints nothing, which is what the ${n:-0} default is for.
swap_fail_count() {
  local n
  n=$(grep -cs 'Failed to create swapchain' "$LOG" 2>/dev/null)
  echo "${n:-0}"
}

black_watchdog() {
  local wedged=0 ticks=0 waited=0
  local prev cur delta ring total active b
  prev=$(swap_fail_count)
  ring=""

  while :; do
    # 250ms is the detector's resolution. The wedge check below still only runs
    # once every 4s (every 16th tick) - it is expensive and slow-moving.
    sleep 0.25
    ticks=$((ticks + 1))

    # ---- (a) swapchain storm, sampled every tick ----
    cur=$(swap_fail_count)
    delta=$((cur - prev))
    prev=$cur
    ring="$ring $delta"
    # keep only the last SWAP_WINDOW_BUCKETS readings
    while [ "$(echo $ring | wc -w)" -gt "$SWAP_WINDOW_BUCKETS" ]; do
      ring=$(echo $ring | cut -d' ' -f2-)
    done

    total=0; active=0
    for b in $ring; do
      total=$((total + b))
      [ "$b" -gt 0 ] && active=$((active + 1))
    done

    if [ "$(echo $ring | wc -w)" -eq "$SWAP_WINDOW_BUCKETS" ] \
       && [ "$total" -ge "$SWAP_MIN_TOTAL" ] \
       && [ "$active" -ge "$SWAP_MIN_ACTIVE" ]; then
      echo "007: swapchain storm - $total failures in ${SWAP_WINDOW_BUCKETS}x250ms, $active/$SWAP_WINDOW_BUCKETS buckets active - ending this attempt" >&2
      : > "$BLACKFLAG"
    fi

    # ---- (b) focused AND hidden, every 4s ----
    if [ $((ticks % 16)) -eq 0 ]; then
      waited=$((waited + 4))
      # see desktop_wedged. Give the window 30s to come up first, and want three
      # readings in a row, so a momentary state during map/unmap is not fatal.
      if [ "$waited" -ge 30 ] && desktop_wedged; then
        wedged=$((wedged + 1))
        if [ "$wedged" -ge 3 ]; then
          echo "007: the Wine desktop is focused but not on screen - ending this attempt" >&2
          : > "$BLACKFLAG"
        fi
      else
        wedged=0
      fi
    fi

    if [ -e "$BLACKFLAG" ]; then
      # -x on the exact comm. NEVER -f: the pattern would be in this loop's argv.
      pkill -x '007FirstLight.e' 2>/dev/null
      sleep 5
      pkill -x -KILL '007FirstLight.e' 2>/dev/null
      return 0
    fi
  done
}

# Returns 78 if the attempt died of BUG-142, otherwise the game's own exit code.
run_attempt() { # $1 = nvidia|igpu
  local rc wd
  rm -f "$BLACKFLAG"
  : > "$LOG"
  wine_teardown          # never start on top of a previous session
  black_watchdog & wd=$!
  if [ "$1" = nvidia ]; then
    # v2, never v1: v1 raises only the effective gid and bash drops it (BUG-102).
    # NOT `exec`: this script has to outlive the game to give the card back.
    dgpu-exec-v2 env "${COMMON[@]}" \
        DRI_PRIME=1 \
        VK_ICD_FILENAMES=/usr/share/vulkan/icd.d/nvidia_icd.json \
        __EGL_VENDOR_LIBRARY_FILENAMES=/usr/share/glvnd/egl_vendor.d/60_nvidia.json \
        "$GE/proton" run "./$GAME_EXE" >> "$LOG" 2>&1
  else
    env "${COMMON[@]}" \
        DRI_PRIME=0 \
        VK_ICD_FILENAMES=/usr/share/vulkan/icd.d/radeon_icd.json \
        __EGL_VENDOR_LIBRARY_FILENAMES=/usr/share/glvnd/egl_vendor.d/50_mesa.json \
        "$GE/proton" run "./$GAME_EXE" >> "$LOG" 2>&1
  fi
  rc=$?
  kill "$wd" 2>/dev/null; wait "$wd" 2>/dev/null
  # `proton run` can return while the game is still up. Restoring the model at
  # that moment would drop 5.7 GB back onto the card underneath a running game -
  # BUG-141 pointed the other way - so wait until the process is really gone.
  # comm truncates at 15 chars: "007FirstLight.exe" NEVER matches.
  while pgrep -x '007FirstLight.e' >/dev/null 2>&1; do sleep 5; done
  wine_teardown          # and never leave one behind
  [ -e "$BLACKFLAG" ] && return 78
  return $rc
}

if [ "$GPU" = "nvidia" ]; then
  command -v dgpu-exec-v2 >/dev/null || die "dgpu-exec-v2 missing - cannot reach the RTX 4050"
  echo "007: RTX 4050, ${RES}, log -> $LOG"

  # ---- TAKING THE CARD (BUG-141) -------------------------------------------
  # [CHANGE: claude-code | 2026-08-25]
  # The 4050's 6 GB is DEDICATED - it is not borrowed from system RAM the way
  # the 780M's is - so a resident HIVE model is not sharing the card, it is
  # holding it. Dolphin-8B at ctx 16384 sits on 5718 of 6141 MiB and leaves 73;
  # Vulkan then offers the game a device-local budget of 61.75 MiB against the
  # ~2100 MiB it needs, and it dies during device setup three lines into the log
  # with no error a human would recognise. Previously this script only PRINTED a
  # warning about it and started anyway.
  #
  # So: park the model, play, put it straight back.
  #
  # THE TRAP IS THE ENTIRE POINT. A crash, an Alt-F4, a Ctrl-C or a kill -TERM
  # must all still end with the model back on the card, because the phone chat
  # depends on it. "The game didn't start" is a far better outcome than "the
  # phone went dead hours ago and nobody knows why".
  YIELD=""
  give_back() { [ -n "$YIELD" ] && luminos-gpu-yield restore; YIELD=""; return 0; }
  if [ "$KEEP_MODEL" = 0 ] && command -v luminos-gpu-yield >/dev/null 2>&1; then
    YIELD=luminos-gpu-yield
    "$YIELD" yield || die "could not free the GPU - refusing to start into a black screen"
    trap give_back EXIT INT TERM HUP
  fi

  # Anything still holding the card after that is a user we do not manage.
  # This warning used to go to STDOUT ONLY - which does not exist when the game
  # is launched from the app menu or from Lutris, so the one message that
  # explained the failure was written to a closed file descriptor every time.
  # It is a notification now. The threshold is the game's real floor (~2100 MiB
  # measured), not the old 4500, so it fires when it actually means something.
  FREE=$(dgpu-exec-v2 nvidia-smi --query-gpu=memory.free --format=csv,noheader,nounits 2>/dev/null | tr -d ' ')
  case "$FREE" in
    ''|*[!0-9]*) : ;;
    *) if [ "$FREE" -lt 2200 ]; then
         HOLDERS=$(dgpu-exec-v2 nvidia-smi --query-compute-apps=pid,process_name,used_memory --format=csv,noheader 2>/dev/null)
         echo "007: only ${FREE} MiB of VRAM free - other GPU users are holding the rest:"
         printf '%s\n' "$HOLDERS" | sed 's/^/     /'
         notify-send "007 First Light" \
           "Only ${FREE} MiB of VRAM free. The game needs about 2100 MiB and will probably fail.
$HOLDERS" --icon=dialog-warning 2>/dev/null
       fi ;;
  esac

  notify-send "007 First Light" "Starting on NVIDIA RTX 4050" --icon=dialog-information 2>/dev/null

  set_vdesk "$RES"
  run_attempt nvidia; RC=$?

  # Attempt 2: a clean restart. run_attempt has just torn the Wine session
  # down, which is the recovery that was measured to work - a black run and the
  # rendering run that followed it differed by nothing else.
  if [ "$RC" = 78 ]; then
    echo "007: black screen detected - restarting from a clean Wine session"
    notify-send "007 First Light" \
      "Black screen detected. Cleaning up and restarting - this takes about a minute." \
      --icon=dialog-warning 2>/dev/null
    sleep 5
    run_attempt nvidia; RC=$?
  fi

  # Attempt 3: the 780M. RADV has never produced this failure. Slower, but it
  # PLAYS - which beats a black screen every time. Give the card back first:
  # the model is more use to him on the GPU than an idle 6 GB is.
  if [ "$RC" = 78 ]; then
    echo "007: NVIDIA is still coming up black - falling back to the 780M"
    give_back
    trap - EXIT INT TERM HUP
    notify-send "007 First Light" \
      "The RTX 4050 would not create a working swapchain (BUG-142). Running on the AMD 780M instead - lower frame rate, but it will render." \
      --icon=dialog-warning 2>/dev/null
    run_attempt igpu; RC=$?
  fi
  exit $RC
else
  echo "007: AMD Radeon 780M, ${RES}, log -> $LOG"
  notify-send "007 First Light" "Starting on AMD Radeon 780M" --icon=dialog-information 2>/dev/null
  set_vdesk "$RES"
  run_attempt igpu
fi
