# Luminos Media Server

Everything about the media server lives in this directory. It is a **different physical
machine** from the G14 that the rest of this repo describes — nothing here runs on the laptop.

```
server/
├── README.md      you are here — the map
├── STATUS.md      what is built, what works, what is pending
├── DECISIONS.md   why it is built this way (decisions 35, 36, 36a, 37)
├── docs/
│   ├── SERVER_INSTALL_RUNBOOK.md   step-by-step build, as actually executed
│   ├── MEDIA_SERVER_PLAN.md        the design, codec rules, hardware notes
│   └── MEDIA_SERVER_SECURITY.md    what is exposed, why, and how to close it
└── scripts/
    ├── luminos-server-install      stage 1 — partition + install Arch
    ├── luminos-server-services     stage 2 — Jellyfin, qBittorrent, Sonarr, Prowlarr
    └── luminos-media-import        media importer, enforces the Roku codec rules
```

## The machine

| | |
|---|---|
| Hardware | Dell Inspiron 3590 — i5-10210U (Comet Lake-U, 4c/8t), 16 GB RAM |
| Storage | 1 TB 2.5" HDD (`WDC WD10SPZX`) at `/srv/media` — the only usable bay |
| Graphics | Intel UHD (`renderD128`, the transcoding GPU) + AMD Radeon 520 (`renderD129`, unused) |
| Power | **battery removed — mains only.** A power cut is a hard stop |
| OS | Arch, headless, on the HDD. Windows lives on an NVMe the installer never touches |

## Reaching it

```bash
ssh -i ~/.ssh/luminos-server shawn@192.168.2.61
```

Dual-homed, both NICs on the same subnet, deliberately:

| interface | address | carries |
|---|---|---|
| `wlan0` | 192.168.2.61 | admin, and Jellyfin streaming to the TV |
| `enp2s0` | 192.168.2.62 | torrents only — see DECISION 36 |

The TV is a Philips 65PUL7973 (Roku) at 192.168.2.13. Public IP 76.64.36.43.

## Services

| service | port | exposure |
|---|---|---|
| Jellyfin | 8096 | LAN only |
| qBittorrent WebUI | 8080 | **stopped** — see the halt below |
| Sonarr | 8989 | LAN only |
| Radarr | 7878 | LAN only |
| Prowlarr | 9696 | LAN only |
| BitTorrent peer port | 25989 | **stopped** — rule still in nftables, nothing listening |

## ⛔ Torrenting is halted until a VPN is installed

<!-- [CHANGE: claude-code | 2026-08-04] -->

**Nothing downloads and nothing uploads right now, on purpose.** Halted 2026-08-04 —
DECISION 42 has the full reasoning, the proof, and the restore commands.

The short version: BitTorrent traffic is unencrypted and easy to identify by protocol
signature, so the port number hides nothing. With an inbound port open this box was an
*advertised* peer — listed in trackers and DHT against the public IP 76.64.36.43, where
anyone can enumerate it. It had uploaded **228.9 GB**, and the uploading half is the
loud half. A VPN goes in front of all of it before any of this restarts.

Enforced in four places so undoing one does not restart traffic:

| layer | state |
|---|---|
| all 22 torrents | `stopped` |
| `qbittorrent-nox@shawn.service` | stopped **and disabled** — survives reboot |
| `qbt-portmap.timer` | stopped **and disabled** — it was still re-punching the router forward hourly |
| Sonarr + Radarr `rssSyncInterval` | `0`, so no grab backlog builds up behind the halt |

Jellyfin is untouched and still streams — that traffic never leaves the house.

**Do not just restart qBittorrent when the VPN is installed.** The VPN has to be pinned
so the tunnel exits via `enp2s0` and qBittorrent binds to the tunnel, or torrents end up
back on the wifi radio and the TV stutters (DECISION 36). Kill-switch must be tested by
downing the interface mid-transfer, not assumed.

API keys are deliberately **not** stored in this repo. Read them off the box:

```bash
sudo grep -oP '(?<=<ApiKey>)[^<]+' /var/lib/sonarr/config.xml     # and radarr, prowlarr
sudo grep -oP '(?<=<ApiKey>)[^<]+' /etc/jellyfin/... 2>/dev/null  # or Jellyfin dashboard
```

## Things that will bite you

These are all learned the hard way — the reasoning is in `DECISIONS.md`.

- **Never flip `SATA Operation` from `RAID On` to `AHCI` in the BIOS.** It stops the owner's
  Windows booting. It is also why Linux cannot see the NVMe at all — Intel RST hides it.
- **Never clear qBittorrent's `current_network_interface`.** That single setting is what keeps
  torrents on the cable and off the wifi radio. The routing rules are backup, not the mechanism.
- **A stopped torrent is not a stopped service.** An app-level pause is one settings write from
  being undone. When the requirement is "no traffic", stop and *disable* the unit — DECISION 42.
- **Jellyfin's `SubtitleMode: Default` means "only tracks the file flags as default".** Most web
  releases flag none, so subtitles silently never appear even though they are right there in the
  file. `Always` + a language preference is what actually turns them on.
- **A quality profile that matches nothing fails silently and forever.** Sonarr will sit on an
  empty season indefinitely rather than tell you. Search before assuming the chain is broken.
- **Public indexer seeder counts are fiction.** Check `GET /api/v2/torrents/trackers` after adding.
- **Sonarr does not search when you change a profile.** Only on RSS (new uploads) or an explicit
  search. An old show will never self-trigger.
- **qBittorrent preallocates**, so a 1% torrent already occupies its full size on disk.
- **Render node numbers are machine-specific.** `renderD128` is Intel here and NVIDIA on the G14.
  Resolve with `ls -l /sys/class/drm/renderD12*/device/driver`, never carry the number over.
- `bc` is not installed. Use python for arithmetic in scripts.

## Owner-only tasks

Things that need physical access or the router admin page:

- Two Cat 6 cables: router→server (the current one downshifts to 100 Mb/s) and router→TV.
- A DHCP reservation for 192.168.2.62.
- The BIOS boot order must keep the HDD first, or a power blip boots Windows and SSH is gone.
