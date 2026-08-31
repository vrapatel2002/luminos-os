# Security on the G14 — what is closed, what is open, and why
# [CHANGE: claude-code | 2026-08-31]

This laptop is used for everything, so the rule behind all of it is: **close the doors
nobody uses, and do not touch anything a person would notice.** If something here ever
gets in your way, every item has an undo.

---

## The one thing to understand

The firewall only governs connections coming **in**. Outbound is deliberately left wide
open (`policy accept`).

Browsing, gaming, Steam, downloads, HIVE, the forex bot, updates, every API call — those
are all things *this* machine starts, and replies to them come back through a rule that
says "if we asked for it, let it in." **None of that changed and none of it can break
because of the firewall.**

The only things affected are connections that some *other* machine starts towards this
laptop. Before, every one of those was allowed.

---

## What was actually open before

Measured on 2026-08-31 by curling this laptop **from the media server**, not assumed:

| Port | What | State before |
|---|---|---|
| `:9091` | `luminos-ram` metrics, running as **root** | **HTTP 200, 9805 bytes, no password**, to anyone on the wifi |
| `:6789` | NZBGet | already loopback-only |
| `:22` | SSH | open to the whole network, **and password login is on** |
| `:8090` | mobile chat | open, but HTTPS and asks for a password (401) |

The `:9091` one is the real finding. It is low-sensitivity telemetry — Go runtime and RAM
numbers — but it was an unauthenticated door served by a root process, and every guest,
every phone, and every device on any wifi this laptop joined could read it.

---

## What is open now, and why each one has to be

| Allowed in | Why removing it would be visible |
|---|---|
| Anything over **Tailscale** | this is the main door. Your phone reaches SSH and the mobile chat from anywhere. Peers are authenticated *before* a packet gets here. |
| **UDP 41641** | Tailscale's direct path. Without it, connections still work but quietly route through a relay in Toronto — slower, and hard to notice. |
| **ICMP / ICMPv6** | ping, "packet too big", and IPv6 neighbour discovery. Blocking the last one breaks IPv6 completely, which looks like "the wifi is broken". |
| **DHCP replies** | how you get an IP address on a new network. |
| **mDNS / LLMNR** (5353, 5355) | printers, casting, KDE Connect pairing. |
| **SSH + mobile chat, from the home network only** | the two things actually used from the LAN. |

Everything else is dropped silently.

## Why this is not just a copy of the server's firewall

The server sits on one network forever, so "trust anything from 192.168.2.x" is a safe
blanket rule there. **A laptop joins airport, hotel and cafe wifi.** The same rule on this
machine would hand every stranger at the gate exactly the trust you meant for your living
room. So here the home network is named explicitly and used for as little as possible, and
Tailscale carries the rest — it is authenticated, it works from anywhere, and it does not
care which wifi you are on.

There is one honest gap left in that: the home rules match by **subnet**, so a cafe that
happens to hand out `192.168.2.x` addresses would match too. Both services demand a
password, so it is not an open door — but it is why SSH should move to key-only.

---

## Encrypted DNS

Every website you visit starts by asking "what is the address for this name?". That
question used to go to the Bell router in plain text. It now goes to Quad9 inside an
encrypted connection.

**It is set to `opportunistic`, not strict, on purpose.** Strict encryption refuses to fall
back — and a hotel or airport wifi *has* to intercept that question to show you its login
page. Strict mode there means no internet and no way to log in, at a gate, with a flight
boarding. Opportunistic encrypts whenever it can and steps aside when it genuinely cannot.

**It is also only forced on the home wifi.** An earlier attempt applied it to every network
at once; that was removed for the same captive-portal reason. Unknown networks behave
completely normally.

To check it at any time:

```bash
resolvectl query github.com | tail -2
# "...encrypted transport: yes"  = working

sudo ss -tnp | grep 853
# a live connection to 9.9.9.9:853 owned by systemd-resolve
```

If you are ever at a hotel and the login page will not load, this is the first thing to
suspend:

```bash
sudo mv /etc/systemd/resolved.conf.d/luminos-dot.conf /tmp/ && sudo systemctl restart systemd-resolved
```

---

## Two things still open, because they are your call

**1. SSH password login is still on.** The server refuses passwords and only accepts keys.
This laptop cannot do that yet, because **there is no `~/.ssh/authorized_keys` file on it** —
switching now would lock out remote SSH entirely. The firewall has narrowed `:22` to the
home network and the tailnet, which shrinks the problem but does not close it.

Options, cheapest first:
- Stop `sshd` altogether if you never SSH *into* the laptop: `sudo systemctl disable --now sshd`
- Or install a key first, test it, then turn passwords off.

**2. 213 pending package updates.** Every one of those is potentially a fixed security bug.
But installing them means a full `pacman -Syu`, which pulls **kirigami 6.28 → 6.29** and
**silently reverts the desktop look** you had built (DECISION 72). The security argument and
the desktop argument genuinely point in opposite directions, so this is not something to do
as a side effect of another task.

---

## Undoing all of it

```bash
# firewall off
sudo systemctl disable --now nftables && sudo nft delete table inet luminos

# encrypted DNS off
sudo rm /etc/systemd/resolved.conf.d/luminos-dot.conf && sudo systemctl restart systemd-resolved

# restore the wifi profiles exactly as they were
sudo cp -a /root/nm-profiles-backup-20260831/. /etc/NetworkManager/system-connections/ \
  && sudo nmcli con reload && sudo nmcli con up "BELL851 2.4 GHz"
```

The pre-change firewall snapshot is at `/root/nft-before-20260831.rules`.

---

## Related

- `LUMINOS_DECISIONS.md` — DECISION 88 (this), 85 (tailnet), 72 (the kirigami trap)
- `server/DECISIONS.md` — DECISION 48/51/84, the server's hardening pass
- `config/nftables-g14.conf`, `config/resolved-dot-g14.conf` — the actual files
