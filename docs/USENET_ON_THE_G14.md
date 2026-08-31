# Usenet on the G14 — downloading without the server
# [CHANGE: claude-code | 2026-08-31]

The media server is a Dell 3590 on a thin cable, and a nudge takes it offline. This
page is the fallback: how to turn a `.nzb` file into a movie **on this laptop**, with
the server switched off entirely.

---

## The one idea that makes Usenet make sense

> Think of it like a torrent file. Downloading the `.torrent` doesn't give you the
> movie until you open it in software like qBittorrent. For Usenet, you need a
> dedicated Usenet download client and a Usenet provider subscription to turn that
> `.nzb` into an actual file.

That is exactly right, and it is the thing that trips everyone up. **An `.nzb` is a
shopping list, not the shopping.** It is a small text file — usually well under a
megabyte — that says "the movie is split into 4,000 numbered pieces, and here are
their names." Opening it in a text editor shows you a wall of IDs and nothing
watchable.

So you always need **two separate things**, and they come from **two different
companies**:

| You need | What it is | Ours |
|---|---|---|
| **An indexer** | The search engine. Gives you the `.nzb` shopping list. | NZBGeek (paid) |
| **A provider** | The warehouse. Actually holds the pieces. | UsenetServer (paid) |
| **A client** | The software that reads the list and fetches the pieces. | **NZBGet — now installed here** |

The torrent world blurs these: a tracker search and the swarm feel like one thing.
Usenet keeps them strictly apart. Paying an indexer gets you **zero** bytes of movie.
Paying a provider gets you **zero** ability to find anything. You need both.

**Why the client is not optional:** the file arrives as thousands of fragments,
encoded in a 1980s text format called yEnc, usually inside a `.rar` archive, with
extra `.par2` repair blocks in case some fragments have rotted off the servers.
NZBGet downloads all of it, decodes it, checks it, repairs anything missing from the
par2 blocks, unpacks the rar, and hands you one playable file. Doing that by hand is
not realistic.

---

## What is installed here, and where

| Thing | Value |
|---|---|
| Client | NZBGet **26.2** (`extra/nzbget`, native package — no Docker) |
| Config | `~/.config/nzbget/nzbget.conf` (mode 600 — it holds the provider password) |
| Service | `systemctl --user status luminos-nzbget` |
| Web UI | **http://127.0.0.1:6789/** — loopback only |
| Login | user `shawn` — password is in the config file, see below |
| Watched folder | `~/Downloads/usenet/nzb/` |
| Finished files | `~/Downloads/usenet/completed/` |
| Provider | UsenetServer, NNTP over TLS on port 563, **8 connections** |

To read the web-UI password back at any time:

```bash
grep '^ControlPassword=' ~/.config/nzbget/nzbget.conf
```

---

## Actually downloading something

### The short way — drop the file in a folder

1. Search **NZBGeek** in a browser, click the download button on a result. You get a
   `.nzb` file in `~/Downloads`.
2. Move it into the watched folder:
   ```bash
   mv ~/Downloads/*.nzb ~/Downloads/usenet/nzb/
   ```
3. That is it. NZBGet checks that folder every 5 seconds, picks the file up, and
   starts. The finished movie lands in `~/Downloads/usenet/completed/`.

There is no step 4. The watched folder exists precisely so you never have to remember
a command or open a UI.

### The visible way — watch it happen

Open **http://127.0.0.1:6789/**, log in, and drag the `.nzb` onto the page. Same
result, but you get the progress bar, the speed, and a pause button. Useful the first
few times, so the process stops feeling like a black box.

### If a download fails

Look at the **History** tab. The three things that actually go wrong:

- **"Par-check failed / not enough blocks"** — the post is too old and pieces have
  been deleted from the provider's servers. Nothing to fix. Grab a different release.
- **"Unpack failed: password required"** — some releases are password-protected;
  the indexer page usually lists the password. Put it in the item's settings.
- **Nothing downloads, 0 connections** — the provider login failed. Re-run the test
  in the next section.

---

## Proving it works (before you are on a plane and it is too late)

Test the provider login without downloading anything:

```bash
python3 - <<'PY'
import os, re, socket, ssl
c = dict(re.match(r"^([\w.]+)=(.*)$", l.rstrip()).groups()
         for l in open(os.path.expanduser("~/.config/nzbget/nzbget.conf"))
         if re.match(r"^[\w.]+=", l))
ctx = ssl.create_default_context()
with socket.create_connection((c["Server1.Host"], int(c["Server1.Port"])), 20) as raw:
    with ctx.wrap_socket(raw, server_hostname=c["Server1.Host"]) as s:
        f = s.makefile("rb"); print(f.readline().decode().strip())
        s.sendall(f"AUTHINFO USER {c['Server1.Username']}\r\n".encode()); f.readline()
        s.sendall(f"AUTHINFO PASS {c['Server1.Password']}\r\n".encode())
        print(f.readline().decode().strip())
PY
```

**`281 Welcome to UsenetServer (No Posting)` means it works.** `502 Authentication
Failed` means the password is wrong. "No Posting" is not an error — the account is
deliberately read-only, so it is incapable of uploading anything.

---

## Things that will bite

**The disk is the real limit, not the speed.** `/home` was 90% full when this was set
up — 61 GB free. A single 4K remux can be 100 GB. NZBGet is configured with
`DiskSpace=20000`, so it **pauses** when free space drops under 20 GB rather than
filling the disk. That guard is there because Timeshift once filled this root to
literally zero bytes and truncated a file. Do not remove it; raise it if anything.

**Do not enable the packaged `nzbget.service`.** Arch ships a *system* unit that runs
as the `nzbget` user and wants root-owned directories. Ours is a `--user` unit. Two
instances would fight over port 6789. Check with `systemctl is-enabled nzbget` — it
should say `disabled`.

**nzbget is pinned to an older package build, on purpose.** `nzbget 26.2-3` in the
repos links `libboost_json.so.1.92`, but this machine has boost **1.91**, and
upgrading boost alone would break `gdb`, `innoextract`, `xrt` (the NPU runtime) and
`libtorrent-rasterbar`. So `26.2-2` from `archive.archlinux.org` is installed — the
**same upstream 26.2**, only an earlier package rebuild. A future full `pacman -Syu`
brings boost 1.92 along and makes the pin unnecessary; **that upgrade also bumps
kirigami 6.28 → 6.29, which silently reverts the desktop look**, so it is a deliberate
decision and not a routine one.

**The provider account is shared with the server.** The server uses 15 connections;
this laptop is set to 8, deliberately lower. The plan's total connection cap is not
known, so if both machines download hard at the same time you may see connection
refusals. In practice this laptop is the *fallback* for when the server is down, so
they rarely run together.

**Two clients, two queues.** Anything downloaded here lands in
`~/Downloads/usenet/completed/` and is invisible to Jellyfin, Sonarr and Radarr. It is
a plain file you play in mpv or VLC. Nothing gets renamed, sorted, or added to the
library. That is the trade for the server not being involved at all.

**Turning it off:**

```bash
systemctl --user disable --now luminos-nzbget    # stop it
sudo pacman -Rns nzbget                          # remove it entirely
```

---

## Related

- `LUMINOS_DECISIONS.md` — DECISION 87 (this), DECISION 48 (Usenet chosen over torrents)
- `server/DECISIONS.md` — DECISION 48/84 for the server-side pipeline
- `server/README.md` — the full server pipeline, if it *is* reachable
