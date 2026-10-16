#!/usr/bin/env bash
# Waits (up to 15 min) for the charger to be pulled, captures the unplug moment, runs the smoothness
# test on battery, then waits (up to 10 min) for the charger to come back and captures that too.
# Each charger moment is caught by a watch that is ALREADY armed when the edge happens.
B=${1:-/home/shawn/luminos-os/docs/spectrum/ab}; HERE=$(cd "$(dirname "$0")" && pwd); AC=/sys/class/power_supply/ACAD/online
echo waiting-unplug > /tmp/battery-cycle.state
"$HERE/run.sh" "$B/unplug3" watch 900 & W=$!
for i in $(seq 1800); do [[ $(cat $AC) == 0 ]] && break; sleep 0.5; done
sleep 15; pkill -TERM -P $W -x sleep; wait $W
echo battery-smooth > /tmp/battery-cycle.state
"$HERE/run.sh" "$B/smooth-bat3" smooth
echo waiting-plug > /tmp/battery-cycle.state
"$HERE/run.sh" "$B/replug3" watch 600 & W=$!
for i in $(seq 1200); do [[ $(cat $AC) == 1 ]] && break; sleep 0.5; done
sleep 20; pkill -TERM -P $W -x sleep; wait $W
echo done > /tmp/battery-cycle.state
