"""
src/gui/lockscreen/lock_window.py
Full-screen Wayland lock screen window.

Uses gtk4-layer-shell OVERLAY + KEYBOARD_MODE_EXCLUSIVE to grab all input.
States: clock → auth → error → locked_out

Visual spec (LUMINOS_DESIGN_SYSTEM.md):
- Full screen, BG_BASE background
- Clock: Inter 80px weight 300, TEXT_PRIMARY, letter-spacing -2px, 20% above center
- Date: Inter 16px weight 400, TEXT_SECONDARY, 8px below clock
- Press Enter → password field slides up 20px + fades in 200ms
- Password: 320×48px, rgba(255,255,255,0.08) + blur, BORDER/BORDER_FOCUS, RADIUS_DEFAULT
- Wrong password: 3 shakes over 300ms, border turns COLOR_ERROR, field clears
- Correct password: fade out over ANIM_SLOW (350ms), launch session
- Nothing else on screen. No username. No logo. No buttons.

GTK class guarded by _GTK_AVAILABLE for headless test compatibility.
"""

import logging

logger = logging.getLogger(__name__)

try:
    import gi
    gi.require_version("Gtk", "4.0")
    from gi.repository import Gtk, GLib, Gdk
    try:
        gi.require_version("GtkLayerShell", "0.1")
        from gi.repository import GtkLayerShell as LayerShell
        _LAYER_SHELL = True
    except (ImportError, ValueError):
        _LAYER_SHELL = False
    _GTK_AVAILABLE = True
except (ImportError, ValueError):
    _GTK_AVAILABLE = False
    _LAYER_SHELL   = False

from gui.lockscreen.pam_auth import PAMAuth

import os, sys
_SRC = os.path.join(os.path.dirname(__file__), "..", "..")
if _SRC not in sys.path:
    sys.path.insert(0, _SRC)

from gui.theme.luminos_theme import (
    BG_BASE, TEXT_PRIMARY, TEXT_SECONDARY, TEXT_DISABLED,
    BORDER, BORDER_FOCUS, COLOR_ERROR,
    FONT_FAMILY, FONT_DISPLAY, FONT_BODY_LARGE, FONT_BODY, FONT_CAPTION,
    RADIUS_DEFAULT, SPACE_2, SPACE_4, SPACE_8,
    ANIM_DEFAULT, ANIM_SLOW,
    glass_bg,
)


# ---------------------------------------------------------------------------
# Pure helpers — testable without GTK
# ---------------------------------------------------------------------------

def _format_clock_time(dt) -> str:
    """Format a datetime as 'HH:MM' for the large clock display."""
    return dt.strftime("%H:%M")


def _format_clock_date(dt) -> str:
    """Format a datetime as 'Tuesday, April 04 2026'."""
    return dt.strftime("%A, %B %-d %Y")


def _get_initials(username: str) -> str:
    """
    Derive display initials from a username.
    'john_doe' → 'JD', 'alice' → 'A'
    """
    parts = username.replace("_", " ").replace(".", " ").split()
    if not parts:
        return "?"
    if len(parts) >= 2:
        return (parts[0][0] + parts[-1][0]).upper()
    return parts[0][0].upper()


# ---------------------------------------------------------------------------
# CSS — all values from luminos_theme
# ---------------------------------------------------------------------------

_LOCK_CSS = f"""
.lock-bg {{
    background-color: {BG_BASE};
}}

.lock-time {{
    font-size: {FONT_DISPLAY}px;
    font-weight: 300;
    font-family: "{FONT_FAMILY}", sans-serif;
    color: {TEXT_PRIMARY};
    letter-spacing: -2px;
}}

.lock-date {{
    font-size: {FONT_BODY_LARGE}px;
    font-weight: 400;
    font-family: "{FONT_FAMILY}", sans-serif;
    color: {TEXT_SECONDARY};
    margin-top: {SPACE_2}px;
}}

.lock-password-entry {{
    font-size: {FONT_BODY}px;
    font-family: "{FONT_FAMILY}", sans-serif;
    min-width: 320px;
    min-height: 48px;
    padding: 12px 18px;
    border-radius: {RADIUS_DEFAULT}px;
    background-color: rgba(255, 255, 255, 0.08);
    border: 1px solid {BORDER};
    color: {TEXT_PRIMARY};
    caret-color: {TEXT_PRIMARY};
    margin-top: {SPACE_8}px;
}}

.lock-password-entry:focus {{
    border-color: {BORDER_FOCUS};
    background-color: rgba(255, 255, 255, 0.10);
    outline: none;
}}

.lock-password-entry-error {{
    border-color: {COLOR_ERROR};
}}

.lock-error-label {{
    font-size: {FONT_CAPTION}px;
    font-family: "{FONT_FAMILY}", sans-serif;
    color: {COLOR_ERROR};
    margin-top: {SPACE_2}px;
}}

.lock-countdown {{
    font-size: {FONT_BODY}px;
    font-family: "{FONT_FAMILY}", sans-serif;
    color: {TEXT_DISABLED};
    margin-top: {SPACE_2}px;
}}

.lock-password-shake {{
    animation: shake 0.3s ease-in-out;
}}

@keyframes shake {{
    0%, 100% {{ margin-left: 0; }}
    33% {{ margin-left: -10px; }}
    66% {{ margin-left: 10px; }}
}}
"""


# ---------------------------------------------------------------------------
# GTK lock screen window
# ---------------------------------------------------------------------------

if _GTK_AVAILABLE:
    class LuminosLockScreen(Gtk.Window):
        """
        Full-screen Wayland lock screen.

        Layer-shell pins to all edges at OVERLAY layer with exclusive keyboard
        grab — no input reaches applications underneath.

        States
        ------
        "clock"      — large clock + date. No input visible.
        "auth"       — password entry visible.
        "error"      — wrong-password shake + error border.
        "locked_out" — countdown to next attempt.
        """

        STATES = ["clock", "auth", "error", "locked_out"]

        def __init__(self, app=None):
            super().__init__()
            if app:
                self.set_application(app)

            self.set_decorated(False)
            self.set_resizable(False)
            self.fullscreen()

            self.state    = "clock"
            self.pam      = PAMAuth()
            self.username = self.pam.get_current_user()

            # Layer shell — grab all input
            if _LAYER_SHELL:
                LayerShell.init_for_window(self)
                LayerShell.set_layer(self, LayerShell.Layer.OVERLAY)
                LayerShell.set_exclusive_zone(self, -1)
                LayerShell.set_keyboard_mode(
                    self, LayerShell.KeyboardMode.EXCLUSIVE
                )
                for edge in (
                    LayerShell.Edge.TOP, LayerShell.Edge.BOTTOM,
                    LayerShell.Edge.LEFT, LayerShell.Edge.RIGHT,
                ):
                    LayerShell.set_anchor(self, edge, True)

            # Apply CSS
            css_provider = Gtk.CssProvider()
            css_provider.load_from_string(_LOCK_CSS)
            Gtk.StyleContext.add_provider_for_display(
                Gdk.Display.get_default(),
                css_provider,
                Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION,
            )

            self._build()
            self._start_clock()

            # Key press → show auth + capture input
            key_ctrl = Gtk.EventControllerKey()
            key_ctrl.connect("key-pressed", self._on_key)
            self.add_controller(key_ctrl)

        # -------------------------------------------------------------------
        # UI construction
        # -------------------------------------------------------------------

        def _build(self):
            """Full-screen dark layout: clock 20% above center, hidden password."""
            root = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
            root.set_hexpand(True)
            root.set_vexpand(True)
            root.add_css_class("lock-bg")
            self.set_child(root)

            # Use an overlay so we can position content 20% above center
            overlay = Gtk.Overlay()
            overlay.set_vexpand(True)
            overlay.set_hexpand(True)
            root.append(overlay)

            # Spacer child fills the overlay
            spacer = Gtk.Box()
            spacer.set_vexpand(True)
            overlay.set_child(spacer)

            # Content box — centered horizontally, offset 30% from top
            content = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
            content.set_halign(Gtk.Align.CENTER)
            content.set_valign(Gtk.Align.START)
            # 30% from top ≈ 20% above vertical center on a 1080p display
            content.set_margin_top(300)
            overlay.add_overlay(content)

            # Clock
            self._time_lbl = Gtk.Label(label="00:00")
            self._time_lbl.add_css_class("lock-time")
            content.append(self._time_lbl)

            # Date
            self._date_lbl = Gtk.Label(label="")
            self._date_lbl.add_css_class("lock-date")
            content.append(self._date_lbl)

            # Password entry — hidden until Enter
            self._pw_entry = Gtk.PasswordEntry()
            self._pw_entry.set_show_peek_icon(False)
            self._pw_entry.add_css_class("lock-password-entry")
            self._pw_entry.set_visible(False)
            self._pw_entry.connect("activate", self._on_entry_activate)
            content.append(self._pw_entry)

            # Error label — hidden by default
            self._error_lbl = Gtk.Label(label="")
            self._error_lbl.add_css_class("lock-error-label")
            self._error_lbl.set_visible(False)
            content.append(self._error_lbl)

            # Countdown label for lockout — hidden by default
            self._countdown_lbl = Gtk.Label(label="")
            self._countdown_lbl.add_css_class("lock-countdown")
            self._countdown_lbl.set_visible(False)
            content.append(self._countdown_lbl)

        # -------------------------------------------------------------------
        # Clock timer
        # -------------------------------------------------------------------

        def _start_clock(self):
            self._update_clock()
            GLib.timeout_add_seconds(1, self._update_clock)

        def _update_clock(self) -> bool:
            import datetime
            now = datetime.datetime.now()
            time_str = _format_clock_time(now)
            date_str = _format_clock_date(now)

            try:
                self._time_lbl.set_label(time_str)
                self._date_lbl.set_label(date_str)
            except Exception:
                pass

            # Locked-out countdown
            if self.state == "locked_out":
                lo = self.pam.is_locked_out()
                if lo["locked"]:
                    self._countdown_lbl.set_label(
                        f"Try again in {lo['wait_seconds']}s"
                    )
                else:
                    self._set_state("auth")

            return True   # GLib.SOURCE_CONTINUE

        # -------------------------------------------------------------------
        # State management
        # -------------------------------------------------------------------

        def _set_state(self, new_state: str):
            self.state = new_state

            if new_state == "clock":
                self._pw_entry.set_visible(False)
                self._error_lbl.set_visible(False)
                self._countdown_lbl.set_visible(False)

            elif new_state == "auth":
                self._error_lbl.set_visible(False)
                self._error_lbl.set_label("")
                self._countdown_lbl.set_visible(False)
                self._pw_entry.set_text("")
                self._pw_entry.remove_css_class("lock-password-shake")
                self._pw_entry.remove_css_class("lock-password-entry-error")
                self._pw_entry.set_visible(True)
                GLib.idle_add(self._pw_entry.grab_focus)

            elif new_state == "locked_out":
                self._pw_entry.set_visible(False)
                self._error_lbl.set_visible(False)
                self._countdown_lbl.set_visible(True)

        # -------------------------------------------------------------------
        # Input handlers
        # -------------------------------------------------------------------

        def _on_key(self, ctrl, keyval, keycode, state) -> bool:
            if self.state == "clock":
                if keyval in (Gdk.KEY_Return, Gdk.KEY_KP_Enter):
                    self._set_state("auth")
                return True

            if self.state in ("auth", "error"):
                if keyval == Gdk.KEY_Escape:
                    self._pw_entry.set_text("")
                    self._set_state("clock")
                    return True
                return False  # let entry handle keys

            if self.state == "locked_out":
                return True   # consume all input during lockout

            return True

        def _on_entry_activate(self, *_):
            self._try_auth()

        # -------------------------------------------------------------------
        # Authentication
        # -------------------------------------------------------------------

        def _try_auth(self):
            password = self._pw_entry.get_text()
            result   = self.pam.authenticate(password)

            if result["success"]:
                self.unlock()
                return

            if result.get("reason") == "locked_out":
                self._countdown_lbl.set_label(
                    f"Try again in {result.get('wait_seconds', 0)}s"
                )
                self._set_state("locked_out")
                return

            # Wrong password
            attempts = result.get("attempts", self.pam.attempts)
            if result.get("lockout_applied"):
                self._countdown_lbl.set_label(
                    f"Try again in {result.get('wait_seconds', 0)}s"
                )
                self._set_state("locked_out")
                return

            self._error_lbl.set_label(
                f"Incorrect password  (attempt {attempts})"
            )
            self._error_lbl.set_visible(True)
            self._pw_entry.set_text("")

            # Error border + shake animation (3 shakes, 300ms)
            self._pw_entry.add_css_class("lock-password-entry-error")
            self._pw_entry.remove_css_class("lock-password-shake")
            GLib.idle_add(
                lambda: self._pw_entry.add_css_class("lock-password-shake")
            )
            self.state = "error"

        def unlock(self):
            """Called after successful authentication."""
            try:
                from gui.wallpaper import on_unlock
                on_unlock()
            except Exception as e:
                logger.debug(f"LuminosLockScreen.unlock: wallpaper on_unlock error — {e}")
            self.hide()
            logger.info("Lock screen: unlocked")

        # -------------------------------------------------------------------
        # Pure-logic mirrors (for test hooks)
        # -------------------------------------------------------------------

        @staticmethod
        def _format_time(dt) -> str:
            return _format_clock_time(dt)

        @staticmethod
        def _format_date(dt) -> str:
            return _format_clock_date(dt)

        @staticmethod
        def _get_initials(username: str) -> str:
            return _get_initials(username)
