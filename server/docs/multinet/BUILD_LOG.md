# BUILD_LOG — multinet (plain English, appended as we go)
- 11:40 Read AGENTS.md + HANDOFF.md. Searched notes/brain/mempalace (mempalace: nothing relevant).
- 11:42 Server state: enp2s0 192.168.2.62 @1000 Mb/s (default route, metric 100); wlan0 192.168.2.61
  on BELL851 2.4 GHz ch6, RSSI -25 dBm, 802.11n MCS7 150 Mb/s link. Same router, same /24.
  BELL851 5.0 GHz visible after a fresh scan. NZBGet idle (rate 0, queue empty). aria2 not installed.
- Decision: measurement first (gate 1). No worker sessions spawned — there is no code to build unless
  the measurement shows a gain; spawning implementers for a feature that may be pointless wastes the budget.
- 11:3x 2.4 GHz HTTPS matrix: E4 ~969, E8 ~972, W4 ~97, EW ~1069 (+10%) → fails the +15% bar.
- 11:4x Switched wlan0 to BELL851 5.0 GHz (802.11ac, 433 Mb/s link, kept .61; 0 clients on .61 first).
  W4 ~354, EW ~1313 (+35%) → passes. ISP line > 1 Gbit; the gigabit port is the cap.
- 11:5x Plexo can't drive NZBGet (HTTP only, GUI only) → measured Usenet directly with a stdlib NNTP-TLS
  reader (GROUP alt.binaries.boneless, BODY by number, bytes discarded, creds via stdin never argv).
  E15 723, E30 ~935, E40 ~957, E15+W15 ~850, E30+W10 ~1136 (+19%) → network gate passes.
- 11:5x Disk gate started; host-shell bridge dropped mid-dd. Shawn told; cleanup commands given.
- 12:0x Bridge back. Verified 0 leftover ddtest files, no dd running. Disk: sdb 97 MB/s, sda 54 MB/s.
  → **KILLED at the disk gate**: Ethernet alone already ~= what InterDir can write. Nothing to build.
- 12:0x Restored wlan0 to 2.4 GHz (.61), removed /tmp scripts on both machines. NZBGet untouched (15 conns).
  Docs: server/DECISIONS.md DECISION 134, server/STATUS.md throughput row, HANDOFF, notes, brain, MemPalace.
- 13:5x USB stick "not detected" on server: NOT a driver problem. Kernel 7.2.2-arch1-1 matches /lib/modules;
  xhci_hcd, usb_storage, uas all loaded (the USB HDD uses them). Every external port reports `not attached`,
  0 over-current, none disabled; kernel log has ZERO USB events since boot (2026-09-30) → the stick never made
  electrical contact. Port map: hotplug USB3 pair usb2-port1 (+usb1-port1) = FREE fast port; usb2-port2 = USB HDD
  (5 Gbit/s); usb1-port3/7 = USB2-only. Started a 15-min `udevadm monitor` → /tmp/usbwatch.log on the server.
- 14:0x Stick connected on the third port = usb1-port3, **USB 2.0 only (480 Mbit/s)**. The other free port
  (USB3 pair usb2-port1/usb1-port1) produced ZERO kernel events when tried → suspect a faulty port (or not
  seated). Shawn approved wiping: SanDisk Ultra 57.3 GB, Arch ISO wiped, now one ext4 partition `sticktest`,
  unmounted, left plugged in. Results on USB2: **write 9.1 MB/s** (400 MB, fdatasync), **read 29 MB/s**
  (USB2-capped; same stick read 161 MB/s on the G14's USB3). Verdict: ~10x slower than sdb (97 MB/s) — a
  scratch disk for NZBGet would make downloads far slower. Watcher stopped, log removed.
- 14:0x Shawn swapped ports: HDD → usb2-port1 (5 Gbit/s — so that port is NOT dead; the stick just wasn't
  seated), stick → port 2. **/srv/external was left UNMOUNTED** after the hot-unplug: systemd does not re-mount
  an fstab `nofail` mount when the device reappears. Bare mountpoint was empty, NZBGet idle → nothing written to
  the root fs. Re-mounted with `systemctl start srv-external.mount`; ext4 journal replayed, state clean.
  HAZARD (not yet fixed, offered): if NZBGet runs while unmounted it writes InterDir onto sda2 (40 GB root).
- Stick in port 2 still enumerates at **480 Mbit/s (USB 2)** although the HDD got 5000 there → the stick's
  USB3 contacts aren't engaging on this machine (it got 5000 on the G14). Re-test: write 9.5 MB/s, read 30.4 MB/s.
