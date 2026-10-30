# SPEC — multi-network downloads on the media server (2026-10-10)

## What Shawn asked (his words)
"try this on server use the best fastest wifi and ethernet and tell if there is some gain in speed
or not. it should work with our setup the nzgb or whatever ... thats the only thing we are using"
Context: he found Plexo (github.com/anmolkapil/plexo) — splits one download across network interfaces.

## Assumptions (gaps filled)
- "nzgb" = **NZBGet** on luminos-server (Server1 news.usenetserver.com:563 TLS, 15 conns). Only downloader.
- "Best fastest wifi" = whichever of BELL851 2.4 GHz / BELL851 5.0 GHz measures faster *now*. Both are
  known iwd networks. The server's original Wi-Fi (2.4 GHz) is restored at the end; switching bands
  permanently is Shawn's call.
- Plexo itself is NOT usable here: it is an Electron GUI (no CLI/daemon) and speaks HTTP range
  requests only. Usenet is NNTP, so the only way NZBGet could use two links is policy routing
  (e.g. a second Server entry on port 443 forced out wlan0). That is built ONLY if the physics test passes.
- Both interfaces sit on the SAME router (192.168.2.1, same /24) and the same Bell line, so the
  expected answer is "no gain" unless the Ethernet path itself is the bottleneck. We measure, not assume.
- Test traffic: HTTPS (TLS over TCP from a remote server, like NNTP-TLS) from the Waterloo CSClub
  mirror, Arch ISO (~1.2 GB). Bound per interface with curl --interface (SO_BINDTODEVICE).
- NZBGet must be idle during tests (checked: DownloadRate 0, queue empty).

## Thresholds — fixed BEFORE any run (gate ladder, cheapest kill first)
- Configs, 12 s each, 3 trials, median: E4 (eth 4 streams), E8 (eth 8 streams), W4 (wifi 4 streams),
  EW (eth 4 + wifi 4 at once).
- E8 is the fair baseline for EW: same total connections, one link.
- **Gain counts only if median(EW) >= 1.15 x max(median E4, E8, W4).**
- Per-interface kernel rx_bytes counters must show BOTH links carrying traffic in EW, otherwise the
  run is invalid (traffic didn't actually split).
- If the gain fails: stop. No NZBGet or routing change is made (nothing to build).

## Done means
A plain-language answer to "is there a speed gain, yes or no, and by how much", backed by the
numbers above, with the server left exactly as found (same Wi-Fi band, no config changes).
