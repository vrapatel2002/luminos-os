# Home Media Server — Cost / Investment Plan
# [CHANGE: claude-code | 2026-07-28]
# Status: PROTOTYPE RUNNING on the G14 — hardware still unpurchased.
# Scope: prototype here, then migrate to a SEPARATE cheap machine (§9).
#        The G14 is NOT the intended long-term host.
#
# Goal: a local "Netflix" (Jellyfin) serving 4K to the Philips Roku TV over LAN,
#       plus an assessment of whether the same box can replace Terabox/Google Drive.

---

## 0. Executive Summary

| Question | Answer |
|---|---|
| Can a ~$100 CAD laptop be the server? | **Yes** — because the Roku decodes video itself. The server mostly just copies bytes. |
| How much storage for 4K? | **~20 GB per movie, ~5 GB per episode.** 8 TB ≈ 300 4K movies. |
| Cheapest/fastest/largest storage? | **External USB desktop HDD. Do NOT buy SSD** — it costs 4-6x more and buys nothing. |
| Will the TV connect and play? | **Yes** — official Jellyfin app exists on Roku. Two fixes needed first (see §5). |
| Can it replace Google Drive? | **Partly.** Different software, same box. But a single drive is a *downgrade* in safety. See §6. |

**Total realistic budget: ~$320–400 CAD** for a server holding roughly 300 4K movies.

---

## 1. What We Already Have (verified 2026-07-28)

Discovered by scanning `192.168.2.0/24` from the G14.

| IP | Device | MAC vendor | Notes |
|---|---|---|---|
| `.1` | Bell Home Hub router | Sagemcom | Also runs a Twonky DLNA MediaServer on :9000 |
| `.13` | **Philips 65PUL7973/F6 Roku TV** | Hui Zhou Gaoshengda | Roku OS 15.2.4, 65", "Primary bedroom" |
| `.16` | G14 primary laptop | — | This machine. No ethernet port. |
| `.40` | Apple device | Apple | phone/tablet/Mac |
| `.50` | **PlayStation** | Sony Interactive | secondary client option |
| `.59` | randomized MAC | — | likely a phone |

**This is a good starting position.** The TV is the single most important
component and it's already a capable client.

### Two problems found on the TV

Both from its own `device-info` API (`http://192.168.2.13:8060/query/device-info`):

1. **`network-type: wifi` / `network-name: BELL851 2.4 GHz`**
   The TV is streaming over the **2.4 GHz** band — the slow, congested one shared
   with microwaves, Bluetooth and every neighbour. This is the worst band for video.

2. **`supports-ethernet: true` / `ethernet-mac: c8:7e:a1:ae:c3:82`**
   **The TV has an ethernet port that is not plugged in.** This is a free fix
   and the single highest-value change on this entire page. A cable costs ~$10.

### One thing to confirm manually

`ui-resolution` reports **`1080p`**. The model number (Philips PUL7973 series) is
marketed as a 4K UHD set, and Roku often renders its *menu* at 1080p on 4K panels
while still playing video at 2160p — so this is probably fine. **But confirm it**,
because it changes the storage budget by 4-5x:

> TV → **Settings → System → About** → read the display resolution.

- If **4K (2160p)** → use the numbers in §3 as written.
- If **1080p** → divide all storage numbers by ~4. An 8 TB drive would then hold
  well over 1,000 movies, and this whole project gets much cheaper.

---

## 2. The Core Insight — Direct Play vs Transcode

This is what makes a $100 laptop viable, so it belongs before the shopping list.

**Direct play** — the Roku decodes the video itself. The server does nothing but
read a file off disk and push it over the network. A 4K stream is only ~25 Mbps
(about 3 MB/s). Any laptop from the last 15 years can do that in its sleep.

**Transcode** — the Roku *can't* handle the format, so the server must decode and
re-encode the video in real time. This is genuinely expensive and is where cheap
hardware falls over.

> **The entire strategy is: build a library the Roku can direct-play, and the
> server never works hard.** Hardware spend then goes to storage, not CPU.

### What this specific Roku can and cannot direct-play

| | Direct plays ✅ | Forces a transcode ❌ |
|---|---|---|
| **Video** | H.264, **HEVC/H.265** | **AV1** (too new for this TV), VC-1 |
| **Audio** | AAC, MP3, AC3 / E-AC3 (Dolby Digital / Plus) | **DTS, DTS-HD, TrueHD** |
| **Subtitles** | **SRT** (text) | **PGS / VOBSUB** (image — must be burned in) |
| **Container** | MKV, MP4, TS | — |

**Target format: HEVC video + AC3/E-AC3 or AAC audio + SRT subtitles, in MKV.**
That combination direct-plays and the server idles.

Two gotchas worth memorising, because they cause 90% of real-world stuttering:

- **DTS audio is the #1 Roku transcode trigger.** Roku TVs generally don't license
  DTS. The good news: audio-only transcoding is cheap, so even a weak CPU copes.
- **Image-based subtitles force a *full video* transcode.** PGS subs (the kind on
  Blu-rays) have to be painted into the picture. Prefer external `.srt` files.

---

## 3. Storage Sizing for 4K

### Per-title sizes

| Source type | Bitrate | 2 hr movie | 45 min episode |
|---|---|---|---|
| 4K remux (untouched disc) | 60–100 Mbps | **55–80 GB** | — |
| 4K high-quality x265 | 20–25 Mbps | **20–30 GB** | 7–10 GB |
| 4K web-dl (streaming tier) | ~15 Mbps | **12–18 GB** | 4–6 GB |
| 4K efficient x265 | 8–10 Mbps | **7–10 GB** | 3–4 GB |

> **Planning numbers: ~20 GB per 4K movie, ~5 GB per 4K episode.**

### Library targets

| Library | Space |
|---|---|
| 100 4K movies | 2 TB |
| 250 4K movies | 5 TB |
| 500 4K movies | 10 TB |
| 150 movies + 30 TV seasons | ~3.5 TB |
| 100 movies as full remuxes | ~7 TB |

Add ~20% headroom — never run a media drive past about **85% full**.

**Recommendation: 8 TB.** Roughly 300 good-quality 4K movies. Big enough not to
feel cramped, cheap enough that it isn't a painful mistake.

---

## 4. Hardware Shopping List

### 4a. The server laptop — target ~$100–180 CAD

Because we're aiming for direct play, raw CPU barely matters. Buy on these,
in priority order:

1. **Gigabit ethernet port** — non-negotiable. Business laptops have one; thin
   ultrabooks often don't. (USB 3.0 gigabit adapter ≈ $20 if missing.)
2. **7th-gen Intel (Kaby Lake, 2016) or newer** — this is the insurance policy for
   when you *do* hit a transcode. See table below.
3. **8 GB RAM** (4 GB works, 8 GB is comfortable).
4. **USB 3.0 ports** — for the storage drive. USB 2.0 would still technically work
   but leave no headroom.

**Quick Sync generation — the only CPU spec that matters:**

| Intel gen | Year | 4K HEVC 10-bit? | Verdict |
|---|---|---|---|
| 4th–5th (Haswell/Broadwell) | 2013–14 | No HEVC at all | Direct play only |
| 6th (Skylake) | 2015 | 8-bit only | Marginal — most 4K is 10-bit HDR |
| **7th (Kaby Lake)** | **2016** | **Decode + encode** | **The sweet spot** |
| 8th–10th | 2017–19 | Same, more cores | Better |
| 11th+ (Tiger Lake) | 2020 | Adds AV1 decode | Nice, not needed |

**Models to search for:** ThinkPad T470 / T480, Dell Latitude 7480 / 5480,
HP EliteBook 840 G3 / G4. Ex-corporate units, built to last, easy to open.
Chips: `i5-7200U`, `i3-7100U`, `i5-8250U`, `i5-8265U`.

**Avoid:** old AMD laptops (weak video engines pre-Vega).

**Honest note:** at *exactly* $100 CAD you'll mostly find 4th–6th gen. Stretching
to **$150–180** reaches 7th/8th gen and is worth the extra ~$60.

**Where:** Kijiji, Facebook Marketplace, local ex-corporate refurbishers.
Check for a swollen battery on any used unit — if it's puffy, remove it.

### 4b. Storage — the "cheapest / fastest / largest" answer

> **Do not buy an SSD. "Fastest" is a trap here.**
>
> One 4K stream needs ~3 MB/s. A lazy 5400 RPM hard drive sustains 150+ MB/s —
> fifty times more than needed, enough to feed a dozen simultaneous 4K streams.
> SSDs cost **4-6x per TB** and deliver zero benefit for this workload.
> Put every one of those dollars into capacity instead.

**Cheapest $/TB: external USB desktop drives.** WD Elements, WD My Book, Seagate
Expansion. These are consistently *cheaper per terabyte than the same bare drive
sold internally*, because manufacturers subsidise them.

Keep it **external over USB 3.0** — don't cram drives into a laptop bay. The 8 TB+
models ship with their own power brick, which is better anyway since laptop USB
ports struggle to spin up large drives.

**Ballpark CAD street prices — APPROXIMATE, verify before buying:**

| Capacity | Rough CAD | ~4K movies |
|---|---|---|
| 8 TB | $180–230 | ~340 |
| 12 TB | $250–300 | ~510 |
| 14 TB | $280–340 | ~600 |
| 16 TB | $330–400 | ~680 |
| 20 TB | $420–500 | ~850 |

**Verify at:** Canada Computers, Memory Express, Amazon.ca, Best Buy, Newegg.ca.
External HDD pricing swings hard on sales — Black Friday / Prime Day routinely
knock 30% off. If not in a rush, wait for one.

Recertified enterprise drives (ServerPartDeals, GoHardDrive) are cheaper per TB
again, but ship from the US — factor duty and a shorter warranty.

### 4c. Total

| Item | CAD |
|---|---|
| Used laptop, 7th/8th gen Intel, 8 GB, gigabit port | $100–180 |
| 8 TB external USB 3.0 HDD | ~$200 |
| Ethernet cable for the TV | ~$10 |
| USB gigabit adapter (only if laptop lacks a port) | ~$20 |
| **TOTAL** | **~$320–400** |

Running cost: roughly **15–25 W**, or about **$20–30/year** in electricity.

---

## 5. Will the TV Actually Work?

**Yes.** There is an **official Jellyfin channel in the Roku Channel Store**.
Install it on the TV, point it at the server's IP, done.

But do these two things first or 4K will stutter regardless of what you buy:

1. **Run an ethernet cable to the TV.** It has a port (`supports-ethernet: true`)
   sitting unused. The TV is currently on 2.4 GHz Wi-Fi, which is the worst
   possible link for 4K video. ~$10 fix, biggest single improvement available.
2. **Wire the server to the router too.** Both endpoints on cable = the whole path
   is gigabit and nothing else on the network can interfere.

If cabling the TV is impossible (it's in the primary bedroom — cable run may not be
practical), the fallback is to at least move it to the router's **5 GHz** SSID.
That's still far better than 2.4 GHz. Powerline or MoCA adapters are a middle option.

### Client options ranked

| Client | Verdict |
|---|---|
| **Roku TV (have it)** | Official Jellyfin app. Good. Free. Start here. |
| **PlayStation at `.50`** | Has a DLNA media player; Plex app exists. Workable backup. |
| Fire TV Stick 4K (~$70) | Only if the Roku app disappoints — better app, adds AV1. |
| Nvidia Shield (~$200) | Overkill unless you go heavy on remuxes and DTS audio. |

**Do not buy any of these yet.** The Roku is already a capable client. Spend
nothing here until it's proven inadequate.

---

## 6. Can It Replace Terabox / Google Drive?

**Same box, yes. Same software, no.** Jellyfin is a media catalogue — it is not
file sync. You'd add a second service alongside it. They coexist fine on one
machine, on the same drive, in different folders.

| Software | What it gives you | Fit for a $100 laptop |
|---|---|---|
| **Syncthing** | Peer-to-peer folder sync between your devices. No cloud, no account. | **Best fit** — tiny footprint |
| **Samba (SMB)** | A network drive that appears in your file manager. LAN only. | Trivial, near-zero overhead |
| **Nextcloud** | The real Google Drive clone — web UI, mobile apps, sharing links, calendar/contacts | Works, but heavy (PHP + database); will feel sluggish |

Practical answer: **Samba for LAN access + Syncthing for phone/laptop sync** covers
most of what people actually use Google Drive for, at a fraction of the resource
cost. Add Nextcloud only if you specifically need share-links and a web UI.

### The warning that matters most

> **A single-drive server is NOT a backup. Replacing Google Drive with one hard
> drive in your bedroom is a DOWNGRADE in data safety, not an upgrade.**

Google keeps your files in multiple datacentres with redundancy. One drive on a
laptop is one drive. Hard drives fail — not *if*, *when* — and when it goes, it
takes everything with it at once. A fire, theft, or flood takes it too.

The standard rule is **3-2-1**: 3 copies, on 2 different types of media, 1 offsite.

**So split the data by whether you can replace it:**

| Data | Where it belongs |
|---|---|
| Movies, TV — re-acquirable | Server, single drive, accept the risk |
| Photos, documents, personal files — **irreplaceable** | Server **+ a real offsite copy** |

Personal files are usually under 100 GB and often fit a free cloud tier. **Keep
using cloud for those.** Use the server for the bulk, re-acquirable stuff. That
split is what actually makes sense — not an all-or-nothing migration.

If you want the server to hold irreplaceable data, budget for a **second drive**
for backup. That roughly doubles the storage line item.

### Remote access

Google Drive works from anywhere; a LAN server doesn't. The safe fix is
**Tailscale** — free, encrypted (WireGuard), no port forwarding, no firewall holes.
Installs on the server and on your phone/laptop; everything then behaves as if
it's on the same LAN.

> **Do not port-forward Jellyfin or Nextcloud straight to the internet.** That is
> how home servers get compromised.

---

## 7. Build Order

Nothing here is committed. Rough sequence when the hardware arrives:

1. **Verify the TV is actually 4K** (§1) — free, and it may quarter the storage budget.
2. Run ethernet to the TV; confirm `network-type` flips from `wifi` to `ethernet`.
3. Buy the laptop. Confirm gigabit port + Intel generation *before* paying.
4. Buy the 8 TB external drive (wait for a sale if possible).
5. Install a minimal Linux + `jellyfin-server`. Set `HandleLidSwitch=ignore` in
   `/etc/systemd/logind.conf` or it sleeps the moment the lid shuts.
6. Install the Jellyfin channel on the Roku; **verify a real direct play** —
   Jellyfin's dashboard shows "Direct Play" vs "Transcode" per stream.
   Don't assume it; watch the dashboard.
7. Only then consider Samba / Syncthing (§6).

### Notes for whoever builds this

- The laptop **battery is a free UPS** — a genuine advantage over a desktop server.
  Power blips won't corrupt the library.
- The Bell router already runs a Twonky DLNA server on `:9000`. Ignore it; it's
  far worse than Jellyfin. Don't let it confuse discovery on the TV.
- **Verify hardware transcoding actually engages** rather than trusting the config
  screen. Jellyfin will silently fall back to software and just be slow.

---

## 9. Prototype As Built (on the G14, 2026-07-28)

Running now, so §1-3 of the reference guide can be evaluated before spending money.

| Piece | State |
|---|---|
| `jellyfin-server` 10.11.11 + `jellyfin-web` | installed from `extra`, `active` + `enabled` |
| Listening | `0.0.0.0:8096`, reachable at `http://192.168.2.16:8096` (HTTP 200) |
| Hardware transcode | **verified** — 4K HEVC encode at 4.75-5.87x realtime on `renderD129` |
| dGPU | deliberately excluded — `jellyfin` is in `render`,`video` but **not** `dgpu` |
| Library root | `/srv/media/{movies,tv}`, owned `jellyfin:jellyfin`, mode `2775` |
| Importer | `scripts/luminos-media-import` |
| **Setup wizard** | **NOT RUN** — needs a human to pick a password at `http://localhost:8096` |

**Transcode verification was negative-tested**: the same ffmpeg command against
`renderD128` (the NVIDIA node) fails with `Device creation failed: -5`, while
`renderD129` (AMD 780M) produces real 3840x2160 HEVC. The check can fail, so a
pass means something.

### The `/srv/media` design — this is what makes §4 cheap

Everything points at **one path**: `/srv/media`. It is currently a plain
directory on `/` (207 GB free) but is intended as a **mount point**.

Migration to a real drive or NAS is then:

```bash
# 1. attach + format the new drive (NTFS if it must also plug into the TV;
#    ext4 if it will only ever be served over the network — ext4 is faster
#    and handles permissions properly)
# 2. copy the library across, preserving ownership
sudo rsync -aHAX --info=progress2 /srv/media/ /mnt/newdrive/
# 3. mount it in place, by UUID so it survives replug
sudo blkid /dev/sdX1                       # get the UUID
echo 'UUID=<uuid>  /srv/media  ext4  defaults,nofail,x-systemd.device-timeout=10  0 2' \
  | sudo tee -a /etc/fstab
sudo systemctl daemon-reload && sudo mount -a
# 4. nothing else changes. Jellyfin's library paths are still /srv/media/*.
```

`nofail` matters: without it, an unplugged USB drive blocks boot.

**Jellyfin's own state is separate and small** — `/var/lib/jellyfin` (2.7 MB,
database + metadata) and `/etc/jellyfin` (32 KB, config). To move the whole
server to the new box, stop Jellyfin, copy those two directories, copy the
media, done. No reconfiguration, no re-scraping.

### Codec profile discovered for this TV

Encoded into `scripts/luminos-media-import` so it's enforced, not remembered:

| Stream | Direct plays | Forces transcode |
|---|---|---|
| Video | HEVC, VP9, **H.264 only up to 1080p** | AV1, VC-1, **H.264 above 1080p** |
| Audio | AAC, MP3, AC3, E-AC3, FLAC, Opus | DTS, DTS-HD, TrueHD |
| Subtitles | SRT, ASS (text) | PGS, VOBSUB (image → **full video** transcode) |

The H.264 ceiling is the one that bites: a 4K H.264 file looks fine on paper and
will not direct-play. **4K must be HEVC.**

### What is deliberately NOT built

The `*Arr` stack (Radarr / Sonarr / **Prowlarr**) wired to torrent or Usenet
indexers for automated acquisition of copyrighted films and TV. Not installed,
not configured, not planned.

The *organisational* value of that stack — consistent naming, correct folder
layout, metadata scraping — is covered by `luminos-media-import` plus Jellyfin's
built-in TMDb/OMDb scrapers, for content you supply yourself.

### `scripts/luminos-media-import`

Stdlib-only Python. Takes a file you already have, probes it, refuses it if it
won't direct-play on the Roku, and files it under Jellyfin's naming convention.

```bash
# movie
scripts/luminos-media-import /path/to/file.mkv \
    --mode movie --title "Movie Name" --year 2008 [--copy] [--dry-run]

# episode
scripts/luminos-media-import /path/to/file.mkv \
    --mode tv --title "Show Name" --year 2013 \
    --season 1 --episode 4 --episode-title "Chapter 4"
```

Exit codes: `0` ok · `2` compatibility FAIL (override with `--force`) ·
`3` destination exists.

Tested 2026-07-28 — all six cases behave, including the failures:
4K H.264 refused · 4K HEVC accepted · 1080p H.264 accepted · TV naming correct ·
real write succeeds · duplicate refused.

> **Group-membership gotcha:** `shawn` was added to the `jellyfin` group, but
> existing login sessions don't pick that up — writes fail with `EACCES` until
> you log out and back in. Workaround in the meantime: `sg jellyfin -c '<cmd>'`.

---

## 10. Content — the legitimate routes

Reference guide §2 lists three sources. Only one of them is being supported here.

- **Ripping discs you own** — MakeMKV (`makemkv` in the AUR) pulls a lossless
  copy off a Blu-ray or DVD. Output is huge (20-40 GB) and H.264/VC-1/HEVC
  depending on the disc, so a 4K rip generally needs re-encoding to HEVC before
  the Roku will direct-play it. The G14 has **no optical drive** — an external
  USB Blu-ray reader is ~$100-150 CAD, and UHD (4K) discs additionally need a
  specific drive with downgraded firmware. Worth knowing before assuming this
  route is cheap.
- **Your own recordings, home video, freely-licensed works.** The current test
  library is Blender's *Big Buck Bunny* (CC-BY).
- **Torrents / Usenet for copyrighted material** — out of scope, see §9.

---

## 11. Open Questions

- [ ] **Is the Philips 65PUL7973/F6 panel 4K or 1080p?** Blocks the storage decision.
      Test kit built at `~/roku-test-kit/` — copy to NTFS USB, view `01_PANEL_TEST_4K.png`.
- [ ] **Run the Jellyfin setup wizard** at `http://localhost:8096` (needs a human password).
- [ ] Can ethernet physically reach the TV in the primary bedroom?
- [ ] Will the server live near the router (wired) or elsewhere?
- [ ] Does any irreplaceable data need to live on this box? (changes §6 and the budget)
