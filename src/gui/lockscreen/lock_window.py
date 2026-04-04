"""
src/gui/lockscreen/lock_window.py
Full-screen Wayland lock screen window.

Uses gtk4-layer-shell OVERLAY + KEYBOARD_MODE_EXCLUSIVE to grab all input.
States: clock → auth → error → locked_out

Visual spec (matches greeter):
- Full screen, dark background (#0d0d12)
- Large clock center screen (HH:MM, updates every second)
- Date below clock (Tuesday, March 31 2026)
- Press Enter → slide in password input field
- No username list visible
- No visible input field until Enter is pressed
- Clean, minimal, dark

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


# ---------------------------------------------------------------------------
# Pure helpers — testable without GTK
# ---------------------------------------------------------------------------

def _format_clock_time(dt) -> str:
    """Format a datetime as 'HH:MM' for the large clock display."""
    return dt.strftime("%H:%M")


def _format_clock_date(dt) -> str:
    """Format a datetime as 'Tuesday, March 31 2026'."""
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
# CSS
# ---------------------------------------------------------------------------

_LOCK_CSS = """
.lock-bg {
    background-color: #0d0d12;
}

.lock-time {
    font-size: 96px;
    font-weight: 200;
    font-family: "Inter", "Helvetica Neue", sans-serif;
    color: rgba(255, 255, 255, 0.92);
    letter-spacing: -2px;
}

.lock-date {
    font-size: 22px;
    font-weight: 400;
    font-family: "Inter", "Helvetica Neue", sans-serif;
    color: rgba(255, 255, 255, 0.50);
    margin-top: 4px;
}

.lock-hint {
    font-size: 14px;
    font-family: "Inter", sans-serif;
    color: rgba(255, 255, 255, 0.25);
    margin-top: 48px;
}

.lock-password-entry {
    font-size: 16px;
    font-family: "Inter", sans-serif;
    min-width: 300px;
    padding: 12px 18px;
    border-radius: 12px;
    background-color: rgba(255, 255, 255, 0.06);
    border: 1px solid rgba(255, 255, 255, 0.12);
    color: rgba(255, 255, 255, 0.92);
    caret-color: #0a84ff;
    margin-top: 32px;
}

.lock-password-entry:focus {
    border-color: rgba(10, 132, 255, 0.6);
    background-color: rgba(255, 255, 255, 0.08);
    outline: none;
}

.lock-error-label {
    font-size: 14px;
    font-family: "Inter", sans-serif;
    color: #ff453a;
    margin-top: 12px;
}

.lock-lockout-title {
    font-size: 20px;
    font-family: "Inter", sans-serif;
    color: rgba(255, 255, 255, 0.80);
    margin-top: 16px;
}

.lock-countdown {
    font-size: 16px;
    font-family: "Inter", sans-serif;
    color: rgba(255, 255, 255, 0.40);
    margin-top: 8px;
}

.lock-lockout-icon {
    font-size: 48px;
}

.lock-password-shake {
    animation: shake 0.4s ease-in-out;
}

@keyframes shake {
    0%, 100% { margin-left: 0; }
    20% { margin-left: -12px; }
    40% { margin-left: 10px; }
    60% { margin-left: -8px; }
    80% { margin-left: 6px; }
}
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
        "clock"      — large clock + date + hint. No input visible.
        "auth"       — password entry visible.
        "error"      — wrong-password label shown.
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
            """Build the full-screen dark layout with clock and hidden password."""
            root = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
            root.set_hexpand(True)
            root.set_vexpand(True)
            root.add_css_class("lock-bg")
            self.set_child(root)

            # Content stack (clock / auth / locked_out)
            self._stack = Gtk.Stack()
            self._stack.set_transition_type(Gtk.StackTransitionType.CROSSFADE)
            self._stack.set_transition_duration(200)
            self._stack.set_halign(Gtk.Align.CENTER)
            self._stack.set_valign(Gtk.Align.CENTER)
            self._stack.set_vexpand(True)
            root.append(self._stack)

            self._build_clock_page()
            self._build_auth_page()
            self._build_locked_out_page()

            self._stack.set_visible_child_name("clock")

        def _build_clock_page(self):
            box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
            box.set_halign(Gtk.Align.CENTER)
            box.set_valign(Gtk.Align.CENTER)

            self._time_lbl = Gtk.Label(label="00:00")
            self._time_lbl.add_css_class("lock-time")
            box.append(self._time_lbl)

            self._date_lbl = Gtk.Label(label="")
            self._date_lbl.add_css_class("lock-date")
            box.append(self._date_lbl)

            self._hint_lbl = Gtk.Label(label="Press Enter to unlock")
            self._hint_lbl.add_css_class("lock-hint")
            box.append(self._hint_lbl)

            self._stack.add_named(box, "clock")

        def _build_auth_page(self):
            box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
            box.set_halign(Gtk.Align.CENTER)
            box.set_valign(Gtk.Align.CENTER)

            self._auth_time_lbl = Gtk.Label(label="00:00")
            self._auth_time_lbl.add_css_class("lock-time")
            box.append(self._auth_time_lbl)

            auth_date_lbl = Gtk.Label(label="")
            auth_date_lbl.add_css_class("lock-date")
            self._auth_date_lbl = auth_date_lbl
            box.append(auth_date_lbl)

            # Password entry
            self._pw_entry = Gtk.PasswordEntry()
            self._pw_entry.set_placeholder_text("Password")
            self._pw_entry.set_size_request(300, -1)
            self._pw_entry.add_css_class("lock-password-entry")
            self._pw_entry.set_show_peek_icon(True)
            self._pw_entry.connect("activate", self._on_entry_activate)
            box.append(self._pw_entry)

            # Error message label (hidden by default)
            self._error_lbl = Gtk.Label(label="")
            self._error_lbl.add_css_class("lock-error-label")
            self._error_lbl.set_visible(False)
            box.append(self._error_lbl)

            self._stack.add_named(box, "auth")

        def _build_locked_out_page(self):
            box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=16)
            box.set_halign(Gtk.Align.CENTER)
            box.set_valign(Gtk.Align.CENTER)

            lock_icon = Gtk.Label(label="🔒")
            lock_icon.add_css_class("lock-lockout-icon")
            box.append(lock_icon)

            too_many = Gtk.Label(label="Too many attempts")
            too_many.add_css_class("lock-lockout-title")
            box.append(too_many)

            self._countdown_lbl = Gtk.Label(label="Try again in 0s")
            self._countdown_lbl.add_css_class("lock-countdown")
            box.append(self._countdown_lbl)

            self._stack.add_named(box, "locked_out")

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
                self._auth_time_lbl.set_label(time_str)
                self._auth_date_lbl.set_label(date_str)
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
            self._stack.set_visible_child_name(new_state)
            if new_state == "auth":
                self._error_lbl.set_visible(False)
                self._error_lbl.set_label("")
                self._pw_entry.set_text("")
                self._pw_entry.remove_css_class("lock-password-shake")
                GLib.idle_add(self._pw_entry.grab_focus)

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

            # Shake animation via CSS class toggle
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
