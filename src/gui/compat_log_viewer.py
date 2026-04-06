"""
src/gui/compat_log_viewer.py
Phase 5.10 Task 5 — Compatibility log viewer window.

Shows last 100 entries from ~/.local/share/luminos/compat.log.
Auto-refreshes every 5 seconds while open.
Accessible from Settings > Zones > "View Log".

Pure helper:
    read_compat_log(path, max_lines) → list[str]
"""

import logging
import os
import sys

logger = logging.getLogger("luminos.compat_log_viewer")

COMPAT_LOG_PATH = os.path.expanduser("~/.local/share/luminos/compat.log")
_MAX_LINES = 100

try:
    import gi
    gi.require_version("Gtk", "4.0")
    from gi.repository import Gtk, GLib
    _GTK_AVAILABLE = True
except (ImportError, ValueError):
    _GTK_AVAILABLE = False

_SRC = os.path.join(os.path.dirname(__file__), "..")
if _SRC not in sys.path:
    sys.path.insert(0, _SRC)

from gui.theme.luminos_theme import (
    BG_BASE, BG_SURFACE, BG_ELEVATED,
    TEXT_PRIMARY, TEXT_SECONDARY, TEXT_DISABLED,
    BORDER, ACCENT,
    COLOR_ERROR,
    SPACE_3, SPACE_4, SPACE_6,
    RADIUS_MD,
)


# ---------------------------------------------------------------------------
# Pure helper
# ---------------------------------------------------------------------------

def read_compat_log(path: str = COMPAT_LOG_PATH,
                    max_lines: int = _MAX_LINES) -> list:
    """
    Read the last max_lines entries from a compat log file.

    Args:
        path:      Log file path.
        max_lines: Maximum number of lines to return.

    Returns:
        List of strings (lines), most-recent last.
        Empty list if file does not exist or on error.
    """
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            lines = f.readlines()
        return [l.rstrip("\n") for l in lines[-max_lines:]]
    except FileNotFoundError:
        return []
    except OSError as e:
        logger.debug(f"compat_log read error: {e}")
        return []


# ---------------------------------------------------------------------------
# GTK Window
# ---------------------------------------------------------------------------

if _GTK_AVAILABLE:

    _LOG_CSS = f"""
    .compat-log-window {{
        background-color: {BG_BASE};
    }}
    .compat-log-view {{
        background-color: {BG_SURFACE};
        color: {TEXT_PRIMARY};
        font-family: "JetBrains Mono", "Fira Code", "Courier New", monospace;
        font-size: 12px;
        border: none;
        padding: 12px;
    }}
    .compat-log-empty {{
        color: {TEXT_DISABLED};
        font-size: 13px;
    }}
    .compat-log-title {{
        color: {TEXT_PRIMARY};
        font-size: 15px;
        font-weight: 600;
    }}
    .compat-log-path {{
        color: {TEXT_SECONDARY};
        font-size: 11px;
    }}
    .compat-clear-btn {{
        background-color: rgba(255, 68, 85, 0.12);
        color: {COLOR_ERROR};
        border: 1px solid rgba(255, 68, 85, 0.3);
        border-radius: {RADIUS_MD}px;
        padding: 6px 16px;
        font-size: 13px;
    }}
    .compat-clear-btn:hover {{
        background-color: rgba(255, 68, 85, 0.22);
    }}
    """

    class CompatLogViewer(Gtk.Window):
        """
        Compatibility log viewer.
        Shows last 100 lines of compat.log with 5s auto-refresh.
        """

        def __init__(self, log_path: str = COMPAT_LOG_PATH):
            super().__init__()
            self._log_path    = log_path
            self._refresh_id  = None

            self.set_title("Compatibility Log")
            self.set_default_size(760, 500)
            self.set_resizable(True)
            self.add_css_class("compat-log-window")

            css = Gtk.CssProvider()
            css.load_from_string(_LOG_CSS)
            Gtk.StyleContext.add_provider_for_display(
                self.get_display(), css,
                Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION,
            )

            self.connect("close-request", self._on_close)
            self._build()
            self._refresh()

            # Auto-refresh every 5 seconds
            self._refresh_id = GLib.timeout_add_seconds(5, self._auto_refresh)

        def _build(self):
            root = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
            root.set_margin_top(SPACE_6)
            root.set_margin_bottom(SPACE_6)
            root.set_margin_start(SPACE_6)
            root.set_margin_end(SPACE_6)
            self.set_child(root)

            # Header
            header = Gtk.Box(
                orientation=Gtk.Orientation.HORIZONTAL, spacing=SPACE_4
            )
            header.set_margin_bottom(SPACE_4)

            title_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
            title_box.set_hexpand(True)

            title = Gtk.Label(label="Compatibility Log")
            title.add_css_class("compat-log-title")
            title.set_halign(Gtk.Align.START)
            title_box.append(title)

            path_lbl = Gtk.Label(label=self._log_path)
            path_lbl.add_css_class("compat-log-path")
            path_lbl.set_halign(Gtk.Align.START)
            title_box.append(path_lbl)

            header.append(title_box)

            # Clear button
            clear_btn = Gtk.Button(label="Clear Log")
            clear_btn.add_css_class("compat-clear-btn")
            clear_btn.set_valign(Gtk.Align.CENTER)
            clear_btn.connect("clicked", self._on_clear)
            header.append(clear_btn)

            root.append(header)

            # Scrolled text view
            scroll = Gtk.ScrolledWindow()
            scroll.set_vexpand(True)
            scroll.set_hexpand(True)
            scroll.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)

            self._text_view = Gtk.TextView()
            self._text_view.set_editable(False)
            self._text_view.set_cursor_visible(False)
            self._text_view.set_wrap_mode(Gtk.WrapMode.NONE)
            self._text_view.add_css_class("compat-log-view")

            self._buffer = self._text_view.get_buffer()
            scroll.set_child(self._text_view)
            root.append(scroll)

            # Status bar
            self._status_lbl = Gtk.Label(label="")
            self._status_lbl.add_css_class("compat-log-path")
            self._status_lbl.set_halign(Gtk.Align.END)
            self._status_lbl.set_margin_top(SPACE_3)
            root.append(self._status_lbl)

        def _refresh(self) -> None:
            lines = read_compat_log(self._log_path)
            if lines:
                text = "\n".join(lines)
                self._buffer.set_text(text)
                # Scroll to end
                end_iter = self._buffer.get_end_iter()
                self._text_view.scroll_to_iter(end_iter, 0.0, False, 0.0, 1.0)
                self._status_lbl.set_text(f"{len(lines)} entries")
            else:
                self._buffer.set_text(
                    "No log entries yet.\n\n"
                    "Entries appear here when Windows apps are launched."
                )
                self._status_lbl.set_text("Empty")

        def _auto_refresh(self) -> bool:
            self._refresh()
            return GLib.SOURCE_CONTINUE

        def _on_clear(self, *_) -> None:
            try:
                with open(self._log_path, "w", encoding="utf-8") as f:
                    f.write("")
                self._refresh()
            except OSError as e:
                logger.warning(f"Failed to clear compat log: {e}")

        def _on_close(self, *_) -> bool:
            if self._refresh_id is not None:
                GLib.source_remove(self._refresh_id)
                self._refresh_id = None
            return False  # allow close

    def open_compat_log_viewer(parent=None) -> None:
        """Open the compat log viewer window."""
        viewer = CompatLogViewer()
        if parent:
            viewer.set_transient_for(parent)
        viewer.present()


else:

    class CompatLogViewer:  # type: ignore[no-redef]
        """Headless stub."""
        def __init__(self, *a, **kw): pass

    def open_compat_log_viewer(parent=None): pass
