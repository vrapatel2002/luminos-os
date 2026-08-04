# ESCAPE CARD — read this when the desktop will not come back
# [CHANGE: claude-code | 2026-08-04]

**Print this or photograph it before starting Phase 2.** If the graphical session
is broken you cannot open a browser, and a card you can only read on the broken
machine is not a card.

---

## 0. First, do not panic and do not reinstall

Nothing done during the Hyprland work touches your data. `/home/shawn` (244 GB),
`/srv/media` (82 GB) and your git repo were **not** modified by any of it. The
worst realistic case is "the login screen only offers a session that does not
start", and that is recoverable from a text console in a few minutes.

---

## 1. Get a text console

    Ctrl + Alt + F3

Log in with your normal username and password. This works even when Wayland,
KDE, Hyprland and SDDM are all completely broken. `F3` through `F6` are all
free consoles; `F1`/`F2` are usually where the graphical session lives.

If the screen is black but the machine is alive, try `Ctrl+Alt+F3` first before
holding the power button.

---

## 2. Get the agent back

The Claude **CLI** is installed independently of the desktop app:

    /usr/bin/claude          (v2.1.101)

So even with no GUI at all:

    cd ~/luminos-os
    claude

The agent reads `HANDOFF.md` and knows where it left off. The desktop app dying
does not lose the thread — `HANDOFF.md` is the thread.

---

## 3. Tell it what happened without having to remember

Every graphical login writes a black-box record automatically
(systemd user unit `luminos-session-recorder.service`):

    ~/luminos-os/scripts/luminos-session-recorder --show

That prints the most recent record: which session started, the systemd-logind
login/logout ledger, errors, coredumps, Hyprland's own log, the five Go daemons,
dGPU power state, disk space, and the last 15 pacman transactions.

All records are kept here:

    ~/luminos-backups/session-log/

Say **"resume"** to the agent and point it at that directory. You do not have to
describe the failure from memory.

---

## 4. Just get me back into KDE Plasma

At the SDDM login screen there is a **session picker** (usually a small menu in
a corner, or press `F1`). Choose **Plasma (Wayland)** and log in. Hyprland is
being installed as an *additional* session; Plasma is untouched and remains the
default.

If SDDM itself will not start:

    sudo systemctl restart sddm

If a broken Hyprland session file is confusing the login screen, remove it —
Plasma comes back immediately:

    sudo rm -f /usr/share/wayland-sessions/hyprland.desktop
    sudo rm -f /usr/local/share/wayland-sessions/hyprland.desktop
    sudo systemctl restart sddm

(Note: SDDM reads **both** `/usr/share/wayland-sessions/` and
`/usr/local/share/wayland-sessions/`. Check both.)

---

## 5. Undo a bad system upgrade

### 5a. Roll the whole OS back (Timeshift)

Baseline snapshot taken immediately before this work:

    2026-08-04_14-35-50      ("PRE-HYPRLAND baseline")
    previous good snapshot:  2026-07-21_18-48-09

List and restore:

    sudo timeshift --list
    sudo timeshift --restore --snapshot '2026-08-04_14-35-50'

**What this does and does not cover.** The snapshot contains `/etc`, `/usr`,
`/var`, `/boot` and `/opt/luminos` — the operating system. It deliberately does
**not** contain `/home/shawn`, `/srv/media`, `/opt/rocm`, `/opt/cuda` or the
pacman cache, because those are bulk data, they are 150 GB+, and including them
overflowed the disk. Restoring therefore rolls back the OS and **leaves all your
files and configs exactly as they are**.

Because `/home` is not in the snapshot, restoring will *not* undo a bad
`~/.config`. For that, see 5c.

### 5b. Downgrade individual packages (no full restore)

There are ~760 cached package versions (12 GB) in `/var/cache/pacman/pkg`, and
the cache is *excluded* from the snapshot so a restore cannot wipe it.

    ls /var/cache/pacman/pkg | grep -i <packagename>
    sudo pacman -U /var/cache/pacman/pkg/<exact-file>.pkg.tar.zst

The exact version of every package as it was before this work:

    ~/luminos-os/backups/preflight-2026-08-04/pkgs-all-with-versions.txt

### 5c. Restore config from the pre-flight tarballs

    ls ~/luminos-backups/preflight-2026-08-04/
      etc-2026-08-04.tar.gz                (3.4M — all of /etc)
      config-2026-08-04.tar.gz             (11M  — all of ~/.config)
      localshare-desktop-2026-08-04.tar.gz (3.4M — ~/.local/share desktop dirs)

Look inside first, never extract blind:

    tar tzf ~/luminos-backups/preflight-2026-08-04/config-2026-08-04.tar.gz | less

Pull back one thing (example: KDE's global config):

    cd /
    tar xzf ~/luminos-backups/preflight-2026-08-04/config-2026-08-04.tar.gz \
        home/shawn/.config/kdeglobals

These tarballs contain wifi passwords and tokens, so they live in
`~/luminos-backups/` and are deliberately **NOT** in the git repo, which is
public.

---

## 6. Recover the source from git

    git clone --recurse-submodules git@github.com:vrapatel2002/luminos-os.git

`--recurse-submodules` matters. The repo has 8 submodules; before 2026-08-04
there was no `.gitmodules` file, so a plain clone produced 8 empty directories
with no error at all. That is fixed, but only a recursive clone pulls the
content. In an existing clone:

    git submodule update --init --recursive

---

## 7. If the disk is full

A full root filesystem breaks logins, truncates files mid-write and makes pacman
fail halfway through a transaction. It presents as random unexplainable
breakage. Check it first:

    df -h /

If it is at 100%, the usual culprits are snapshots and the package cache:

    sudo timeshift --list                 # delete an old snapshot if needed
    sudo pacman -Sc                       # clears old cached packages
    du -x -h -d1 / | sort -rh | head      # find the real hog

---

## 8. The one-line summary

Plasma still works, your files are untouched, the CLI agent still runs from a
text console, and there is a snapshot from just before any of this started.
There is no situation here that requires reinstalling the OS.
