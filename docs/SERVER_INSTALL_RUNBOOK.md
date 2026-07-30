# Media Server Install Runbook
# [CHANGE: claude-code | 2026-07-30]
#
# STATUS: Phases 1-7 are DONE on the real machine (Dell Inspiron 3590).
# It is installed, headless, and reachable at 192.168.2.61 as `shawn`.
# Live next step is Phase 8. Everything above it is kept as the record of how,
# and as the recipe for the next box.

Step-by-step, from your friend's Windows desktop to a working headless Jellyfin
server. Follow it in order. Anything marked **YOU** needs hands on the Dell;
everything else is driven over SSH from the G14.

Design summary, so you know what you're agreeing to:

- Arch goes **entirely on the HDD**, including its own EFI partition. The SSD
  with the owner's Windows is never opened for writing.
- Two **independent** bootloaders. Nothing shared, so nothing our side can
  corrupt on his side.
- Headless. No desktop. Administered over SSH with a key.
- WiFi only (no ethernet in use). All three Bell SSIDs are seeded so it connects
  to whichever is in range.

### Machine facts worth knowing before you start

- **Dell Inspiron 3590.** InsydeH2O text BIOS — see Phase 2.
- **The battery is removed and bypassed. It runs on AC only.** There is no
  ride-through. A tripped breaker, a tugged cord, or a power cut is a hard
  power-off mid-write, every time. This is why the install runs inside `tmux`
  and why the boot order is fixed *before* the first reboot rather than after.
- Target disk: `/dev/sda`, 931.5 GiB WDC WD10SPZX-75Z10T3 (the spinning one).
- The NVMe SSD holding Windows is **invisible to Linux** because the BIOS is in
  Intel RST `RAID On` mode. Windows is unharmable by construction, not by care.
- WiFi MAC `18:47:3d:f3:22:25`. DHCP gave `.60` under the ISO and `.61` once
  installed — different DHCP client identifiers, not a fault. Set a router
  reservation if you want it pinned; mDNS (`luminos-server.local`) is seeded as
  a fallback either way.

---

## Already done — nothing to do here

| Thing | State |
|---|---|
| Arch ISO | Downloaded, sha256 + GPG verified |
| USB stick | Written and **byte-verified** by reading it back (`e86295dc…a6c0`) |
| SSH keypair | `~/.ssh/luminos-server` on the G14 |
| Stage 1 installer | `scripts/luminos-server-install` — **run for real, 17/17 checks passed** |
| Stage 2 services | `scripts/luminos-server-services`, dry-run tested — not yet run |
| BitLocker | Confirmed off on both disks |
| Secure Boot | Confirmed off |
| Base OS on the Dell | **Installed and booting from the HDD** |
| Headless reconnect | **Proven** — rebooted with nobody at the keyboard, rejoined `BELL851 5.0 GHz` at −35 dBm, came back as `192.168.2.61` |
| WiFi passphrases | Read from the G14's saved networks; never printed anywhere |

Verified against the real ISO image (not assumed):

- `sshd.service` **starts automatically** on the ISO.
- `/etc/ssh/sshd_config.d/10-archiso.conf` sets `PermitRootLogin yes` and
  `PasswordAuthentication yes`.
- Root's password field is **empty**, and sshd rejects empty passwords — which
  is exactly why `passwd` in Phase 3 is not optional.
- `iwd.service` starts automatically and `iwctl` is present.
- `systemd-networkd` runs `20-wlan.network` with `DHCP=yes`, so once WiFi
  associates the address arrives on its own. Nothing else to start.

---

## Phase 1 — Windows, one last time · **YOU**

Skip if the machine is already off and you never booted Windows.

```
shutdown /s /t 0
```

**Not** "Restart", and not sleep. Windows' Fast Startup hibernates the kernel and
leaves filesystems in a half-mounted state; a real shutdown avoids it.

---

## Phase 2 — BIOS · **YOU**

Power on, tap **`F2`** at the Dell logo.

> **The Inspiron 3590 uses InsydeH2O**, a plain text BIOS with tabs across the
> top (`Main` `Advanced` `Security` `Boot` `Exit`) — *not* the graphical Dell
> setup with a left-hand tree. An earlier draft of this runbook described the
> graphical one and sent the owner hunting for settings that do not exist on his
> machine. If you see a mouse cursor and a category tree, you have the other
> BIOS and the labels below will differ.

On InsydeH2O, everything you need is on the **`Boot`** tab:

| Setting | Set to | Note |
|---|---|---|
| `Boot List Option` / `Boot Mode` | **UEFI** | not `Legacy` |
| `Secure Boot` | **Disabled** | may live under `Security`; greyed out until you set a Supervisor Password on some builds |
| `USB Boot Support` / `USB Boot` | **Enabled** | absent on some 3590 builds — that's fine, it's on by default |
| `Fastboot` | **Thorough** | optional; `Minimal` can skip USB enumeration entirely |

> **Change nothing else. In particular do NOT touch `SATA Operation`.** If it
> says `RAID On`, leave it. Windows was installed against the Intel RST driver
> and will not start without it. Linux reads the HDD either way.

Exit saving changes (`Exit` tab → `Exit Saving Changes`, or `F10`).

### If the USB stick still isn't in the `F12` menu

Work down this list. Each step rules something out.

1. **Is it a UEFI stick at all?** Ask me — I can mount its EFI partition from the
   G14 and tell you in seconds whether `\EFI\BOOT\BOOTX64.EFI` is present. Don't
   rewrite the stick on a hunch; we proved ours was fine and saved an hour.
2. **Try the other physical port.** The 3590 has USB 2.0 and USB 3.0 ports, and
   some BIOS builds enumerate only one of them early enough.
3. **Look for it under `Boot` → `UEFI Boot Path Security`** — if set to
   `Always`, it demands a password before booting any removable device.
4. **The escape hatch: point the firmware at the file yourself.**
   `F2` → `Boot` tab → **`Add Boot Option`** / `File Browser Add Boot Option` →
   pick the USB volume → navigate `EFI` → `BOOT` → `BOOTX64.EFI`, give it any
   name, save, then move it to the top of the boot order. This bypasses
   auto-detection completely and works even when the stick never appears in
   `F12`.

---

## Phase 3 — Boot the stick and hand me the keys · **YOU**

Plug the USB in. Power on, tap **`F12`**, pick the USB device (it may be named
after the stick, e.g. "SanDisk"). Choose the first entry, *Arch Linux install
medium (x86_64, UEFI)*.

You land at a root prompt. Three things, in this order.

**1. Get on WiFi.**

```
iwctl
```

Then inside the `[iwd]#` prompt:

```
device list
```

Note the device name in the first column — usually `wlan0`, sometimes `wlp2s0`.
Use it below.

```
station wlan0 scan
station wlan0 get-networks
station wlan0 connect "BELL851 2.4 GHz"
```

It asks for the passphrase. Type it — it is not echoed and not logged. Use
whichever band's password you actually remember; this stage only downloads
packages, so the band doesn't matter. Then:

```
exit
```

Check it worked:

```
ping -c3 archlinux.org
```

If you get replies, the address already arrived. You do **not** need to start
anything else.

**2. Give me a way in.** Root has no password, and SSH refuses empty passwords:

```
passwd
```

Type any short throwaway password twice. This whole environment is erased at the
end of the install, so it does not need to be good.

**3. Tell me where it is.**

```
ip -4 addr show scope global
```

**Send me: the IP address, and that throwaway password.** That's the end of your
part until Phase 6.

---

## Phase 4 — Confirm the disk before anything is written

From the G14. Nothing destructive happens in this phase.

```bash
IP=192.168.2.xxx        # the address from Phase 3

ssh root@$IP 'lsblk -o NAME,SIZE,ROTA,RM,TRAN,TYPE,MODEL'
```

`ROTA=1` marks the spinning disk. There must be **exactly one** disk with
`ROTA=1`, `RM=0`, and `TYPE=disk`. That is the install target.

> **If no disk shows `ROTA=1`, stop.** The HDD is not visible to Linux, probably
> hidden behind Intel RST. Do not "fix" it by switching to AHCI — that breaks
> Windows. Come back and we'll work out the real cause.

> **If two disks show `ROTA=1`, stop.** The installer will refuse anyway rather
> than guess, which is the point.

---

## Phase 5 — Install the base system

Copy the installer, the SSH key and the WiFi credentials over:

```bash
# Rebuild the credentials file (nothing is stored between sessions).
# Passphrases go straight from NetworkManager into a 0600 file in RAM.
umask 077
CREDS=$(mktemp /dev/shm/luminos-wifi.XXXXXX)
for p in "BELL851 5.0 GHz" "BELL851 2.4 GHz" "BELL851"; do
  s=$(nmcli -g 802-11-wireless.ssid connection show "$p")
  k=$(nmcli -s -g 802-11-wireless-security.psk connection show "$p")
  [ -n "$s" ] && [ -n "$k" ] && printf '%s\t%s\n' "$s" "$k" >> "$CREDS"
done

scp ~/luminos-os/scripts/luminos-server-install \
    ~/.ssh/luminos-server.pub \
    "$CREDS" \
    root@$IP:/root/
```

Dry run first — this writes nothing:

```bash
ssh root@$IP
# now on the ISO:
cd /root
./luminos-server-install --dry-run \
  --confirm-disk /dev/sdX \
  --wifi-creds /root/luminos-wifi.* \
  --key "$(cat /root/luminos-server.pub)"
```

Read the output. It prints the exact partition layout, names every disk it will
**not** touch, and lists the WiFi networks it will seed. It also refuses outright
if the machine would have no network after reboot.

When that all looks right, swap `--dry-run` for `--yes`:

```bash
./luminos-server-install --yes \
  --confirm-disk /dev/sdX \
  --wifi-creds /root/luminos-wifi.* \
  --key "$(cat /root/luminos-server.pub)"
```

It partitions, formats, `pacstrap`s the base system (the slow part — it is
writing to a spinning disk), configures the network, creates your user, installs
the bootloader on the **HDD's own** ESP, and finishes with ~16 assertions.

> **If any assertion FAILS, do not reboot.** The script says so too. Send me the
> failures. A machine that fails these is not bootable and rebooting only makes
> it harder to see why.

Then:

```bash
rm -f /root/luminos-wifi.*     # don't leave passphrases on the ISO
umount -R /mnt
reboot
```

Also clean up the G14 side:

```bash
shred -u "$CREDS"
```

---

## Phase 6 — Pull the stick · **YOU**

As it reboots, **remove the USB stick.** If you leave it in, it may boot the
installer again instead of the new system.

Nothing will appear on screen worth watching — it is headless by design. Give it
a minute to associate with WiFi.

---

## Phase 7 — Find it and log in

On this machine it came up at **`192.168.2.61`**. From the G14:

```bash
ssh -i ~/.ssh/luminos-server shawn@192.168.2.61
# or by name, via mDNS:
ssh -i ~/.ssh/luminos-server shawn@luminos-server.local
```

If neither works, sweep the subnet — `nmap` and `arp-scan` are not installed on
the G14 and you don't need them:

```bash
for i in $(seq 1 254); do ping -c1 -W1 192.168.2.$i >/dev/null 2>&1 & done; wait
ip neigh | sort -t. -k4 -n
```

The address can move between the ISO and the installed system (it went `.60` →
`.61` here) because the DHCP client identifier differs. That is expected.

No password — the key is the only accepted credential, and root login over SSH
is disabled.

**Give it a DHCP reservation** on the Bell Home Hub now, so the address stops
moving. That is the single thing that makes everything afterwards easier.

---

## Phase 8 — Install the services

From the G14:

```bash
scp ~/luminos-os/scripts/luminos-server-services \
    ~/luminos-os/scripts/luminos-media-import \
    ~/luminos-os/scripts/luminos-servarr-health \
    shawn@$SERVER:/tmp/

ssh shawn@$SERVER
sudo /tmp/luminos-server-services --dry-run --scripts-dir /tmp
sudo /tmp/luminos-server-services --yes      --scripts-dir /tmp
```

This installs Jellyfin, `qbittorrent-nox`, Sonarr and Prowlarr, builds the
`media` group and `/srv/media` layout, installs the update guard, and then
**proves** the permissions work by writing a file as `sonarr` and reading it back
as `jellyfin`. It prints what the Intel chip actually reports for hardware video
decoding rather than assuming.

At the end it prints the four web addresses. Change the qBittorrent password
straight away — it regenerates on every restart until you do.

---

## Phase 9 — Move the library over, don't rebuild it

Stop the services on **both** machines first, or you will copy a database
mid-write and get a corrupt library:

```bash
# on the G14
sudo systemctl stop jellyfin sonarr prowlarr
# on the server
ssh shawn@$SERVER 'sudo systemctl stop jellyfin sonarr prowlarr'
```

Then copy state — this carries your users, watch history, artwork, series list
and indexers, so none of it gets set up by hand again:

```bash
sudo rsync -aHAX --info=progress2 /var/lib/jellyfin/  shawn@$SERVER:/tmp/jellyfin/
sudo rsync -aHAX --info=progress2 /var/lib/sonarr/    shawn@$SERVER:/tmp/sonarr/
sudo rsync -aHAX --info=progress2 /var/lib/prowlarr/  shawn@$SERVER:/tmp/prowlarr/
sudo rsync -aHAX               /etc/jellyfin/         shawn@$SERVER:/tmp/etc-jellyfin/
```

On the server, move into place and fix ownership — the user IDs are not
guaranteed to match between the two machines:

```bash
for s in jellyfin sonarr prowlarr; do
  sudo rsync -aHAX --delete "/tmp/$s/" "/var/lib/$s/"
  sudo chown -R "$s:$s" "/var/lib/$s"
done
sudo rsync -aHAX /tmp/etc-jellyfin/ /etc/jellyfin/
sudo chown -R jellyfin:jellyfin /etc/jellyfin
sudo systemctl start jellyfin sonarr prowlarr
```

Then in Jellyfin, **repoint the libraries** at the server's paths. The media
files themselves are a separate, much larger copy — do that once the rest works.

---

## Phase 10 — Boot order · *now automatic, verify only*

The installer sets this itself. **It did not, the first time, and that was a
real bug** — worth reading, because the failure is silent:

`bootctl install` exited 0 and wrote every file correctly to the ESP, while
creating **no firmware boot entry at all**. No error, no warning. The firmware
then fell through to Dell's pre-existing `Boot0000 "UEFI Hard Drive"`, which
points at *Windows'* EFI partition GUID. A headless box that quietly boots
Windows looks exactly like a dead one from the far end of an SSH session.

The installer now finds or creates the entry with `efibootmgr` and forces it to
the front of `BootOrder`, and stage-1 verification fails if either isn't true.
Checking that the loader *files* exist — which is all it used to do — proves
nothing about what the firmware will actually try.

Confirm from the G14, no keyboard needed:

```bash
ssh shawn@$SERVER 'sudo efibootmgr | head -3'
```

The first ID in `BootOrder:` must be the `Luminos Server` entry.

Why it has to be first: it is a headless machine on **AC power with no
battery**, so any power blip is a cold boot. If that lands in Windows it sits at
a login screen with no SSH and someone has to walk over. Windows becomes the
thing you pick deliberately with `F12`.

Accepted consequence: **while Windows is running, the media server is offline.**

---

## Phase 11 — Final checks

```bash
ssh shawn@$SERVER 'luminos-servarr-health'
```

Then play something on the Roku and watch Jellyfin's Dashboard → Activity. It
must say **Direct Play**. If it says Transcode, the whole cheap-hardware premise
is void and the file needs looking at — see `MEDIA_SERVER_PLAN.md` §2 for what
this TV can and cannot take.

---

## Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| Stick not listed under `F12` | Secure Boot on, Legacy boot mode, or the BIOS just won't enumerate it | Phase 2 → work down the numbered list; `Add Boot Option` is the guaranteed way |
| Boots straight into Windows after install | No firmware entry, or Windows ordered first | `sudo efibootmgr -v` — see Phase 10. This was a real bug, now fixed and verified |
| Logged in over SSH but `sudo` asks for a password you never set | Admin account has no password and the `%wheel` rule demands one — total lockout | Fixed: installer writes a NOPASSWD drop-in and *functionally tests* it with `sudo -l -U`. On an older build, boot the ISO and add it by hand |
| WiFi connects by hand but never at boot | `iwd` ignored the credential file because the filename wasn't hex-encoded | An SSID containing a `.` (e.g. `BELL851 5.0 GHz`) **must** be stored as `=<hex>.psk`. Fixed in the installer; verify with `ls /var/lib/iwd` |
| `iwctl` → `device list` shows nothing | WiFi firmware not loaded | `dmesg \| grep -i firmware` — send me the output |
| WiFi connects, `ping` fails | DHCP didn't complete | `networkctl status` — should say `routable` |
| `ssh root@…` rejects the password | `passwd` wasn't run | Run `passwd` on the ISO |
| "no non-removable rotational disk found" | HDD invisible to Linux (likely Intel RST) | **Stop.** Do not switch to AHCI. Send me `lsblk` + `dmesg \| tail -40` |
| ">1 candidate disk" | Two spinning disks | Stop. The script won't guess and neither should we |
| Assertions FAIL at the end of stage 1 | Various | **Don't reboot.** Send me the failing lines |
| Can't find the box after reboot | WiFi didn't come up | Needs a monitor. `journalctl -u iwd` will say why |
| Jellyfin plays nothing on the Roku | Wrong codec, not a server fault | `MEDIA_SERVER_PLAN.md` §2 — AV1, DTS/TrueHD and PGS subs are the usual culprits |

---

## If you want to give the laptop back

Because we never touched the SSD or Windows' bootloader, undoing this is clean:

1. Boot Windows (`F12` → Windows Boot Manager).
2. `diskmgmt.msc` → delete the three partitions on the HDD → make one NTFS
   volume if he wants the space back.
3. `F2` → remove the "Luminos Server" boot entry if it's listed, and set Windows
   first in the boot order.
4. `F2` → **re-enable Secure Boot**. Do this one if he plays anything with
   kernel anti-cheat (Valorant, Fortnite, recent Battlefield) — those refuse to
   launch on Windows 11 without it.

There is no bootloader repair step, because there was never a shared bootloader.
That was the point of giving the HDD its own EFI partition.
