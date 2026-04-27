# Luminos OS — Bug Tracker
Last Updated: 2026-03-29

## Format
Each bug entry:
### BUG-XXX — Short title
- Status: OPEN / FIXED / WONTFIX
- Severity: CRITICAL / HIGH / MEDIUM / LOW
- Component: which file/module affected
- Description: what happens
- Root Cause: why it happens
- Fix Applied: what was changed
- Date Found: date
- Date Fixed: date

---

## Fixed Bugs

### BUG-043 — HIVE popup crash (import: command not found)
- Status: FIXED
- Severity: HIGH
- Component: /usr/local/bin/luminos-hive-popup
- Description: Pressing SUPER+SPACE to launch HIVE popup crashes with bash syntax errors like "import: command not found".
- Root Cause: An agent rewrote the popup script as a Python script using GTK4 (which is banned), but the global shortcut was executing it via `bash -x`.
- Fix Applied: Rewrote the script to a native bash script using `kdialog` for UI and `llama-cli` for inference, matching project rules.
- Date Found: 2026-04-26
- Date Fixed: 2026-04-26

### BUG-001 — build.log directory missing at start
- Status: FIXED
- Severity: HIGH
- Component: scripts/build_iso.sh
- Description: tee fails because build/ dir doesn't exist when LOG variable is defined
- Root Cause: mkdir -p $BUILD_DIR was missing
- Fix Applied: mkdir -p $BUILD_DIR added before LOG= line
- Date Found: 2026-03-23
- Date Fixed: 2026-03-23

### BUG-002 — cp copies directory into itself
- Status: FIXED
- Severity: HIGH
- Component: scripts/build_iso.sh stage2
- Description: cp -r . $CHROOT_DIR/luminos-build/ fails because build/ is subdir of current dir
- Root Cause: source and destination overlap
- Fix Applied: replaced with rsync --exclude=build
- Date Found: 2026-03-23
- Date Fixed: 2026-03-23

### BUG-003 — No apt sources in minimal chroot
- Status: FIXED
- Severity: CRITICAL
- Component: scripts/strip_ubuntu.sh
- Description: apt cant find packages in chroot
- Root Cause: debootstrap minimal has no universe repo configured
- Fix Applied: Added sources.list with all Ubuntu repos at top of strip script
- Date Found: 2026-03-23
- Date Fixed: 2026-03-23

### BUG-004 — fuser -km crashes the OS
- Status: FIXED
- Severity: CRITICAL
- Component: scripts/build_iso.sh safe_cleanup
- Description: fuser -km kills display server and systemd causing full system crash
- Root Cause: fuser -km kills ALL processes using any file under the path including critical system processes
- Fix Applied: Removed fuser -km, replaced with sleep 5
- Date Found: 2026-03-24
- Date Fixed: 2026-03-24

### BUG-005 — Stage order wrong squashfs vs cleanup
- Status: FIXED
- Severity: HIGH
- Component: scripts/build_iso.sh main block
- Description: stage6_cleanup deleted chroot before stage7_squashfs could read it
- Root Cause: stages in wrong order
- Fix Applied: Reordered to stage7 before stage6
- Date Found: 2026-03-24
- Date Fixed: 2026-03-24

### BUG-006 — meson option typo
- Status: FIXED
- Severity: MEDIUM
- Component: scripts/strip_ubuntu.sh
- Description: -Dexample=false fails on newer gtk4-layer-shell versions
- Root Cause: option renamed to -Dexamples=false
- Fix Applied: Fixed typo
- Date Found: 2026-03-24
- Date Fixed: 2026-03-24

### BUG-007 — requirements.txt wrong path
- Status: FIXED
- Severity: HIGH
- Component: scripts/install_luminos.sh
- Description: pip3 install fails, file not found at /opt/luminos/requirements.txt
- Root Cause: pip runs before files are copied to /opt/luminos/
- Fix Applied: Changed path to /luminos-build/requirements.txt
- Date Found: 2026-03-24
- Date Fixed: 2026-03-24

### BUG-008 — typing-extensions conflict
- Status: FIXED
- Severity: MEDIUM
- Component: scripts/install_luminos.sh
- Description: pip fails on typing-extensions installed by debian
- Root Cause: debian-installed packages have no RECORD file, pip cant uninstall
- Fix Applied: Added --ignore-installed flag
- Date Found: 2026-03-25
- Date Fixed: 2026-03-25

### BUG-009 — Wine missing i386 architecture
- Status: FIXED
- Severity: HIGH
- Component: scripts/install_compatibility.sh
- Description: wine-stable uninstallable, wine-stable-i386 not available
- Root Cause: 32-bit architecture not enabled
- Fix Applied: Added dpkg --add-architecture i386 before Wine install
- Date Found: 2026-03-25
- Date Fixed: 2026-03-25

### BUG-010 — proc virtual files block rm -rf
- Status: FIXED
- Severity: CRITICAL
- Component: scripts/build_iso.sh safe_cleanup
- Description: rm -rf $CHROOT_DIR fails on /proc/PID/* kernel virtual files
- Root Cause: mount --bind /proc inside chroot creates kernel virtual files that cannot be deleted with rm -rf. umount fails if any process still running inside chroot.
- Fix Applied: lsof-based process killer + proc-aware find deletion (skip proc/sys/dev, rmdir after unmount)
- Date Found: 2026-03-25
- Date Fixed: 2026-03-25

### BUG-011 — wine-gecko and wine-mono not in apt
- Status: FIXED
- Severity: MEDIUM
- Component: scripts/install_compatibility.sh
- Description: apt install wine-gecko wine-mono fails — packages not in Ubuntu repos
- Root Cause: gecko and mono are distributed by WineHQ directly, not through apt
- Fix Applied: wget from dl.winehq.org directly to /usr/share/wine/gecko and mono dirs
- New Bugs Introduced: None — wget uses || true so build continues even if download fails. Wine works without gecko/mono for most apps, only needed for .NET and browser controls.
- Date Found: 2026-03-25
- Date Fixed: 2026-03-25

### BUG-012 — safe_cleanup cant clean proc at start
- Status: FIXED
- Severity: CRITICAL
- Component: scripts/build_iso.sh
- Description: rm -rf chroot at build start fails on /proc/* kernel virtual files
- Root Cause: Fundamental design error — cant rm -rf chroot that has proc mounted. lsof fix doesnt work because cleanup runs in same process tree as the chroot.
- Fix Applied: Removed rm -rf from build start. Only unmount at start, let debootstrap overwrite. Only delete chroot AFTER squashfs + ISO are complete. Added --keep-debootstrap-dir to reuse partial downloads on retry.
- New Bugs Introduced: Old chroot files may persist if debootstrap fails mid-run. Acceptable tradeoff — better than crashing.
- Date Found: 2026-03-25
- Date Fixed: 2026-03-25

### BUG-013 — update-desktop-database not found
- Status: FIXED
- Severity: MEDIUM
- Component: scripts/install_luminos.sh
- Description: update-desktop-database command missing in minimal chroot environment
- Root Cause: desktop-file-utils package not installed in chroot at that point
- Fix Applied: Added || true fallback so build continues without failing. Also added || true to systemctl, ldconfig in install_luminos.sh and strip_ubuntu.sh.
- New Bugs Introduced: None — desktop database will be rebuilt on first boot automatically
- Date Found: 2026-03-25
- Date Fixed: 2026-03-25

### BUG-014 — mksquashfs includes proc/sys/dev
- Status: FIXED
- Severity: HIGH
- Component: scripts/build_iso.sh stage7
- Description: mksquashfs tries to read kernel virtual files in /proc /sys /dev causing thousands of "Failed to read" errors
- Root Cause: No exclusions passed to mksquashfs
- Fix Applied: Added -e exclusions for proc sys dev run tmp
- New Bugs Introduced: None — these dirs are recreated automatically on every boot
- Date Found: 2026-03-25
- Date Fixed: 2026-03-25

### BUG-015 — debootstrap cache corruption
- Status: FIXED
- Severity: HIGH
- Component: scripts/build_iso.sh stage1
- Description: --keep-debootstrap-dir reuses corrupted partial downloads causing tar extraction failures
- Root Cause: Previous failed runs leave corrupted .deb files in debootstrap cache
- Fix Applied: Removed --keep-debootstrap-dir, added rm of debootstrap cache before each run
- Date Found: 2026-03-25
- Date Fixed: 2026-03-25

### BUG-016 — grub.cfg not found in Stage 8
- Status: FIXED
- Severity: HIGH
- Component: scripts/build_iso.sh stage8
- Description: cp build/grub.cfg fails, file not found
- Root Cause: grub.cfg path wrong or file missing from repo
- Fix Applied: Added inline grub.cfg generation as fallback if file not found
- Date Found: 2026-03-25
- Date Fixed: 2026-03-25

### BUG-017 — No kernel in chroot for Stage 8
- Status: FIXED
- Severity: CRITICAL
- Component: scripts/build_iso.sh
- Description: Stage 8 fails copying vmlinuz because no kernel installed in chroot
- Root Cause: linux-image-generic not installed during chroot setup stages
- Fix Applied: Added kernel + casper install in stage5, dynamic kernel file detection in stage8
- Date Found: 2026-03-25
- Date Fixed: 2026-03-25

### BUG-018 — debootstrap fails inside build script
- Status: WORKAROUND
- Severity: CRITICAL
- Component: scripts/build_iso.sh stage1
- Description: debootstrap always fails with tar extraction error when run from build script but works fine when run manually
- Root Cause: Unknown — likely environment variable or directory state issue inside the script context
- Fix Applied: Added SKIP_STAGE1=1 env var to skip Stage 1 when chroot already exists
- Date Found: 2026-03-25
- Date Fixed: 2026-03-25 (workaround)

### BUG-020 — useradd fails if user exists
- Status: FIXED
- Severity: MEDIUM
- Component: scripts/build_iso.sh stage5
- Description: useradd fails when luminos user already exists from previous run
- Root Cause: No check if user exists before creating
- Fix Applied: Added id check before useradd
- Date Found: 2026-03-25
- Date Fixed: 2026-03-25

### BUG-021 — lupin-casper removed in Ubuntu 24.04
- Status: FIXED
- Severity: MEDIUM
- Component: scripts/build_iso.sh stage5
- Description: lupin-casper package not found
- Root Cause: Package removed in Ubuntu 24.04
- Fix Applied: Removed lupin-casper and other obsolete packages from install list
- Date Found: 2026-03-25
- Date Fixed: 2026-03-25

### BUG-022 — casper can't mount squashfs on boot
- Status: FIXED
- Severity: CRITICAL
- Component: ISO boot / casper
- Description: casper finds squashfs but fails to mount it as root filesystem. Errors: "mounting /dev/nvme0n1p3 on /cdrom failed" and "/root/dev/console: no such file"
- Root Cause: Missing live-boot packages (live-boot, live-boot-initramfs-tools, live-config, live-config-systemd) and initrd not regenerated after casper install. Also missing /root directory structure and live-media-path GRUB parameter.
- Fix Applied: Added live-boot packages to stage5, regenerated initrd with update-initramfs -u -k all, created /root/{dev,proc,sys,run,tmp} and /cdrom directories, added live-media-path=/casper and toram to GRUB boot parameters
- Date Found: 2026-03-27
- Date Fixed: 2026-03-27

### BUG-023 — initrd missing live-boot hooks
- Status: FIXED
- Severity: CRITICAL
- Component: ISO build stage5
- Description: Kernel panic on boot, /root empty, /root/dev/console not found
- Root Cause: initrd generated before live-boot installed — no live filesystem hooks in initrd
- Fix Applied: Install live-boot first, create custom initramfs hook, force initrd regeneration with clean env, verify live modules present via lsinitramfs, copy fresh initrd to ISO casper folder
- Date Found: 2026-03-27
- Date Fixed: 2026-03-27

### BUG-024 — grub search command fails to find root device
- Status: FIXED
- Severity: HIGH
- Component: scripts/smart_build.sh stage8 grub.cfg
- Description: GRUB search --file command can fail to locate the ISO root device, preventing vmlinuz from loading
- Root Cause: search command relies on runtime device enumeration which is unreliable across BIOS/EFI/VM environments
- Fix Applied: Replaced search command with hardcoded set root=(cd0), removed loopback/gfxterm modules and toram parameter, simplified grub.cfg to minimal direct boot
- Date Found: 2026-03-27
- Date Fixed: 2026-03-27

### BUG-025 — GRUB embedded config ignores grub.cfg on ISO
- Status: FIXED
- Severity: CRITICAL
- Component: scripts/smart_build.sh stage8
- Description: GRUB loads and shows menu but every entry fails with "file '/casper/vmlinuz' not found". Manual boot from GRUB command line works fine.
- Root Cause: grub-mkstandalone embedded the full grub.cfg into the EFI binary's memdisk. GRUB's $prefix pointed to (memdisk)/boot/grub, so it never read the grub.cfg from the ISO filesystem.
- Fix Applied: Switched to grub-mkrescue which handles embedded config, boot images, and xorriso automatically. grub.cfg uses search --file to find boot device. Superseded by BUG-026 fix.
- Date Found: 2026-03-27
- Date Fixed: 2026-03-27

### BUG-026 — search_file.mod not found in grub-mkimage
- Status: FIXED
- Severity: HIGH
- Component: scripts/smart_build.sh stage8
- Description: grub-mkimage fails with "cannot open search_file.mod: No such file" when building BIOS boot image
- Root Cause: Wrong module name — Ubuntu 24.04 GRUB uses search_fs_file.mod, not search_file.mod. Manual grub-mkimage + grub-mkstandalone + xorriso approach was fragile and error-prone.
- Fix Applied: Replaced entire manual BIOS/EFI boot image pipeline with grub-mkrescue, which resolves all module names automatically, creates both BIOS and EFI boot images, and invokes xorriso correctly in one command. Modules pre-loaded: all_video boot cat chain configfile echo fat iso9660 linux loadenv normal part_gpt part_msdos reboot search search_label search_fs_file search_fs_uuid squash4 gfxterm png.
- Date Found: 2026-03-27
- Date Fixed: 2026-03-27

### BUG-027 — squashfs missing root filesystem mount point directories
- Status: FIXED
- Severity: CRITICAL
- Component: scripts/smart_build.sh stage7
- Description: casper mounts squashfs but /root/dev, /root/proc, /root/sys are missing. Boot fails with "mount: mounting /dev on /root/dev failed: No such file or directory" and "can't open /root/dev/console: no such file"
- Root Cause: mksquashfs -e "$CHROOT_DIR/dev" excluded the directories entirely from the squashfs — not even empty directory stubs survived. casper's /init needs /dev /proc /sys /run /tmp to exist as empty mount points inside the squashfs root.
- Fix Applied: Changed mksquashfs exclusions from -e "$CHROOT_DIR/dev" (excludes entire directory) to -wildcards -e "dev/*" (keeps empty directory stub, excludes only contents). Added explicit creation of /dev /proc /sys /run /tmp /root /cdrom directories and /etc/fstab before squashfs build.
- Date Found: 2026-03-27
- Date Fixed: 2026-03-27

### BUG-028 — GUI does not auto-start on boot
- Status: FIXED
- Severity: HIGH
- Component: ISO boot / sway config
- Description: User must manually type sway and launch GUI components after login
- Root Cause: No sway config, no auto-login, no session script
- Fix Applied: Auto-login on tty1 via getty override, .bash_profile starts sway on tty1, sway config auto-launches all Luminos GUI components (bar, dock, notifications, session)
- Date Found: 2026-03-27
- Date Fixed: 2026-03-27

### BUG-029 — Desktop has no visual styling
- Status: FIXED
- Severity: HIGH
- Component: Desktop environment
- Description: Raw Sway desktop with no wallpaper, no theme, Waybar unstyled, no app launcher styling
- Root Cause: No GTK theme, Waybar config, wofi config, or wallpaper configured in stage5
- Fix Applied: Catppuccin Mocha GTK theme, macOS Sequoia style Waybar (translucent menu bar), Wofi Spotlight-style launcher, custom Sequoia dark gradient wallpaper (PIL-generated), Inter font, full Sway config with macOS-style window colors and keybindings, Papirus-Dark icons
- Date Found: 2026-03-27
- Date Fixed: 2026-03-27

### BUG-030 — Missing macOS UX features
- Status: FIXED
- Severity: MEDIUM
- Component: Desktop UX
- Description: No window switcher, no dock auto-start, no animations, no styled terminal, no shell config
- Root Cause: Not configured in stage5
- Fix Applied: swayfx animations (corner radius, shadows, blur, dim inactive), swayr Alt+Tab window switcher, grim/slurp screenshot tools, foot terminal with macOS dark colors, .bashrc with styled prompt and aliases, all Luminos GUI components auto-start via exec_always
- Date Found: 2026-03-27
- Date Fixed: 2026-03-27

### BUG-031 — Sway config errors + waybar 3x + no lock screen
- Status: FIXED
- Severity: HIGH
- Component: Desktop config
- Description: Red error bar from swayfx options, waybar running 3 instances, no lock screen on boot
- Root Cause: swayfx options in regular sway, duplicate exec statements, no swaylock on startup
- Fix Applied: Removed swayfx options, single waybar via bar{} block only, swaylock on auto-login
- Date Found: 2026-03-27
- Date Fixed: 2026-03-27

### BUG-032 — Hyprland installation
- Status: FIXED
- Severity: IMPROVEMENT
- Component: Compositor
- Description: Added Hyprland as primary compositor with full config
- Fix Applied: Hyprland installed, full config with blur/shadows/animations/rounded corners, hyprlock lock screen, hypridle auto-lock, hyprpaper wallpaper, fallback to Sway
- Date Found: 2026-03-27
- Date Fixed: 2026-03-27

### BUG-033 — Visual styling complete
- Status: FIXED
- Severity: HIGH
- Component: Desktop visual layer
- Description: No wallpaper gradient, unstyled Waybar, basic Wofi, no terminal colors
- Root Cause: No CSS/config for visual components
- Fix Applied: Sequoia dark gradient wallpaper, macOS-style translucent Waybar, Spotlight Wofi, macOS dark terminal, GTK dark theme, Wayland environment variables
- Date Found: 2026-03-27
- Date Fixed: 2026-03-27

### BUG-035 — Hyprland not in Ubuntu 24.04 apt
- Status: FIXED
- Severity: CRITICAL
- Component: Compositor installation
- Description: Hyprland package not available in Ubuntu 24.04 noble apt repos. Original stage_hyprland() failed silently due to set -e exiting on missing packages.
- Root Cause: Hyprland too new for Ubuntu LTS. set -e in heredoc caused immediate exit when any dep not found. Several package names wrong for noble (libgles2, libvulkan-volk-dev).
- Fix Applied: Removed set -e from heredoc. Split apt deps into 7 resilient groups with || true each. Try PPA (ppa:hyprwm/hyprland-dev) first, fall back to source build. Fixed package names (libgles2-mesa-dev, libxkbcommon-x11-dev). Removed hard exit 1 so Sway fallback works. Added directory guards on ecosystem builds.
- Date Found: 2026-03-28
- Date Fixed: 2026-03-28

### BUG-036 — Hyprland source build fails silently
- Status: FIXED
- Severity: CRITICAL
- Component: scripts/smart_build.sh stage_hyprland
- Description: stage_hyprland() completes in 30 seconds instead of 30-60 minutes, says "ecosystem build complete" but Hyprland binary not found. Build silently skips all compilation.
- Root Cause: Multiple issues: (1) `$?` after pipe (`cmake ... | tail -5`) captures tail exit code (always 0), not cmake exit code — so configure failures never detected. (2) `touch .hyprland_done` was unconditional — marked "done" even when nothing built. (3) All build stderr suppressed with `2>/dev/null`. (4) Hyprland-specific lib packages (hyprlang, hyprutils, hyprcursor, aquamarine, hyprwayland-scanner) not available in Ubuntu 24.04 apt — must be built from source first as Hyprland deps.
- Fix Applied: Complete rewrite of stage_hyprland(): (1) Added diagnostic test script with pkg-config checks. (2) Used `set -o pipefail` + direct exit code capture (no pipes). (3) Three-method install: PPA → OBS repo → source build. (4) Source build now builds all 5 Hyprland deps from source first (hyprutils → hyprwayland-scanner → hyprlang → hyprcursor → aquamarine → Hyprland). (5) Full verbose output on all build commands. (6) Conditional flag file — only touch .hyprland_done if `/usr/bin/Hyprland` actually exists.
- Date Found: 2026-03-28
- Date Fixed: 2026-03-28

### BUG-037 — CMake too old for Hyprland
- Status: FIXED
- Severity: CRITICAL
- Component: Hyprland build
- Description: Hyprland requires CMake 3.30+ but Ubuntu 24.04 ships CMake 3.28.3
- Root Cause: Ubuntu LTS ships older toolchain
- Fix Applied: Install CMake 3.30+ from Kitware official apt repository before Hyprland build
- Date Found: 2026-03-28
- Date Fixed: 2026-03-28

### BUG-038 — Hyprland deps built in wrong order / aquamarine not found
- Status: FIXED
- Severity: CRITICAL
- Component: scripts/smart_build.sh stage_hyprland
- Description: aquamarine pkg-config not found even after cmake install. Piecemeal dep builds were out of order and duplicated across multiple heredocs. aquamarine needs hyprutils and hyprwayland-scanner built first.
- Root Cause: Dependencies were added incrementally without correct ordering. aquamarine requires hyprutils + hyprwayland-scanner. hyprcursor requires hyprlang + hyprutils. hyprlang requires hyprutils. Build order was not enforced.
- Fix Applied: Complete rewrite of stage_hyprland() with single chroot heredoc, helper function build_hypr_lib(), and correct 10-step build order: (1) hyprwayland-scanner (2) hyprutils (3) hyprlang (4) hyprcursor (5) glslang (6) aquamarine (7) Hyprland (8) hyprpaper (9) hyprlock (10) hypridle. Each step verifies pkg-config. PKG_CONFIG_PATH exported. ldconfig after each install. Removed PPA/OBS methods (never worked on Ubuntu 24.04).
- Date Found: 2026-03-28
- Date Fixed: 2026-03-28

### BUG-039 — Hyprland build fails: multiple missing deps and wrong compiler
- Status: FIXED
- Severity: CRITICAL
- Component: scripts/smart_build.sh stage_hyprland
- Description: Hyprland and its entire dependency chain failed to build on Ubuntu 24.04. Multiple cascading failures: hyprwayland-scanner missing pugixml, hyprutils needs C++23 <print> (GCC 14+), hyprcursor missing tomlplusplus, aquamarine needs libinput>=1.26 (Ubuntu has 1.25), Hyprland needs wayland>=1.22.91 (Ubuntu has 1.22.0), xkbcommon>=1.11 (Ubuntu has 1.6), wayland-protocols>=1.47 (Ubuntu has 1.45), xcb-errors (not packaged), re2, lcms2, muparser, and new dep hyprgraphics.
- Root Cause: Ubuntu 24.04 ships system libraries that are too old for latest Hyprland HEAD. The build script was not using GCC 14 (needed for C++23), was missing pugixml/tomlplusplus deps, and wasn't building system deps from source.
- Fix Applied: Complete rewrite of stage_hyprland() — (1) Use GCC 14 for all builds. (2) Build wayland, wayland-protocols, xkbcommon, libinput, xcb-errors, sdbus-c++ from source. (3) Upgrade meson via pip. (4) Install pugixml, tomlplusplus, re2, lcms2, muparser. (5) Add hyprgraphics to build chain. (6) Correct build order with all deps. (7) Mark hyprpaper/hyprlock/hypridle as best-effort (need hyprwire which requires GCC 15+ append_range).
- Date Found: 2026-03-28
- Date Fixed: 2026-03-29

## Open Bugs

(none)

### BUG-041 — SUPER+SPACE not triggering HIVE popup
- Status: FIXED
- Severity: HIGH
- Component: KDE global shortcuts / Albert launcher
- Description: Meta+Space (SUPER+SPACE) shortcut registered in kglobalshortcutsrc for HIVE popup but never triggered. 3 previous fix attempts failed.
- Root Cause: Albert launcher had `hotkey=Meta+Space` in `~/.config/albert/albert.conf` with `autostart=true`. Albert uses Wayland input-method protocols to grab the key at the compositor level BEFORE kglobalaccel can process it. The shortcut was properly registered in kglobalaccel, but Albert's grab always won on Wayland.
- Fix Applied: Changed Albert hotkey from `Meta+Space` to `Alt+Space` in albert.conf, restarted Albert, and toggled kglobalaccel block/unblock to force re-registration. Meta+Space now free for HIVE.
- Date Found: 2026-04-26
- Date Fixed: 2026-04-26

### BUG-042 — HIVE Settings not appearing in KDE System Settings
- Status: FIXED
- Severity: HIGH
- Component: KDE System Settings / KCM registration
- Description: "HIVE Settings" never appeared in KDE System Settings despite multiple .desktop file attempts. Searching "HIVE" in System Settings returned nothing.
- Root Cause: The desktop file at `/usr/share/applications/luminos-hive-settings.desktop` used `Type=Application` with `X-KDE-AliasFor=systemsettings` — this only creates an app launcher redirect, NOT a System Settings module. Plasma 6 requires a compiled Qt6 KCM plugin (`.so` in `/usr/lib/qt6/plugins/plasma/kcms/systemsettings/`) with matching JSON metadata embedding `X-KDE-ParentApp: kcontrol`. The previous `Type=Service` + `X-KDE-ServiceTypes=KCModule` approach (Plasma 5 pattern) does NOT work in Plasma 6 without a compiled plugin.
- Fix Applied: Created proper KCM plugin `kcm_luminos_hive` with C++ backend (reads luminos-hive.conf, queries nvidia-smi/pgrep for model status), QML UI (mode toggle, model roster, VRAM bar, shortcut display), and CMake build system. Compiled and installed to `/usr/lib/qt6/plugins/plasma/kcms/systemsettings/kcm_luminos_hive.so`. Module now appears in `kcmshell6 --list` and KDE System Settings.
- Date Found: 2026-04-26
- Date Fixed: 2026-04-26


## Recently Fixed

### BUG-040 — hyprpaper/hyprlock/hypridle fail to build (need GCC 15+)
- Status: FIXED
- Severity: LOW
- Component: scripts/smart_build.sh stage_hyprland ecosystem tools
- Description: hyprpaper, hyprlock, and hypridle require hyprwire and hyprtoolkit libraries. hyprwire uses C++23 std::vector::append_range which is only available in GCC 15+ (libstdc++). GCC 14 on Ubuntu 24.04 does not support this.
- Root Cause: Bleeding-edge hyprwm ecosystem tools outpaced Ubuntu 24.04's compiler. append_range was added to libstdc++ in GCC 15.
- Fix Applied: Installed GCC 15 from ppa:ubuntu-toolchain-r/test, set as default via update-alternatives. Built hyprwire, hyprtoolkit, hyprland-protocols, and iniparser as new deps. Then built hyprpaper, hyprlock, hypridle successfully with GCC 15 + C++23 support.
- Date Found: 2026-03-29
- Date Fixed: 2026-03-29

---

## Architecture Decision Bugs

### BUG-ARCH-001 — Custom shell on Hyprland+GTK4 cost 6+ weeks with no stable result
- Status: FIXED
- Severity: CRITICAL (project risk)
- Component: Entire UI stack (bar, dock, login, settings)
- Description: 6+ weeks spent on shell bugs: gtk4-layer-shell anchors, WAYLAND_DISPLAY propagation, Python venv fragility, taskbar input passthrough, minimize button broken on all apps, dock center-screen positioning, greetd GTK4 gl failures. No stable result achieved.
- Root Cause: Building a full desktop environment from scratch on Hyprland required gtk4-layer-shell (third-party library to pin windows to screen edges). KDE Plasma does this natively. We were recreating what KDE does natively, from scratch, with a third-party library, in Python. AI cannot do visual fine-tuning — custom shell requires human designer iteration.
- Fix Applied: Complete permanent move to KDE Plasma. All Hyprland, GTK4, HyprPanel, PyGObject, Python UI, greetd, swww retired. New stack: KDE Plasma + KWin + Qt/QML + Go. See LUMINOS_DECISIONS.md Decision 12.
- Date Found: April 2026 (accumulated)
- Date Fixed: 2026-04-19

---

## UI/Desktop Bugs (merged from LUMINOS_BUG_LOG.md on 2026-04-19)

### BUG-UI-001 — Dock center screen positioning
- Status: FIXED
- Severity: HIGH
- Component: src/gui/dock/dock_window.py
- Description: Dock appeared center screen instead of bottom center
- Root Cause: Missing LEFT and RIGHT layer-shell anchors
- Fix Applied: Added GtkLayerShell.set_anchor LEFT=True RIGHT=True
- Date Found: April 2026
- Date Fixed: April 2026

### BUG-UI-002 — Dock layer wrong (TOP instead of BOTTOM)
- Status: FIXED
- Severity: HIGH
- Component: src/gui/dock/dock_window.py
- Description: Dock set to Layer.TOP, causing it to render above all windows and reserve screen space
- Root Cause: Layer.TOP was used instead of Layer.BOTTOM; exclusive_zone was DOCK_HEIGHT+DOCK_BOTTOM_MARGIN instead of -1
- Fix Applied: Set Layer.BOTTOM and exclusive_zone=-1 (floating pill, no reserved zone)
- Date Found: April 2026
- Date Fixed: April 2026

### BUG-UI-003 — Bar/dock not autostarting
- Status: FIXED
- Severity: HIGH
- Component: systemd user services
- Description: Bar and dock not launching reliably on boot
- Root Cause: exec-once without env vars — GTK/Wayland init fails silently when WAYLAND_DISPLAY not set
- Fix Applied: Systemd user services with explicit Environment= vars; dock delayed 2s after bar
- Date Found: April 2026
- Date Fixed: April 2026

### BUG-UI-004 — Wrong apps pinned to dock
- Status: FIXED
- Severity: MEDIUM
- Component: src/gui/dock/dock_config.py
- Description: Dock defaulted to nautilus/foot/luminos-store which are not installed on target hardware
- Root Cause: DEFAULT_PINNED not updated for ROG G14 target environment
- Fix Applied: Updated DEFAULT_PINNED to dolphin, firefox, kitty, settings_app.py
- Date Found: April 2026
- Date Fixed: April 2026

### BUG-UI-005 — MemPalace Python 3.14 incompatibility
- Status: FIXED
- Severity: HIGH
- Component: MemPalace / chromadb
- Description: chromadb pydantic v1 broken on Python 3.14
- Root Cause: Arch ships Python 3.14, pydantic v1 not updated yet
- Fix Applied: uv + Python 3.12 venv at ~/mempalace-venv
- Date Found: April 2026
- Date Fixed: April 2026

### BUG-UI-006 — MemPalace normalize.py sender field
- Status: FIXED
- Severity: MEDIUM
- Component: ~/mempalace/mempalace/normalize.py
- Description: Only 3 drawers mined instead of 837 from Claude.ai export
- Root Cause: Claude.ai privacy exports use "sender" field not "role"; _try_claude_ai_json only checked "role"
- Fix Applied: Added sender fallback: item.get("role", "") or item.get("sender", "")
- Date Found: April 2026
- Date Fixed: April 2026

### BUG-UI-007 — Bar/dock services running but nothing visible on screen
- Status: FIXED
- Severity: CRITICAL
- Component: /opt/luminos/venv/pyvenv.cfg
- Description: luminos-bar and luminos-dock systemd services showed as active/running but bar and dock were invisible; services were crash-looping with "ERROR: GTK4 not available"
- Root Cause: /opt/luminos/venv/pyvenv.cfg had include-system-site-packages = false. PyGObject (the `gi` module) is a system package and cannot be pip-installed into a venv
- Fix Applied: Set include-system-site-packages = true in pyvenv.cfg
- Date Found: April 2026
- Date Fixed: April 2026

### BUG-UI-008 — Python venv system packages missing
- Status: RESOLVED (root cause retired)
- Severity: HIGH
- Component: All src/gui/ Python files
- Description: Multiple UI bugs traced back to Python venv not finding system packages (GTK4, PyGObject)
- Root Cause: Python venv packaging is fundamentally fragile
- Fix Applied: Retired Python for all UI work. Stack migrated to AGS/JS (bar/dock) and Go + libadwaita (settings/login). Then further migrated to HyprPanel.
- Date Found: April 2026
- Date Fixed: April 2026

---

## Known Limitations (not bugs)

- NPU classifier: stubbed, needs ONNX models on real AMD XDNA hardware
- HIVE models: needs GGUF files downloaded
- Zone 3 VM boot: needs vmlinux + rootfs.ext4
- RAM compression: zram not configured yet
- Disk encryption: not enabled by default
- Secure Boot: ISO not signed
