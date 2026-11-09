#!/bin/bash
# [CHANGE: claude-code | 2026-11-07] snappy build — full knob snapshot for before/after-resume diffs (read-only). Run as root: snap.sh <out>
O=$1; D=/sys/kernel/debug/dri/0000:65:00.0
kv() { for f in "$@"; do [ -r "$f" ] && [ -f "$f" ] && printf '%s = %s\n' "$f" "$(tr '\n' '|' < "$f" 2>/dev/null | head -c 600)"; done; }
{
kv /sys/class/drm/card2/device/{power_dpm_force_performance_level,pp_dpm_sclk,pp_dpm_mclk,pp_dpm_fclk,pp_dpm_socclk,pp_power_profile_mode,power_dpm_state,current_link_speed}
kv /sys/firmware/acpi/platform_profile /sys/devices/platform/asus-nb-wmi/ppt_* /sys/devices/system/cpu/amd_pstate/status /sys/devices/system/cpu/cpufreq/boost
kv /sys/devices/system/cpu/cpu*/cpufreq/{scaling_governor,energy_performance_preference,scaling_min_freq,scaling_max_freq,boost}
kv /sys/devices/system/cpu/cpu*/cpuidle/state*/disable /sys/devices/system/cpu/cpuidle/current_governor
kv /sys/bus/pci/devices/*/power/{control,runtime_status} /sys/bus/pci/devices/*/d3cold_allowed /sys/bus/pci/devices/*/link/l1_aspm /sys/bus/pci/devices/*/link/l1_1_aspm /sys/bus/pci/devices/*/link/l1_2_aspm
kv /sys/bus/usb/devices/*/power/{control,runtime_status,level}
kv /sys/module/pcie_aspm/parameters/policy /sys/module/amdgpu/parameters/* /sys/module/nvme_core/parameters/default_ps_max_latency_us
kv /proc/sys/kernel/{nmi_watchdog,timer_migration,sched_autogroup_enabled} /sys/kernel/mm/transparent_hugepage/{enabled,defrag} /proc/sys/vm/{swappiness,dirty_writeback_centisecs,laptop_mode}
kv /sys/class/backlight/*/brightness $D/eDP-2/{psr_capability,psr_state} $D/amdgpu_pm_info
kv /sys/class/rtc/rtc0/wakealarm /sys/power/{mem_sleep,pm_debug_messages}
for p in /sys/bus/pci/devices/*; do echo "lnkctl $(basename $p) = $(lspci -vv -s ${p##*/} 2>/dev/null | grep -E 'LnkCtl:|L1SubCtl1' | tr -s ' ' | tr '\n' '|')"; done
echo "wifi_ps = $(iw dev 2>/dev/null | awk '/Interface/{print $2}' | while read i; do iw dev $i get power_save; done)"
echo "== systemd running (system)"; systemctl list-units --state=running --no-legend --plain | awk '{print "sys "$1}'
echo "== systemd running (user)"; sudo -u shawn XDG_RUNTIME_DIR=/run/user/1000 systemctl --user list-units --state=running --no-legend --plain | awk '{print "user "$1}'
echo "== processes"; ps -eo comm= | sort | uniq -c | awk '{print "proc "$2" x"$1}'
} > "$O" 2>/dev/null
