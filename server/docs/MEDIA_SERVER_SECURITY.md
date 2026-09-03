# Media Server — Security Brief
# [CHANGE: claude-code | 2026-07-30]

**Machine:** `luminos-server` — Dell Inspiron 3590, i5-10210U, Arch on `/dev/sda`.
**Addresses:** wlan0 `192.168.2.61` · enp2s0 `192.168.2.62` · public IP `76.64.36.43`
**Admin access:** `ssh -i ~/.ssh/luminos-server shawn@192.168.2.61` from the G14 (`192.168.2.16`).
**Services:** Jellyfin 8096 · qBittorrent WebUI 8080 · Sonarr 8989 · Radarr 7878 · Prowlarr 9696 · SSH 22

This document is a standalone handover. It assumes no knowledge of the conversation
that produced it. Everything marked **DONE** is already applied and verified on the
box; everything marked **TODO** still needs doing, and each one says *why*.

---

## 0. One-paragraph summary

The server was **reachable from the public internet** — not through any of the web
apps, but because qBittorrent used UPnP to ask the router to forward port **25989**
(TCP and UDP) from the internet straight to it — silently, without anyone choosing it.
A LAN-only firewall is now installed and enabled at boot, and qBittorrent's UPnP is
off so nothing can reopen a port behind your back. HTTPS was *not* the actual risk and
is deliberately deferred — the reasoning is in §5.

**Updated 2026-07-31:** port 25989 has since been reopened **on purpose**, with the
owner's approval, because a fully unreachable client could not download (§2a). The
difference from the original problem is consent and scope: it is now one named port
with no login behind it, written down in the firewall file, re-asserted by a service
that names the interface explicitly — instead of an unknown port opened by an app.
Everything with a control surface is still LAN-only.

Two things remain, both needing a human: check the router for **manual** port forwards
(§4), and firewall the G14 itself (§7).

---

## 1. DONE — the internet-facing hole is closed

### What was wrong
qBittorrent's `upnp` preference was `true`. UPnP (Universal Plug and Play) lets any
program on the LAN silently instruct the router to open a port from the internet to
itself, with **no prompt and no log entry you would ever see**. qBittorrent used it to
open its listen port so that torrent peers could connect inbound.

Evidence it was real, not theoretical — with a temporary logging rule on the new
firewall, over roughly 20 seconds:

```
SRC=92.247.115.73    DST=192.168.2.62  DPT=25989   (Bulgaria)
SRC=89.238.177.246   DST=192.168.2.62  DPT=25989   (United Kingdom)
754 packets / 775,744 bytes
```

### Why it matters
For qBittorrent itself the traffic was legitimate — that is how seeding works. The
problem is the *shape* of it: a program on the LAN could open a door to the internet
whenever it felt like it, and nothing on the machine was positioned to say no. The
next program to do it might not be one you chose.

### What was done
1. Deleted both mappings (`upnpc -d 25989 TCP` and `… UDP`, both returned `0`,
   meaning "a mapping existed and is now removed").
2. Set `upnp: false` via the qBittorrent API so it cannot re-create them:
   ```bash
   curl -X POST http://localhost:8080/api/v2/app/setPreferences \
        --data-urlencode 'json={"upnp":false}'
   ```
3. Re-probed afterwards to confirm it stayed shut.

### How to re-check later
```bash
upnpc -d 25989 TCP    # 714 = nothing forwarded (good).  0 = a mapping existed.
upnpc -d 44444 TCP    # control port nobody uses — must also return 714
```

> **Trap — do not trust `upnpc -l` on this router.** It prints an **empty mapping
> table even while a mapping is live.** This was proved: a throwaway mapping was
> created on port 39555, the router itself confirmed it
> (`external 76.64.36.43:39555 TCP is redirected to internal 192.168.2.61:39555`),
> and `upnpc -l` still showed nothing. Only `upnpc -d` and its return code are
> trustworthy here. Note `-d` is destructive by design, so **never probe a port that
> something is legitimately using** — in particular the live torrent listen port.

---

## 2. DONE — LAN-only firewall

`/etc/nftables.conf`, loaded by `nftables.service`, `systemctl is-enabled nftables` =
`enabled`.

```
#!/usr/bin/nft -f
# [CHANGE: claude-code | 2026-07-30] LAN-only firewall for luminos-server.
flush ruleset

table inet filter {
  chain input {
    type filter hook input priority filter; policy drop;

    ct state invalid drop
    ct state established,related accept
    iif lo accept

    icmp   type { echo-request, destination-unreachable, time-exceeded } accept
    icmpv6 type { echo-request, destination-unreachable, packet-too-big, time-exceeded,
                  nd-neighbor-solicit, nd-neighbor-advert, nd-router-advert } accept

    ip  saddr 192.168.2.0/24 accept     # the home network is trusted
    ip6 saddr fe80::/10      accept

    # [CHANGE: claude-code | 2026-07-31] see §2a — deliberately public
    tcp dport 25989 accept comment "qbittorrent peer port"
    udp dport 25989 accept comment "qbittorrent peer port (uTP/DHT)"

    counter comment "everything else is dropped"
  }

  chain forward { type filter hook forward priority filter; policy drop; }
  chain output  { type filter hook output  priority filter; policy accept; }
}
```

**The rule in one sentence:** anything from `192.168.2.x` is welcome, plus the single
torrent peer port from anywhere, and everything else is dropped.

## 2a. The one deliberate exception — port 25989

Added **2026-07-31**, with the owner's explicit approval. This reverses part of §1, so
the reasoning matters.

**Why it was needed.** With the port closed, qBittorrent had uploaded **0 bytes, ever**.
No peer on the internet could open a connection to it, so it could only ever reach the
minority of peers that are themselves connectable. Downloads of well-seeded 4K releases
sat at **1 connected peer** and stalled at 0.00 MB/s.

**Why this specific port is an acceptable exposure.** It is a BitTorrent peer data port:
no login, no admin surface, no stored data reachable through it. It is the one port the
protocol is designed to expose. Everything with a control surface stays LAN-only —
qBittorrent's WebUI (8080), Jellyfin (8096), Sonarr (8989), Radarr (7878), Prowlarr
(9696) and SSH (22) are all still covered by the subnet rule alone.

**nftables is the authority, not the router.** The `dport 25989` rules are the thing
that decides. The router forward is only convenience, and is re-asserted by
`qbt-portmap.service` / `.timer` (hourly + 90 s after boot), pinned to
`192.168.2.61`. qBittorrent's own UPnP is **off** — see §2b for why.

**To close it again:** delete the two `dport 25989` lines from `/etc/nftables.conf`,
`sudo systemctl restart nftables`, then `sudo systemctl disable --now qbt-portmap.timer`
and `upnpc -d 25989 TCP; upnpc -d 25989 UDP`.

### Verified from outside the network, not assumed
A port checker website reported 25989 **closed** — it was wrong. The real test opened a
throwaway port 39555, served a known string on it, and fetched
`http://76.64.36.43:39555/` from a host outside the LAN, which returned
`LUMINOS-REACHABILITY-OK`. That proves the whole chain — nftables rule, router forward,
listener. The temporary rule, mapping and server were all removed afterwards.

> **Do not test your own public IP from inside your own LAN.** Every port answered
> ambiguously that way (`connection refused` vs `timeout`) because consumer routers
> handle hairpin NAT inconsistently. Only an genuinely external client gives a real answer.

## 2b. Trap — qBittorrent's UPnP mapped the *wrong* interface

This box is dual-homed on one subnet: `wlan0` = `192.168.2.61`, `enp2s0` =
`192.168.2.62`. With `upnp=true`, qBittorrent forwarded the router to **192.168.2.62**,
the ethernet IP — a link negotiated at **100 Mb/s** because of a bad cable. Every
inbound peer packet was therefore delivered over a path that caps the machine at about
**12.5 MB/s**, and measured throughput sat at 10.7 MB/s, i.e. a saturated link that
looked like "slow torrents".

Caught with `tcpdump -i enp2s0 port 25989`, which showed tens of thousands of packets
addressed to `192.168.2.62` while `wlan0` saw none.

Fixes applied, in order:
1. Bound qBittorrent to `wlan0` / `192.168.2.61` only.
2. Turned qBittorrent's UPnP **off** and moved the mapping into `qbt-portmap.service`,
   which names `192.168.2.61` explicitly. (Left on, qBittorrent later stopped creating
   any mapping at all — the delete-probe returned `714`.)
3. `/etc/sysctl.d/30-luminos-arp-flux.conf` sets `arp_ignore=1` and `arp_announce=2`.
   Without these, Linux answers an ARP request for *any* local IP out of *any*
   interface, so the router had learned `192.168.2.61` at the **ethernet** card's MAC
   and delivered traffic for the wifi IP over the slow wire regardless of routing.

> **The general lesson:** on a machine with two interfaces in one subnet, the routing
> table tells you nothing about which cable a packet actually arrives on. `ip route get`
> said `wlan0`; the bytes were on `enp2s0`. Only per-interface counters
> (`/sys/class/net/<if>/statistics/rx_bytes`) and `tcpdump -i <if>` tell the truth.

### Why this shape and not per-port rules
> **⚠️ REVERSED on 2026-09-02 by DECISION 90 — see §2c. The argument below is kept
> because it was the reasoning at the time and it is worth knowing why it stopped
> holding, not because it is still the design.**

Per-port allow-lists rot. Every new service means remembering to add a rule, and
forgetting means either a broken app or an open port. Trusting the subnet instead
means new services on the box work automatically for the house and are invisible from
outside, with no maintenance. The cost is that it gives you nothing against a device
*already on your wifi* — which is the correct trade for a home LAN, but see §7.

**What changed:** the sentence "the cost is that it gives you nothing against a device
already on your wifi" was written as an acceptable cost. It stopped being acceptable
once two things were true. First, DECISION 80/84 put **Caddy in front of every app over
TLS**, so the bare ports became a *duplicate* of access that already existed — closing
them removed nothing, it removed the unencrypted copy. Second, an audit found
**byparr on `:8191` answering HTTP 200 with no authentication whatsoever**, which is
precisely the "device already on your wifi" case turning into a real problem. The
maintenance argument also weakened: adding an app now means editing the Caddyfile
anyway, and the firewall rule is a **port range** (`8443-8449`) that new apps fall into
without a firewall edit at all.

### Verified, not assumed
- All five services still answer from the G14: `8096→302` (Jellyfin's normal
  redirect to `/web/`), `8080→200`, `8989→200`, `7878→200`, `9696→200`.
- SSH from `192.168.2.16` works.
- Dropped-packet counter after the UPnP mappings died: **t=0 → 0, t=60s → 0 (+0)**,
  and a 15-second `tcpdump` of non-LAN inbound captured nothing.

### If you ever need to change these rules — arm the rollback first
```bash
sudo systemd-run --unit=fw-rollback --on-active=240 /usr/bin/nft flush ruleset
sudo nft -f /etc/nftables.conf
# ... now open a NEW ssh session and prove it works ...
sudo systemctl stop fw-rollback.timer 2>/dev/null; sudo systemctl reset-failed fw-rollback 2>/dev/null
```
An empty ruleset means *no table*, which means *accept everything* — so wiping the
ruleset is a safe rollback, not a further lockout. Arm it **before** loading.

> **Two traps.**
> 1. Because `ct state established,related accept` comes first, **your current SSH
>    session survives any rule change** — so testing in the session you are already
>    sitting in proves nothing. You must open a fresh connection.
> 2. `nftables.service` is a **oneshot**. After a *successful* load
>    `systemctl is-active nftables` reads `inactive` and exits 3 (which will kill a
>    `set -e` script). Use `is-enabled` plus a live `nft list ruleset` instead.

> **A third trap, found 2026-09-02.** The rollback above says `nft flush ruleset`, and
> that is still safe *for getting back in* — no table means no policy means accept.
> But `flush ruleset` deletes **every** table on the machine, including the four
> `ip`/`ip6` `filter`/`nat`/`mangle` tables that **tailscaled** owns. You get your SSH
> back and quietly lose the tunnel's rules until tailscaled next rewrites them. If you
> only want to undo *this* file, use `nft delete table inet filter` instead.

---

## 2c. DONE (2026-09-02) — the LAN gets named ports, not the whole machine
# [CHANGE: claude-code | 2026-09-02]

This is DECISION 90. It reverses the "trust the subnet" shape above, plus three other
things that were only safe because the subnet rule was hiding them.

### What was actually open

A sweep from the G14 (`192.168.2.16`) against every service port found:

| Port | Service | What answered |
|---|---|---|
| 8191 | **byparr** | **HTTP 200 on `/docs`, no authentication at all** — FastAPI's interactive API console, to anyone on the wifi |
| 8099 | luminos-space | running **as root**, bound `0.0.0.0`, URL token the only lock, and its buttons delete films |
| 8989 / 7878 / 9696 | Sonarr / Radarr / Prowlarr | plain HTTP, API keys in the clear on the wire |
| 6789 | NZBGet | plain HTTP with the Usenet account behind it |
| 5055 | Jellyseerr | plain HTTP |

byparr is the one that mattered most, and not because of the data behind it — it has
none. Its **job** is to fetch arbitrary URLs through a real headless browser. An open
one is a machine on your home network that will make requests on someone else's behalf.

### The four changes

1. **Firewall narrowed** — `/etc/nftables.conf`, tracked at `server/config/nftables.conf`.
   `ip saddr 192.168.2.0/24 accept` became five named rules: `22`, `{80,443}`,
   `8443-8449`, `8096`, and `udp 68`. The `tailscale0` interface rule stays wide open,
   and that gap is now the point: **the tailnet is the trusted path** (every peer is
   authenticated and every machine on it is ours), the home wifi is not.
   - `8096` stays open in the clear **on purpose**: the Roku app stores a bare server
     address, does not follow redirects, and will not accept Caddy's local CA. The TV
     working beats closing it, and Jellyfin demands a login regardless.
   - `udp 68` is not optional. Both NICs get their address by DHCP, and a renewal
     answered by *broadcast* is not matched by `ct state established`. Without that
     rule the lease can fail to renew and the box drops off the network by itself some
     hours later — the exact unattended failure this whole effort exists to prevent.
   - `flush ruleset` at the top of the file was removed at the same time (see the trap
     note above).

2. **byparr moved to loopback** — `server/systemd/byparr-override.conf`.
   The packaged unit ships `HOST=0.0.0.0`; it is now `127.0.0.1`. Prowlarr is the only
   consumer and already addressed it as `http://localhost:8191/`, so this cost nothing.
   Sandboxing added around it.
   - `ProtectSystem` is **deliberately absent**, and that was measured, not assumed.
     With `ProtectSystem=strict` byparr starts fine and then fails every real request
     with `OSError: [Errno 30] Read-only file system` on a path inside
     `/usr/lib/python3.14/site-packages/playwright_captcha/...` — the library rewrites
     scripts inside its own install directory at solve time. All three levels
     (`yes`/`full`/`strict`) make `/usr` read-only, so all three break it. A
     `ReadWritePaths` carve-out was **rejected**: the path contains `python3.14`, so a
     Python minor bump would move it, systemd would keep starting the unit happily, and
     the failure would only appear at request time looking like "flaky indexers". A
     brittle carve-out that fails silently is worse than not having the setting.
   - `MemoryDenyWriteExecute` is also absent — it would break the JavaScript JIT and
     the browser would never start.

3. **luminos-space de-rooted and moved to loopback** — `server/systemd/luminos-space.service`.
   Runs as `luminosspace`, binds `127.0.0.1:8099`, sits behind Caddy's `:8446`.
   The old unit justified root with two reasons and **both measured false**:
   - *"it needs root to read the Sonarr/Radarr API keys."* Those files are `0664`
     `<app>:media`. Group `media` reads them fine. The script was shelling out to
     `sudo -n grep`, so it needed root only because it had chosen to use sudo —
     circular. It now opens the file directly.
   - *"it needs root to unlink hardlink twins under `/srv/media/downloads`."*
     Unlinking needs write on the **directory**, not the file, and both directories are
     `drwxrwsr-x` group `media`.
   - `nzbget.conf` is the one genuine exception (`0640 nzbget:nzbget`, it holds the
     Usenet password). Granted with a single ACL entry, matching luminoshub's:
     `setfacl -m u:luminosspace:r /var/lib/nzbget/nzbget.conf`.
   - The URL token still exists and is still required. It is now a second lock rather
     than the only one.

4. **Caddy answers on the wire too** — `/etc/caddy/Caddyfile`.
   Every site block listed `100.82.125.26` and `192.168.2.61` but **not**
   `192.168.2.62`. Since the wire is the default route (DECISION 79) and the wifi is
   the interface whose firmware crashed earlier the same day, the entire web front door
   depended on the less reliable address. `.62` was added to all eight blocks. A host
   missing from every block does not 404 — it fails the TLS handshake (curl exit 35),
   which reads as "the server is down".

### Verified, not assumed

- **Positive:** Roku path `8096→302`; all of `443`, `8443`–`8449` answer over TLS on
  both `.61` and `.62`; tailnet reaches `8989`/`9696`/`6789`; Prowlarr's byparr proxy
  test returns `{}` `HTTP:200`; luminos-space `/api/data` and `/api/downloads` return
  real data through Caddy and a bad token returns `403`.
- **Negative:** the seven bare ports `8191, 8099, 8989, 7878, 9696, 6789, 5055` all
  refuse from `192.168.2.16`. A change that only proves the good path is half a test.
- **Cold table:** `nft delete table inet filter` then `systemctl start nftables`, to
  prove the new file loads when the table does not already exist (the create/delete/
  define idiom would otherwise fail on a cold boot).
- The whole firewall load ran behind a 5-minute `systemd-run --on-active=300`
  auto-rollback, cancelled only after a **new** SSH session proved access.

### What this leaves broken

**nzb360 on the phone**, if it was pointed at bare `192.168.2.61:8989` / `:7878` /
`:6789`, will stop connecting. Point it at the Caddy ports (`8448`, `8447`, `8445`) or
use the tailnet address instead. Nothing else on the LAN was using the bare ports.

### Undo

Every replaced file was copied to `/root/<name>.bak-20260902` first:
```bash
sudo cp /root/nftables.conf.bak-20260902 /etc/nftables.conf && sudo nft -f /etc/nftables.conf
sudo cp /root/Caddyfile.bak-20260902 /etc/caddy/Caddyfile && sudo systemctl reload caddy
sudo cp /root/byparr-override.bak-20260902 /etc/systemd/system/byparr.service.d/override.conf
sudo cp /root/luminos-space.service.bak-20260902 /etc/systemd/system/luminos-space.service
sudo cp /root/luminos-space.bak-20260902 /usr/local/bin/luminos-space
sudo systemctl daemon-reload && sudo systemctl restart byparr luminos-space
```

---

## 3. DONE / already good — SSH and accounts

No changes were needed; recording it so nobody "fixes" it later.

| Setting | Value | Why it matters |
|---|---|---|
| `PermitRootLogin` | `no` | root is the one username every scanner tries |
| `PasswordAuthentication` | `no` | password guessing becomes impossible, not just hard |
| `KbdInteractiveAuthentication` | `no` | closes the second password path people forget |
| `PubkeyAuthentication` | `yes` | the only way in is a key held on the G14 |
| `X11Forwarding` | `no` | headless box, no reason to expose it |
| root account | `L` (locked) | no password exists to crack |
| login users | only `shawn` | nothing else to attack |

**Do not add a password to `shawn` and do not re-enable password auth.** On a key-only
box a sudo password adds no attacker cost — the only way in already requires a key we
control — but it does add a way to lock *ourselves* out of a machine with no keyboard
attached.

---

## 4. TODO (user only) — check the router for manual port forwards

**What to do:** log into the Bell Home Hub at `http://192.168.2.1`, find
**Port Forwarding** (sometimes under Advanced → Firewall / NAT), and write down
every rule listed. Delete anything that points at `192.168.2.61` or `192.168.2.62`
unless you deliberately want it.

**Why only you can do this:** the UPnP probe used above can only ever see mappings
that were created *through UPnP*. A rule someone typed into the router by hand is
invisible to it. A clean UPnP probe is therefore **not** a clean bill of health.

**One specific loose end:** probing port **22** returns UPnP error code **606**
(`Action not authorized`) on both the server and the G14 — the router refuses to
discuss that port over UPnP. That is *inconclusive*, not *safe*. If SSH is forwarded
from the internet, that is the single highest-value thing on this list to find and
remove. The router page is the only place that can answer it.

**What "good" looks like:** an empty port-forwarding table.

---

## 5. Decision — HTTPS is deliberately NOT enabled

Shawn asked for HTTPS. The honest answer is that on this LAN it is a nice-to-have,
not the thing that was at risk, and every cheap way of doing it breaks the TV.

**What HTTPS defends against** is somebody positioned between your device and the
server, reading or altering the traffic. Inside the house that person would have to
already be on your wifi — and that hop is *already encrypted* by WPA2/WPA3
regardless of what the browser bar says.

| Option | Laptop / phone | Roku TV | Real cost |
|---|---|---|---|
| Self-signed certificate | warning on every visit | **breaks** — Jellyfin clients reject it | loses the TV, the main use case |
| Private CA (own root cert) | works if installed per device | **breaks** — Roku has no way to add a CA | loses the TV |
| Let's Encrypt + DNS-01 | works | works | needs a domain name (~$12/year) |

Only the third row works everywhere. **DNS-01 validation is the important detail**:
it proves domain ownership through a DNS TXT record, so **no port has to be opened**
to get or renew the certificate. Any guide that tells you to forward port 80 or 443
for HTTP-01 validation is describing the wrong method for this situation — that would
undo §1 and §2.

**Recommended order:** do §4, §6 and §7 first. Then, if you still want HTTPS, buy a
domain and set up Let's Encrypt with DNS-01 behind a reverse proxy (Caddy is the
least-effort choice; it does DNS-01 and renewal automatically).

**For access from outside the house: use a VPN, never a forwarded port.** Tailscale
installs on the server and on your phone and makes your phone a member of the home
network from anywhere, with nothing opened at the router. This was declined earlier in
the project; §1 is the reason to reconsider it.

---

## 6. DECIDED (2026-07-31) — the torrent port trade-off

> **Outcome: option 2 was chosen and is implemented.** Port 25989 TCP+UDP is forwarded
> to `192.168.2.61` and allowed in `/etc/nftables.conf`; `upnp` stays `false`. The
> full reasoning, the outside-in proof, and how to undo it are in **§2a**. The section
> below is kept as the record of the decision.
>
> The prediction below turned out to be exactly right, and worse than expected:
> qBittorrent had uploaded **0 bytes for its entire lifetime** and 4K downloads sat at
> **1 connected peer**.

**This is a genuine cost of the fix in §1 and it should be a conscious choice.**

qBittorrent now reports `connection_status: firewalled`. That means peers on the
internet cannot start a connection *to* the server; the server can only reach *out*.
Torrents still work, but a significant share of any swarm is itself behind a
firewall — and **two firewalled peers can never connect to each other**, so the
reachable pool shrinks and downloads get slower and less reliable.

Three ways forward, in order of how much they give away:

1. **Leave it closed.** Nothing is exposed. Torrents are slower, especially on small
   swarms. *This was the state until 2026-07-31.*
2. **Forward exactly one port, by hand, at the router** — `25989` TCP+UDP →
   `192.168.2.61`, plus a matching `tcp dport 25989 accept` / `udp dport 25989 accept`
   rule in `/etc/nftables.conf`. This is the standard setup. The difference from what
   was wrong before is that it is **one known port you chose**, visible in the router
   page, rather than any program opening whatever it likes whenever it likes. Keep
   `upnp: false` either way.
3. **Re-enable UPnP.** Do not. This is what created the problem.

Option 2 is the reasonable middle. If you take it, note that the exposed surface is
qBittorrent's BitTorrent protocol handler — keep the package updated
(`pacman -Syu` over SSH, manually, which is already the policy for this box).

**One caveat learned while implementing option 2:** forwarding to "the server" is not
specific enough on this machine. It has two IPs on the same subnet and the router will
happily forward to the slow one. Always name `192.168.2.61` (wifi), and confirm with
`tcpdump -i enp2s0 port 25989` that the ethernet card is *not* carrying peer traffic.
See §2b.

**Do NOT forward port 8080.** That is the qBittorrent *WebUI*, which is a full
remote-control panel, and `WebUI\LocalHostAuth=false` is set so connections from the
machine itself skip authentication entirely. It must stay LAN-only.

---

## 6a. HALTED (2026-08-04) — the ISP can see all of this, so torrenting is off until a VPN is in
<!-- [CHANGE: claude-code | 2026-08-04] -->

Everything in §2a and §6 is about *who can reach in*. This section is about the
opposite direction: **who can see what goes out.** The answer, today, is the ISP and
anyone who cares to look, and that is why torrent traffic is currently stopped.

Full record in [`../DECISIONS.md`](../DECISIONS.md) → **DECISION 42**.

### What is actually visible

| | |
|---|---|
| **The protocol** | BitTorrent is unencrypted by default and identifiable by its handshake signature. Running it on 25989 instead of 6881 does not disguise it — port choice is not obfuscation. |
| **The IP, in a public list** | Because §2a opened an *inbound* port, this box is an **advertised** peer. It appears in the tracker's peer list and in DHT results for every torrent it carries, against **76.64.36.43**. That list is readable by anyone, which is precisely how monitoring firms build notices. |
| **The volume** | `up_info_data` had reached **228.9 GB** uploaded against 389.9 GB down. Seeding is the conspicuous half — an outbound-only client is a face in the crowd, a seeder is on the list. |

Note the interaction: **§2a made §6a worse.** Opening the port was the right call for
throughput and it is what made seeding work at all, but working seeding is exactly what
puts the IP on a public list. The two decisions are correct individually and in tension
together, which is the whole reason a VPN is now required rather than optional.

### Current state — verified 2026-08-04

Four layers, so that undoing any one of them does not resume traffic:

```
1. all 22 torrents          -> stopped   (POST /api/v2/torrents/stop, hashes=all)
2. qbittorrent-nox@shawn    -> stopped AND disabled  (nothing listens, survives reboot)
3. qbt-portmap.timer        -> stopped AND disabled  (was still re-punching the router
                                           forward hourly, armed to fire in 15 min)
4. Sonarr/Radarr rssSync    -> 0         (no grab backlog builds behind the halt)
```

Layer 3 is the one that is easy to miss: the thing keeping the port open at the *router*
is a **separate unit from the service it serves** (§2b — qBittorrent's own UPnP stopped
mapping, so a timer took over). Stopping qBittorrent does not stop it.

Proven from the G14, with a control so the probe cannot lie:

```
192.168.2.62:25989   Connection refused    <- peer port dead
192.168.2.61:8080    Connection refused    <- WebUI dead (same process)
192.168.2.61:8096    OPEN                  <- CONTROL: the probe can still see
                                              an open port, so the two above mean
                                              something
```

The nftables `accept` rules for 25989 were **deliberately left in place**. They are
inert while nothing is listening, and removing them is a real reversal of §2a /
DECISION 35 rather than a side effect of this halt.

### Not affected
Jellyfin keeps serving. That is LAN traffic between the server and the TV; it never
crosses the ISP. Prowlarr can still query indexers — ordinary HTTPS, not swarm
participation, and it does not put the IP in a peer list.

### Before this is switched back on
A VPN client alone is not enough. All three of these have to be true and none are yet:

- [ ] **The tunnel exits via `enp2s0`, and qBittorrent binds to the tunnel.** DECISION 36
      keeps torrents off the wifi radio by `SO_BINDTODEVICE`. Get this wrong and the
      encrypted tunnel rides the radio, and the TV stutters again for a reason that will
      look nothing like a VPN problem.
- [ ] **Kill-switch tested, not assumed.** Down the tunnel interface mid-transfer and
      confirm the byte counters go to zero. Binding to a dead interface *should* stall
      rather than fall back — verify that it does.
- [ ] **Port forwarding through the provider decided.** Most do not offer it. Without it
      the inbound port from §2a is gone and the client is outbound-only again — an
      acceptable cost, but it should be known in advance rather than discovered.

**Provider choice is the user's** — it is a paid subscription and a decision about who
gets to see the traffic instead of the ISP.

### 6b. A VPN is not the only answer, and for this box it is not the best one
<!-- [CHANGE: claude-code | 2026-08-04] -->

Asked directly: *"we can use vpn right? or is there something better?"* Yes, and yes.
The trap is that "hide it from the ISP" is **two** exposures, and a VPN only closes one.

| # | Exposure | Who sees it | Closed by VPN? |
|---|---|---|---|
| 1 | BitTorrent on the wire — unencrypted, obvious protocol signature | the ISP | **yes** |
| 2 | The IP published in every swarm's peer list, enumerable by anyone, permanently | anyone | **no** — it becomes the VPN's IP, still listed |

Exposure 2 is the larger one and the one people forget. Seeding is what puts an address
at the top of those lists, and this box had uploaded **228.9 GB**.

**Usenet — best fit here.** No swarm, so no peer list, no seeding, nothing to enumerate;
an encrypted NNTP connection to one provider, which is all the ISP sees. Sonarr and
Radarr support it natively through **SABnzbd or NZBGet — both native Arch packages**, so
it satisfies the NO DOCKER rule. It also closes a *separate* open problem: downloads
were **swarm-limited at 10.74 MB/s** while the network measured **46.34 MB/s**. Usenet
has no swarm to be limited by, so it is the only option that fixes the privacy problem
and the "46 MB/s" goal at once. Costs two subscriptions (provider + indexer). The real
downside is **retention** — old or obscure material can simply be gone, where a torrent
survives as long as one seeder does.

**Seedbox — second.** Torrenting happens on a rented remote machine and the finished
file comes down over HTTPS/SFTP. The home IP never enters a peer list at all. Dearer,
and it is another host to maintain.

**VPN — third.** Cheapest and simplest, genuinely closes exposure 1, and moves the trust
from the ISP to the VPN company. But the address is still in the swarm.

**Ruled out: qBittorrent's built-in protocol encryption (MSE/PE).** It obfuscates the
peer-to-peer payload against naive traffic shaping. It does **not** remove the IP from
the peer list, so it does nothing about exposure 2. Do not mistake that checkbox for a
solution.

**Recommendation:** Usenet as the primary path, with a VPN only for the residue that
Usenet cannot supply. Which providers, and whether to pay for both, is Shawn's call.

---

## 7. DONE — the G14 itself has no firewall
# [CHANGE: claude-code | 2026-09-02]

> **Resolved by DECISION 88.** The laptop now runs its own nftables ruleset plus
> DNS-over-TLS. Its config deliberately **diverges** from the server's rather than
> copying it, for the reason given at the bottom of this section: the G14 roams, so a
> `192.168.2.0/24` trust rule is meaningless on a café network. The audit below is the
> state as of 2026-07-30 and is kept for the port inventory. Note that qBittorrent is
> long gone from both machines (DECISION 42, then 48).

The laptop (`192.168.2.16`) was audited at the same time. **No firewall is
configured.** Listening on non-loopback addresses:

| Port | Process | Note |
|---|---|---|
| 22 | sshd | |
| 5355 | systemd-resolved | LLMNR, normal |
| 8080 | qBittorrent WebUI | full remote-control panel |
| 21861 | qBittorrent | **live seeding port for 9 torrents — do not touch** |
| 9091 | `luminos-ram` (pid 786) | a Luminos daemon, bound to `*` rather than localhost |

A UPnP probe found **no** internet-facing holes for 8080 / 9091 / 8989 / 7878 / 9696 /
8096, so nothing here is exposed to the internet — but nothing stops other devices on
the wifi either.

**What to do:** apply the same LAN-only ruleset from §2, adding an accept for port
**21861** so seeding keeps working. `luminos-ram` on `*:9091` is worth a separate
look — if nothing remote needs it, binding it to `127.0.0.1` is better than
firewalling around it.

**Why it matters less here than on the server:** the G14 is a laptop that leaves the
house. On a café or airport network, `192.168.2.0/24` will not match anything, so a
subnet-trust rule becomes an effective deny-all — which is the right behaviour, but it
does mean the rule must be written to fail closed, not opened up per-network.

---

## 8. Checklist

| # | Item | Who | Status |
|---|---|---|---|
| 1 | Remove UPnP port-forward on 25989 | done | ✅ |
| 2 | Disable UPnP in qBittorrent so it cannot reopen | done | ✅ |
| 3 | Install LAN-only nftables firewall, enable at boot | done | ✅ |
| 4 | Verify all 5 services + SSH still reachable | done | ✅ |
| 5 | Confirm SSH hardening + locked root | done | ✅ (already good) |
| 6 | Check router page for **manual** port forwards | **Shawn** | ⬜ |
| 7 | Resolve the port-22 UPnP code 606 unknown | **Shawn** | ⬜ |
| 8 | Decide the torrent-port trade-off (§6) | **Shawn** | ⬜ |
| 9 | Firewall the G14, keeping 21861 open | done | ✅ DECISION 88 (21861 moot, qBittorrent removed) |
| 10 | Bind `luminos-ram` to localhost, or justify `*:9091` | either | ⬜ |
| 11 | HTTPS via domain + Let's Encrypt DNS-01 | done | ✅ DECISION 80/84, local CA not Let's Encrypt |
| 12 | Halt all torrent traffic until a VPN is in place (§6a) | done | ✅ 2026-08-04 |
| 13 | **Choose the path: Usenet, seedbox or VPN** (§6b — Usenet recommended) | done | ✅ Usenet, DECISION 48 |
| 14 | Install the VPN so the tunnel exits `enp2s0` (§6a, DECISION 36) | — | ➖ dropped — no torrents to protect |
| 15 | Test the kill-switch by downing the tunnel mid-transfer | — | ➖ dropped with 14 |
| 16 | Narrow the LAN rule to named ports (§2c) | done | ✅ 2026-09-02, DECISION 90 |
| 17 | Close byparr — was HTTP 200 unauthenticated (§2c) | done | ✅ 2026-09-02, DECISION 90 |
| 18 | De-root luminos-space, move it off the LAN (§2c) | done | ✅ 2026-09-02, DECISION 90 |
| 19 | Off-box backups of the *arr databases | done | ✅ 2026-09-02, DECISION 90 |
| 20 | Full-disk encryption with TPM auto-unlock | **Shawn** | ➖ declined — needs a root-fs rebuild on a headless box |
| 21 | BIOS admin password | **Shawn** | ➖ declined — would block the remote firmware access WakeOnAc needs |
| 22 | Physically test WakeOnAc: unplug at the wall, wait 10s, replug | **Shawn** | ⬜ |

---

## 9. Principle worth keeping

Every finding here came from a check that could **fail**. The UPnP hole was only found
because a deliberately-created test mapping proved that `upnpc -l` lies; the firewall
was only trusted after a logging rule caught real packets from real strangers; the
services were only declared reachable after a *new* connection was opened rather than
the one already sitting open.

A check that asks *"does this exist?"* instead of *"does this work?"* will eventually
tell you what you want to hear. Write the negative test, or the check will lie.
