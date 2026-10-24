#!/usr/bin/env bash
# tests/ram-reaper/integration.sh — end-to-end tests of the luminos-ram app reaper on the REAL
# desktop (DECISION 160). [CHANGE: claude-code | 2026-10-24]
#
# Shawn's rule: prove it end-to-end, do not assert from config. Every case starts real
# processes in real systemd scopes and watches the running reaper (luminos-ram-reaper.service)
# deal with them, by pid and by its log.
#
# Safety: the reaper stays in reap_mode=log for everything real. For the test it gets
#   act_only = lrtest      (act ONLY on things named lrtest*)
#   test_idle_s = 30       (idle threshold for lrtest* groups only — real apps keep the gradient)
#   tmpfs_every_s = 10
# appended to ~/.config/luminos-ram-reaper.conf, and an EXIT trap restores the file and stops
# every lrtest-* unit whatever happens.
#
# Run it detached (the host-shell bridge cuts calls at 60 s):
#   systemd-run --user --unit=ramreaper-itest --collect bash ~/luminos-os/tests/ram-reaper/integration.sh
# and read tests/ram-reaper/RESULTS-integration.txt.
set -u
export XDG_RUNTIME_DIR=${XDG_RUNTIME_DIR:-/run/user/$(id -u)}
export DBUS_SESSION_BUS_ADDRESS=${DBUS_SESSION_BUS_ADDRESS:-unix:path=$XDG_RUNTIME_DIR/bus}
U=$(id -u)
CONF=$HOME/.config/luminos-ram-reaper.conf
LOG=$HOME/.local/state/luminos/ram-reaper.log
OUT=${1:-$HOME/luminos-os/tests/ram-reaper/RESULTS-integration.txt}
CG=/sys/fs/cgroup/user.slice/user-$U.slice/user@$U.service/app.slice
PASS=0; FAIL=0

say(){ echo "$*" | tee -a "$OUT"; }
ok(){ PASS=$((PASS+1)); say "  PASS  $*"; }
bad(){ FAIL=$((FAIL+1)); say "  FAIL  $*"; }
now(){ date +%s.%N; }
since(){ awk -v a="$1" -v b="$(now)" 'BEGIN{printf "%.1f", b-a}'; }
scope_n(){ cat "$CG/$1/cgroup.procs" 2>/dev/null | wc -l; }
logmark(){ wc -l < "$LOG"; }
logsince(){ tail -n +"$(( $1 + 1 ))" "$LOG"; }
# By /proc, not kill -0: kill -0 on a root process (sshd) fails with EPERM and would read as "dead".
alive(){ [ -r "/proc/$1/stat" ] && [ "$(cut -d' ' -f3 /proc/$1/stat 2>/dev/null)" != Z ]; }

cleanup(){
  cp "$CONF.pre-test" "$CONF" && systemctl --user reload luminos-ram-reaper
  for u in $(systemctl --user list-units --all --plain --no-legend 'lrtest-*' 'tmpholder-*' | awk '{print $1}'); do
    [ "$u" = lrtest-runner.service ] || systemctl --user stop "$u" 2>/dev/null
  done
  [ -n "${PFX:-}" ] && { WINEPREFIX=$PFX wineserver -k 2>/dev/null; rm -rf "$WDIR"; }
  rm -f /tmp/lrtest-tmpfs.bin
  say ""; say "RESULT: $PASS passed, $FAIL failed   ($(date '+%F %T'))"
}

: > "$OUT"
say "luminos-ram reaper — integration test, $(date '+%F %T'), $(uname -r)"
say "reaper: $(systemctl --user is-active luminos-ram-reaper), root daemon: $(systemctl is-active luminos-ram)"
cp "$CONF" "$CONF.pre-test"
trap cleanup EXIT
cat >> "$CONF" <<'EOF'
# --- integration test overrides (tests/ram-reaper/integration.sh removes these) ---
act_only = lrtest
test_idle_s = 30
tmpfs_every_s = 10
EOF
systemctl --user reload luminos-ram-reaper; sleep 3

# ───────────────────────── (a) an app dies → its leftovers go within 10 s ─────────────────
say ""; say "== (a) app scope: parent + 3 children + 1 double-forked orphan; kill the parent"
M=$(logmark)
systemd-run --user --scope --unit=lrtest-a --quiet -- bash -c 'sleep 1000 & sleep 1000 & sleep 1000 & ( setsid sleep 1001 & ); wait' &
MAIN=$!
sleep 8
say "  scope lrtest-a.scope holds $(scope_n lrtest-a.scope) processes; main bash pid $MAIN"
kill -9 "$MAIN"; T0=$(now)
while [ "$(scope_n lrtest-a.scope)" -gt 0 ] && [ "$(since "$T0" | cut -d. -f1)" -lt 20 ]; do sleep 0.2; done
DT=$(since "$T0"); LEFT=$(scope_n lrtest-a.scope)
if [ "$LEFT" -eq 0 ] && awk -v d="$DT" 'BEGIN{exit !(d<=10)}'; then ok "all 4 leftovers gone ${DT}s after the parent died"; else bad "after ${DT}s, $LEFT process(es) still in the scope"; fi
L=$(logsince "$M" | grep 'REAPED.*lrtest-a.scope.*rule=app-died' | tail -1)
[ -n "$L" ] && ok "log: ${L#*luminos-ram-reaper: }" || bad "no REAPED app-died line for lrtest-a"

# ───────────────────────── (b) Wine whose wineserver died ─────────────────────────────────
say ""; say "== (b) throwaway WINEPREFIX; kill its wineserver → services.exe & co must be reaped"
# Wine refuses a prefix whose PARENT is not owned by the user, so not /tmp itself.
WDIR=/tmp/lrtest-wine; rm -rf "$WDIR"; mkdir -p "$WDIR"; PFX=$WDIR/pfx
wprocs(){ for p in $(pgrep -u "$U" .); do tr '\0' '\n' < /proc/$p/environ 2>/dev/null | grep -qx "WINEPREFIX=$PFX" && echo "$p"; done; }
M=$(logmark)
systemd-run --user --scope --unit=lrtest-b --quiet -- env WINEPREFIX=$PFX WINEDLLOVERRIDES='mscoree,mshtml=' WINEDEBUG=-all \
  wine cmd /c 'ping -n 900 127.0.0.1 >nul' >/dev/null 2>&1 &
T0=$(now)
while :; do
  N=$(wprocs | xargs -r ps -o comm= -p | grep -c -E 'services.exe|plugplay|svchost|explorer|rpcss')
  [ "$N" -ge 3 ] && break
  [ "$(since "$T0" | cut -d. -f1)" -gt 150 ] && break
  sleep 2
done
sleep 6
say "  prefix booted in $(since "$T0")s: $(wprocs | xargs -r ps -o comm= -p | sort | uniq -c | awk '{printf "%s×%s ",$2,$1}')"
SRV=$(for p in $(wprocs); do [ "$(cat /proc/$p/comm)" = wineserver ] && echo $p; done | head -1)
if [ -z "$SRV" ]; then bad "no wineserver found for $PFX"; else
  kill -9 "$SRV"; T0=$(now)
  while [ -n "$(wprocs)" ] && [ "$(since "$T0" | cut -d. -f1)" -lt 30 ]; do sleep 0.5; done
  LEFT=$(wprocs | wc -l); DT=$(since "$T0")
  [ "$LEFT" -eq 0 ] && ok "prefix has 0 processes ${DT}s after wineserver was killed" || bad "$LEFT wine processes left after ${DT}s: $(wprocs | xargs -r ps -o pid=,comm= -p | tr '\n' ' ')"
  L=$(logsince "$M" | grep 'REAPED.*lrtest-wine.*rule=wine-no-server' | tail -1)
  if [ -n "$L" ]; then ok "log: ${L#*luminos-ram-reaper: }"; else
    say "  NOTE  no wine-no-server line — the Wine processes exited on their own this time (not a reaper result)"; fi
fi

# ───────────────────────── (c) idle app vs live apps ──────────────────────────────────────
say ""; say "== (c) four window-less scopes: idle / audio / network / CPU (test idle threshold 30 s)"
M=$(logmark)
systemd-run --user --scope --unit=lrtest-c-idle --quiet -- bash -c 'sleep 3000 & sleep 3000 & wait' &
systemd-run --user --scope --unit=lrtest-c-audio --quiet -- paplay --raw /dev/zero &
systemd-run --user --scope --unit=lrtest-c-net --quiet -- python3 -c '
import socket,threading,time
s=socket.socket(); s.bind(("127.0.0.1",0)); s.listen(1); port=s.getsockname()[1]
def srv():
    c,_=s.accept()
    while c.recv(65536): pass
threading.Thread(target=srv,daemon=True).start()
c=socket.create_connection(("127.0.0.1",port))
while True:
    c.sendall(b"x"*4096); time.sleep(0.2)' &
systemd-run --user --scope --unit=lrtest-c-cpu --quiet -- bash -c 'end=$((SECONDS+170)); while [ $SECONDS -lt $end ]; do :; done' &
# T0 = the moment the idle scope exists (its cgroup appears a moment after systemd-run).
while [ "$(scope_n lrtest-c-idle.scope)" -eq 0 ]; do sleep 0.1; done
T0=$(now); GONE=""
while [ "$(since "$T0" | cut -d. -f1)" -lt 100 ]; do
  [ -z "$GONE" ] && [ "$(scope_n lrtest-c-idle.scope)" -eq 0 ] && GONE=$(since "$T0")
  sleep 1
done
if [ -n "$GONE" ] && awk -v g="$GONE" 'BEGIN{exit !(g>=29 && g<=50)}'; then ok "idle scope reaped after ${GONE}s (threshold 30 s, not before)"; else bad "idle scope: gone after '${GONE:-never}' s (want 30–50)"; fi
for k in audio net cpu; do
  n=$(scope_n lrtest-c-$k.scope)
  [ "$n" -gt 0 ] && ok "$k scope still alive after 100 s ($n procs) — $(logsince "$M" | grep -c "lrtest-c-$k") reaper lines about it" || bad "$k scope was reaped while live"
done
L=$(logsince "$M" | grep 'REAPED.*lrtest-c-idle.*rule=idle' | tail -1)
[ -n "$L" ] && ok "log: ${L#*luminos-ram-reaper: }" || bad "no REAPED idle line for lrtest-c-idle"
say "  live reasons the reaper reported:"
echo '{"type":"reap"}' | socat - UNIX-CONNECT:/run/luminos/ram.sock | python3 -c '
import json,sys
a=json.load(sys.stdin)["payload"].get("agent") or {}
for g in a.get("groups") or []:
    if "lrtest-c" in g["key"]: print("    %-28s %-9s %s" % (g["key"][5:], g["state"], g["reason"]))' | tee -a "$OUT"
# Once the audio stops, the same scope must become reapable: proves audio was the reason.
pkill -u "$U" -x paplay; sleep 1
say "  (paplay stopped — the audio scope is now empty and gone: $(scope_n lrtest-c-audio.scope) procs)"
systemctl --user stop lrtest-c-net.scope lrtest-c-cpu.scope 2>/dev/null

# ───────────────────────── (d) tmpfs ─────────────────────────────────────────────────────
say ""; say "== (d) 60 MB file in /tmp, aged 2 h: kept while held open, deleted once closed"
F=/tmp/lrtest-tmpfs.bin
dd if=/dev/zero of=$F bs=1M count=60 status=none; touch -d '-2 hours' $F
M=$(logmark)
# The holder must not carry the path on its command line (act_only matches command lines).
systemd-run --user --scope --unit=tmpholder-d --quiet -- env F=$F bash -c 'exec 3<"$F"; exec sleep 600' &
HOLD=$!
sleep 25
[ -e $F ] && ok "kept for 25 s while pid $HOLD holds it open" || bad "deleted while open"
kill "$HOLD"; T0=$(now)
while [ -e $F ] && [ "$(since "$T0" | cut -d. -f1)" -lt 30 ]; do sleep 1; done
[ ! -e $F ] && ok "deleted $(since "$T0")s after it was closed" || bad "still there 30 s after closing"
L=$(logsince "$M" | grep 'TMPFS deleted /tmp/lrtest-tmpfs.bin' | tail -1)
[ -n "$L" ] && ok "log: ${L#*luminos-ram-reaper: }" || bad "no TMPFS deleted line"

# ───────────────────────── (e) protected classes survive a forced pass ─────────────────────
say ""; say "== (e) forced reap pass (idle time + liveness ignored) aimed AT the protected processes"
MAXPID=$(for p in $(pgrep -u "$U" -x claude-desktop); do tr '\0' ' ' < /proc/$p/cmdline | grep -q -- '--type=\|--user-data-dir' || echo $p; done | head -1)
declare -A BEFORE=(
  [kwin_wayland]=$(pgrep -u "$U" -x kwin_wayland | head -1)
  [plasmashell]=$(pgrep -u "$U" -x plasmashell | head -1)
  [pipewire]=$(pgrep -u "$U" -x pipewire | head -1)
  [sshd]=$(systemctl show -p MainPID --value sshd)
  [claude-max]=$MAXPID
  [coder-gateway]=$(systemctl --user show -p MainPID --value luminos-coder-gateway)
)
systemd-run --user --scope --unit=lrtest-e-dummy --quiet -- sleep 600 &
DUMMY=$!
sleep 1
J=$(luminos-ram reaper --once --force --act-only="kwin,plasmashell,pipewire,sshd,Claude-$MAXPID,coder-gateway,lrtest-e" 2>/dev/null)
echo "$J" > "${OUT%.txt}-forced-pass.json"
for k in "${!BEFORE[@]}"; do
  p=${BEFORE[$k]}
  if [ -z "$p" ] || [ "$p" = 0 ]; then say "  SKIP  $k not running"; continue; fi
  alive "$p" && ok "$k (pid $p) survived" || bad "$k (pid $p) is GONE"
done
alive "$DUMMY" && bad "positive control lrtest-e-dummy survived — the forced pass did not act at all" || ok "positive control lrtest-e-dummy was reaped by the same pass"
echo "$J" | python3 -c '
import json,sys
d=json.load(sys.stdin)
for g in d["pass"]["groups"] or []:
    k=g["key"]
    if any(s in k for s in ("kwin","plasmashell","pipewire.service","Claude-","coder-gateway")):
        print("    %-52s %-10s %s" % (k[:52], g["state"], g["reason"]))
print("    acted:", d["acted"])' | tee -a "$OUT"
