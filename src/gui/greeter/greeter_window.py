"""
src/gui/greeter/greeter_window.py
Luminos login greeter — full-screen dark login for greetd.

Spec (do not deviate):
- Full screen, dark background
- Large clock center screen (HH:MM, updates every second)
- Date below clock (format: Tuesday, March 31 2026)
- Press Enter → if account has password: slide in password input field
- Press Enter → if no password: launch Hyprland session immediately
- No username list visible at any point
- No visible input field until Enter is pressed
- Clean, minimal, dark — no clutter

Auth backend: greetd IPC via greetd_client.py
"""

import logging
import os
import pwd

logger = logging.getLogger(__name__)

try:
    import gi
    gi.require_version("Gtk", "4.0")
    from gi.repository import Gtk, GLib, Gdk
    _GTK_AVAILABLE = True
except (ImportError, ValueError):
    _GTK_AVAILABLE = False

try:
    if _GTK_AVAILABLE:
        gi.require_version("GtkLayerShell", "0.1")
        from gi.repository import GtkLayerShell as LayerShell
        _LAYER_SHELL = True
except (ImportError, ValueError):
    _LAYER_SHELL = False

from gui.greeter.greetd_client import GreetdClient


# ---------------------------------------------------------------------------
# Pure helpers — testable without GTK
# ---------------------------------------------------------------------------

def format_time(dt) -> str:
    """Format a datetime as 'HH:MM'."""
    return dt.strftime("%H:%M")


def format_date(dt) -> str:
    """Format a datetime as 'Tuesday, March 31 2026'."""
    return dt.strftime("%A, %B %-d %Y")


def get_default_user() -> str:
    """Return the login name — default 'luminos'."""
    try:
        return pwd.getpwuid(os.getuid()).pw_name
    except (KeyError, OSError):
        return os.environ.get("USER", "luminos")


# ---------------------------------------------------------------------------
# CSS
# ---------------------------------------------------------------------------

_GREETER_CSS = """
.greeter-bg {
    background-color: #0d0d12;
}

.greeter-time {
    font-size: 96px;
    font-weight: 200;
    font-family: "Inter", "Helvetica Neue", sans-serif;
    color: rgba(255, 255, 255, 0.92);
    letter-spacing: -2px;
}

.greeter-date {
    font-size: 22px;
    font-weight: 400;
    font-family: "Inter", "Helvetica Neue", sans-serif;
    color: rgba(255, 255, 255, 0.50);
    margin-top: 4px;
}

.greeter-hint {
    font-size: 14px;
    font-family: "Inter", sans-serif;
    color: rgba(255, 255, 255, 0.25);
    margin-top: 48px;
}

.greeter-password-entry {
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

.greeter-password-entry:focus {
    border-color: rgba(10, 132, 255, 0.6);
    background-color: rgba(255, 255, 255, 0.08);
    outline: none;
}

.greeter-error {
    font-size: 14px;
    font-family: "Inter", sans-serif;
    color: #ff453a;
    margin-top: 12px;
}

.greeter-password-shake {
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
# Session command
# ---------------------------------------------------------------------------

_SESSION_CMD = ["Hyprland"]


# ===========================================================================
# GTK Window
# ===========================================================================

if _GTK_AVAILABLE:

    class LuminosGreeter(Gtk.Window):
        """
        Full-screen greetd greeter.

        States:
          "clock"  — large clock + date + hint. No input visible.
          "auth"   — password entry visible (slid in after Enter).
          "error"  — wrong password, entry still visible.
        """

        def __init__(self, app=None):
            super().__init__()
            if app:
                self.set_application(app)

            self.set_decorated(False)
            self.set_resizable(False)
            self.fullscreen()

            self._state = "clock"
            self._greetd = GreetdClient()
            self._username = get_default_user()
            self._needs_password = True  # assume yes until greetd says otherwise

            # Layer shell — cover everything
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
            css_provider.load_from_string(_GREETER_CSS)
            Gtk.StyleContext.add_provider_for_display(
                Gdk.Display.get_default(),
                css_provider,
                Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION,
            )

            self._build()
            self._start_clock()

            # Key press handler
            key_ctrl = Gtk.EventControllerKey()
            key_ctrl.connect("key-pressed", self._on_key)
            self.add_controller(key_ctrl)

        # -------------------------------------------------------------------
        # UI construction
        # -------------------------------------------------------------------

        def _build(self):
            # Full-screen dark background
            root = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
            root.set_hexpand(True)
            root.set_vexpand(True)
            root.add_css_class("greeter-bg")
            self.set_child(root)

            # Content container — centered
            self._content = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
            self._content.set_halign(Gtk.Align.CENTER)
            self._content.set_valign(Gtk.Align.CENTER)
            self._content.set_vexpand(True)
            root.append(self._content)

            # Clock
            self._time_lbl = Gtk.Label(label="00:00")
            self._time_lbl.add_css_class("greeter-time")
            self._content.append(self._time_lbl)

            # Date
            self._date_lbl = Gtk.Label(label="")
            self._date_lbl.add_css_class("greeter-date")
            self._content.append(self._date_lbl)

            # Hint (visible in clock state only)
            self._hint_lbl = Gtk.Label(label="Press Enter to unlock")
            self._hint_lbl.add_css_class("greeter-hint")
            self._content.append(self._hint_lbl)

            # Password entry (hidden until Enter pressed)
            self._pw_entry = Gtk.PasswordEntry()
            self._pw_entry.set_placeholder_text("Password")
            self._pw_entry.add_css_class("greeter-password-entry")
            self._pw_entry.set_show_peek_icon(True)
            self._pw_entry.set_visible(False)
            self._pw_entry.connect("activate", self._on_pw_activate)
            self._content.append(self._pw_entry)

            # Error label (hidden)
            self._error_lbl = Gtk.Label(label="")
            self._error_lbl.add_css_class("greeter-error")
            self._error_lbl.set_visible(False)
            self._content.append(self._error_lbl)

        # -------------------------------------------------------------------
        # Clock
        # -------------------------------------------------------------------

        def _start_clock(self):
            self._update_clock()
            GLib.timeout_add_seconds(1, self._update_clock)

        def _update_clock(self) -> bool:
            import datetime
            now = datetime.datetime.now()
            self._time_lbl.set_label(format_time(now))
            self._date_lbl.set_label(format_date(now))
            return True  # GLib.SOURCE_CONTINUE

        # -------------------------------------------------------------------
        # Input handling
        # -------------------------------------------------------------------

        def _on_key(self, ctrl, keyval, keycode, state) -> bool:
            if self._state == "clock":
                if keyval in (Gdk.KEY_Return, Gdk.KEY_KP_Enter):
                    self._initiate_login()
                    return True
                # Consume all other keys in clock state
                return True

            if self._state in ("auth", "error"):
                if keyval == Gdk.KEY_Escape:
                    self._return_to_clock()
                    return True
                # Let the password entry handle other keys
                return False

            return True

        def _on_pw_activate(self, *_):
            """Password entry activated (Enter pressed in entry)."""
            self._submit_password()

        # -------------------------------------------------------------------
        # Login flow
        # -------------------------------------------------------------------

        def _initiate_login(self):
            """
            Start greetd session for the user.
            If greetd responds with auth_message → show password field.
            If greetd responds with success → no password needed, start session.
            """
            if not self._greetd.available:
                # Fallback: assume password needed (for testing without greetd)
                logger.warning("greetd not available — showing password field")
                self._show_password_field()
                return

            try:
                resp = self._greetd.create_session(self._username)
                msg_type = resp.get("type", "")

                if msg_type == "auth_message":
                    # Password required
                    self._needs_password = True
                    self._show_password_field()

                elif msg_type == "success":
                    # No password — start session directly
                    self._needs_password = False
                    self._start_session()

                elif msg_type == "error":
                    self._show_error(resp.get("description", "Login failed"))

                else:
                    logger.warning(f"Unexpected greetd response: {resp}")
                    self._show_password_field()

            except Exception as e:
                logger.error(f"greetd create_session failed: {e}")
                self._show_password_field()

        def _show_password_field(self):
            """Transition from clock to auth state — slide in password field."""
            self._state = "auth"
            self._hint_lbl.set_visible(False)
            self._error_lbl.set_visible(False)
            self._error_lbl.set_label("")
            self._pw_entry.set_text("")
            self._pw_entry.set_visible(True)
            self._pw_entry.remove_css_class("greeter-password-shake")
            GLib.idle_add(self._pw_entry.grab_focus)

        def _submit_password(self):
            """Send password to greetd and handle response."""
            password = self._pw_entry.get_text()

            if not self._greetd.available:
                # Fallback: use PAM directly
                self._try_pam_auth(password)
                return

            try:
                resp = self._greetd.post_auth_response(password)
                msg_type = resp.get("type", "")

                if msg_type == "success":
                    self._start_session()

                elif msg_type == "auth_message":
                    # Another auth prompt (e.g. 2FA) — re-show entry
                    self._pw_entry.set_text("")
                    self._pw_entry.set_placeholder_text(
                        resp.get("auth_message", "Password")
                    )
                    GLib.idle_add(self._pw_entry.grab_focus)

                elif msg_type == "error":
                    self._show_error(
                        resp.get("description", "Authentication failed")
                    )
                    # Cancel session so we can retry
                    try:
                        self._greetd.cancel_session()
                    except Exception:
                        pass
                    self._greetd.close()

                else:
                    self._show_error("Unexpected response")

            except Exception as e:
                logger.error(f"greetd post_auth failed: {e}")
                self._show_error("Authentication error")

        def _try_pam_auth(self, password: str):
            """Fallback PAM auth when greetd is not available."""
            from gui.lockscreen.pam_auth import PAMAuth
            pam = PAMAuth()
            result = pam.authenticate(password)
            if result["success"]:
                # Can't start a greetd session, just exit
                logger.info("PAM auth succeeded (no greetd)")
                self.close()
            else:
                self._show_error("Incorrect password")

        def _start_session(self):
            """Tell greetd to launch the Hyprland session."""
            try:
                resp = self._greetd.start_session(_SESSION_CMD)
                if resp.get("type") == "success":
                    logger.info("Session started — greeter exiting")
                    # greetd will handle the rest; greeter exits
                    raise SystemExit(0)
                else:
                    self._show_error(
                        resp.get("description", "Failed to start session")
                    )
            except SystemExit:
                raise
            except Exception as e:
                logger.error(f"start_session failed: {e}")
                self._show_error("Failed to start session")

        def _show_error(self, message: str):
            """Show error message and shake the password field."""
            self._state = "error"
            self._error_lbl.set_label(message)
            self._error_lbl.set_visible(True)
            self._pw_entry.set_text("")
            self._pw_entry.remove_css_class("greeter-password-shake")
            GLib.idle_add(
                lambda: self._pw_entry.add_css_class("greeter-password-shake")
            )
            GLib.idle_add(self._pw_entry.grab_focus)

        def _return_to_clock(self):
            """Go back to the clock screen, cancel any pending session."""
            self._state = "clock"
            self._pw_entry.set_visible(False)
            self._pw_entry.set_text("")
            self._error_lbl.set_visible(False)
            self._hint_lbl.set_visible(True)

            if self._greetd.available:
                try:
                    self._greetd.cancel_session()
                except Exception:
                    pass
                self._greetd.close()
