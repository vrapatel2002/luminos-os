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

---

## DECISION 42 — All torrent traffic is halted until a VPN is in front of it
<!-- [CHANGE: claude-code | 2026-08-04] -->
**Date:** 2026-08-04
**Status:** Accepted (user-directed) — **active halt, not a plan**
**Applies to:** the media server (Dell Inspiron 3590), not the G14.
**Amends:** DECISION 35, which opened port 25989 to the internet on purpose.

### Context
DECISION 35 deliberately exposed the BitTorrent peer port so the client could accept
inbound connections and actually seed. It worked — `up_info_data` reached **228.9 GB**
uploaded against **389.9 GB** downloaded.

That is exactly the problem. Every one of those transfers is visible to the ISP:

- BitTorrent peer traffic is **unencrypted by default** and trivially identifiable by
  protocol signature, regardless of port number. Moving off 6881 hides nothing.
- With an **inbound** port open the machine is not just a client, it is an advertised
  peer. It appears in the tracker's peer list and in every DHT lookup for those
  torrents, tied to the public IP **76.64.36.43**. Anyone can enumerate that list —
  monitoring outfits do exactly this, and it is the usual source of ISP notices.
- Seeding is the half that draws attention. Uploading 228.9 GB is a far louder signal
  than downloading the same volume.

### Decision
**No torrent download and no torrent upload until a VPN is in place.** Halted on
2026-08-04, enforced at three independent layers so undoing one does not restart traffic:

1. All 22 torrents set to `stopped` via `POST /api/v2/torrents/stop` with `hashes=all`.
2. `qbittorrent-nox@shawn.service` **stopped and disabled** — so it does not come back
   on reboot, and nothing is listening on 25989 at all.
3. `qbt-portmap.timer` **stopped and disabled**. This is the hourly job that keeps the
   router's forward to 25989 alive, since qBittorrent's own UPnP stopped mapping. It was
   still armed and due to fire 15 minutes later. It could not have restarted traffic —
   nothing is listening — but it would have kept re-advertising a forward to a machine
   that is meant to be silent, which is the opposite of the intent. Easy to miss,
   because it is a *separate unit from the thing it serves*.

Plus a fourth layer to stop a backlog building up behind the halt:

4. `rssSyncInterval` set to **0** in both Sonarr and Radarr. Left at their defaults they
   would keep polling indexers, grabbing releases, and failing to hand them to a dead
   download client — filling the queue with retries and possibly blocklisting good
   releases. Original values recorded below for restore.

The nftables `accept` rules for 25989 were **left in place**. They are inert while
nothing listens on the port, and removing them is a real DECISION 35 reversal that
should be a deliberate act rather than a side effect of this halt.

### Verified, not assumed
Stopping was confirmed by measurement at both ends, with a control to prove the test
could detect the failure case:

```
after stop:  dl_info_speed 0   up_info_speed 0   (was up 1,013,529 B/s)
             Counter({'stoppedUP': 20, 'stoppedDL': 2})
from the G14:
  192.168.2.62:25989  Connection refused     <- peer port dead
  192.168.2.61:8080   Connection refused     <- WebUI dead (same process)
  192.168.2.61:8096   OPEN                   <- CONTROL: proves the probe
                                                can still see an open port
```

Without that third line the first two prove nothing — a probe that cannot detect
anything reports every port as closed.

`rssSyncInterval=0` was confirmed by reading the value back from both APIs, not from
the fact that the `PUT` returned success.

### What is NOT affected
Jellyfin keeps running. Streaming to the TV is LAN-only traffic that never leaves the
house, and nothing about it is of interest to the ISP. The library is untouched —
610 GB already on disk stays fully playable.

Prowlarr can still reach indexers. Those are ordinary HTTPS requests, not swarm
participation, and they do not put the IP in a peer list.

### Restore procedure — only after the VPN is up and leak-tested
The values to put back, recorded now so they are not guesses later:

```bash
# 1. ONLY after the VPN is confirmed working AND kill-switched
sudo systemctl enable --now qbittorrent-nox@shawn.service
sudo systemctl enable --now qbt-portmap.timer   # only if the VPN does NOT forward a port

# 2. restore RSS polling (these were the values before the halt)
#    Sonarr rssSyncInterval 15, Radarr rssSyncInterval 30
curl -X PUT -H "X-Api-Key: $SONARR_KEY" -H 'Content-Type: application/json' \
  -d '{"minimumAge":0,"retention":0,"maximumSize":0,"rssSyncInterval":15,"id":1}' \
  http://127.0.0.1:8989/api/v3/config/indexer/1

# 3. resume torrents
curl -b /tmp/qbc.txt -d 'hashes=all' http://127.0.0.1:8080/api/v2/torrents/start
```

### The hard part, which is not yet decided
A VPN on this box is **not** just "install a client". Three things have to be true, and
none of them are true today:

- **The VPN must not break DECISION 36.** Torrents are pinned to `enp2s0` by
  `SO_BINDTODEVICE` (`current_network_interface=enp2s0`) so the wifi radio stays free
  for the TV. A VPN introduces a `wg0`/`tun0` interface, and qBittorrent must be
  re-pinned to *that* — but the VPN's own encrypted tunnel must still exit via
  `enp2s0`, or the torrent traffic lands back on the radio inside the tunnel and the
  TV stutters again. This is the fiddly part.
- **A kill-switch is mandatory, not optional.** If the tunnel drops and qBittorrent is
  bound to a dead interface it should stall, not fall back to the bare connection. The
  binding gives this mostly for free — a dead `wg0` means no route — but it must be
  *tested* by downing the interface mid-transfer and confirming the counters go to zero.
- **Port forwarding through the VPN** decides whether seeding still works at all. Most
  providers do not offer it; on those, DECISION 35's inbound port is simply gone and
  the client is back to outbound-only. That is an acceptable cost but it should be a
  known one, not a surprise.

**Provider choice is the user's call** — it is a paid subscription and a trust decision
about who gets to see the traffic instead of the ISP.

### Lesson
The halt is enforced by *stopping the service*, not by unticking something in the app.
An app-level pause is one settings write away from being undone, including by the app
itself on restart. When the requirement is "no traffic", the enforcement belongs at a
layer the app does not control.

---

## DECISION 44 — A series may hold at most 2 seasons, and the rule is a timer, not a habit
<!-- [CHANGE: claude-code | 2026-08-04] -->
**Date:** 2026-08-04
**Status:** Accepted (user-directed) — enforced daily by `luminos-season-limit.timer`
**Applies to:** the media server (Dell Inspiron 3590), not the G14.

### Context
The disk had **222 GB free of 876 GB** and was heading down. Two separate things were
eating it, and they needed different fixes.

**1. Orphaned downloads — 131.10 GB.** 45 files in `/srv/media/downloads` that Sonarr
had never imported, or had imported by *copying* rather than hardlinking, leaving a
second full copy behind. They were being seeded and would be re-fetched by a
"resume all" the moment torrenting came back.

**2. Seasons nobody asked for.** House of Cards was monitored on all six seasons and
had already pulled S03–S06. Sonarr has **no maximum-seasons setting** — its per-series
Monitor options are All / Future / Missing / Existing / First Season / Last Season /
Pilot / None. There is nothing between *one* season and *every* season. On a disk
holding Bluray remuxes at roughly **12 GB an episode**, "All" is how 876 GB disappears.

### Decision
1. Delete the 131.10 GB of orphans, with a manifest and a torrent-state backup first.
2. Delete House of Cards S03–S06 (user-confirmed).
3. Cap every series at **2 monitored seasons**, enforced by a script on a daily timer.
4. Remove the dead torrents from qBittorrent's state so the halt cannot un-delete them.

### How the cap decides which two to keep
`luminos-season-limit` (`server/scripts/`, installed at `/usr/local/bin/`). Two rules
carry all the weight, and both exist because the obvious version was wrong:

**Rule 1 — anything already at or under the limit is left completely alone.**
True Detective is monitored on **S01 + S04** on purpose: those are the two that exist
on disk. A "first N seasons" rule would silently rewrite that to S01+S02 and queue
~90 GB of remuxes for a season nobody wanted. Respecting a hand-picked pair is what
makes the script safe to run unattended.

**Rule 2 — when trimming, seasons that have files on disk beat empty ones; season
number only breaks the tie.** This one was caught by negative test, not by reading.
The first implementation ranked purely by season number. Fed the real True Detective
with a third season monitored (S01 = 8 files, S02 = empty, S04 = 6 files) it planned
to **keep S01+S02 and drop S04** — throwing away **47.46 GB** of files already on disk
in favour of an empty season, and queueing the replacements. The sort key is now
`(episodeFileCount == 0, seasonNumber)`.

It **never deletes**. Unmonitoring stops Sonarr *acquiring*; existing episodes stay put.
Over-limit seasons that still hold files are printed at the end with a reclaimable
total, so the choice to delete stays a human one. Default is a **dry run**; `--apply`
is required, and after writing it **re-reads state from Sonarr and verifies** every
change landed, exiting 2 if not — an HTTP 202 from Sonarr is not proof.

### Why a timer and not "run it when you remember"
The user asked for a *setting*. A script you have to remember to run is not a setting —
it is a chore, and the failure mode is silent (a new series quietly monitors 9 seasons
until the disk fills). `luminos-season-limit.timer` runs daily with `Persistent=true`,
because this box is powered on and off by hand and a missed run must still happen.
Daily rather than hourly so it does not fight a deliberate hand edit made minutes ago.

### Verified, not assumed
- **Never deleted a file with a second link.** The delete pass asserted `nlink == 1`
  and would have aborted on any hardlink. It nearly mattered: two True Detective
  S01 files looked like duplicates of library files but had **different inodes**
  (downloads 42205243/42205247 vs library 50331738/50331739) — Sonarr had *copied*,
  not hardlinked. Checking made the deletion provably safe rather than probably safe.
- **Library re-verified after the deletions** — 522.81 GB, every file readable.
- **Reversibility bought before the destructive step:** `qbt-BT_backup-20260804-193838.tar.gz`
  (46 entries) and `deleted-orphans-20260804.json`, both in `/home/shawn`.
- **The unit was negative-tested, not just started.** Running it against an already-
  compliant library proves nothing — it prints "nothing to change" whether it works or
  is broken. So House of Cards S03 was deliberately re-monitored and the unit run:
  it reported `trim 3 -> 2, keeping S01,S02`, unmonitored S03, and verified the
  read-back. Then it was run again to confirm idempotency.
- **Torrents removed offline**, by deleting `<hash>.torrent` + `<hash>.fastresume`
  from `BT_backup` with the daemon down — 22 entries to 14. Zero network traffic,
  which matters because DECISION 42 forbids exactly that.

### Result
| | Free on `/srv/media` |
|---|---|
| before | 222 GB |
| after orphan delete | 345 GB |
| after House of Cards S03–S06 | **382 GB** |

**171.83 GB reclaimed.** Final library: House of Cards S01 (151.95 GB) + S02 (132.41 GB),
MobLand S01 (49.93 GB), True Detective S01 (100.32 GB) + S04 (47.46 GB).

### Lesson
A health check that only ever runs against healthy input has never been tested. Both
real bugs here — the wrong-season trim and the question of whether the systemd unit
could read the API key as root — were invisible until the check was fed something it
was supposed to catch. Break it on purpose, once, before trusting it on a timer.

---

## DECISION 48 — Downloads move to Usenet over TLS, and the server's own DNS stops leaking
<!-- [CHANGE: claude-code | 2026-08-05] -->
**Date:** 2026-08-05
**Status:** Accepted (user-directed) — NZBGet installed, running, wired into Sonarr + Radarr
**Applies to:** the media server (Dell Inspiron 3590), not the G14.
**Follows:** DECISION 42, which halted all torrent traffic until a VPN was in front of it.

### The decision
The user bought a **UsenetServer** subscription. Downloads now arrive over **NNTP-over-TLS
on port 563**, through **NZBGet**, instead of over BitTorrent. Torrenting stays halted
exactly as DECISION 42 left it — this does not restart it, it replaces the need for it.

### Why this closes what a VPN was going to close
DECISION 42 halted torrents for two separate reasons, and Usenet answers both without a
subscription to a third party who can see the traffic:

| | BitTorrent | Usenet |
|---|---|---|
| Is the transfer encrypted? | No — protocol signature is identifiable on the wire | Yes, TLS 1.3 to the provider |
| Is there a peer list? | Yes — the box was *advertised* in trackers and DHT against 76.64.36.43 | No. One connection, to one server |
| Does anyone else learn our IP? | Every peer in the swarm | The provider only |
| Do we upload? | 228.9 GB uploaded, and seeding is the conspicuous half | **Structurally impossible** — see below |

The account is **read-only**. The server's own greeting says so:
`281 Welcome to UsenetServer (No Posting)`. It cannot upload even if something were
misconfigured to try, which is a stronger guarantee than a setting that says "don't".

**A VPN was therefore not bought for this.** NNTP/563 is already TLS and there is no peer
list, so a VPN would add a hop and protect nothing that is not already protected. The
bundled PrivadoVPN stays unconfigured; it is only relevant if torrents ever restart, and
their free SOCKS5 proxy is explicitly **not encrypted** (their own documentation), so it
would change the exit IP and nothing else.

### Encrypted DNS, and why the obvious configuration is not enough
Before this the box asked `mtrlpq02dnsvp1.srvr.bell.ca` for every name, in cleartext.
Encrypting the downloads while broadcasting *what you are downloading from* to the ISP's
resolver is theatre, so DNS is now **DNS-over-TLS to Quad9**, strict mode.

The trap: **DNS configured on a link beats DNS configured globally** in
`systemd-resolved`. Writing `/etc/systemd/resolved.conf.d/luminos-dot.conf` alone leaves
DHCP handing Bell's resolver to `wlan0` and `enp2s0`, and every lookup keeps going out in
cleartext through the *link* setting while the global config sits there looking correct.
Both `.network` files therefore got a drop-in with `UseDNS=false` for DHCPv4, DHCPv6 and
IPv6 RA. Drop-ins rather than edits, so the hand-commented originals stay readable.

`DNSOverTLS=yes` and not `opportunistic`. Opportunistic falls back to plaintext when the
handshake fails and tells you nothing — the exact silent-failure shape this project keeps
running into. Strict mode fails closed: no DNS at all is a problem you notice.

### Proven by packet capture, and the capture had to be fixed first
`resolvectl status` claiming `+DNSOverTLS` is the service reporting on itself. The wire
is the only witness:

```
total packets: 51
PLAINTEXT port 53: 0
ENCRYPTED port 853: 51        all to 9.9.9.9
```

Three earlier attempts at this test returned `0 / 0` and would have been read as "no
plaintext, success" by anyone in a hurry. **They were all broken tests, not clean results:**
- `tcpdump -c 40` to a file buffers, and the buffer is lost — `-U` (packet-buffered) is required.
- Backgrounding `tcpdump` over SSH holds the channel open and **kills the session** (exit 255).
- `tcpdump -w` under `timeout` loses the pcap entirely: SIGTERM does not flush it.

The result above is trustworthy *because* it captured 51 packets. A test that captures
nothing cannot distinguish "no plaintext DNS" from "not listening".

### Measured, because "is it fast enough" is not a matter of opinion
`server/scripts/luminos-usenet-speed` opens N real TLS connections and pulls real article
bodies, which is what a download actually does — there is no synthetic test file on Usenet.

**15 connections, 20 seconds: 307 articles, 235.7 MB, 11.45 MB/s (92 Mb/s).**

That is **above** the best BitTorrent ever managed here (10.74 MB/s, DECISION 44 notes) and
it is sitting on the 100 Mb/s wifi ceiling. The plan allows 50 connections; raising the
count would buy **nothing**, because the radio is the bound, not the provider. The router
reports `MaxBitRateDown : 1024000000 bps` — the line is ~1 Gbps. **Only a Cat 6 cable
changes this number**, which makes the already-pending cable worth about 10x rather than a
nicety.

### What is installed
- **NZBGet** on `0.0.0.0:6789`, LAN-only in practice because nftables is `policy drop` with
  a single `192.168.2.0/24` accept. User `luminos`.
- Downloads land in `/srv/media/usenet/{complete,incomplete}`, deliberately **separate from
  the torrent download dir** so a half-finished job can never be confused with a torrent and
  the arrival path is obvious from the filename.
- Added to **Sonarr and Radarr as download client id=2**, both confirmed with `testall`
  returning `valid=True`. (`id=1` is qBittorrent, `valid=False`, which is DECISION 42
  working as intended and not a fault.)
- Credentials live in `server/.env`, mode 600, **gitignored** — verified with
  `git check-ignore -v` and `git status --porcelain --ignored`.

### Three real bugs the setup script caught by reading its own work back
`luminos-nzbget-setup` writes the config, then re-reads the file and compares every key.
That is not ceremony; it found all three of these:

1. **The verifier itself was wrong.** In Python, `\s` matches newlines — so `\s*` after `=`
   on an empty value (`LockFile=`) swallowed the line break and captured the *next* line,
   failing three keys that had been written perfectly. `[ \t]*` is the fix.
2. **`os.makedirs()` creates missing *parent* directories using the process umask**, not the
   mode you `chmod` onto the leaves. Under `sudo` that umask is `0077`, so
   `/srv/media/usenet` came out `drwx--S---` and nzbget could not traverse into its own
   download directories even though the leaves underneath were a perfect `2775`. Every
   directory in the chain has to be listed explicitly.
3. **`CertCheck=yes` refuses to start without `CertStore`.** Fair — validating against no
   trust anchors would be theatre. Pointed at `/etc/ssl/certs/ca-certificates.crt`.
   Certificate checking stays **on**: with it off, a spoofed certificate is accepted
   silently and the "encrypted" connection protects nothing.

`systemctl is-active` said `active` while two of these were live in the journal. **Service
active is not service working.**

### What is still missing
**An indexer.** The news server stores the articles; an *indexer* is the search engine that
tells Sonarr which articles hold which episode, and they are separate purchases. UsenetServer's
bundled "Global Search" is a website with no API, so Sonarr cannot drive it. NZBGeek or
DrunkenSlug, roughly USD 15-20 a year. Until one exists, NZBGet can be fed a `.nzb` by hand
but nothing is automatic. `INDEXER_NAME` / `INDEXER_URL` / `INDEXER_APIKEY` are waiting in
`server/.env`.

---

## DECISION 51 — Remote Jellyfin goes over Tailscale, and no port is opened to do it
<!-- [CHANGE: claude-code | 2026-08-05] -->

**Decided 2026-08-05.** DECISION 48 left one question open: how to watch Jellyfin away from
the house. The three candidates were Tailscale, self-hosted WireGuard, and a plain port
forward. **Tailscale.** Installed, authenticated, and proven the same day.

### Why not the other two

| option | what it costs | verdict |
|---|---|---|
| Port-forward 8096 | a login page on the public internet, permanently | **No.** Jellyfin has shipped auth-bypass bugs. A reverse proxy makes it less bad, not good. |
| Self-hosted WireGuard | one open UDP port on the Bell router + dynamic DNS (76.64.36.43 is not permanent) + a router admin session | Viable, no third party. Rejected only because it needs the owner at the router and it still opens a port. |
| **Tailscale** | a third-party coordination server learns device names and connect times | **Chosen.** Both ends dial *out*, so **nothing is opened**. The box stays invisible from the internet — `upnpc -l` still shows zero forwards. |

The video itself is end-to-end encrypted between the two devices; Tailscale's servers
carry key exchange and NAT-traversal coordination, not media. Personal tier is $0,
unlimited devices, up to 6 users.

**The Roku can run none of them.** Remote means a phone or a laptop. Watching *on the TV*
from outside the house was never on the table.

### What was actually done

- `pacman -S tailscale` — `extra/tailscale 1.98.10-1`, native, dependency is glibc only.
  **NO DOCKER is satisfied by the package, not worked around.**
- `tailscale up --hostname=luminos-server --accept-dns=false`
- Firewall opened for the tunnel interface only (see below).
- `tailscaled` enabled + active. Tailnet IP **100.82.125.26**, MagicDNS name
  `luminos-server.tail1fd435.ts.net`.

### The trap: the LAN rule does not cover the tunnel

nftables had `ip saddr 192.168.2.0/24 accept` under a `policy drop`. Tailscale peers do
**not** arrive with a 192.168.2.x address — they arrive on `tailscale0` carrying
`100.64.0.0/10` (CGNAT space). That rule misses them entirely. Without an explicit rule the
tunnel comes up, `tailscale status` looks perfect, and **every service is silently
unreachable through it**. Added to `/etc/nftables.conf`:

```
iifname "tailscale0" accept comment "tailscale mesh"
```

Tailscale also installs its own accept rules, but they live in the `iptables-nft` `filter`
table. Those do not override a `drop` policy in a separate table, so **our rule is the one
doing the work.** `nftables.service` is `enabled`, so it survives reboot.
Backups: `/etc/nftables.conf.pre-tailscale`, `/root/nft-pre-tailscale.rules`.

### `--accept-dns=false` is not optional here

Tailscale takes over DNS by default. That would have quietly undone the DNS-over-TLS to
Quad9 set up hours earlier in DECISION 48 — lookups would go back out in cleartext while
`resolved.conf.d/` still looked correct. The before-state was recorded so the after could be
compared, and it is unchanged:

```
Global      Protocols: +DNSOverTLS   DNS Servers: 9.9.9.9#dns.quad9.net 149.112.112.112#dns.quad9.net
Link 5 (tailscale0)   Current Scopes: none      (no DNS claimed)
resolvectl query news.usenetserver.com -> "acquired via local or encrypted transport: yes"
```

The cost is that the server cannot resolve other peers by their MagicDNS name. It does not
need to — it is the thing being connected *to*.

### Proof, and the limit of it

`curl --interface 100.82.125.26 http://100.82.125.26:8096/System/Info/Public` → **200**.
That proves Jellyfin listens on the tunnel address. It does **not** prove the firewall rule,
because traffic from the box to itself never traverses `iifname tailscale0` — the rule's
counter is still 0. **The firewall rule is only proven the first time a real peer connects.**
Recorded here so it is not mistaken for a completed test.

### Owner-only: key expiry

The machine key expires **2027-02-01**. When it does, the server drops off the tailnet
silently and remote access simply stops working, months from now, with no error anywhere on
the box. Disabling expiry for `luminos-server` is one toggle in the Tailscale admin console
and cannot be done from the command line. **Do it, or diarise it.**

---

## DECISION 52 — Requesting media gets its own front door (Jellyseerr), built from source because the AUR package is a year stale

<!-- [CHANGE: claude-code | 2026-08-05] -->

**Decision:** searching for a film or show and asking for it now happens in **Jellyseerr
3.4.1** on port 5055, signed in with the same Jellyfin account, wired to Sonarr and Radarr.
Built from upstream source rather than installed from the AUR. No Docker.

### Why not "just add it to Jellyfin's search"

The original ask was for Jellyfin's own search box to also show things you don't own yet,
with a download button. **Jellyfin's search is not extensible** — there is no plugin hook
that injects Sonarr/Radarr results into it, and the Roku and Android clients are native, so
even a web-only hack would not reach the two places the library actually gets used. A
separate request app is the standard answer to this and the only one that works on a phone.

### Why build 3.4.1 instead of `pacman -S jellyseerr`

The project was renamed to **`seerr-team/seerr`** and moved on; the AUR recipe is pinned to
**2.7.3 (2025-08-14)** while upstream is **3.4.1 (2026-07-30)**. Roughly a year of fixes.
The AUR PKGBUILD was used as the starting point and adapted — vendored at
`server/packaging/jellyseerr/PKGBUILD`, with `PKGBUILD.orig` kept on the box for diffing.

Three things had to change, and one thing deliberately did **not**:

- **The upstream file renames.** `jellyseerr-api.yml` → `seerr-api.yml`, `next.config.js` →
  `next.config.ts`. The old `package()` copies these by name and would have failed.
- **`engines.node`, because of `engine-strict=true`.** The repo ships an `.npmrc` with
  `engine-strict=true`, which makes pnpm **hard-refuse to install** on a version mismatch —
  it is not a warning. The server runs **Node 26.5.0**; seerr declares `^22.19.0`. Installing
  `nodejs-lts-jod` was not an option: it conflicts with `nodejs`, which `python-playwright`
  requires, and that is Byparr. So `engines.node` was relaxed to `>=22.19.0` in `prepare()`
  and the result tested empirically instead. It builds and runs clean.
- **`arch.patch` is not applied.** Its pnpm hunk is obsolete in 3.4.1, and its other hunk
  rewrites `server.use(csurf({...}))` to `server.use(() => csurf({...}))` — which does not
  fix CSRF, it **silently disables** it, because an arrow function handed to `use()` is
  treated as middleware that never calls anything. Carrying that patch forward would have
  quietly removed a protection.

**Noted for the next upgrade:** the build prints `The "pnpm" field in package.json is no
longer read by pnpm`. pnpm 11 dropped it, so `onlyBuiltDependencies` and `overrides` are
being ignored. That did **not** bite here — `bcrypt@6.0.0` and `sqlite3@5.1.7` both compiled
— but if a future build produces a package that starts and then throws on a native module,
this is the first place to look. Build took 2m21s and produced a 220,903,491-byte package.

### Wiring, and the one setting that matters

Both `*arr` services point at **quality profile id=7**, `Max Bitrate (4K if there, else best
1080p)`, with `is4k: false` and `movie4kEnabled` / `series4kEnabled` left **off**. This is
deliberate and it is the whole lesson of the True Detective failure: profile **5**
`Ultra-HD` accepts only 2160p, and turning on Jellyseerr's separate "4K" request path would
route requests down exactly that kind of strict profile and reject everything, silently,
forever. There is one request path here and it degrades to 1080p when 4K does not exist.

**No firewall change was needed.** `/etc/nftables.conf` accepts `ip saddr 192.168.2.0/24`
and `iifname "tailscale0"` wholesale, not per-port, so 5055 was already reachable from the
LAN and over Tailscale the moment it started listening — with nothing opened to the internet.
Worth knowing in both directions: **any new service on this box is LAN-and-tailnet-exposed
by default.** That is convenient here and would be a mistake for something unauthenticated.

### Proof — a real request, not the test button

Following the standing rule (Prowlarr's "Test Successful" only ever proved the API key was
accepted), the chain was exercised with a genuine request for *Interstellar* (tmdb 157336):

```
Jellyseerr  POST /api/v1/request         -> 201, request id 1, auto-approved
Radarr      GET  /api/v3/movie           -> Interstellar 2014, profileId 7,
                                            root /srv/media/movies, monitored true
Radarr      GET  /api/v3/history         -> grabbed: Interstellar.2014.2160p.PROPER.IMAX
                                            .REMUX.DV.HDR10.TrueHD.7.1.Atmos
NZBGet      listgroups                   -> 103.5 GB, DOWNLOADING
```

Reachability was tested **from the G14**, a genuinely different machine —
`http://192.168.2.61:5055/api/v1/status` → 200, and `GET /` → 200 redirecting to `/login`
with 298 KB of rendered HTML. The Tailscale path is **untested**: this laptop is not on the
tailnet (no `tailscale` binary), so a 000 from `100.82.125.26:5055` proves nothing either
way. The Pixel 9 is the peer that would prove it.

### What the proof exposed: there are no size limits anywhere

Every quality definition in Radarr reads `maxSize: None` — 1080p and 2160p alike. So
"max bitrate" means literally *the largest file the indexer offers*, and it chose a
**103.5 GB** Dolby Vision / TrueHD Atmos remux. At the measured 11.5 MB/s wifi ceiling that
is ~2.4 hours of the only link, for one film.

**Left as-is by choice**, because the owner treats films as watch-then-delete and the disk
has 382 GB free. Recorded because it is a standing property of the setup, not a one-off: a
size cap on the quality definitions is the lever if a request ever needs to be smaller, and
it is the same lever for TV, where the same profile is attached to season packs.

### The trap found while pausing it

**NZBGet's `pausedownload` over `GET` returns an empty body and does nothing.** It requires
POST — `{"error":{"code":4,"message":"Not safe procedure for HTTP-Method GET"}}` only appears
when the response is actually read. The first pause was silently a no-op and downloading
continued at 11.8 MB/s. Confirmed properly with POST and then proven by three status samples
12 s apart, all `paused=True`, `0.00 MB/s`, bytes frozen at 0.803 GB — one sample would not
have distinguished a pause from a stalled article.

### Interaction with the 2-season cap (DECISION 44)

Jellyseerr will happily accept a request for more than two seasons — it has no per-series
season limit and its "quota" is a rolling request count, not a cap. `luminos-season-limit.timer`
is still the thing that enforces it, trimming to two monitored seasons within a day. As
designed, it keeps **any** two, not the first two, and prefers seasons that already hold
files. Live evidence rather than a reading of the code: True Detective is currently monitored
on **S01 and S04**.
