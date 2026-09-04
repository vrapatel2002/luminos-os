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
| Storage (2) | 500 GB USB HDD (`ST500LM030`) at `/srv/external` — second root folder, **not** pooled, DECISION 91 |
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

<!-- [CHANGE: claude-code | 2026-09-02] Exposure column rewritten for DECISION 90. -->

| service | port | exposure |
|---|---|---|
| Caddy landing page | 443 | LAN + Tailscale — TLS front door |
| Jellyfin | 8096 | **LAN in the clear, deliberately** — the Roku can't do TLS here |
| Jellyfin (via Caddy) | 8443 | LAN + Tailscale, TLS |
| Jellyseerr | 8444 → 5055 | LAN + Tailscale, TLS — request films/shows, DECISION 54 |
| NZBGet | 8445 → 6789 | LAN + Tailscale, TLS |
| luminos-space | 8446 → 8099 | LAN + Tailscale, TLS — disk browser, DECISION 62 |
| Radarr | 8447 → 7878 | LAN + Tailscale, TLS |
| Sonarr | 8448 → 8989 | LAN + Tailscale, TLS |
| Prowlarr | 8449 → 9696 | LAN + Tailscale, TLS |
| byparr | 8191 | **loopback only** — no auth of any kind, DECISION 90 |
| SSH | 22 | LAN + Tailscale, key-only |
| Tailscale | — | outbound only — remote access to Jellyfin, opens nothing |
| qBittorrent | — | **uninstalled**, DECISION 84 |

**The bare app ports (`8989`, `7878`, `9696`, `6789`, `5055`, `8099`, `8191`) are no
longer reachable from the LAN** — DECISION 90. They still listen on loopback, and Caddy
is the way in. If a phone app stops connecting, that is why: point it at the `844x` port
or at the tailnet address.

## ⛔ Torrenting is over — Usenet replaced it

<!-- [CHANGE: claude-code | 2026-08-04] -->
<!-- [CHANGE: claude-code | 2026-09-02] -->

> **Superseded.** The halt below was "until a VPN is installed". **DECISION 48 chose Usenet
> instead, so the VPN is not coming and this is permanent.** `qbittorrent-nox` was
> uninstalled in the DECISION 84 pass and the peer-port firewall rule removed. The section
> is kept because it explains *why*, and because the four enforcement layers are still the
> reason nothing restarts by accident.

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

- **Any new service on this box is tailnet-exposed the moment it listens, but no longer
  LAN-exposed.** <!-- [CHANGE: claude-code | 2026-09-02] --> This used to be true of the LAN
  too, and it bit: **byparr sat on `:8191` answering HTTP 200 with no authentication at all**
  to every device on the wifi. DECISION 90 narrowed the LAN rule to named ports.
  `iifname "tailscale0" accept` is still wholesale, and that is now deliberate — the tailnet
  is the trusted path, the home wifi is not. Nothing is open to the internet either way.
- **Jellyfin skips an *empty* library folder, and doesn't watch it either.**
  <!-- [CHANGE: claude-code | 2026-09-04] --> The log says
  `Library folder "…" is inaccessible or empty, skipping`. Harmless when it's true, except
  that no inotify watcher gets attached — so the **first** import into a newly added folder
  is invisible, long after the folder stopped being empty. Cost six episodes on
  `/srv/external/tv`. **Sonarr's `MediaBrowser` connection does not save you here**: it fires,
  reports success and tests green, but refreshing a path under a skipped folder is a no-op.
  One full `POST /Library/Refresh` fixes it permanently for that path. `/srv/external/movies`
  is still empty, so the first film there will do it again. DECISION 94.
- **When something is on disk but not in the Jellyfin UI, open
  `/var/log/jellyfin/jellyfin<YYYYMMDD>.log` before theorising.** <!-- [CHANGE: claude-code |
  2026-09-04] --> The answer was one `[WRN]` line. A whole plausible wrong diagnosis
  (`refreshLibrary=false`) got built instead, and two full scans had already disproven it.
  Note the glob needs `sudo` on the *whole* command — `sudo grep /var/log/jellyfin/*.log`
  expands the glob as your unprivileged shell and fails with "No such file".
- **`flush ruleset` in `/etc/nftables.conf` deletes Tailscale's tables too.** It removes
  *every* table, including the four `ip`/`ip6` `filter`/`nat`/`mangle` tables tailscaled owns
  and marks "do not touch". Reloading the firewall silently broke the tunnel's rules, and it
  only showed up later as odd behaviour. Use `table inet filter` / `delete table inet filter`
  / `table inet filter { … }` instead — naming it first means the delete can't fail on a cold
  boot. The same applies to the rollback recipe in the security brief.
- **`ct state established,related accept` means your SSH session survives any firewall
  change.** Testing in the session you're already in proves nothing. Open a new one — and arm
  `systemd-run --on-active=300` first.
- **`pacman -Qu` lies when the sync DB is stale.** It said **1** package; the real number was
  **145**, including a kernel jump. It compares against the sync database, not the mirrors.
  `pacman -Sy` first. `informant` will also abort the upgrade until Arch news is read.
- **`PRAGMA integrity_check` returns `ok` on a zero-byte file.** It is not proof a backup has
  content. Query a real row count.
- **A host missing from every Caddy site block fails the TLS handshake, it doesn't 404.**
  curl exits 35 and it reads as "the server is down". Every block listed `.61` but not `.62`,
  so the whole web front door hung off the *wifi* address while the *wire* is the default
  route.
- **`engine-strict=true` in an `.npmrc` makes pnpm refuse, not warn.** A Node version mismatch
  stops the build dead. Hit building Jellyseerr 3.4.1 against the box's Node 26. DECISION 54.
- **pnpm 11 no longer reads the `pnpm` field in `package.json`.** `onlyBuiltDependencies` and
  `overrides` are ignored and it only prints a notice. If a rebuilt Node package installs fine
  and then dies on a native module, look here first.
- **NZBGet's `pausedownload` does nothing over `GET`.** It returns an empty body and keeps
  downloading; it needs POST. And one status sample cannot tell a pause from a stalled
  article — take several, spaced out, and watch the byte counter.
- **NZBGet ignores a config line written `Name = value` with spaces.** It falls back to the
  built-in default and says nothing — no warning, no log line. `DiskSpace = 25000` sat in the
  file for days while the live value stayed at the default **250 MB**, i.e. the disk-full guard
  was effectively off. Every other line in `nzbget.conf` is `Name=value`; match that. **Verify
  settings by reading them back out of the running process** (`{"method":"config"}` over
  JSON-RPC), never by grepping the file.
- **Deleting a library file can free zero bytes.** Sonarr and Radarr import by **hardlink**, so
  the library file and its twin under `/srv/media/downloads` are the same inode — measured
  `links=1: 0.0 GB` against `links>1: 369.9 GB`. Match twins by `(st_dev, st_ino)`, never by
  filename. The flip side: `links=1` in the downloads tree means Sonarr *copied*, and those are
  real orphans worth reclaiming (MobLand had 49.94 GB of them). DECISION 62.
- **NZBGet's `PausedSizeMB` is not a pause flag, and `Status` lags.** `PausedSizeMB` is the par2
  repair set that every healthy group holds back (1.6 of 21.9 GB while downloading), so the real
  test is `PausedSizeMB >= RemainingSizeMB`. And pausing the *active* item leaves
  `Status = DOWNLOADING` for up to **16 s** while its connections drain — its bytes stop long
  before its status admits it. DECISION 62.
- **`editqueue` reports success for a command that matched no group.** So does a delete against a
  nonexistent id, which then looks exactly like a completed delete. Check the queue *before* as
  well as after, and poll across the drain window — a single eager read reports a working pause
  as a failure. DECISION 62.
- **Descriptive-audio releases do not set the flags that would identify them.** The real offender
  had `visual_impaired=0` and `comment=0`; only `tags.title` said "British (Descriptive)". Key
  detection on the **track title**. And keep the pattern narrow — `\bAD\b` would reject
  *Ad Astra*. DECISION 61.
- **Sonarr applies `addOptions.monitor` asynchronously, after the add.** It overwrites monitored
  flags set in the same POST body, so a series can silently unmonitor itself moments after you
  added it. Set monitoring as a separate `PUT` afterwards, then re-read to confirm it settled.
- **Radarr and Sonarr delete files asynchronously.** Checking that the directory is gone straight
  after the API call is a false positive — it will still be there, and then it won't be.
- **Backgrounding a long command over SSH returns exit 255 and kills the session.** Use
  `systemd-run --unit=NAME --collect` on the server instead of `&` or `nohup`.
- **There are no download size caps.** Every quality definition is `maxSize: None`, so
  "Max Bitrate" can and does pull 100 GB+ remuxes. That is on purpose, but know it before
  requesting a whole season pack. DECISION 54.
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
- **A Jellyfin plugin cannot draw a Skip button.** Since 10.10, Intro Skipper is a *Media
  Segment Provider* — it only writes timestamps, and the button is rendered by the **client**.
  Ask-to-skip vs auto-skip is a per-device setting on the Roku/phone, not something settable
  from the server. DECISION 64.
- **Two ffmpegs are not always faster than one on this box.** The library is on a spinning
  HDD; Intro Skipper's workers sat at 15% and 8% CPU, so a full-library scan is bound by disk
  seeks, not cores. Raising `MaxParallelism` buys nothing and fights playback.
- **`ffmpeg` on `$PATH` is not the ffmpeg Jellyfin uses.** Jellyfin runs
  `/usr/lib/jellyfin-ffmpeg/ffmpeg`. The system build has no `chromaprint`; the Jellyfin one
  does. Check the right binary before concluding a codec or muxer is missing.
- **A faster cable does not mean the box uses it.** [CHANGE: claude-code | 2026-08-20] After the
  Cat 6 swap the wire ran at a full gigabit and the server still sent every byte over wifi —
  `wlan0`'s DHCP route is metric **600**, the wired one gets systemd-networkd's default **1024**,
  and lower wins. Finish a cabling change with `ip route get 8.8.8.8`, not `ethtool`. DECISION 79.
- **Never read `%{speed_download}` without `%{http_code}`.** Three "45–90 KB/s" readings here were
  460-byte **404 pages** timed as if they were transfers, and Cloudflare's `/__down` returns **403**
  above ~75 MB while still printing as a plausible `0.0 Mbps`. A speed number cannot fail loudly.
- **`systemd-run` does not inherit your working directory.** `cd /tmp && sudo systemd-run ...
  python3 -m http.server` serves `/`. Use `--working-directory=`.
- **`/tmp` is tmpfs on this box.** A benchmark against a file there measures RAM (8.6 GB/s observed)
  and never touches `/dev/sda`. `df | grep -v tmpfs` hides precisely the line you need.
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
- **`preferredProtocol=usenet` does not stop torrent grabs.** "Preferred" ranks a protocol
  first; it does not forbid the other one. That flag was already set while MobLand, House of
  Cards and two Odyssey grabs all still came over torrent. The flag that actually forbids a
  protocol is `enableTorrent` on the **delay profile**. See DECISION 59.
- **Prowlarr disables indexers in Sonarr/Radarr but never deletes them.** After an
  `ApplicationIndexerSync` the torrent entries stay visible in the UI with `enableRss`,
  `enableAutomaticSearch` and `enableInteractiveSearch` all `False`. Seeing "The Pirate Bay"
  in the indexer list does not mean the torrent path is open — read the three flags.
- **A download client can be enabled while the program does not exist.** qBittorrent was
  `enable=True` in both apps at NZBGet's priority, but `systemctl is-enabled qbittorrent`
  returns `not-found`. Grabs went to a nonexistent client and failed with no error — the item
  simply never arrived. Check the *unit*, not just the app's client list.
- **Jellyfin extracts embedded subtitles on first play, not at import.** A cold track on a
  2160p remux takes minutes to demux while the viewer sees nothing; a cached one serves in
  ~6 ms. There is no library option and no scheduled task for it in 10.11.11 — run
  `server/scripts/luminos-subtitle-warm`. New downloads are cold until you do.
- **Nothing here fetches subtitles.** Bazarr is not installed, so the only subtitles that exist
  are the ones already inside the release file.
- **NZBGeek is a US/English indexer, and it is now the only source.** A search for two
  well-known French titles returned **0** French-tagged results out of 100 each. Non-English
  audio is effectively unavailable; widen with another *Usenet* indexer, not with torrents.
- **Jellyfin over wifi crosses the radio twice.** server→router→G14 shares airtime, measuring
  ~35 Mbit/s against a 32.3 Mbit/s remux — about 5% headroom, which stutters. The idle wired
  `.62` measures 89.8 Mbit/s on the same file. YouTube working proves nothing here: it is
  ~5 Mbit/s over one hop.
- **The 500 GB USB drive has no readable SMART.** [CHANGE: claude-code | 2026-09-03] The
  enclosure passes none of `auto`, `sat`, `sat,12`, `usbjmicron`, `usbsunplus`, `usbcypress`
  or `scsi` — no power-on hours, no reallocated or pending sectors, on a laptop drive of
  unknown age. It will fail with no warning, so nothing irreplaceable lives only on it and
  `/srv/media/backup` was deliberately left on the internal disk. DECISION 91.
- **A second disk mounted *inside* `/srv/media` is a trap.** If it ever fails to mount, writes
  land on the underlying directory on `sda3` and silently fill the internal disk instead of
  failing loudly. That is why it is at `/srv/external`. Any future disk goes outside too.
- **An fstab entry without `nofail` can strand this box.** Root is locked (`passwd -S root`
  → `L`) and there is no keyboard — a USB disk that does not enumerate would drop it to
  `emergency.target` at a prompt nobody can answer. And `nofail` is worth *verifying*, not
  assuming: check the generated unit has empty `RequiredBy=` and only `WantedBy=local-fs.target`.
- **Root folder choice is automated by a timer, not by any app setting.** Neither Sonarr,
  Radarr nor Jellyseerr has a "most free space" policy — `activeDirectory` pins one path
  forever. `luminos-root-balance.timer` supplies the missing policy hourly, the same way
  `luminos-season-limit.timer` supplies the maximum-seasons setting Sonarr lacks. **If you
  hand-edit the root folder in the Jellyseerr UI, expect it back within the hour** unless the
  disks are within 20 GB of each other. DECISION 92.
- **Editing `/var/lib/jellyseerr/settings.json` while Jellyseerr runs achieves nothing.** It
  holds settings in memory and rewrites the file on its next save, silently discarding the
  edit. Go through the API (`PUT /api/v1/settings/{radarr,sonarr}/{id}`).
- **Jellyseerr rejects its own GET body on PUT.** Round-tripping an object straight from
  `GET /api/v1/settings/radarr` returns **HTTP 400 `request/body/id is read-only`** — `id`
  belongs in the URL only and must be stripped. Every *other* field has to be sent back or it
  counts as a change, so strip exactly that one.
- **The hardlink objection to a second filesystem no longer applies, but only just.** 360 of
  414 GB of large files are hardlinked, which argues loudly against splitting the library. Those
  twins are torrent-era residue; nothing seeds since DECISION 84, and both apps have
  `removeCompletedDownloads=True`, so an import that copies costs one release transiently rather
  than permanently. **If completed-download removal is ever switched off, that reasoning dies**
  and a second filesystem starts costing real space. DECISION 91.
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
