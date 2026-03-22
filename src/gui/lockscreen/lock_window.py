"""
src/gui/lockscreen/lock_window.py
Full-screen Wayland lock screen window.

Uses gtk4-layer-shell OVERLAY + KEYBOARD_MODE_EXCLUSIVE to grab all input.
States: clock → auth → error → locked_out
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
    """Format a datetime as 'Weekday, Month Day' for the date line."""
    return dt.strftime("%A, %B %-d")


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
        "clock"      — idle display: large clock + hint
        "auth"       — password entry visible
        "error"      — shake + wrong-password label
        "locked_out" — countdown to next attempt
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
            self._initials = _get_initials(self.username)
            self._hint_visible = True

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

            self._build()
            self._start_clock()

            # Click anywhere → show auth
            click = Gtk.GestureClick()
            click.connect("pressed", self._on_click)
            self.add_controller(click)

            # Key press → show auth + capture input
            key_ctrl = Gtk.EventControllerKey()
            key_ctrl.connect("key-pressed", self._on_key)
            self.add_controller(key_ctrl)

        # -------------------------------------------------------------------
        # UI construction
        # -------------------------------------------------------------------

        def _build(self):
            """Build the overlay stack: wallpaper → dim → content."""
            root = Gtk.Overlay()
            self.set_child(root)

            # Bottom layer: blurred wallpaper placeholder
            self._wallpaper_pic = Gtk.Picture()
            self._wallpaper_pic.set_hexpand(True)
            self._wallpaper_pic.set_vexpand(True)
            self._wallpaper_pic.add_css_class("lock-wallpaper")
            root.set_child(self._wallpaper_pic)

            # Dim overlay
            dim_box = Gtk.Box()
            dim_box.set_hexpand(True)
            dim_box.set_vexpand(True)
            dim_box.add_css_class("lock-dim")
            root.add_overlay(dim_box)

            # Content stack (clock / auth / error / locked_out)
            self._stack = Gtk.Stack()
            self._stack.set_transition_type(Gtk.StackTransitionType.CROSSFADE)
            self._stack.set_transition_duration(200)
            self._stack.set_halign(Gtk.Align.CENTER)
            self._stack.set_valign(Gtk.Align.CENTER)
            root.add_overlay(self._stack)

            self._build_clock_page()
            self._build_auth_page()
            self._build_locked_out_page()

            self._stack.set_visible_child_name("clock")

        def _avatar_label(self) -> Gtk.Label:
            lbl = Gtk.Label(label=self._initials)
            lbl.add_css_class("lock-avatar")
            return lbl

        def _build_clock_page(self):
            box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
            box.set_halign(Gtk.Align.CENTER)
            box.set_valign(Gtk.Align.CENTER)
            box.add_css_class("lock-clock-page")

            box.append(self._avatar_label())

            self._clock_user_lbl = Gtk.Label(label=self.username)
            self._clock_user_lbl.add_css_class("lock-username")
            box.append(self._clock_user_lbl)

            self._time_lbl = Gtk.Label(label="00:00")
            self._time_lbl.add_css_class("lock-time")
            box.append(self._time_lbl)

            self._date_lbl = Gtk.Label(label="")
            self._date_lbl.add_css_class("lock-date")
            box.append(self._date_lbl)

            self._hint_lbl = Gtk.Label(label="Click to unlock")
            self._hint_lbl.add_css_class("lock-hint")
            box.append(self._hint_lbl)

            self._stack.add_named(box, "clock")

        def _build_auth_page(self):
            box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=16)
            box.set_halign(Gtk.Align.CENTER)
            box.set_valign(Gtk.Align.CENTER)
            box.add_css_class("lock-auth-page")

            box.append(self._avatar_label())

            user_lbl = Gtk.Label(label=self.username)
            user_lbl.add_css_class("lock-username")
            box.append(user_lbl)

            self._auth_time_lbl = Gtk.Label(label="00:00")
            self._auth_time_lbl.add_css_class("lock-time-small")
            box.append(self._auth_time_lbl)

            # Password entry row
            entry_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=0)
            entry_row.set_halign(Gtk.Align.CENTER)
            entry_row.add_css_class("lock-entry-row")

            self._pw_entry = Gtk.PasswordEntry()
            self._pw_entry.set_placeholder_text("Enter password")
            self._pw_entry.set_size_request(300, -1)
            self._pw_entry.add_css_class("lock-password-entry")
            self._pw_entry.set_show_peek_icon(True)
            self._pw_entry.connect("activate", self._on_entry_activate)
            entry_row.append(self._pw_entry)
            box.append(entry_row)

            # Error message label (hidden by default)
            self._error_lbl = Gtk.Label(label="")
            self._error_lbl.add_css_class("lock-error-label")
            self._error_lbl.set_visible(False)
            box.append(self._error_lbl)

            # Cancel button
            cancel_btn = Gtk.Button(label="Cancel")
            cancel_btn.add_css_class("lock-cancel-btn")
            cancel_btn.set_halign(Gtk.Align.CENTER)
            cancel_btn.connect("clicked", self._on_cancel)
            box.append(cancel_btn)

            self._stack.add_named(box, "auth")

        def _build_locked_out_page(self):
            box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=16)
            box.set_halign(Gtk.Align.CENTER)
            box.set_valign(Gtk.Align.CENTER)
            box.add_css_class("lock-lockedout-page")

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
        # Clock + countdown timer
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
                    # Lockout expired — return to auth
                    self._set_state("auth")

            # Hint blink
            if self.state == "clock":
                self._hint_visible = not self._hint_visible
                self._hint_lbl.set_opacity(1.0 if self._hint_visible else 0.0)

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
                self._pw_entry.add_css_class("lock-password-entry")
                self._pw_entry.remove_css_class("lock-password-shake")
                GLib.idle_add(self._pw_entry.grab_focus)

        # -------------------------------------------------------------------
        # Input handlers
        # -------------------------------------------------------------------

        def _on_click(self, *_):
            if self.state == "clock":
                self._set_state("auth")
            elif self.state == "error":
                self._set_state("auth")

        def _on_key(self, ctrl, keyval, keycode, state) -> bool:
            if self.state == "clock":
                # Any printable key shows auth and feeds the keypress
                self._set_state("auth")
                return True

            if self.state in ("auth", "error"):
                if keyval == Gdk.KEY_Return or keyval == Gdk.KEY_KP_Enter:
                    self._try_auth()
                    return True
                if keyval == Gdk.KEY_Escape:
                    # Clear password and return to clock view
                    self._pw_entry.set_text("")
                    self._set_state("clock")
                    return True

            if self.state == "locked_out":
                return True   # consume all input during lockout

            return True       # ALWAYS consume — no bypass

        def _on_entry_activate(self, *_):
            self._try_auth()

        def _on_cancel(self, *_):
            self._pw_entry.set_text("")
            self._set_state("clock")

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
                f"Wrong password  (attempt {attempts})"
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
        # Pure-logic mirrors (for symmetry / test hooks)
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
