#!/usr/bin/env bash
# phaseA.sh CAPTION_SUBSTR [SECONDS] — step 1 of luminos-focus: does a window stop costing compute when
# minimized (KWin sends xdg_toplevel suspended) vs merely covered? [CHANGE: claude-code | 2026-11-07]
set -u
export XDG_RUNTIME_DIR=/run/user/$(id -u) DBUS_SESSION_BUS_ADDRESS=unix:path=/run/user/$(id -u)/bus
C=${1:?caption}; T=${2:-20}; D=$(dirname "$0")
win="const v = workspace.windowList().filter(w => w.normalWindow && w.caption.indexOf('$C')>=0)[0];
     const o = workspace.windowList().filter(w => w.normalWindow && w.resourceClass=='com.anthropic.Claude')[0];"
k(){ "$D/kwin-eval.sh" "$win $1"; }
audio(){ pw-dump | python3 -c 'import json,sys
print("audio:", [ (o["id"],o["info"]["state"]) for o in json.load(sys.stdin) if (o.get("info") or {}).get("props",{}).get("media.class")=="Stream/Output/Audio"])'; }
k 'v.minimized=false; workspace.activeWindow=v;'; sleep 3; "$D/measure.sh" "A1 video focused+visible" $T; audio
k 'workspace.activeWindow=o;'; sleep 3; "$D/measure.sh" "A2 video COVERED by Claude" $T; audio
k 'v.minimized=true;'; sleep 3; "$D/measure.sh" "A3 video MINIMIZED" $T; audio
k 'v.minimized=false; workspace.activeWindow=v;'; sleep 3; "$D/measure.sh" "A4 video restored" $T; audio
