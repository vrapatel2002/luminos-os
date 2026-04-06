"""
src/gui/firstrun/firstrun_window.py
Phase 5.9 — First Run Experience window.

Four screens: welcome → account → wallpaper → ready
Transitions:  forward = slide-left 300ms, back = slide-right
Progress:     4 dots at bottom, current highlighted in ACCENT
Close:        not allowed until "Go to Desktop" is pressed

Architecture:
- Gtk.Window, fullscreen, no decoration.
- Layer-shell OVERLAY when available (Wayland).
- Gtk.Stack with SLIDE_LEFT/SLIDE_RIGHT transitions.
- Bottom nav: Back (secondary) on left, Continue (primary) on right.
- Screen 1: no back, no skip.
- Screen 4: no back, "Go to Desktop" instead of Continue.
- On completion: create ~/.config/luminos/first_run_complete, launch desktop.
"""

import logging
import os
import subprocess
import sys

logger = logging.getLogger("luminos.firstrun.window")

try:
    import gi
    gi.require_version("Gtk", "4.0")
    from gi.repository import Gtk, GLib
    _GTK_AVAILABLE = True
except (ImportError, ValueError):
    _GTK_AVAILABLE = False

_LAYER_SHELL_AVAILABLE = False
if _GTK_AVAILABLE:
    try:
        gi.require_version("Gtk4LayerShell", "1.0")
        from gi.repository import Gtk4LayerShell as LayerShell
        _LAYER_SHELL_AVAILABLE = True
    except (ImportError, ValueError):
        pass

_SRC = os.path.join(os.path.dirname(__file__), "..", "..")
if _SRC not in sys.path:
    sys.path.insert(0, _SRC)

from gui.firstrun.firstrun_state import (
    FirstRunState, SCREENS,
    is_complete, mark_complete, save_state, load_state,
)
from gui.firstrun.step_widgets import (
    FIRSTRUN_CSS,
    WelcomeScreen, AccountScreen, WallpaperScreen, ReadyScreen,
    validate_account,
)


# ===========================================================================
# Validation — headless testable
# ===========================================================================

def check_can_advance(screen: str, state: FirstRunState,
                      account_ref=None) -> tuple:
    """
    Return (can_advance: bool, error_msg: str) for a given screen.

    Args:
        screen:      Current screen ID.
        state:       Current FirstRunState.
        account_ref: AccountScreen widget reference (may be None).

    Returns:
        (True, "") if can advance, (False, error_msg) otherwise.
    """
    if screen in ("welcome", "wallpaper", "ready"):
        return (True, "")

    if screen == "account":
        if account_ref is not None:
            name, pw, confirm = account_ref.collect()
        else:
            name, pw, confirm = state.username, state.password, state.password
        return validate_account(name, pw, confirm)

    return (True, "")


# ===========================================================================
# Window
# ===========================================================================

if _GTK_AVAILABLE:

    _DOT_COUNT = len(SCREENS)

    class FirstRunWindow(Gtk.Window):
        """
        Full-screen first-run wizard — 4 screens, slide transitions.
        Cannot be closed by the user until "Go to Desktop" is pressed.
        """

        def __init__(self):
            super().__init__()
            self.set_decorated(False)
            self.set_resizable(False)
            self.fullscreen()

            # Block close until done
            self.connect("close-request", self._block_close)

            # Apply CSS
            css = Gtk.CssProvider()
            css.load_from_string(FIRSTRUN_CSS)
            Gtk.StyleContext.add_provider_for_display(
                self.get_display(), css,
                Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION,
            )

            # Layer-shell — OVERLAY so it sits above everything
            if _LAYER_SHELL_AVAILABLE:
                LayerShell.init_for_window(self)
                LayerShell.set_layer(self, LayerShell.Layer.OVERLAY)
                LayerShell.set_keyboard_mode(
                    self, LayerShell.KeyboardMode.ON_DEMAND
                )
                for edge in (
                    LayerShell.Edge.TOP, LayerShell.Edge.BOTTOM,
                    LayerShell.Edge.LEFT, LayerShell.Edge.RIGHT,
                ):
                    LayerShell.set_anchor(self, edge, True)

            self.state = FirstRunState()
            self._screen_cache: dict[str, Gtk.Widget] = {}
            self._account_ref = None   # AccountScreen ref for validation
            self._done = False

            self._build_ui()
            self._show_screen("welcome")

        # -------------------------------------------------------------------
        # Layout
        # -------------------------------------------------------------------

        def _build_ui(self):
            root = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
            root.add_css_class("fr-root")
            root.set_hexpand(True)
            root.set_vexpand(True)
            self.set_child(root)

            # Content stack (takes all space above nav)
            self._stack = Gtk.Stack()
            self._stack.set_transition_type(Gtk.StackTransitionType.SLIDE_LEFT)
            self._stack.set_transition_duration(300)
            self._stack.set_hexpand(True)
            self._stack.set_vexpand(True)
            root.append(self._stack)

            # Bottom area: progress dots + nav buttons
            bottom = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=SPACE_4)
            bottom.set_margin_start(40)
            bottom.set_margin_end(40)
            bottom.set_margin_bottom(32)
            bottom.set_margin_top(16)
            root.append(bottom)

            # Progress dots (4 dots, centered)
            self._dots_box = Gtk.Box(
                orientation=Gtk.Orientation.HORIZONTAL, spacing=8
            )
            self._dots_box.set_halign(Gtk.Align.CENTER)
            self._dot_labels: list[Gtk.Label] = []
            for _ in range(_DOT_COUNT):
                dot = Gtk.Label(label="●")
                dot.add_css_class("fr-dot")
                self._dots_box.append(dot)
                self._dot_labels.append(dot)
            bottom.append(self._dots_box)

            # Nav row: back (left) | error (center) | continue (right)
            nav = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=0)
            nav.set_hexpand(True)
            bottom.append(nav)

            self._back_btn = Gtk.Button(label="← Back")
            self._back_btn.add_css_class("fr-btn-secondary")
            self._back_btn.set_visible(False)
            self._back_btn.connect("clicked", self._on_back)
            nav.append(self._back_btn)

            spacer = Gtk.Box()
            spacer.set_hexpand(True)
            nav.append(spacer)

            self._error_lbl = Gtk.Label(label="")
            self._error_lbl.add_css_class("fr-error")
            self._error_lbl.set_halign(Gtk.Align.CENTER)
            self._error_lbl.set_hexpand(True)
            nav.append(self._error_lbl)

            spacer2 = Gtk.Box()
            spacer2.set_hexpand(True)
            nav.append(spacer2)

            self._continue_btn = Gtk.Button(label="Continue")
            self._continue_btn.add_css_class("fr-btn-primary")
            self._continue_btn.connect("clicked", self._on_continue)
            nav.append(self._continue_btn)

        # -------------------------------------------------------------------
        # Screen navigation
        # -------------------------------------------------------------------

        def _show_screen(self, screen_id: str):
            if screen_id not in SCREENS:
                return

            self.state.current_screen = screen_id
            idx = SCREENS.index(screen_id)

            # Build widget if not cached
            if screen_id not in self._screen_cache:
                widget = self._make_screen(screen_id)
                self._stack.add_named(widget, screen_id)
                self._screen_cache[screen_id] = widget

            self._stack.set_visible_child_name(screen_id)

            # Fire ready-screen animations
            if screen_id == "ready":
                w = self._screen_cache["ready"]
                if isinstance(w, ReadyScreen):
                    w.start_animations()

            # Update dots
            for i, dot in enumerate(self._dot_labels):
                dot.remove_css_class("fr-dot")
                dot.remove_css_class("fr-dot-current")
                dot.remove_css_class("fr-dot-done")
                if i < idx:
                    dot.add_css_class("fr-dot-done")
                elif i == idx:
                    dot.add_css_class("fr-dot-current")
                else:
                    dot.add_css_class("fr-dot")

            # Nav visibility
            is_welcome = screen_id == "welcome"
            is_ready   = screen_id == "ready"

            self._back_btn.set_visible(not is_welcome and not is_ready)
            self._continue_btn.set_visible(not is_ready)
            self._error_lbl.set_text("")

        def _make_screen(self, screen_id: str) -> Gtk.Widget:
            if screen_id == "welcome":
                return WelcomeScreen(on_get_started=self._on_continue)
            if screen_id == "account":
                w = AccountScreen(self.state)
                self._account_ref = w
                return w
            if screen_id == "wallpaper":
                return WallpaperScreen(self.state)
            if screen_id == "ready":
                return ReadyScreen(on_go_to_desktop=self._on_complete)
            return Gtk.Label(label=screen_id)

        def _on_continue(self, *_):
            screen = self.state.current_screen
            idx    = SCREENS.index(screen)

            # Collect + validate account screen
            if screen == "account" and self._account_ref:
                name, pw, confirm = self._account_ref.collect()
                valid, msg = validate_account(name, pw, confirm)
                if not valid:
                    self._error_lbl.set_text(msg)
                    self._account_ref.show_error(msg)
                    return
                self._account_ref.clear_error()
                self.state.username = name
                self.state.password = pw
            else:
                valid = True

            self._error_lbl.set_text("")
            save_state(self.state)

            # Slide to next screen
            if idx + 1 < len(SCREENS):
                self._stack.set_transition_type(
                    Gtk.StackTransitionType.SLIDE_LEFT
                )
                self._show_screen(SCREENS[idx + 1])

        def _on_back(self, *_):
            screen = self.state.current_screen
            idx    = SCREENS.index(screen)
            if idx > 0:
                self._stack.set_transition_type(
                    Gtk.StackTransitionType.SLIDE_RIGHT
                )
                self._show_screen(SCREENS[idx - 1])

        # -------------------------------------------------------------------
        # Completion
        # -------------------------------------------------------------------

        def _on_complete(self):
            """Called by ReadyScreen 'Go to Desktop' button."""
            self._done = True

            # Apply chosen wallpaper permanently
            self._apply_wallpaper_permanent()

            # Save username/password
            self._create_user()

            # Write completion flag
            mark_complete()
            save_state(self.state)

            # Fade out wizard, start desktop
            self._fade_out_and_launch()

        def _apply_wallpaper_permanent(self):
            """Save wallpaper config so session script can apply it."""
            if not self.state.wallpaper_value:
                return
            try:
                from gui.wallpaper.wallpaper_config import save_config
                wp_type = self.state.wallpaper_type
                wp_val  = self.state.wallpaper_value
                if wp_type == "static":
                    save_config({"type": "image", "value": wp_val})
                elif wp_type == "video":
                    save_config({"type": "video", "value": wp_val})
                elif wp_type == "live":
                    save_config({"type": "live", "value": wp_val})
            except Exception as e:
                logger.debug(f"Wallpaper save error: {e}")

        def _create_user(self):
            """Create OS user account if name was provided (best-effort)."""
            if not self.state.username:
                return
            try:
                subprocess.run(
                    ["pkexec", "useradd", "-m", self.state.username],
                    timeout=10, check=False,
                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                )
                if self.state.password:
                    inp = f"{self.state.username}:{self.state.password}\n"
                    subprocess.run(
                        ["pkexec", "chpasswd"],
                        input=inp.encode(), timeout=10, check=False,
                        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                    )
            except Exception as e:
                logger.debug(f"User creation error: {e}")

        def _fade_out_and_launch(self):
            """Fade out this window then launch desktop components."""
            self._fade_opacity = 1.0
            GLib.timeout_add(16, self._fade_step)

        def _fade_step(self) -> bool:
            self._fade_opacity -= 0.06
            if self._fade_opacity <= 0.0:
                self.set_opacity(0.0)
                self._launch_desktop()
                self.close()
                return GLib.SOURCE_REMOVE
            self.set_opacity(self._fade_opacity)
            return GLib.SOURCE_CONTINUE

        def _launch_desktop(self):
            for cmd in (["luminos-bar"], ["luminos-dock"]):
                try:
                    subprocess.Popen(cmd)
                except FileNotFoundError:
                    logger.debug(f"{cmd[0]} not found — skipping")
                except Exception as e:
                    logger.debug(f"Launch {cmd[0]} error: {e}")

        def _block_close(self, *_) -> bool:
            """Prevent window close until setup is done."""
            return not self._done


# Spacing constant used in _build_ui (imported after module-level constants)
try:
    from gui.theme import SPACE_4
except ImportError:
    SPACE_4 = 16
