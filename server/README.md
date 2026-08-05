# Luminos Media Server

Everything about the media server lives in this directory. It is a **different physical
machine** from the G14 that the rest of this repo describes — nothing here runs on the laptop.

```
server/
├── README.md      you are here — the map
├── STATUS.md      what is built, what works, what is pending
├── DECISIONS.md   why it is built this way (decisions 35-52)
├── docs/
│   ├── SERVER_INSTALL_RUNBOOK.md   step-by-step build, as actually executed
│   ├── MEDIA_SERVER_PLAN.md        the design, codec rules, hardware notes
│   └── MEDIA_SERVER_SECURITY.md    what is exposed, why, and how to close it
├── packaging/
│   └── jellyseerr/PKGBUILD         builds 3.4.1 from source — the AUR one is a year stale
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

Away from the house, it is also on a Tailscale tailnet as **100.82.125.26**
(`luminos-server.tail1fd435.ts.net`). No router port is open for this — DECISION 51.

## Services

| service | port | exposure |
|---|---|---|
| Jellyfin | 8096 | LAN only |
| qBittorrent WebUI | 8080 | **stopped** — see the halt below |
| Sonarr | 8989 | LAN only |
| Radarr | 7878 | LAN only |
| Prowlarr | 9696 | LAN only |
| Jellyseerr | 5055 | LAN + Tailscale — request films/shows, DECISION 52 |
| Tailscale | — | outbound only — remote access to Jellyfin, opens nothing |
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

- **Any new service on this box is LAN- and tailnet-exposed the moment it listens.** The
  nftables rules accept `ip saddr 192.168.2.0/24` and `iifname "tailscale0"` *wholesale*, not
  per-port. Convenient — Jellyseerr on 5055 needed no firewall work at all — and a mistake
  waiting to happen for anything unauthenticated. Nothing is open to the internet either way.
- **`engine-strict=true` in an `.npmrc` makes pnpm refuse, not warn.** A Node version mismatch
  stops the build dead. Hit building Jellyseerr 3.4.1 against the box's Node 26. DECISION 52.
- **pnpm 11 no longer reads the `pnpm` field in `package.json`.** `onlyBuiltDependencies` and
  `overrides` are ignored and it only prints a notice. If a rebuilt Node package installs fine
  and then dies on a native module, look here first.
- **NZBGet's `pausedownload` does nothing over `GET`.** It returns an empty body and keeps
  downloading; it needs POST. And one status sample cannot tell a pause from a stalled
  article — take several, spaced out, and watch the byte counter.
- **There are no download size caps.** Every quality definition is `maxSize: None`, so
  "Max Bitrate" can and does pull 100 GB+ remuxes. That is on purpose, but know it before
  requesting a whole season pack. DECISION 52.
- **Jellyseerr's "4K" request toggle is the profile-5 trap in a new costume.** Leave
  `is4k`/`movie4kEnabled`/`series4kEnabled` off — a strict 2160p profile rejects everything
  with no 4K release, silently and forever, which is what happened to True Detective.
- **Never flip `SATA Operation` from `RAID On` to `AHCI` in the BIOS.** It stops the owner's
  Windows booting. It is also why Linux cannot see the NVMe at all — Intel RST hides it.
- **Never clear qBittorrent's `current_network_interface`.** That single setting is what keeps
  torrents on the cable and off the wifi radio. The routing rules are backup, not the mechanism.
- **A stopped torrent is not a stopped service.** An app-level pause is one settings write from
  being undone. When the requirement is "no traffic", stop and *disable* the unit — DECISION 42.
- **Jellyfin's `SubtitleMode: Default` means "only tracks the file flags as default".** Most web
  releases flag none, so subtitles silently never appear even though they are right there in the
  file. `Always` + a language preference is what actually turns them on.
- **Sonarr has no maximum-seasons setting** — there is nothing between "First Season" and "All".
  `luminos-season-limit.timer` supplies one, capping every series at 2 monitored seasons. It
  leaves anything already within the limit completely alone, so a hand-picked pair like True
  Detective S01+S04 survives it. DECISION 44.
- **Sonarr sometimes copies on import instead of hardlinking**, so `nlink == 1` in `downloads`
  does *not* by itself mean "not in the library". Compare inodes before deleting anything.
- **A quality profile that matches nothing fails silently and forever.** Sonarr will sit on an
  empty season indefinitely rather than tell you. Search before assuming the chain is broken.
- **Public indexer seeder counts are fiction.** Check `GET /api/v2/torrents/trackers` after adding.
- **Sonarr does not search when you change a profile.** Only on RSS (new uploads) or an explicit
  search. An old show will never self-trigger.
- **qBittorrent preallocates**, so a 1% torrent already occupies its full size on disk.
- **Render node numbers are machine-specific.** `renderD128` is Intel here and NVIDIA on the G14.
  Resolve with `ls -l /sys/class/drm/renderD12*/device/driver`, never carry the number over.
- **In `systemd-resolved`, DNS set on a *link* beats DNS set globally.** Configuring
  DNS-over-TLS in `resolved.conf.d/` and stopping there leaves DHCP handing the ISP's
  resolver to each interface, and every lookup keeps leaving in cleartext while the global
  config sits there looking correct. `UseDNS=false` on the `.network` files is the other
  half. And use `DNSOverTLS=yes`, never `opportunistic` — opportunistic falls back to
  plaintext silently. DECISION 48.
- **`os.makedirs()` creates missing *parent* directories with the process umask**, not the
  mode you `chmod` onto the leaves. Under `sudo` that umask is `0077`, so a perfect `2775`
  leaf can sit under a `drwx--S---` parent that nobody can traverse. List every directory
  in the chain explicitly. It cost an afternoon on `/srv/media/usenet`.
- **`tcpdump` lies about quiet networks unless you make it flush.** Without `-U` it buffers;
  under `timeout` a `-w` capture loses the whole pcap because SIGTERM does not flush it; and
  backgrounding it over SSH holds the channel open and **kills the session** (exit 255). All
  three present as "0 packets captured", which reads exactly like "no traffic found". A
  capture that catches nothing has proven nothing.
- **In Python, `\s` matches newlines.** A config verifier using `\s*` after `=` will swallow
  the line break on any key with an empty value and compare against the *next* line, failing
  keys that were written perfectly. Use `[ \t]*`.
- **`systemctl is-active` returning `active` is not proof the service works.** NZBGet came
  up `active` with a permissions error and a `CertStore` error both live in the journal.
  Read the journal, then exercise the thing.
- **A news server is not an indexer.** UsenetServer stores the articles; Sonarr needs a
  *Newznab* search API to know which articles hold which episode. The bundled "Global
  Search" is a website with no API. That is a second, separate subscription — **NZBGeek**,
  bought 2026-08-05. DrunkenSlug was not a choice: its registration is closed to all but
  invites. **One indexer serves both Sonarr and Radarr** via Prowlarr's `fullSync`.
- **Retention belongs to the news server, not the indexer.** If an old release turns up
  "not found", that is UsenetServer's article retention. Swapping indexers will not fix it,
  and it is an easy thing to misdiagnose as a broken search chain.
- **Prowlarr's "Test Successful" only proves the API key was accepted.** It does not prove a
  search returns anything usable. Run a real `/api/v3/release?seriesId=` query and count the
  results per indexer.
- **A LAN `ip saddr` firewall rule does not cover a VPN tunnel.** Tailscale peers arrive on
  `tailscale0` carrying `100.64.0.0/10` (CGNAT) addresses, which `ip saddr 192.168.2.0/24`
  never matches. Under `policy drop` the tunnel comes up, `tailscale status` looks perfect,
  and every service is unreachable through it. Needs `iifname "tailscale0" accept`.
  Tailscale's own accept rules sit in the `iptables-nft` filter table and do **not** override
  a drop policy in another table. DECISION 51.
- **`tailscale up` hijacks DNS unless you pass `--accept-dns=false`.** On this box that would
  have silently undone the DNS-over-TLS to Quad9. Record `resolvectl status` before, compare
  after — the failure mode is invisible.
- **A local `curl` to your own tailnet IP does not test the firewall.** Loopback traffic never
  crosses `iifname tailscale0`, so the rule's counter stays 0. It proves the listener, nothing
  more. Only a real peer proves the rule.
- **Jellyfin's "Forgot Password" cannot recover an admin account.** It fails twice over:
  it refuses any request not from the LAN (a Tailscale `100.x` peer logs *"Password reset
  process initiated from outside the local network"* and gets nothing), and even from the
  LAN it resets the password to **empty**, which `UserManager.ChangePassword` then rejects
  with `ArgumentException: Admin user passwords must not be empty`. Recover via the API key
  in the `ApiKeys` table of `/var/lib/jellyfin/data/jellyfin.db`:
  `POST /Users/{id}/Password` with `{"CurrentPw":"","NewPw":"<new>","ResetPassword":false}`.
- **Changing a Jellyfin password revokes every logged-in device.** The `Devices` table went
  from 4 rows to 0 — Roku, phone and browser all have to sign in again. Warn before doing it.
- `bc` is not installed. Use python for arithmetic in scripts.

## Owner-only tasks

Things that need physical access or the router admin page:

- Two Cat 6 cables: router→server (the current one downshifts to 100 Mb/s) and router→TV.
  **Now measured, not theoretical:** Usenet does 11.45 MB/s and is sitting exactly on the
  wifi ceiling, while the router reports a ~1 Gbps line. The cable is worth about 10x.
- A DHCP reservation for 192.168.2.62.
- The BIOS boot order must keep the HDD first, or a power blip boots Windows and SSH is gone.
- **Disable Tailscale key expiry for `luminos-server`** in the admin console. The machine key
  expires **2027-02-01**, and when it does the server drops off the tailnet silently — remote
  access just stops, months from now, with nothing logged on the box. There is no CLI for it.
