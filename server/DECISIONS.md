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

**Amended 2026-08-31 — the cost also applied to its *own* name, and that is now fixed with
one `/etc/hosts` line.** Once DECISION 84 put a real Let's Encrypt certificate on
`luminos-server.tail1fd435.ts.net`, the server was the only machine on the tailnet that
could not reach its own front door by name. Nothing user-facing was broken — the phone and
the G14 resolve it fine — but every test run *on* the box returned `000`, which reads like a
service failure and is not one. **That false signal is the actual cost, and it burned an
hour.** The fix does not touch systemd-resolved at all:

```
# /etc/hosts   (backup: /etc/hosts.bak-20260831)
100.82.125.26  luminos-server.tail1fd435.ts.net
```

`nss-files` is consulted ahead of DNS, so that one name is answered locally and never becomes
a query; **every other name still leaves over DNS-over-TLS to Quad9, unchanged.** Verified
after the edit: `Current DNS Server: 9.9.9.9#dns.quad9.net`, `+DNSOverTLS`,
`resolvectl query github.com` → "encrypted transport: yes", `Tailscale DNS: disabled`,
`ip route get 8.8.8.8` still `dev enp2s0`. All 8 HTTPS ports answer by name from the box with
no `-k` (11–48 ms), `openssl s_client -verify_return_error` → `Verification: OK`, and the
download test that originally failed now returns **206** with `accept-ranges: bytes` —
negative-tested at **401** with the key removed.

**The split-DNS alternative was rejected on purpose.** Routing only `~tail1fd435.ts.net` to
`100.100.100.100` is the more general answer and would scale to future peers, but it means
claiming DNS on the `tailscale0` link — and on this box **link DNS beats global DNS**, which
is the exact trap that forced the `UseDNS=false` drop-ins in DECISION 48. `tailscale0` is
also the one link with `Default Route: yes`, so a link resolver there would be a candidate
for *every* query, not just tailnet ones. One static line for one static address is the
smaller blast radius. Revisit only if the server ever needs to resolve a *peer* by name.

**Undo is one command:** `sudo cp /etc/hosts.bak-20260831 /etc/hosts`.

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

## DECISION 54 — Requesting media gets its own front door (Jellyseerr), built from source because the AUR package is a year stale

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

---

## DECISION 59 — Downloads are Usenet-only, and that is enforced in three places rather than assumed
# [CHANGE: claude-code | 2026-08-07]

**Decision.** Sonarr and Radarr may acquire media over **Usenet only**. The torrent path is
disabled at every layer that can independently re-open it.

**Why now.** DECISION 42 halted torrenting and DECISION 48 moved downloads to Usenet, but
neither actually *closed* the torrent path — it was left preferred-but-permitted. An audit of
the grab history on 2026-08-07 showed torrents were still being used well after those
decisions. Sonarr's history records `data.protocol` as `1` = usenet, `2` = torrent:

```
sonarr: 1  The Sopranos S01E02..E11        usenet
sonarr: 2  MobLand S01E01..E10             torrent
sonarr: 2  House of Cards 2013 S01 REMUX   torrent
radarr: 1  Interstellar 2014 IMAX REMUX    usenet
radarr: 2  The Odyssey 2026 WEBRip LAMA    torrent
radarr: 2  www.1TamilMV... Odyssey PreDVD  torrent
```

**The silent failure this was causing.** `qbittorrent` is **not installed** —
`systemctl is-enabled qbittorrent` returns `not-found`. But the qBittorrent *client entry* was
still `enable=True` in both apps at the same priority as NZBGet. So every torrent grab was
handed to a client that does not exist: no error surfaced, the item simply never arrived. The
two Odyssey grabs in the history with no corresponding file are the evidence.

**What was changed (all reversible toggles, nothing deleted):**

| layer | before | after |
|---|---|---|
| qBittorrent client, Sonarr | `enable=True` | `enable=False` |
| qBittorrent client, Radarr | `enable=True` | `enable=False` |
| Delay profile, both apps | `enableTorrent=True` | `enableTorrent=False` |
| Prowlarr torrent indexers | 9 enabled | 9 disabled |

**Three layers, because any one of them alone is not enough.** `preferredProtocol=usenet` was
*already* set and did nothing to stop torrent grabs — "preferred" means ranked first, not
exclusive. The delay profile's `enableTorrent` is the flag that actually forbids the protocol
at the decision layer; the client toggle and the indexer toggle are the belt and braces.

**Verified by negative test, not by trusting the writes.** Real searches run against both apps
after the change:

```
sonarr, episode search : 59 releases, 59 usenet, TORRENT: 0
radarr, movie search   :  3 releases,  3 usenet, TORRENT: 0
sonarr queue           : 26 items, all protocols: {'usenet'}
```

**The trap to remember: Prowlarr disables indexers in the apps but never deletes them.**
Triggering `ApplicationIndexerSync` pushes `enableRss`, `enableAutomaticSearch` and
`enableInteractiveSearch` to `False`, but the indexer *entries* remain visible in the Sonarr
and Radarr UI. "The Pirate Bay" still appears in the indexer list and is inert. Do not read
its presence as a live torrent path — read the three flags.

**Consequence to accept.** NZBGeek is now the single acquisition source. It is a US/English
indexer, so non-English content is effectively unavailable (see DECISION 60's note on French).
Adding a second *Usenet* indexer is the supported way to widen coverage; re-enabling torrents
is not.

---

## DECISION 60 — Embedded subtitles are pre-extracted on a sweep, because Jellyfin only demuxes them on first play
# [CHANGE: claude-code | 2026-08-07]

**Decision.** Run `server/scripts/luminos-subtitle-warm` over the library so embedded text
subtitle tracks are already in Jellyfin's cache before anyone presses play.

**The symptom.** "Subs are gone" on MobLand S01E02. The subtitles were not missing: the track
was present at index 2, the settings were intact, and the server was selecting it correctly.

**The real cause is latency, not absence.** Jellyfin demuxes an embedded subtitle out of the
MKV **on demand, on first request**, caching to
`/var/lib/jellyfin/data/subtitles/<2-char>/<uuid>/<index>.srt`. The extraction has to read the
whole file, which on a 2160p remux on a spinning disk takes minutes. The log showed extraction
running 23:08:40 → 23:11:04 (**144 s**) while playback had already been abandoned at 23:09:53
(69 s in). The subtitles arrived after the viewer gave up.

**Proven with a timed control rather than inference:**

```
E02 (cached)   served in 0.005923 s
E03 (uncached) still not served after 2 minutes
```

Only **5** cached `.srt` files existed library-wide at that point.

**Why a sweep and not a setting.** Jellyfin 10.11.11 has **no library option and no scheduled
task** for pre-extracting subtitles. There is nothing to switch on; the work has to be driven
externally by requesting each track once.

**Result.** 78 embedded text tracks across 51 items; **77 ok, 1 failed** (Interstellar,
`TimeoutError` — the largest file). Cache went from 5 to **290** files.

**Known weaknesses, recorded rather than papered over:**
- The script reads its credentials from `/tmp/jftoken` and `/tmp/jfuid`, which do not survive a
  reboot. It must be given a durable credential source before it can run unattended.
- It is **not yet on a timer**, so newly downloaded episodes are still cold and will show the
  same "missing subtitles" symptom on first play. This is the obvious next step.
- It only handles **text** codecs (`subrip`, `ass`, `ssa`, `mov_text`, `subviewer`, `webvtt`).
  Image-based subtitles (PGS/VOBSUB) are untouched — those need OCR or burn-in, not extraction.

**Related finding — no subtitle *fetching* exists on this box.** Bazarr is not installed, so
the only subtitles available are the ones already inside the release file. This is what makes
"French audio with English subtitles" unachievable today: a search of the one live indexer
returned **0** French/MULTI-tagged results for two well-known French titles, and no Oggy
release advertises English subtitles at all. Bazarr plus a French-capable Usenet indexer would
both be required.

## DECISION 61 — Descriptive audio is blocked at four layers, because one file proved the flags cannot be trusted
# [CHANGE: claude-code | 2026-08-07]

**Decision.** Treat audio-description and commentary releases as a grab-time rejection, not a
thing to notice afterwards. Four layers, because any single one of them can be bypassed.

**The symptom.** MobLand played with a narrator describing the picture out loud. The file was
not corrupt and the wrong track was not selected by accident — the release itself carried
descriptive narration as its only usable English audio.

**The trap that made this invisible.** Descriptive audio is supposed to be marked by the
container. On the actual offending file it was not:

```
disposition.visual_impaired = 0
disposition.comment         = 0
tags.title                  = "British (Descriptive)"
```

**Only the track title said it.** Any detector keyed on the disposition flags — which is the
documented, obvious way to do this — reads that file as clean. Detection must look at the
title string, and treat the flags as a bonus signal rather than the source of truth.

**The four layers:**
1. **Grab time.** A Sonarr/Radarr custom format scoring `-10000`, applied to all 7 quality
   profiles in both apps. `minFormatScore = 0`, so a negative score is a hard rejection.
2. **Self-healing.** The already-imported bad file scores below `cutoffFormatScore`, which
   makes *any* clean release an upgrade. Sonarr replaces it on the next search on its own —
   no manual delete was needed.
3. **Playback.** Jellyfin's per-user `AudioLanguagePreference` now pins English rather than
   deferring to the file's default-track flag, so a mislabelled file still plays the right track.
4. **Audit.** `server/scripts/luminos-audio-audit`, weekly, ffprobes the library and splits
   **UNWATCHABLE** (no clean track at all) from **MISLABELLED** (a clean track exists but the
   descriptive one is default — fixable in the player, not worth a re-download).

**Why the audit unit is allowed to fail.** It exits 1 when a file has no usable audio, and the
service deliberately does not mask that. `systemctl list-units --failed` then surfaces the
finding, instead of it sitting unread in a log nobody opens.

**The regex was nearly a bug.** The first version matched `\bAD\b`, which would have rejected
*Ad Astra* and anything else with "Ad" as a word. Tightened to require an adjacent quality
token (`[. _-]AD[. _-](1080p|720p|2160p|WEB|...)`) and negative-tested against 13 real titles,
0 false positives. Same reasoning in the audit's word list: `"AD"` alone is far too common in
real titles to be safe, so it matches `descri`, `commentary`, `narrat` instead.

**Honest note on how this was missed.** The offending release title was on screen during an
earlier torrent audit. That row was read for its protocol number and the title was never read.
The fix for that is the scheduled audit, not a promise to be more careful.

## DECISION 62 — Library space gets its own web view, and it does hardlink accounting properly
# [CHANGE: claude-code | 2026-08-08]

**Decision.** `server/scripts/luminos-space` on **port 8099**, a small Chrome-friendly page
showing what is using the disk, with delete by movie, by season and by episode, plus live
download control. Filelight for the media library, minus everything that is not media.

**Why not Filelight.** Filelight shows directories. The question being asked is "which show,
which season" — and the answer has to come with a *correct* number for how much deleting it
would actually free, which is not the file size.

**The hardlink trap, which is the whole reason this is not a `du` wrapper.** Sonarr and Radarr
import by **hardlink**, so the library file and the copy under `/srv/media/downloads` are the
same inode. Measured across the library:

```
links = 1 :   0.0 GB
links > 1 : 369.9 GB
```

Deleting the library name frees **nothing** while the download twin still points at the inode.
So the tool matches twins by `(st_dev, st_ino)` — never by filename — snapshots the inodes
*before* the API delete, and unlinks the twins after. It reports `frees` (bytes that will
actually come back) separately from `bytes` (apparent size). Negative-tested on the case that
would make it lie: an inode also linked from outside the deletion set correctly reports 0.

**Corollary worth remembering:** `links = 1` in the downloads tree means Sonarr **copied**
instead of hardlinking, and those are true orphans. MobLand had 49.94 GB of them, which is why
deleting the show freed 221 GB and not 275 GB.

**Download control, and the two ways NZBGet lies about pausing.**
- **`pausedownload` over GET is a silent no-op.** Empty body, downloading continues, looks
  exactly like success. It must be POSTed.
- **`PausedSizeMB > 0` is not a pause flag.** It is the par2 repair set, which NZBGet holds
  back on *every* healthy group — measured 1.6 GB of 21.9 GB on an actively downloading item.
  The correct test is `PausedSizeMB >= RemainingSizeMB`.
- **`Status` lags by up to 16 seconds.** Pausing the item that is actively downloading leaves
  `Status = DOWNLOADING` while its connections drain. Measured: bytes froze at t+4s
  (2690 MB, unchanged thereafter) but `Status` did not read `PAUSED` until **t+16s**. The
  `PausedSizeMB >= RemainingSizeMB` test flips at t+4s, so the UI uses it and is *more*
  truthful than NZBGet's own status string.

**Every action is read back, and a wrong id must not read as success.** `editqueue` returns
success for a command that matched no group at all — so "gone afterwards" only means something
if it was there beforehand, otherwise a bad id looks like a completed delete. The tool checks
the queue before *and* after, and polls across the drain window rather than reading once (a
single eager read reported a working pause as a failure).

**Access.** A token in the URL, not the network. nftables here accepts `192.168.2.0/24` and
`iifname tailscale0` **wholesale**, not per port, so anything that listens is already reachable
from the whole LAN and the tailnet the moment it starts.

**Runs as root** for exactly two reasons, both required: reading the Sonarr/Radarr API keys out
of `/var/lib/*/config.xml`, and unlinking hardlink twins under `/srv/media/downloads`, which is
owned `nzbget:media`. The NZBGet credentials are read once and cached — the panel polls every
5 seconds, and re-shelling `sudo` three times per poll floods the auth log for values that
never change.

## DECISION 64 — Skip intro and skip credits come from Intro Skipper, and the button is drawn by the client, not the server
# [CHANGE: claude-code | 2026-08-11]

**Decision.** The **Intro Skipper** plugin (`intro-skipper/intro-skipper`, branch `10.11`,
**v1.10.11.22**) is installed on the Jellyfin server. It fingerprints episodes, finds the
opening titles and the end credits, and writes them into Jellyfin's own `MediaSegments` table.
Detection re-runs **daily at 00:00** via the built-in `Detect and Analyze Media Segments`
scheduled task, so new episodes are picked up without anyone asking.

**Installed by hand, not from the catalogue.** The plugin repository
`https://manifest.intro-skipper.org/manifest.json` is version-aware and serves nothing to a
plain browser, so the release zip was fetched from GitHub and unpacked into
`/var/lib/jellyfin/plugins/Intro Skipper_1.10.11.22/`. The zip contains **only
`IntroSkipper.dll`** — no `meta.json`. Jellyfin loads it anyway and reports
`Status: Active`; do not go hunting for a missing metadata file.

**Since Jellyfin 10.10 this plugin does not touch the web UI at all.** It is a *Media Segment
Provider*. It only produces timestamps; **the Skip button is rendered by the client**. That is
the single most important thing to know here, because it means:
- a client that does not implement media segments will show no button no matter what the
  server does, and
- the *behaviour* (ask-to-skip vs auto-skip) is a **per-client, per-device setting** that only
  the person holding the remote can change. It is not a server setting and cannot be set from
  here.

The Roku client does support it — "Skip Segments", with a per-segment-type **Ask to skip**
option, and segments drawn on the progress bar. This server's Roku is **3.2.3**, well past the
3.1.8 that introduced the setting.

**The dependency that actually matters is chromaprint, and Arch is not on the plugin's
supported list.** Detection shells out to `jellyfin-ffmpeg` with `-f chromaprint`. Checked
directly rather than trusted: `jellyfin-ffmpeg 1:7.1.4p1-2` at
`/usr/lib/jellyfin-ffmpeg/ffmpeg` reports the `chromaprint` muxer and `--enable-chromaprint`
in its build flags. The **system** `ffmpeg 8.1.2` has no chromaprint and is irrelevant —
Jellyfin is launched with `--ffmpeg=/usr/lib/jellyfin-ffmpeg/ffmpeg`.

**It compares episodes within a season, so a one-episode season can never work.** The method
is acoustic fingerprinting of the first 10 minutes (`AnalysisLengthLimit=10`) looking for the
audio that repeats. A season holding a single episode has nothing to compare against and will
be skipped silently — that is not a fault.

**Tuned for a weak box, deliberately left alone.** Defaults are `MaxParallelism=2` and
`ProcessPriority=BelowNormal`. On this machine (i5-10210U, library on a spinning HDD) the two
ffmpeg workers sat at **15% and 8% CPU** — the scan is **I/O bound on the disk, not the CPU**,
so raising parallelism would buy nothing and would fight playback. Leave it at 2.

**Proven, not assumed.** First results, read back out of the client-facing
`GET /MediaSegments/{itemId}` endpoint and not just the database:
Better Call Saul S02E01 intro `340s → 355s`, credits `2781s → 2828s`; S02E02 intro
`391s → 406s`, credits `2802s → 2852s`. Better Call Saul puts its title card several minutes
into the episode, so those late intro timestamps are correct, not a misdetection.

**An API key was added** to the Jellyfin database as `luminos-admin` (row 3, alongside the
existing `Sonarr` and `Seerr` keys) so the task can be driven over the API. It is stored at
`/root/.jellyfin-token`, mode 600. Delete the row to revoke it.

---

## DECISION 79
# [CHANGE: claude-code | 2026-08-20]
### The wire is the default route now — a Cat 6 cable and one metric were both needed

**Decision:** replace the router→server ethernet cable with Cat 6, and add a static default
route via `enp2s0` at metric 100 so internet-bound traffic actually uses it.

**The cable was the fault, and it was measurable.** Before the swap `ethtool enp2s0` reported
**`Speed: 100Mb/s`** while the *link partner already advertised `1000baseT/Full`* — the router
and the Realtek RTL8111 were both willing, so the only remaining variable was the cable
(gigabit needs all four pairs; 100Mb/s needs two). After the swap: **`Speed: 1000Mb/s`,
`Duplex: Full`, zero RX/TX errors.**

**The second half of the problem: a gigabit cable that nothing was using.** systemd-networkd
gives the wired DHCP route the default metric **1024**, while `25-wireless.network` pins
wlan0 at **`RouteMetric=600`**. Lower wins, so `ip route get 8.8.8.8` still answered
`dev wlan0`. Every Usenet download and every remote Tailscale stream was going over a 1x1
2.4 GHz radio. **Re-cabling on its own changed nothing measurable** — that is the trap.

**Fixed with a drop-in, `20-wired.network.d/10-prefer-cable.conf`, adding one route:**
```
[Route]
Gateway=192.168.2.1
Metric=100
```
**Deliberately NOT done by lowering `[DHCPv4] RouteMetric`** on the wired file. That would
also outrank the on-link `192.168.2.0/24` route and move reply traffic for **192.168.2.61**
— the address this headless box is administered over — onto the wire. Changing the admin path
was an unnecessary risk for zero benefit. One default route was the whole fix.

**Fallback is automatic.** The static route lives with the wired link; pull the cable, the
carrier drops, networkd withdraws the route, and wlan0's metric-600 default takes over. This
is by design and was *not* physically tested — nobody unplugged anything.

**Measured, internet-facing, 4 parallel streams × 50 MB, two runs each:**

| Path | Download | Upload |
|---|---|---|
| Cat 6 cable (`enp2s0`/.62) | **927 / 958 Mbps** | **754 / 657 Mbps** |
| Wifi (`wlan0`/.61) | 95 / 107 Mbps | 59 / 66 Mbps |
| Unbound, after the change | **974.6 Mbps** | **755.1 Mbps** |

LAN throughput to the G14 went **10.7 MB/s → 41 MB/s**; that 41 is the *G14's* 2.4 GHz wifi,
not the server. The server's own remaining ceiling is the HDD at **88.8 MB/s (~710 Mbps)**.

**Applied behind a 5-minute auto-revert** (`systemd-run --on-active=300` removing the drop-in
and reloading), disarmed only after DNS, an internet fetch, Tailscale, all six services,
Prowlarr's indexers, and Jellyfin on **both** .61 and .62 were confirmed good. Do remote
network changes this way.

### Traps this turned up
- **`systemd-run` does not inherit your `cd`.** `cd /tmp && sudo systemd-run ... python3 -m
  http.server` serves from `/`. Three "45–90 KB/s" readings were 460-byte **404 pages** being
  timed as if they were transfers. Always assert `%{http_code}` and `%{size_download}`, never
  read `%{speed_download}` alone.
- **Cloudflare's `/__down` returns 403 above ~75 MB.** A `bytes=100000000` request yields
  `code=403 size=1`, which prints as a plausible-looking `0.0 Mbps` rather than an error.
- **Single-stream `curl` understates a fast link.** 25 MB at ~500 Mbps completes in 0.38 s and
  measures mostly ramp-up. Use 4 parallel streams and sum.
- **`/tmp` on this box is tmpfs.** A "disk" benchmark against a file there read at 8.6 GB/s and
  never touched `/dev/sda`. `df | grep -v tmpfs` hides exactly the fact you need.

---

## DECISION 84
# [CHANGE: claude-code | 2026-08-27]
### The phone gets one HTTPS front door — but the login prompt had to be built before the door was

> **Renumbered 80 → 84 on 2026-08-27, a few hours after it was written.** It was filed as 80
> without checking `LUMINOS_DECISIONS.md`, which already had a DECISION 80 from 08-25. Per
> CLAUDE.md the two files share **one** sequence, so 84 is the next genuinely free number.
> Commit `e2fc90d7` and the Luminos Note from that day still say "DECISION 80" — they mean
> this entry. **A pre-existing collision on 79 is still unresolved** and is not mine to fix
> silently: server 79 (Cat 6 / default route, 08-20) and main 79 (Dolphin over TLS, 08-24)
> are different decisions with the same number.

**Decision:** put Caddy in front of everything on ports 443 and 8443–8449, serve a small
landing page (`luminos-hub`) at the root, and reach it from a phone over Tailscale. **But the
first and most important part of this work was not the proxy — it was discovering that three
apps had no password at all, and that adding the proxy would have hidden that fact instead of
fixing it.**

**The landmine.** Radarr, Sonarr and Prowlarr were all set to
`AuthenticationRequired = DisabledForLocalAddresses`, with `Username` and `Password` **empty
and unsalted** in `/var/lib/{app}/{app}.db`. "Local" to those apps means loopback *and* RFC1918
— so every device on the house wifi was already a full administrator with delete rights over
the whole library. Tailscale's 100.64.0.0/10 is CGNAT, not RFC1918, which is the only reason
the tailnet still saw a login prompt. **A reverse proxy makes every request arrive from
127.0.0.1.** Shipping the proxy first would have made even the tailnet look local and silently
deleted the last remaining prompt. Passwords were set through each app's own API (so they are
hashed and salted properly) and auth switched to `Enabled` **before** Caddy was installed.

**The rule that falls out of this: before proxying any app, hit it from 127.0.0.1 with no
credentials and confirm you are refused.** Done for all seven — arrs 302 to `/login`, NZBGet
401, Jellyfin 401, Jellyseerr 307 to `/login`, luminos-space 403 without its token. NZBGet's
`AuthorizedIP=` was checked and is empty; had it listed 127.0.0.1 it would have become an
open-by-design bypass the moment the proxy went in.

**One port per app, not sub-paths — sub-paths were tried and failed.** Radarr/Sonarr/Prowlarr
do have a `urlBase` setting, and it was set to `/radarr`, `/sonarr`, `/prowlarr` and verified
working. It then turned out `urlBase` **only rewrites the UI shell**: the login page stays at
`/login` and the API stays at `/api/` regardless. Three apps under one hostname therefore all
fight over the single path `/login`, with no clean tie-break. `urlBase` was reverted to empty.
Jellyfin, Jellyseerr and luminos-space have no base-path setting at all.

| Port | Behind it | Why not a sub-path |
|---|---|---|
| 443 | `luminos-hub` (the landing page) | — |
| 8443 | Jellyfin 8096 | no base-path setting; also see below |
| 8444 | Jellyseerr 5055 | upstream feature request, open since Overseerr |
| 8445 | NZBGet 6789 | root-absolute URLs |
| 8446 | luminos-space 8099 | root-absolute URLs; Caddy injects its token |
| 8447 | Radarr 7878 | `/login` collision |
| 8448 | Sonarr 8989 | `/login` collision |
| 8449 | Prowlarr 9696 | `/login` collision |

**Jellyfin was deliberately left unconfigured.** Setting a `BaseUrl` on it would break the
Roku's saved server address. The TV working is worth more than tidy URLs, and 8096 stays open
on the LAN for exactly that reason.

**`luminos-hub` holds the API keys so the browser never does.** A static page of bookmarks
could not show free space, the download queue or recent imports without shipping Radarr's and
Sonarr's keys to every device that loads it. The hub queries them server-side and returns only
answers. It binds **127.0.0.1 only** — verified by a refused connection to
`192.168.2.61:8100` — so Caddy is the single front door. Confirmed the rendered page contains
zero 32-hex-character strings. Unlike `luminos-space` it does **not** run as root: it only
reads, so it gets its own account, group `media` for the three `config.xml` files, and a single
ACL entry (`setfacl -m u:luminoshub:r`) on `nzbget.conf` rather than loosening its 0600 mode.

**HTTPS was Caddy's local CA for about an hour, then became a real certificate — the owner
turned on HTTPS Certificates at login.tailscale.com/admin/dns and the block cleared.**
`luminos-server.tail1fd435.ts.net` now serves a genuine Let's Encrypt certificate on all eight
ports: no browser warning, no `-k`, handshake 10–25 ms. The two bare IP addresses
(`192.168.2.61`, `100.82.125.26`) stay on `tls internal`, because a public CA will not certify a
private address — that is a permanent split, not a temporary one, and it is why the name and the
IPs are separate site blocks.

**Caddy is deliberately not allowed to fetch its own certificate.** Caddy's native
`get_certificate tailscale` would work, but `tailscale cert` refuses a non-root caller unless
that user is made the tailnet **operator** — and an operator can run `tailscale down`, change
exit nodes, and re-authenticate the machine. Granting that to the one internet-facing process on
the box would turn a Caddy compromise into a Tailscale compromise, on a machine whose entire
security model is "Tailscale is the perimeter". So root fetches and Caddy only reads two files:
`/var/lib/luminos/tls/cert.pem` (0644 root:caddy) and `key.pem` (0640 root:caddy).

**The price of that choice, stated plainly: renewal is now our job, and its failure mode is
silence.** `luminos-tailscale-cert` runs daily from a timer (`RandomizedDelaySec=1h`,
`Persistent=true` because this box is switched on and off by hand). Certificates last 90 days
and tailscaled only re-issues near expiry, so a daily run costs nothing and gives ~14 chances to
succeed. The script compares the SHA-256 fingerprint before and after and reloads Caddy **only**
when the file actually changed, and it **exits 1 while there are still 30 days of runway** so
`systemctl list-units --failed` surfaces the problem a month early rather than on the day the
site dies. The unit has no `Restart=` and is not silenced, on purpose.

**The real cost of the toggle, and it is a privacy cost, not a security one: the machine name
is now published in public Certificate Transparency logs, permanently.** Every certificate any
public CA issues must be submitted to append-only public logs, and the certificate proves its
own submission — `openssl x509 -text` on ours shows **two CT Precertificate SCTs** stamped
`Aug 27 04:35:03 2026 GMT`. So `luminos-server.tail1fd435.ts.net` and the tailnet ID
`tail1fd435` are searchable by anyone on crt.sh forever, and every future machine that gets a
cert adds its name too. This is inherent to public TLS, not something Tailscale chose. **It
does not open anything:** those names have no public DNS records, so knowing one gets you a
NXDOMAIN — the door is still Tailscale's WireGuard tunnel and an unexpired machine key. What it
does leak is that this tailnet exists and roughly what is on it. The alternative was the local
CA and a warning on every device; that trade was made knowingly.

**The first `tailscale cert` call after flipping the toggle fails, and it is not a real
failure.** It returns `acme: order ... status: invalid` — the DNS-01 TXT record on
`_acme-challenge.<name>` is published and then queried immediately, and the first request loses
that propagation race. A `sleep 15` and one retry are baked into the script.

### Traps this turned up
- **Caddy hijacks `*.ts.net` names and it fails silently as a 20-second hang.** Caddy has
  built-in Tailscale support and routes any `.ts.net` name through **on-demand TLS**, which
  **overrides an explicit `tls internal` in the site block**. It asks tailscaled, gets the 500
  above, and falls through to **public Let's Encrypt** for a name with no public DNS record —
  failing NXDOMAIN, forever, against both prod and staging. The symptom is not an error
  message: the TLS handshake just hangs and the browser spins, on *every* port at once. The
  name was removed from the Caddyfile; `100.82.125.26` works identically over mobile data.
  Handshake went from a 20 s timeout to **2.5 ms**. **Resolved the same day** — with the toggle
  on and an explicit `tls /var/lib/luminos/tls/cert.pem /var/lib/luminos/tls/key.pem` in the site
  block, the on-demand path is never entered and `journalctl -u caddy` shows **zero** ACME lines.
  The rule to keep is narrower than "never use the name": a `.ts.net` name in a Caddyfile must
  carry explicit certificate files, or Caddy will go and find its own.
- **`local_certs` in the global block did not stop it.** The adapted JSON showed exactly one
  automation policy with `{"module":"internal"}` — and Caddy went to ACME anyway, because the
  on-demand path has its own policy. Reading the adapted config was not enough; only the
  runtime log told the truth.
- **The `*arr` API ignores `urlBase`.** With `urlBase=/radarr`, `GET /radarr/api/v3/config/host`
  returns **302 to a login page** and `GET /api/v3/config/host` returns **200**. A script that
  assumed the prefix got a `JSONDecodeError` on HTML, which reads like an auth failure and is
  not one.
- **Prowlarr is API v1 while Radarr and Sonarr are v3.** Asking Prowlarr for v3 returns **404
  with a perfectly valid key** — and 401 with an invalid one, so a 404 actually *proves* auth
  passed.
- **Right after a Caddy restart, requests to newly-added ports return `000`, not an error.**
  Twenty-one certificate identifiers were being minted at once. Everything was fine; the tests
  were early. Re-run before believing a failure.

---

## DECISION 89 — The server powers itself on, because it has no battery to ride out anything
# [CHANGE: claude-code | 2026-09-02]

**The finding that reframes this whole machine.** `/sys/class/power_supply/` on the Dell
3590 contains exactly one entry: `AC`. **There is no battery device at all.** So the thing
we have been treating as "an old laptop that crashes if you nudge it" is really a desktop
with no PSU hold-up: every power blip, every yanked cable, every outage is an *instant hard
power-off*, and it then stays off until a human walks over and presses the button.

That is why the box keeps "dying" and why it needed someone physically present to come back.
A normal laptop would have ridden the outage out on its battery; this one cannot.

### The fix is a BIOS setting, and it can be set from Linux

`dell_wmi_sysman` is loaded and exposes 90 BIOS attributes under
`/sys/class/firmware-attributes/dell-wmi-sysman/attributes/`. No BIOS admin password is set
(`authentication/Admin/is_enabled` = `0`), so writes go straight through — **no reboot into
the firmware menu, no screen, no keyboard.**

| Attribute | Was | Now | Effect |
|---|---|---|---|
| `WakeOnAc` | `Disabled` | **`Enabled`** | power returns → it boots itself |
| `WakeOnLan` | `Disabled` | **`LanOnly`** | can be woken on demand from the LAN |

**Read the values with `sudo`.** The attribute files are mode `0600 root`, and a plain `cat`
returns an *empty string* rather than a permission error — a first pass listing all the
attributes showed every `current_value` as blank and looked like the driver was broken. Same
silent-empty shape as `tcpdump`/`checkupdates` printing `0` when not installed. Always write
then **read back**, because a `tee` into sysfs can return success and still be rejected by
firmware.

### Wake-on-LAN needs BOTH halves

The BIOS setting alone does nothing: the NIC also has to be armed, and it was at
`Wake-on: d` (disabled). `/etc/systemd/network/10-wired-wol.link` sets `WakeOnLan=magic`,
matched on the wire's MAC (`c0:3e:ba:29:2d:c8`). Now `Wake-on: g`.

**That .link file copies `NamePolicy`, `AlternativeNamesPolicy` and `MACAddressPolicy`
verbatim from `/usr/lib/systemd/network/99-default.link`, and those lines are load-bearing.**
A `.link` that matches a device but omits them does not inherit the stock policy — it falls
back to different naming and can rename `enp2s0`. On a headless box reached only over that
NIC, that means driving to it. Verified after `udevadm trigger` that the name survived, and
that the DECISION 79 routing rules (`from 192.168.2.62 lookup 100`, wire winning the default
route at metric 100) were still intact.

`scripts/luminos-wake-server` sends the packet. It is **stdlib-only on purpose** — installing
`wakeonlan` or `etherwake` on the G14 means touching pacman with 213 upgrades pending, one of
which reverts the desktop look (DECISION 72), and a 102-byte packet does not justify that.
It targets the **broadcast** address, not `192.168.2.62`: the machine is off, nothing answers
ARP for it, and a unicast magic packet has nowhere to go. This is the usual reason WoL
"doesn't work". It also means **WoL only works from inside the house** — broadcast does not
cross the tailnet.

### What is proven and what is not

Proven: both BIOS values read back correctly; `ethtool` reports `Wake-on: g`; interface name
and routing survived; all services active/enabled; hub answers 200 in 46 ms.

**Not proven remotely: `WakeOnAc` itself.** The only real test is cutting mains power, which
needs someone at the machine. The 20-second version: unplug it at the wall, wait ten seconds,
plug it back in, do not touch the power button. It should boot on its own.


### The thing that would have broken "comes back on its own" anyway

`journalctl --list-boots` shows **4 of the last 4 previous boots ended uncleanly** — the
power cable, exactly as described. Nothing is damaged yet: both ext4 filesystems report
`Filesystem state: clean` with no error count, and all four SQLite databases (jellyfin,
sonarr, radarr, prowlarr) are in **WAL** mode and return `integrity_check = ok`. WAL is doing
real work here; it is the reason repeated hard cuts have not corrupted the library.

But the kernel cmdline had **no `fsck.repair`**, so it defaulted to **`preen`** — which fixes
only trivially-safe things and, on anything worse, **fails and drops to `emergency.target`**.
And `passwd -S root` returns **`L`: the root account is locked**, so that emergency prompt
cannot be logged into at all. The combination means one bad power cut would leave a headless
box sitting at a prompt nobody can answer, needing a monitor, a keyboard and a USB stick.

Added **`fsck.repair=yes`** to `/boot/loader/entries/luminos.conf`. Auto-repair without a
human is the correct trade for a machine nobody can see; the alternative is not "a human
decides", it is "the server is dead until someone drives to it".

**That file is the single point of failure for booting** — there is exactly one boot entry
and `editor no` is set. It was backed up to `luminos.conf.bak-20260902` (a `.bak` suffix, so
systemd-boot will not parse it as a second entry), rewritten with deterministic content
rather than a regex, and verified with `diff` plus `bootctl list` showing the entry still
default and selected.

### Deliberately not done

`AutoOn` (`Disabled;Everyday;Weekdays;SelectDays` + `AutoOnHr`/`AutoOnMn`) would power the
box on at a fixed time daily, which would recover even from *someone pressing the button*.
Left off pending a decision — it is a behaviour change with a schedule attached, not a
straight repair.

**Undo:**

```bash
A=/sys/class/firmware-attributes/dell-wmi-sysman/attributes
echo -n Disabled | sudo tee $A/WakeOnAc/current_value
echo -n Disabled | sudo tee $A/WakeOnLan/current_value
sudo rm /etc/systemd/network/10-wired-wol.link && sudo udevadm control --reload
```

---

## DECISION 90 — The home network stops being a trust boundary, and three services stop relying on it
# [CHANGE: claude-code | 2026-09-02]

**Ask:** "what can we do to make server most secure — forget the G14."

Six changes. Five are closures, one is the thing that was actually missing.

### 0. The finding that set the priority

A port sweep from the G14 against the server found **byparr on `:8191` answering
HTTP 200 on `/docs` — FastAPI's interactive API console, no authentication of any
kind — to every device on the wifi.** byparr holds no data worth stealing. That is
not the risk. Its entire purpose is to fetch arbitrary URLs through a real headless
browser, so an open one is a machine inside the house that makes requests on
somebody else's behalf.

The same sweep found **luminos-space running as root**, bound to `0.0.0.0:8099`,
with a token in the URL as the only thing between the network and a button that
deletes films.

Both were reachable because of one firewall line: `ip saddr 192.168.2.0/24 accept`.
Everything below follows from deciding that line was wrong.

### 1. Backups — the gap, not a closure

There were **none**. Four SQLite databases held every quality profile, indexer,
naming rule and watch state, on a machine whose last four boots all ended
uncleanly because the power cable gets bumped. WAL mode is why that has not
corrupted anything yet, but "it has not happened yet" is not a backup.

`server/scripts/luminos-backup` uses `sqlite3 .backup` (a consistent snapshot of a
*live* database — copying the file while an app writes to it gives you a file that
may not open), then `PRAGMA integrity_check`, then tars the configs.

Two things it gets right that the obvious version does not:

- **`DEST=/srv/media/backup/luminos`, not `/srv/backup`.** The obvious path lands on
  sda2 — the 23 GB root partition. Backups grow. Filling root is precisely what
  strands a headless box. sda3 has 446 GB.
- **`integrity_check` returns `ok` on a zero-byte file.** So it is not proof of
  content. Verification queries actual row counts: 4 series, 5 movies, 11 indexers,
  1 user.

Jellyfin's `library.db` and `authentication.db` are excluded with a comment saying
why: they are 0-byte leftovers, and dumping them would "pad the log with two
reassuring lines that mean nothing."

**Direction is a security control.** `scripts/luminos-pull-server-backup` runs on the
G14 and *pulls*. Push would require the server to hold a credential for the laptop,
which means anything that compromises the server reaches the laptop. Pull means the
server holds nothing. It uses `--rsync-path="sudo rsync"` to read root-owned 0600
files as an unprivileged user, over the wire (`.62`) because that is the default
route. Both ends run daily with `Persistent=true` — the box is off more than it is on,
so a missed timer must fire late rather than never.

### 2. The firewall — named ports, and the tailnet becomes the trusted path

`server/config/nftables.conf`. The blanket subnet accept became five rules: `22`,
`{80,443}`, `8443-8449`, `8096`, `udp 68`.

**Narrowing this cost nothing**, and that is the whole reason it was possible.
DECISION 80/84 already publishes every one of those apps over TLS on 8443-8449.
Closing the bare ports did not remove access, it removed the *unencrypted duplicate*
of access that already existed.

Three details that are not decoration:

- **`8096` stays open in the clear, deliberately.** The Roku app stores a bare server
  address, does not follow redirects, and will not accept Caddy's local CA. The
  Caddyfile already refuses Jellyfin a base URL for the same reason. The TV working
  beats closing this, and Jellyfin demands a login regardless of where you came from.
- **`udp 68` is load-bearing.** Both NICs get their address by DHCP, and a renewal
  answered by *broadcast* is not matched by `ct state established,related`. Leave it
  out and the lease can silently fail to renew, dropping the box off the network by
  itself some hours later — the exact unattended failure DECISION 89 exists to fix.
- **`iifname "tailscale0" accept` stays wide open, and that gap is now the design.**
  The tailnet is the trusted path: every peer is authenticated and every machine on it
  is ours. The home wifi holds a TV, phones and guests. Anything needing a port not
  listed above should be reached over Tailscale, not by reopening it here.

**`flush ruleset` was removed from the top of the file.** It had been there since
2026-07-30. It deletes *every* table on the machine, not just this one — including the
four `ip`/`ip6` `filter`/`nat`/`mangle` tables **tailscaled** owns and marks "do not
touch". Every reload silently deleted Tailscale's rules, and the damage showed up
later as the tunnel behaving strangely. Replaced with the standard idiom:
`table inet filter` / `delete table inet filter` / `table inet filter { … }` — name it
first so the delete cannot fail on a cold boot.

Loaded behind a 5-minute `systemd-run --on-active=300` auto-rollback, cancelled only
after a **new** SSH session proved access. This matters because
`ct state established,related accept` comes first, so the session you are already
sitting in survives any rule change — testing in it proves nothing.

### 3. byparr — loopback, and a sandbox setting deliberately left out

`server/systemd/byparr-override.conf`. The packaged unit ships `HOST=0.0.0.0`; now
`127.0.0.1`. Prowlarr is the only consumer and already used `http://localhost:8191/`,
so this cost nothing. Checked that no other config references 8191 — the hits in
`sonarr.db`/`radarr.db` are digits inside UUIDs and timestamps, not settings.

**`ProtectSystem` is absent on purpose, and that was measured.** With
`ProtectSystem=strict` byparr starts cleanly and then fails every actual request:

```
OSError: [Errno 30] Read-only file system:
'/usr/lib/python3.14/site-packages/playwright_captcha/utils/
 camoufox_add_init_script/addon/scripts/script_*.js'
```

`playwright_captcha` deletes and rewrites files inside its own site-packages
directory at solve time. All three levels (`yes`/`full`/`strict`) make `/usr`
read-only, so all three break it.

The obvious fix — a `ReadWritePaths` carve-out for that one directory — was
**rejected**. The path contains `python3.14`. A Python minor bump moves it, systemd
goes on starting the unit happily, and byparr fails only at request time, which reads
as "the indexers are flaky" rather than as a config error. **A brittle carve-out that
fails silently is worse than not having the setting at all.**

`MemoryDenyWriteExecute` is also absent — it breaks the JavaScript JIT and the browser
never starts. Everything else is on.

I caught this because the Prowlarr proxy test returned 500 after my change and I read
the journal instead of assuming it was pre-existing. Post-fix it returns `{}` `HTTP:200`.

### 4. luminos-space — both reasons for root were false

`server/systemd/luminos-space.service` + edits to `server/scripts/luminos-space`.
Now runs as `luminosspace`, binds `127.0.0.1:8099`, sits behind Caddy's `:8446`.

The old unit justified root with two reasons and **both measured wrong**:

1. *"It needs root to read the Sonarr/Radarr API keys."* Those files are `0664`
   `<app>:media`; group `media` reads them fine. The script was shelling out to
   `sudo -n grep` — so it needed root only because it had chosen to use sudo.
   Circular. It now opens the file and regexes `<ApiKey>` directly.
2. *"It needs root to unlink hardlink twins under `/srv/media/downloads`."*
   **Unlinking needs write on the directory, not the file.** Both directories are
   `drwxrwsr-x` group `media`.

`nzbget.conf` is the one genuine exception — `0640 nzbget:nzbget`, it holds the Usenet
password. Granted with a single ACL entry rather than widening a group:
`setfacl -m u:luminosspace:r /var/lib/nzbget/nzbget.conf`. Reading it is non-fatal, so
the disk view still works if NZBGet is down.

`luminos-hub` had been running this exact unprivileged pattern since 2026-08-27, and
its own comment pointed at luminos-space as the one still unfixed.

The unit gets `IPAddressAllow=localhost` / `IPAddressDeny=any` — every peer it talks
to is on this machine, so a bug here cannot become a route to the internet. The URL
token still exists; it is now a second lock rather than the only one.

### 5. Caddy answers on the wire

Every site block listed `100.82.125.26` and `192.168.2.61` but **not `192.168.2.62`**.
The wire is the default route (DECISION 79), and the wifi is the interface whose
ath10k firmware crashed earlier the same day — so the entire web front door depended
on the less reliable of the two addresses. `.62` added to all eight blocks.

A host absent from every block does not 404. It **fails the TLS handshake** (curl exit
35), which reads as "the server is down".

### 6. The update, and a false negative worth remembering

`pacman -Qu` reported **1** package. The real number was **145**, including openssl,
glibc, tailscale and a kernel jump 7.1.5 → 7.2.2. `-Qu` compares against the *sync
database*, so a stale DB is a silent false negative — it tells you you are current when
you are 145 behind. Also: `informant` hooks pacman and aborts the upgrade until Arch
news is read.

Rebooted, since after a kernel upgrade the running kernel's `/usr/lib/modules/<ver>` is
deleted and the machine cannot load *any* module until it restarts. Back in **55
seconds**: 0 failed units, fsck clean on its first `fsck.repair=yes` run (DECISION 89),
all 11 services active, firewall loaded, `Wake-on: g` still armed, BIOS `WakeOnAc` and
`WakeOnLan` persisted, and **zero ath10k firmware crashes** on the new kernel with
`linux-firmware-atheros` installed.

### Verified, not assumed

- **Negative tests:** all seven bare ports (`8191, 8099, 8989, 7878, 9696, 6789, 5055`)
  refuse from `192.168.2.16`. A change that only proves the good path is half a test.
- **Positive:** Roku path `8096→302`; `443` and `8443`–`8449` answer on both `.61` and
  `.62`; tailnet reaches `8989`/`9696`/`6789`; luminos-space `/api/data` and
  `/api/downloads` return real data and a bad token returns 403.
- **Cold table:** `nft delete table inet filter` then `systemctl start nftables`, to
  prove the file loads when the table does not already exist.
- One scare that was not: `systemctl status nftables` reads `inactive (dead)` after
  `status=0/SUCCESS`. It is a `Type=oneshot` without `RemainAfterExit`. Normal.
- One diagnosis that was not the firewall: `ssh 100.82.125.26` failed host-key
  verification mid-sweep. Tailnet HTTP had already succeeded, so it was the G14's
  `known_hosts`, not my rules. Confirmed with `-o StrictHostKeyChecking=accept-new`.

### Deliberately declined

- **Full-disk encryption with TPM auto-unlock.** The correct answer for a machine
  someone could carry off, and genuinely the largest remaining gap. It needs the root
  filesystem rebuilt, which on a headless box with no monitor and a locked root account
  means one bad step ends in a drive to the machine with a USB stick. Not something to
  do unattended.
- **A BIOS admin password.** It is credential creation (which I do not do), it risks
  locking the machine out of its own firmware, and it would block the `dell_wmi_sysman`
  path DECISION 89 uses to set `WakeOnAc` from Linux.
- **`fail2ban`.** SSH is key-only with `PasswordAuthentication no`. There is nothing to
  brute-force, so it would add a service and log noise for no reduction in risk.
- **Removing passwordless sudo.** It is what the backup pull and every automation here
  runs on. Removing it breaks the things that make the box survivable.

### What this leaves broken

**nzb360 on the phone**, if pointed at bare `192.168.2.61:8989` / `:7878` / `:6789`,
stops connecting. Use the Caddy ports (`8448`, `8447`, `8445`) or the tailnet address.
Nothing else on the LAN used the bare ports.

**Undo** — every replaced file was copied first:

```bash
sudo cp /root/nftables.conf.bak-20260902 /etc/nftables.conf && sudo nft -f /etc/nftables.conf
sudo cp /root/Caddyfile.bak-20260902 /etc/caddy/Caddyfile && sudo systemctl reload caddy
sudo cp /root/byparr-override.bak-20260902 /etc/systemd/system/byparr.service.d/override.conf
sudo cp /root/luminos-space.service.bak-20260902 /etc/systemd/system/luminos-space.service
sudo cp /root/luminos-space.bak-20260902 /usr/local/bin/luminos-space
sudo systemctl daemon-reload && sudo systemctl restart byparr luminos-space
sudo systemctl disable --now luminos-backup.timer
```


## DECISION 91 — The library grows to 1.5 TB by adding a second root folder, not by pooling the two disks

<!-- [CHANGE: claude-code | 2026-09-03] -->

A 500 GB USB drive (`ST500LM030`, serial `ZDE7LHD0`) was plugged into the box and left
unmounted. It came up as `sdb`, one ext4 partition labelled `MEDIA`, **empty** — formatted
the same day, 36 K used, nothing but `lost+found`. Mounted at **`/srv/external`**, taking the
library from 876 G to a **1.4 TiB pool with 903 G free**.

### Why not one filesystem

The obvious reading of "1 TB to 1.5 TB" is a single 1.5 TB volume — LVM spanning, or btrfs
multi-device. Both are wrong here for the same reason: **they fuse the failure domains.** A
spanned volume across an internal SATA disk and a bus-powered USB laptop drive loses
*everything*, including the 386 G already on the internal disk, when the USB side hiccups —
and USB drives drop off for reasons a SATA drive never would: a knocked cable, a spin-down,
the brownouts this machine already gets (four unclean boots in four, DECISION 89). It also
can't be done in place: `/srv/media` is a plain ext4 partition with 386 G on it and nowhere
to stage a rebuild.

`mergerfs` would pool them and degrade gracefully — losing a branch loses only that branch.
It was rejected on cost, not correctness: **it is not in the Arch repos** (checked against
`archlinux.org/packages`, 0 results — AUR only), so it means a from-source build plus a
maintained out-of-tree FUSE layer sitting in the media server's data path, and a restructure
that remounts `sda3` away from `/srv/media` — the path every service is configured against.

### The hardlink argument, and why it expired

The reflex objection to a second filesystem is hardlinks: Sonarr and Radarr import by
hardlink, hardlinks cannot cross filesystems, so a second disk turns every import into a
copy. Measured, that is **360.1 GB of 414.3 GB of large files currently hardlinked** — 87%,
which looks decisive.

It isn't, because those twins are **torrent-era residue**. Downloads were retained to seed;
`qbittorrent-nox` was uninstalled in DECISION 84 and nothing seeds now. Both apps have
`removeCompletedDownloads=True` on the NZBGet client, so a completed download is deleted
after import. The copy penalty is therefore **transient** — one release, on the internal disk,
during the import window — not permanent double storage. Internal has 446 G of headroom
against a worst-case ~100 G remux (DECISION 54). That is the whole reason a FUSE layer is not
needed, and if completed-download removal is ever turned off, this reasoning expires with it.

### What was actually done

- `nofail,x-systemd.device-timeout=10` in `/etc/fstab`, by UUID. **This is the load-bearing
  option.** Root is locked (`passwd -S root` → `L`) and there is no keyboard on this box; a
  USB disk that fails to enumerate must never reach `emergency.target`. Verified through the
  generated unit, not assumed: `RequiredBy=` is empty and `WantedBy=local-fs.target`, so an
  absent drive lets boot continue. `fstab` backed up to `/etc/fstab.bak-20260903` and checked
  with `findmnt --verify` before `daemon-reload`.
- Mounted outside `/srv/media` on purpose. A mountpoint *inside* it means that if the drive
  ever fails to mount, writes land on the underlying directory on `sda3` and silently fill the
  internal disk instead of failing.
- `root:media 2775`, setgid, and the **whole traverse chain** checked with `namei -l` — the
  `os.makedirs` umask trap that cost an afternoon on `/srv/media/usenet` produces a perfect
  leaf under an untraversable parent. All four service accounts (`sonarr`, `radarr`,
  `jellyfin`, `nzbget`) were proven to write there before anything was registered.
- Second root folders added: `/srv/external/tv` (Sonarr), `/srv/external/movies` (Radarr),
  both reporting `accessible: true`.
- Added as **additional paths on the existing Jellyfin libraries**, not as new libraries, so
  `Movies` and `Shows` each span both disks and the split is invisible to the Roku.

### The lever, left deliberately unpulled

> **Superseded the same day by DECISION 92** — the lever is now pulled automatically by
> `luminos-root-balance.timer`. Kept because it states the constraint that decision solves.

Jellyseerr's `activeDirectory` still points at `/srv/media/movies` and `/srv/media/tv`, so
**every new request still lands on the internal disk** and the external one stays empty. That
is the correct order — fill the faster internal spindle first, and keep new writes off the USB
bus while 446 G of better storage is free. When internal runs low, change `activeDirectory` in
`/var/lib/jellyseerr/settings.json` (or the Jellyseerr UI) to the `/srv/external` paths. There
is no auto-balancing; this is the one manual step, and it is a single setting.

### Known and accepted

**This drive's health is unreadable.** `smartctl` was tried through `auto`, `sat`, `sat,12`,
`usbjmicron`, `usbsunplus`, `usbcypress` and `scsi` — the enclosure passes none of them. No
power-on hours, no reallocated or pending sector counts, on a laptop drive of unknown age.
It will fail without warning. Nothing irreplaceable should live only here, and `/srv/media/backup`
was deliberately **not** moved onto it — a backup you cannot health-check is a poor backup.
The graceful-degradation property is what makes this acceptable: if the drive dies, Jellyfin
shows fewer items and everything on the internal disk is untouched.


## DECISION 92 — The root folder picks itself, because no app in the chain has a "most free space" policy

<!-- [CHANGE: claude-code | 2026-09-03] -->

DECISION 91 left one manual step: Jellyseerr pins `activeDirectory` to a single path, so every
request landed on the internal disk until a human changed it. That is not automation, it is a
reminder someone has to remember months from now. This removes it.

### Why a timer and not a pooling filesystem

The textbook answer is `mergerfs` with a most-free-space create policy — placement happens in
the filesystem and no app knows there are two disks. It was rejected in DECISION 91 for being
AUR-only, and wanting automation does not change that arithmetic: it still means a from-source
FUSE layer in the media server's data path plus remounting `sda3` away from `/srv/media`, the
path every service is configured against.

The thing that actually needs deciding is not *where each file goes* but **which root folder a
request is created with** — one choice per request, not per file. That is a scheduling problem, and
`luminos-season-limit.timer` already establishes the pattern on this box: when an app is missing
a setting, supply it from outside on a timer rather than replacing the app. Same shape here.

`/usr/local/bin/luminos-root-balance`, hourly, stdlib-only Python (installing anything means
pacman on a headless box). It reads free space on both library disks and moves Jellyseerr's
`activeDirectory` to whichever has more. Hourly rather than the season-limiter's daily cadence:
a request can arrive at any moment and the root folder has to be right *before* it does.

### The guard that is the whole point

**`/srv/external` is a mount point, so if the USB drive drops off, the directory still exists —
empty, on the root filesystem — and `statvfs()` reports root's free space.** Measured with the
drive unmounted: **19 GB**, presented exactly as if it were a healthy library disk. A naive
most-free-space check would, once the internal disk filled below that, route a 100 GB remux at
`/` and take the whole box down.

So a candidate is only eligible if `os.path.ismount()` is true for its disk root, plus the
directory exists and is writable. **Verified by actually unmounting the drive**, not by reading
the code: the script correctly skipped `/srv/external/movies` and held its current choice.

### Hysteresis, because two disks of similar size flap

Pure most-free-space would rewrite the setting every hour while the disks sit 13 GB apart.
A switch only happens on a **20 GB** lead, so the current choice wins ties. The disks are at
478 G and 491 G today, so the live behaviour is "hold on the internal disk" — which is also
the right answer on the merits, since the internal spindle is faster than the USB bus.
`LOW_WATER_BYTES` warns at 120 G: quality definitions are all `maxSize: None` (DECISION 54)
and a 103.5 GB grab has already happened, so headroom has to clear one worst-case release.

### Two Jellyseerr traps found while building it

- **Editing `/var/lib/jellyseerr/settings.json` under a running Jellyseerr does nothing.** It
  keeps settings in memory and rewrites the file on its next save, silently discarding the
  edit. The API is the only real way in.
- **Jellyseerr rejects its own `GET` body on `PUT`.** Feeding an object straight back from
  `GET /api/v1/settings/radarr` returns **HTTP 400 `request/body/id is read-only`**. `id` goes
  in the URL and must be stripped from the body — but only `id`, since every other field
  omitted is treated as a change. The first build of this script failed exactly here, which is
  the argument for testing the write path rather than trusting a 204 on the read path.

### Verified, not assumed

The forced-switch test ran with `HYSTERESIS_BYTES = 0` to make it commit a real change, then
confirmed the new value by reading it back through the API, then ran again to prove idempotency
("already on … — no change"). Both services were restored to `/srv/media` afterwards and
`settings.json` **diffed field-by-field against a pre-change backup: identical**, so the PUT
round-trip dropped nothing — the real risk when sending a whole object back. The unit was then
exercised through systemd, not just from a shell.

Failure is loud on purpose: the script exits 1 if a disk is unusable or a write does not stick,
and the unit is `Type=oneshot`, so systemd marks it failed. Continuing to quietly fill one disk
is the failure mode this exists to prevent.
