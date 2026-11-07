#!/usr/bin/env bash
# kwin-eval.sh 'JS' — run a one-shot KWin script, print what it print()s. [CHANGE: claude-code | 2026-11-07]
set -eu
export XDG_RUNTIME_DIR=/run/user/$(id -u) DBUS_SESSION_BUS_ADDRESS=unix:path=/run/user/$(id -u)/bus
tag="lfeval$$"; f=$(mktemp --suffix=.js)
printf 'print("%s-BEGIN");\ntry {\n%s\n} catch (e) { print("ERR " + e); }\nprint("%s-END");\n' "$tag" "$1" "$tag" > "$f"
since=$(date '+%Y-%m-%d %H:%M:%S')
id=$(qdbus6 org.kde.KWin /Scripting org.kde.kwin.Scripting.loadScript "$f" "$tag")
qdbus6 org.kde.KWin /Scripting/Script$id org.kde.kwin.Script.run >/dev/null
sleep 0.4
qdbus6 org.kde.KWin /Scripting org.kde.kwin.Scripting.unloadScript "$tag" >/dev/null || true
rm -f "$f"
journalctl --user -u plasma-kwin_wayland --since "$since" -o cat 2>/dev/null | sed -n "/$tag-BEGIN/,/$tag-END/p" | grep -v "$tag" | sed 's/^js: //'
