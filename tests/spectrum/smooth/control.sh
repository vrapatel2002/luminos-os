#!/usr/bin/env bash
# Control arm: same smoothness test with luminos-power stopped (ExecStopPost leaves PPT 45/54/65 W and full clocks).
# Always restarts the daemon afterwards.
trap 'systemctl start luminos-power' EXIT
systemctl stop luminos-power; sleep 2
"$(dirname "$0")/run.sh" /home/shawn/luminos-os/docs/spectrum/ab/smooth-ac-nodaemon smooth
