#!/usr/bin/env bash
# Waits (up to 60 min) for: USB-C source offline AND AC online (= barrel brick), settles 20 s, then runs the smooth test.
U=/sys/class/power_supply/ucsi-source-psy-USBC000:001/online; A=/sys/class/power_supply/ACAD/online
echo waiting > /tmp/brick.state
for i in $(seq 7200); do [[ $(cat $U) == 0 && $(cat $A) == 1 ]] && break; sleep 0.5; done
[[ $(cat $U) == 0 && $(cat $A) == 1 ]] || { echo timeout > /tmp/brick.state; exit 1; }
sleep 20; grep -E 'STATUS|CAPACITY=' /sys/class/power_supply/BAT1/uevent > /tmp/brick.bat
echo running > /tmp/brick.state
"$(dirname "$0")/run.sh" /home/shawn/luminos-os/docs/spectrum/ab/smooth-brick smooth
echo done > /tmp/brick.state
