"""
src/installer/luminos_installer.py
Phase 6 Task 5 — Luminos OS guided installer.

5 screens: Welcome → Disk Selection → Partition Scheme →
           Confirm → Installing → Done

Uses arch-install-scripts:
  pacstrap, genfstab, arch-chroot

Pure helpers (testable without GTK):
  get_block_devices()          → list[dict]
  format_disk_size(bytes)      → str
  validate_disk_choice(device) → (bool, str)
  build_install_stages()       → list[str]

GTK app: io.luminos.installer
"""

import logging
import os
import subprocess
import sys
import time

logger = logging.getLogger("luminos.installer")

try:
    import gi
    gi.require_version("Gtk", "4.0")
    from gi.repository import Gtk, GLib, Gio, Pango
    _GTK_AVAILABLE = True
except (ImportError, ValueError):
    _GTK_AVAILABLE = False

_SRC = os.path.join(os.path.dirname(__file__), "..")
if _SRC not in sys.path:
    sys.path.insert(0, _SRC)

MOUNT_POINT = "/mnt"
CONFIRM_WORD = "install"

INSTALL_STAGES = [
    "Partitioning disk",
    "Formatting partitions",
    "Mounting filesystems",
    "Installing base system",
    "Installing Luminos packages",
    "Copying Luminos OS",
    "Generating fstab",
    "Configuring system",
    "Installing bootloader",
    "Cleaning up",
]


# ===========================================================================
# Pure helpers
# ===========================================================================

def get_block_devices() -> list:
    """
    List available block devices (disks, not partitions).

    Returns:
        List of dicts: {name, path, size_bytes, size_human, model, type}
    """
    devices = []
    try:
        result = subprocess.run(
            ["lsblk", "--json", "--output",
             "NAME,SIZE,TYPE,MODEL,TRAN", "--bytes",
             "--nodeps"],
            capture_output=True, text=True, timeout=10,
        )
        if result.returncode != 0:
            return _fallback_block_devices()

        import json
        data = json.loads(result.stdout)
        for dev in data.get("blockdevices", []):
            if dev.get("type") not in ("disk",):
                continue
            try:
                size_bytes = int(dev.get("size", 0))
            except (ValueError, TypeError):
                size_bytes = 0
            devices.append({
                "name":       dev["name"],
                "path":       f"/dev/{dev['name']}",
                "size_bytes": size_bytes,
                "size_human": format_disk_size(size_bytes),
                "model":      dev.get("model") or "Unknown",
                "type":       dev.get("tran") or "disk",
            })
    except Exception as e:
        logger.debug(f"lsblk error: {e}")
        return _fallback_block_devices()
    return devices


def _fallback_block_devices() -> list:
    """Fallback: scan /dev/sd* and /dev/nvme*n*"""
    devices = []
    import glob
    patterns = ["/dev/sd[a-z]", "/dev/nvme[0-9]n[0-9]", "/dev/vd[a-z]"]
    for pat in patterns:
        for path in sorted(glob.glob(pat)):
            name = os.path.basename(path)
            devices.append({
                "name":       name,
                "path":       path,
                "size_bytes": _get_device_size(path),
                "size_human": format_disk_size(_get_device_size(path)),
                "model":      "Unknown",
                "type":       "disk",
            })
    return devices


def _get_device_size(path: str) -> int:
    """Read device size in bytes from sysfs."""
    name = os.path.basename(path)
    size_path = f"/sys/block/{name}/size"
    try:
        with open(size_path) as f:
            sectors = int(f.read().strip())
        return sectors * 512
    except (OSError, ValueError):
        return 0


def format_disk_size(size_bytes: int) -> str:
    """
    Format byte count as human-readable string.

    Examples:
        1_073_741_824 → "1.0 GB"
        500_107_862_016 → "465.8 GB"
    """
    if size_bytes <= 0:
        return "Unknown"
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if size_bytes < 1024:
            return f"{size_bytes:.1f} {unit}"
        size_bytes /= 1024
    return f"{size_bytes:.1f} PB"


def validate_disk_choice(device_path: str) -> tuple:
    """
    Validate that a device path is a real block device.

    Args:
        device_path: e.g. "/dev/sda"

    Returns:
        (valid: bool, error_msg: str)
    """
    if not device_path:
        return (False, "No disk selected.")
    if not os.path.exists(device_path):
        return (False, f"Device not found: {device_path}")
    if not os.path.isabs(device_path):
        return (False, "Device path must be absolute.")
    if not device_path.startswith("/dev/"):
        return (False, "Device must be under /dev/.")
    return (True, "")


def build_install_stages() -> list:
    """Return ordered list of installation stage names."""
    return list(INSTALL_STAGES)


# ===========================================================================
# GTK Installer App
# ===========================================================================

if _GTK_AVAILABLE:

    from gui.theme.luminos_theme import (
        BG_BASE, BG_SURFACE, ACCENT, ACCENT_HOVER, ACCENT_PRESSED,
        TEXT_PRIMARY, TEXT_SECONDARY, BORDER,
        COLOR_ERROR, COLOR_SUCCESS, COLOR_WARNING,
        SPACE_3, SPACE_4, SPACE_6, SPACE_8,
    )

    _INSTALLER_CSS = f"""
    .inst-root {{
        background-color: {BG_BASE};
        color: {TEXT_PRIMARY};
        font-family: "Inter", system-ui, sans-serif;
    }}
    .inst-title {{
        font-size: 28px;
        font-weight: 600;
        color: {TEXT_PRIMARY};
        letter-spacing: -0.5px;
    }}
    .inst-subtitle {{
        font-size: 15px;
        color: {TEXT_SECONDARY};
    }}
    .inst-btn-primary {{
        background-color: {ACCENT};
        color: white;
        border: none;
        border-radius: 8px;
        padding: 10px 28px;
        font-size: 14px;
        font-weight: 500;
        min-height: 40px;
    }}
    .inst-btn-primary:hover {{ background-color: {ACCENT_HOVER}; }}
    .inst-btn-secondary {{
        background-color: rgba(255,255,255,0.06);
        color: {TEXT_PRIMARY};
        border: 1px solid {BORDER};
        border-radius: 8px;
        padding: 10px 24px;
        font-size: 14px;
        min-height: 40px;
    }}
    .inst-btn-secondary:hover {{ background-color: rgba(255,255,255,0.10); }}
    .inst-btn-destructive {{
        background-color: rgba(255,68,85,0.15);
        color: {COLOR_ERROR};
        border: 1px solid rgba(255,68,85,0.4);
        border-radius: 8px;
        padding: 10px 28px;
        font-size: 14px;
        font-weight: 500;
    }}
    .inst-input {{
        background-color: rgba(255,255,255,0.06);
        color: {TEXT_PRIMARY};
        border: 1px solid {BORDER};
        border-radius: 8px;
        padding: 0 12px;
        font-size: 14px;
        min-height: 42px;
    }}
    .inst-disk-row {{
        border-radius: 8px;
        padding: 12px;
        background-color: rgba(255,255,255,0.04);
        border: 1px solid {BORDER};
    }}
    .inst-disk-selected {{
        border-color: {ACCENT};
        background-color: rgba(0,128,255,0.08);
    }}
    .inst-warning {{
        color: {COLOR_WARNING};
        font-size: 13px;
    }}
    .inst-error {{
        color: {COLOR_ERROR};
        font-size: 13px;
    }}
    .inst-progress-stage {{
        color: {TEXT_PRIMARY};
        font-size: 14px;
    }}
    .inst-progress-done {{
        color: {COLOR_SUCCESS};
        font-size: 14px;
    }}
    """

    SCREENS = ["welcome", "disk", "partition", "confirm", "installing", "done"]

    class LuminosInstaller(Gtk.Application):

        def __init__(self):
            super().__init__(
                application_id="io.luminos.installer",
                flags=Gio.ApplicationFlags.DEFAULT_FLAGS,
            )
            self._window  = None
            self._state   = {
                "target_disk":   "",
                "partition_mode": "auto",
                "confirmed":     False,
            }

        def do_activate(self):
            if self._window is None:
                self._window = InstallerWindow(self._state)
                self._window.set_application(self)
                self._window.connect("destroy", lambda *_: self.quit())
            self._window.present()

    class InstallerWindow(Gtk.Window):

        def __init__(self, state: dict):
            super().__init__()
            self._state   = state
            self._screen  = "welcome"
            self._cache   = {}

            self.set_title("Luminos OS Installer")
            self.set_default_size(720, 520)
            self.set_resizable(True)

            css = Gtk.CssProvider()
            css.load_from_string(_INSTALLER_CSS)
            Gtk.StyleContext.add_provider_for_display(
                self.get_display(), css,
                Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION,
            )

            self._build()
            self._show_screen("welcome")

        def _build(self):
            root = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
            root.add_css_class("inst-root")
            root.set_hexpand(True)
            root.set_vexpand(True)
            self.set_child(root)

            # Content
            self._stack = Gtk.Stack()
            self._stack.set_transition_type(Gtk.StackTransitionType.SLIDE_LEFT)
            self._stack.set_transition_duration(250)
            self._stack.set_hexpand(True)
            self._stack.set_vexpand(True)
            root.append(self._stack)

            # Nav
            nav = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=0)
            nav.set_margin_start(32)
            nav.set_margin_end(32)
            nav.set_margin_bottom(24)
            nav.set_margin_top(12)

            self._back_btn = Gtk.Button(label="← Back")
            self._back_btn.add_css_class("inst-btn-secondary")
            self._back_btn.set_visible(False)
            self._back_btn.connect("clicked", self._on_back)
            nav.append(self._back_btn)

            spacer = Gtk.Box()
            spacer.set_hexpand(True)
            nav.append(spacer)

            self._error_lbl = Gtk.Label(label="")
            self._error_lbl.add_css_class("inst-error")
            self._error_lbl.set_hexpand(True)
            self._error_lbl.set_halign(Gtk.Align.CENTER)
            nav.append(self._error_lbl)

            spacer2 = Gtk.Box()
            spacer2.set_hexpand(True)
            nav.append(spacer2)

            self._next_btn = Gtk.Button(label="Next →")
            self._next_btn.add_css_class("inst-btn-primary")
            self._next_btn.connect("clicked", self._on_next)
            nav.append(self._next_btn)

            root.append(nav)

        def _show_screen(self, screen_id: str):
            if screen_id not in SCREENS:
                return
            self._screen = screen_id

            if screen_id not in self._cache:
                w = self._make_screen(screen_id)
                self._stack.add_named(w, screen_id)
                self._cache[screen_id] = w

            self._stack.set_visible_child_name(screen_id)

            idx      = SCREENS.index(screen_id)
            is_first = screen_id == "welcome"
            is_done  = screen_id in ("done", "installing")

            self._back_btn.set_visible(not is_first and not is_done)
            self._next_btn.set_visible(screen_id not in ("installing", "done"))

            if screen_id == "confirm":
                self._next_btn.set_label("Install")
                self._next_btn.remove_css_class("inst-btn-primary")
                self._next_btn.add_css_class("inst-btn-destructive")
            else:
                self._next_btn.set_label("Next →")
                self._next_btn.remove_css_class("inst-btn-destructive")
                self._next_btn.add_css_class("inst-btn-primary")

            self._error_lbl.set_text("")

        def _make_screen(self, screen_id: str) -> Gtk.Widget:
            if screen_id == "welcome":    return self._make_welcome()
            if screen_id == "disk":       return self._make_disk()
            if screen_id == "partition":  return self._make_partition()
            if screen_id == "confirm":    return self._make_confirm()
            if screen_id == "installing": return self._make_installing()
            if screen_id == "done":       return self._make_done()
            return Gtk.Label(label=screen_id)

        # --- Welcome ---
        def _make_welcome(self) -> Gtk.Widget:
            box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=SPACE_4)
            box.set_halign(Gtk.Align.CENTER)
            box.set_valign(Gtk.Align.CENTER)
            box.set_hexpand(True)
            box.set_vexpand(True)

            title = Gtk.Label(label="Install Luminos")
            title.add_css_class("inst-title")
            box.append(title)

            sub = Gtk.Label(label="This will install Luminos OS on your computer.")
            sub.add_css_class("inst-subtitle")
            box.append(sub)

            warn = Gtk.Label(label="⚠  The selected disk will be completely erased.")
            warn.add_css_class("inst-warning")
            warn.set_margin_top(SPACE_4)
            box.append(warn)

            return box

        # --- Disk selection ---
        def _make_disk(self) -> Gtk.Widget:
            box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=SPACE_4)
            box.set_margin_start(32)
            box.set_margin_end(32)
            box.set_margin_top(32)

            title = Gtk.Label(label="Choose installation disk")
            title.add_css_class("inst-title")
            title.set_halign(Gtk.Align.START)
            box.append(title)

            self._disk_group = Gtk.Box(
                orientation=Gtk.Orientation.VERTICAL, spacing=SPACE_3
            )
            self._disk_group.set_margin_top(SPACE_4)
            self._disk_buttons = []

            devices = get_block_devices()
            if not devices:
                empty = Gtk.Label(label="No disks found.")
                empty.add_css_class("inst-subtitle")
                self._disk_group.append(empty)
            else:
                for dev in devices:
                    row = self._make_disk_row(dev)
                    self._disk_group.append(row)

            scroll = Gtk.ScrolledWindow()
            scroll.set_vexpand(True)
            scroll.set_child(self._disk_group)
            box.append(scroll)

            return box

        def _make_disk_row(self, dev: dict) -> Gtk.Widget:
            row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=SPACE_4)
            row.add_css_class("inst-disk-row")
            row.set_hexpand(True)

            text = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
            text.set_hexpand(True)

            name_lbl = Gtk.Label(label=f"{dev['path']}  {dev['size_human']}")
            name_lbl.set_halign(Gtk.Align.START)
            name_lbl.add_css_class("inst-progress-stage")
            text.append(name_lbl)

            model_lbl = Gtk.Label(label=dev.get("model", ""))
            model_lbl.set_halign(Gtk.Align.START)
            model_lbl.add_css_class("inst-subtitle")
            text.append(model_lbl)

            row.append(text)

            select_btn = Gtk.Button(label="Select")
            select_btn.add_css_class("inst-btn-secondary")
            select_btn.set_valign(Gtk.Align.CENTER)
            select_btn.connect("clicked", lambda *_, p=dev["path"], r=row: self._on_select_disk(p, r))
            row.append(select_btn)

            self._disk_buttons.append((dev["path"], row, select_btn))
            return row

        def _on_select_disk(self, path: str, selected_row) -> None:
            self._state["target_disk"] = path
            for _, row, btn in self._disk_buttons:
                row.remove_css_class("inst-disk-selected")
            selected_row.add_css_class("inst-disk-selected")

        # --- Partition scheme ---
        def _make_partition(self) -> Gtk.Widget:
            box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=SPACE_4)
            box.set_margin_start(32)
            box.set_margin_end(32)
            box.set_margin_top(32)

            title = Gtk.Label(label="Partition scheme")
            title.add_css_class("inst-title")
            title.set_halign(Gtk.Align.START)
            box.append(title)

            sub = Gtk.Label(
                label="Recommended: Auto creates EFI 512MB + swap 4GB + root (rest)"
            )
            sub.add_css_class("inst-subtitle")
            sub.set_halign(Gtk.Align.START)
            box.append(sub)

            # Radio buttons
            self._auto_radio = Gtk.CheckButton(
                label="Auto (Recommended) — EFI 512MB + Swap 4GB + Root"
            )
            self._auto_radio.set_active(True)
            self._auto_radio.connect("toggled", lambda *_: self._state.update(
                {"partition_mode": "auto"}
            ))
            box.append(self._auto_radio)

            manual_radio = Gtk.CheckButton(label="Manual — Open GParted")
            manual_radio.set_group(self._auto_radio)
            manual_radio.connect("toggled", lambda *_: self._state.update(
                {"partition_mode": "manual"}
            ))
            box.append(manual_radio)

            return box

        # --- Confirm ---
        def _make_confirm(self) -> Gtk.Widget:
            box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=SPACE_4)
            box.set_margin_start(32)
            box.set_margin_end(32)
            box.set_margin_top(32)
            box.set_halign(Gtk.Align.CENTER)
            box.set_valign(Gtk.Align.CENTER)
            box.set_hexpand(True)
            box.set_vexpand(True)

            disk = self._state.get("target_disk", "(none)")

            title = Gtk.Label(label="Ready to install?")
            title.add_css_class("inst-title")
            box.append(title)

            warn = Gtk.Label(
                label=f"This will completely erase:\n{disk}\n\nThis cannot be undone."
            )
            warn.add_css_class("inst-warning")
            warn.set_justify(Gtk.Justification.CENTER)
            warn.set_margin_top(SPACE_4)
            box.append(warn)

            confirm_lbl = Gtk.Label(label=f'Type "{CONFIRM_WORD}" to confirm:')
            confirm_lbl.add_css_class("inst-subtitle")
            confirm_lbl.set_margin_top(SPACE_6)
            box.append(confirm_lbl)

            self._confirm_entry = Gtk.Entry()
            self._confirm_entry.set_placeholder_text(CONFIRM_WORD)
            self._confirm_entry.add_css_class("inst-input")
            self._confirm_entry.set_halign(Gtk.Align.CENTER)
            self._confirm_entry.set_size_request(200, -1)
            box.append(self._confirm_entry)

            return box

        # --- Installing ---
        def _make_installing(self) -> Gtk.Widget:
            box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=SPACE_3)
            box.set_margin_start(32)
            box.set_margin_end(32)
            box.set_margin_top(32)

            title = Gtk.Label(label="Installing Luminos...")
            title.add_css_class("inst-title")
            title.set_halign(Gtk.Align.START)
            box.append(title)

            # Progress bar
            self._install_progress = Gtk.ProgressBar()
            self._install_progress.set_margin_top(SPACE_4)
            self._install_progress.set_hexpand(True)
            box.append(self._install_progress)

            # Stage label
            self._stage_lbl = Gtk.Label(label="Starting...")
            self._stage_lbl.add_css_class("inst-subtitle")
            self._stage_lbl.set_halign(Gtk.Align.START)
            box.append(self._stage_lbl)

            # Stage list
            self._stage_list_box = Gtk.Box(
                orientation=Gtk.Orientation.VERTICAL, spacing=4
            )
            self._stage_list_box.set_margin_top(SPACE_4)
            self._stage_labels = []

            stages = build_install_stages()
            for stage in stages:
                lbl = Gtk.Label(label=f"  ○  {stage}")
                lbl.add_css_class("inst-subtitle")
                lbl.set_halign(Gtk.Align.START)
                self._stage_labels.append((stage, lbl))
                self._stage_list_box.append(lbl)

            box.append(self._stage_list_box)

            # Start installation in background
            GLib.idle_add(self._start_installation)

            return box

        def _start_installation(self) -> bool:
            import threading
            t = threading.Thread(
                target=self._run_installation,
                daemon=True,
                name="luminos-installer",
            )
            t.start()
            return GLib.SOURCE_REMOVE

        def _run_installation(self) -> None:
            disk  = self._state.get("target_disk", "")
            mode  = self._state.get("partition_mode", "auto")
            total = len(INSTALL_STAGES)

            try:
                from installer.install_backend import run_install
                run_install(
                    disk=disk,
                    partition_mode=mode,
                    progress_callback=self._on_install_progress,
                )
                GLib.idle_add(self._on_install_done)
            except Exception as e:
                logger.error(f"Installation failed: {e}")
                GLib.idle_add(self._on_install_error, str(e))

        def _on_install_progress(self, stage_idx: int, stage_name: str) -> None:
            def _update():
                stages = build_install_stages()
                frac = (stage_idx + 1) / len(stages)
                self._install_progress.set_fraction(frac)
                self._stage_lbl.set_text(stage_name)

                # Update stage labels
                for i, (name, lbl) in enumerate(self._stage_labels):
                    lbl.remove_css_class("inst-subtitle")
                    lbl.remove_css_class("inst-progress-stage")
                    lbl.remove_css_class("inst-progress-done")
                    if i < stage_idx:
                        lbl.set_text(f"  ✓  {name}")
                        lbl.add_css_class("inst-progress-done")
                    elif i == stage_idx:
                        lbl.set_text(f"  ▶  {name}")
                        lbl.add_css_class("inst-progress-stage")
                    else:
                        lbl.set_text(f"  ○  {name}")
                        lbl.add_css_class("inst-subtitle")
                return GLib.SOURCE_REMOVE

            GLib.idle_add(_update)

        def _on_install_done(self) -> bool:
            self._stack.set_transition_type(Gtk.StackTransitionType.SLIDE_LEFT)
            self._show_screen("done")
            return GLib.SOURCE_REMOVE

        def _on_install_error(self, error: str) -> bool:
            self._stage_lbl.set_text(f"Installation failed: {error}")
            self._stage_lbl.remove_css_class("inst-subtitle")
            self._stage_lbl.add_css_class("inst-error")
            return GLib.SOURCE_REMOVE

        # --- Done ---
        def _make_done(self) -> Gtk.Widget:
            box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=SPACE_4)
            box.set_halign(Gtk.Align.CENTER)
            box.set_valign(Gtk.Align.CENTER)
            box.set_hexpand(True)
            box.set_vexpand(True)

            check = Gtk.Label(label="✓")
            check.add_css_class("inst-title")
            check.set_markup(f"<span foreground='#00C896' size='xx-large'>✓</span>")
            box.append(check)

            title = Gtk.Label(label="Luminos is installed.")
            title.add_css_class("inst-title")
            box.append(title)

            sub = Gtk.Label(
                label="Remove the USB drive and restart your computer."
            )
            sub.add_css_class("inst-subtitle")
            sub.set_margin_top(SPACE_3)
            box.append(sub)

            restart_btn = Gtk.Button(label="Restart Now")
            restart_btn.add_css_class("inst-btn-primary")
            restart_btn.set_halign(Gtk.Align.CENTER)
            restart_btn.set_margin_top(SPACE_6)
            restart_btn.connect("clicked", self._on_restart)
            box.append(restart_btn)

            return box

        def _on_restart(self, *_) -> None:
            try:
                subprocess.run(["systemctl", "reboot"], check=False)
            except Exception:
                pass

        # --- Navigation ---
        def _on_next(self, *_) -> None:
            screen = self._screen
            idx    = SCREENS.index(screen)

            # Validation
            if screen == "disk":
                ok, msg = validate_disk_choice(self._state.get("target_disk", ""))
                if not ok:
                    self._error_lbl.set_text(msg)
                    return

            if screen == "confirm":
                typed = getattr(self, "_confirm_entry", None)
                if typed and typed.get_text().strip().lower() != CONFIRM_WORD:
                    self._error_lbl.set_text(
                        f'Type "{CONFIRM_WORD}" exactly to confirm.'
                    )
                    return
                self._state["confirmed"] = True

            self._error_lbl.set_text("")
            if idx + 1 < len(SCREENS):
                self._stack.set_transition_type(Gtk.StackTransitionType.SLIDE_LEFT)
                self._show_screen(SCREENS[idx + 1])

        def _on_back(self, *_) -> None:
            screen = self._screen
            idx    = SCREENS.index(screen)
            if idx > 0:
                self._stack.set_transition_type(Gtk.StackTransitionType.SLIDE_RIGHT)
                self._show_screen(SCREENS[idx - 1])


    def main() -> int:
        app = LuminosInstaller()
        return app.run(sys.argv)

    if __name__ == "__main__":
        sys.exit(main() or 0)


else:

    def main() -> int:
        logger.warning("GTK not available — cannot run installer")
        return 1
