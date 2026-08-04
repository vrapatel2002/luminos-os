# Luminos Media Server — Decisions

Why the server is built the way it is. Numbering continues the main
[`../LUMINOS_DECISIONS.md`](../LUMINOS_DECISIONS.md) sequence — these entries were moved
here on 2026-08-02, and stubs remain in that file so the numbering still reads straight.

Ordered so amendments follow what they amend (36a directly after 36), which is not the
order they were written in.

---

## DECISION 35 — The media server's BitTorrent port is open to the internet on purpose; everything else stays LAN-only
<!-- [CHANGE: claude-code | 2026-07-31] -->
**Date:** 2026-07-31
**Status:** Accepted (user-consented)
**Applies to:** the media server (Dell Inspiron 3590, `192.168.2.61`), not the G14.

### Context
qBittorrent had **uploaded 0 bytes in its entire life**. With no inbound port it can only dial
*out*, which limits it to the minority of peers that are themselves reachable. On large,
thinly-seeded 4K swarms that meant 1 connection and a stalled download — the symptom looked like a
speed problem and was actually a reachability problem.

Separately, an earlier audit found the router had **already** been forwarding port 25989 from the
internet, created silently by qBittorrent's own UPnP with nobody's consent. So the honest choice was
never "closed vs open" — it was "open by accident vs open on record."

### Decision
1. **Exactly one port is exposed: 25989/tcp + 25989/udp**, in `/etc/nftables.conf`, with a comment
   saying why. It is a peer data port: no login, no admin surface, no directory listing.
2. **Every service keeps its LAN-only rule** — WebUI 8080, Jellyfin 8096, Sonarr 8989, Radarr 7878,
   Prowlarr 9696, ssh 22. nftables, not the router, is the authority; a stray UPnP mapping can no
   longer open anything by itself.
3. **The router forward is owned by us, not by the client.** `qbt-portmap.service` + `.timer`
   (boot+90 s, hourly) re-assert the mapping at `192.168.2.61`. qBittorrent's own UPnP is **off**:
   it had mapped the *ethernet* address `.62`, and later stopped mapping at all.
4. **Firewall changes load behind an auto-rollback.** `nft -c -f` to syntax-check, then
   `systemd-run --on-active=180` armed to restore the backup, cancelled only after SSH is confirmed
   alive. A ruleset that locks you out of a headless box in another building is unrecoverable.

### Why this is acceptable rather than merely convenient
A listening BitTorrent port is the same class of exposure as any peer-to-peer client. The risk is
concentrated in the *client binary*, not in the port, and `qbittorrent-nox` runs as an unprivileged
user with no shell. Closing it again is one line and a `systemctl disable --now qbt-portmap.timer` —
documented in `server/docs/MEDIA_SERVER_SECURITY.md` §2a.

### How it was proven, and what lied
- **An online port checker reported 25989 CLOSED. It was wrong.** Replaced with a positive control:
  a throwaway port, `python3 -m http.server`, and a genuinely external fetcher that came back with
  our sentinel string.
- **Never test your own public IP from inside your own LAN.** Hairpin NAT makes every result
  ambiguous — refused and timed-out become indistinguishable from open.
- **`upnpc -l` prints an empty table on the Bell hub even while a mapping is live.** Only the `-d`
  return code is trustworthy: 714 = nothing there, 0 = existed and is now deleted, 606 = refused.
- The port-map unit was **negative-tested**: mappings deleted (714), unit run, mapping back (0).

### Tradeoffs
- Accepted: the box is now addressable from the internet on one port. Mitigated by scope (one port),
  by ownership (our timer, not the client's UPnP), and by a written close-it-again procedure.
- Accepted: the mapping depends on UPnP staying enabled on the Bell hub. If the owner disables it,
  the timer fails quietly and throughput regresses — the doc says to check `qbt-portmap` first.
- Not accepted: exposing the WebUI, even behind a password. There is no version of that trade that
  pays.

### Related
`server/docs/MEDIA_SERVER_SECURITY.md` §2a (the exception) and §2b (ARP flux on a dual-homed host — the
routing table does **not** tell you which cable a packet arrived on). Memory:
`reference_linux_silent_failures.md`, same shape as every entry there — each of these checks asked
whether a thing *existed* instead of whether it *worked*.

---

## DECISION 36 — Torrents take the ethernet cable and give up peak speed, so the wifi radio is free for the TV
<!-- [CHANGE: claude-code | 2026-07-31] -->

**Status:** Implemented and verified live, with someone watching at the time.

### The problem this actually solves
DECISION 35 opened the peer port and throughput went to ~10.7 MB/s. That worked, and it broke
Jellyfin: LAN ping went to **256 ms average / 547 ms max with 12.5% packet loss**, and the phone
could not open the app. The instinct was that the 100 Mb/s ethernet was the bottleneck. It was not.

The **router's wifi radio** was. It is one shared medium and it was carrying two things at once:
the torrent traffic on the server's `wlan0`, and the TV's stream on its last hop. Measured: the TV
at `192.168.2.13` pings **2.8–10 ms with 2.1 ms jitter**, versus **0.21–1.45 ms** to the router over
the wire — the TV is **wireless**, so its last hop needs that radio and cannot be moved off it.
Torrents can be moved. So they were.

### Why binding qBittorrent to .62 is not enough on its own
Both NICs sit on `192.168.2.0/24` behind the same gateway, and `wlan0` wins the default route on
metric (600 vs 1024). Read-only proof before changing anything:

    ip route get 1.1.1.1 from 192.168.2.62
    -> 1.1.1.1 from 192.168.2.62 via 192.168.2.1 dev wlan0

Source address alone does not choose the exit. `/etc/systemd/network/20-wired.network` now gives
.62 its own routing table (`RoutingPolicyRule From=192.168.2.62 Table=100`), after which the same
lookup returns `dev enp2s0 table 100`. Peer sockets now show as `192.168.2.62%enp2s0`.

### This reverses two earlier notes, on purpose
- `qbt-portmap.service` used to pin the router forward to **.61** specifically to avoid the
  12.5 MB/s wire. That trade is now taken deliberately: capped throughput beats a radio fight.
- The old status note said *"do not pin `current_network_interface` — every tracker announce died."*
  The setting was not the bug; **not restarting after changing it** was. See DECISION 35's lesson —
  sockets bound under the old setting never re-bind. Pinned, restarted, verified: `dht_nodes 128`,
  `connection_status connected`.

### The cap, and why it is not the constraint it looks like
Downloads are capped at **10 MB/s (80 Mb/s)** on a 100 Mb/s wire. Ethernet is **full duplex**, so
downloads occupy the *inbound* channel (measured 10.92 MB/s in) while the stream occupies *outbound*
(2.07 MB/s out). They do not collide. Replacing the cable with one that negotiates 1000 Mb/s removes
the ceiling entirely and makes this strictly better than the old arrangement in every dimension.

### Verified, under live load, mid-playback
| | Before the split | After |
|---|---|---|
| TV latency | 256 ms avg / 547 ms max, 12.5% loss | **8.4 ms avg / 13.8 ms max, 0% loss** |
| Torrent traffic on wifi | all of it | **0.00 MB/s** |
| Torrent traffic on cable | none | **10.92 MB/s in** |
| Stalled 2-seed torrent | 0.01 MB/s (9.8 day ETA) | **10.0 MB/s** |
| Playback | — | never dropped: 25.87 → 30.8 min, 3 connections held |

### Safety pattern reused
Changes loaded behind `systemd-run --on-active=180` running `/usr/local/sbin/luminos-splitnet-revert`,
cancelled only after the stream and SSH both survived. `networkctl reload` was **deliberately not run**
— the live rules already do the job, and a reload could bounce the link under an active stream. The
declarative config takes over at next reboot.

### Known fragility
`From=192.168.2.62` stops matching if the DHCP lease changes. A **router DHCP reservation for .62 is
now load-bearing**, not cosmetic (owner-only task).

---

## DECISION 36a — Correction: it is the *socket* binding that holds the split, not the policy rule
<!-- [CHANGE: claude-code | 2026-08-02] -->

DECISION 36 said the `[RoutingPolicyRule] From=192.168.2.62 Table=100` was what forced
torrents onto the cable. **That was wrong**, and it was caught by re-testing rather than
by anything failing.

### What was found
`ip rule show` on 2026-08-02 listed **no rule at priority 100** — only the three defaults.
Table 100 still held both routes. So the rule had been removed while the table survived.

That rules out the auto-revert script: `luminos-splitnet-revert` does
`ip route flush table 100` as well, and the table was intact.

**The actual cause**, from the journal:
```
Jul 31 15:08:00  enp2s0: DHCP lease lost
Jul 31 15:08:08  enp2s0: Link UP
Jul 31 15:08:29  enp2s0: DHCPv4 address 192.168.2.62/24 acquired
```
The cable flapped. When systemd-networkd reconfigures a link it **flushes routing rules it
does not own**. The rule was added by hand with `ip rule add`, and `networkctl reload` was
deliberately never run (DECISION 36, to avoid bouncing the link mid-stream) — so networkd's
in-memory config had no rule, and it cleaned mine up as foreign.

### And yet the split never broke
Measured with the rule absent:

| interface | inbound |
|---|---|
| `wlan0` | **0.00 MB/s** |
| `enp2s0` | **9.80 MB/s** |

20 peer sockets on `.62`. The split was fully intact for ~2 days with no rule at all.

**Why:** qBittorrent's `current_network_interface=enp2s0` is a bind to the *device*
(`SO_BINDTODEVICE`), not to the address. That pins the exit interface at the socket layer and
**overrides the routing table entirely**. `current_interface_address=192.168.2.62` is the
weaker of the two settings and is the one that needs the policy rule.

### The corrected model
- **Load-bearing:** qBittorrent's device binding. If that setting is cleared, the split dies
  instantly no matter what the routing rules say.
- **Belt-and-braces:** the policy rule. It matters for *anything else* sourced from `.62`, and
  for the `current_interface_address` path — not for qBittorrent as configured.

The `ip route get 1.1.1.1 from 192.168.2.62` test in DECISION 36 is still the right test for
**source-address** selection. It simply does not describe what qBittorrent does, so it was
never evidence about the torrent path. Two different mechanisms were conflated.

### Action taken
Rule re-added live (`ip rule add from 192.168.2.62 lookup 100 priority 100`); route test now
returns `dev enp2s0 table 100`. `networkctl reload` was **again not run** — 284 GB was
downloading and the rule is demonstrably not load-bearing, so a link bounce buys nothing. The
declarative block is present in `20-wired.network` and installs at next reboot, which is also
the point at which networkd starts *owning* the rule and re-adding it after future flaps.

### Lesson
**A config that is "working" is not evidence that the thing you configured is what makes it
work.** Two mechanisms were installed at once and credited to the wrong one. Re-verify the
mechanism, not just the outcome — and prefer the test that exercises the actual code path
(`ss` on live sockets, byte counters per interface) over one that models it.

### Separate finding — wlan0 is dropping its wifi association
48 × `wlan0: Lost carrier` → `DHCP lease lost` → reconnect to `BELL851 5.0 GHz` in the two days
to 2026-08-01, **0 so far on 2026-08-02**. The address always came back as `.61`, so nothing
broke permanently, but each drop is a ~1 s gap that would surface as a stutter on the TV.
Cause not established — do not assume it was radio contention just because the timing is
suggestive. This is an independent argument for **wiring the TV to the router**.

---

## DECISION 37 — Jellyfin transcodes on the Intel iGPU, and the render-node number is machine-specific
<!-- [CHANGE: claude-code | 2026-08-02] -->

**Context:** Jellyfin was reporting `PlayMethod: Transcode` to h264 with
`HardwareAccelerationType: none` — every transcode was running on the CPU of a
Dell Inspiron 3590 that also seeds torrents.

**Decision:** enable VAAPI on `/dev/dri/renderD128`.

### The trap: renderD128 is not the same GPU on every machine
An earlier note (from the **G14**) says *"use renderD129, not renderD128 — renderD128 is
the NVIDIA node and reports nothing."* That is true **on the G14 and nowhere else**. The
number is just enumeration order. On this server it is the exact opposite:

| node | driver | device |
|---|---|---|
| `renderD128` | `i915` | Intel CometLake-U UHD Graphics ← **the useful one** |
| `renderD129` | `amdgpu` | AMD Radeon 520 (Jet PRO) |

**Never carry a render-node number between machines.** Resolve it every time:
`ls -l /sys/class/drm/renderD12*/device/driver`.

### What the Intel chip actually supports (measured, not assumed)
`vainfo --device /dev/dri/renderD128`, driver **Intel iHD 26.1.5**:
- **Decode (VLD):** H264, HEVC Main, HEVC Main10, VP9 Profile0/Profile2, VP8, VC1, MPEG2, JPEG
- **Encode (EncSlice):** H264, HEVC Main, MPEG2, VP8, JPEG
- **No AV1** — absent from the profile list, so it is not enabled.

`HardwareDecodingCodecs` was set to exactly that measured list
(`h264, hevc, mpeg2video, vc1, vp8, vp9`) rather than the full menu Jellyfin offers.

### Applied through the API, not the file
`/etc/jellyfin/encoding.xml` was backed up (`.bak-2026-08-02`) but **not hand-edited** —
Jellyfin rewrites that file from memory on shutdown and would have silently discarded the
change. Set via `POST /System/Configuration/encoding` (http 204), then verified in **both**
the API readback and the on-disk XML.

### Proof it works, and proof it is not a silent software fallback
Real job: the 4K HEVC 10-bit `True Detective S04E01` (3840x1920, yuv420p10le) → 1080p H264.

| path | speed |
|---|---|
| `libx264 -preset veryfast` (CPU) | **1.22x** realtime |
| `h264_vaapi` on renderD128 | **4.8x** realtime |

1.22x means the CPU *barely* kept up with a single 4K stream — one extra viewer, or a busy
torrent moment, and it stutters. 4.8x has real headroom.

**Negative test (the part that makes the number trustworthy):** the same command against
`renderD129` fails hard rather than quietly falling back —
`libva: /usr/lib/dri/radeonsi_drv_video.so init failed` → `Device creation failed: -5`.
So the 4.8x was genuinely the Intel encoder, and `encoder: h264_vaapi` in the output
confirms it.

### Left off deliberately
- `AllowHevcEncoding=false` — the TV takes H264 happily; HEVC encode on Gen9.5 is slower
  and buys nothing here.
- `EnableTonemapping=false` — HDR→SDR tonemapping on Comet Lake needs OpenCL
  (`intel-compute-runtime`), which is not installed. Separate change, separate proof.
