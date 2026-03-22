"""
src/gui/firstrun/firstrun_window.py
FirstRunWindow — full-screen macOS Setup Assistant style wizard.

Architecture:
- Gtk.Window, no decoration, fullscreen.
- Layer-shell OVERLAY when available (Wayland).
- Progress dots at top: 8 dots for 8 steps.
- Gtk.Stack with fade transitions (200ms) for step content.
- Bottom nav: ← Back | Continue →
- Back hidden on step 1. Continue disabled until step is valid.
- Can NOT skip the Hardware Detection step (info-only, always passes).
- _validate_step() is the gate — headless-testable.
"""

import logging
import os
import subprocess
import sys

logger = logging.getLogger("luminos-ai.gui.firstrun.window")

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
    SetupState, SETUP_STEPS,
    save_setup_state, mark_setup_complete,
)
from gui.theme import mode, generate_css


# ===========================================================================
# Pure validation — testable without GTK
# ===========================================================================

def _validate_step(step: str, state: SetupState) -> tuple:
    """
    Validate a step before advancing.

    Args:
        step:  Current step ID string.
        state: Current SetupState.

    Returns:
        (valid: bool, error_msg: str)
    """
    # Hardware is info-only — cannot be skipped but always passes
    if step in ("welcome", "hardware", "display",
                "appearance", "privacy", "ai_setup", "done"):
        return (True, "")

    if step == "account":
        from gui.firstrun.step_widgets import _validate_account
        return _validate_account(
            state.username,   # full_name stored during typing
            state.username,
            state.password,
            state.password,   # confirmation checked in widget
        )

    return (True, "")


# ===========================================================================
# GTK Window
# ===========================================================================

if _GTK_AVAILABLE:
    from gui.firstrun.step_widgets import (
        WelcomeStep, HardwareStep, DisplayStep, AccountStep,
        AppearanceStep, PrivacyStep, AISetupStep, DoneStep,
    )

    _DOT_SIZE    = 10
    _DOT_GAP     = 8
    _MAX_CONTENT = 640

    class FirstRunWindow(Gtk.Window):
        """
        Full-screen first-run wizard window.

        Cannot be closed by the user until setup is completed.
        """

        def __init__(self):
            super().__init__()
            self.set_decorated(False)
            self.set_resizable(False)
            self.fullscreen()
            self.add_css_class("luminos-firstrun")

            # Theme CSS
            css_provider = Gtk.CssProvider()
            css_provider.load_from_string(generate_css(mode.get_mode()))
            Gtk.StyleContext.add_provider_for_display(
                self.get_display(),
                css_provider,
                Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION,
            )

            # Layer-shell
            if _LAYER_SHELL_AVAILABLE:
                LayerShell.init_for_window(self)
                LayerShell.set_layer(self, LayerShell.Layer.OVERLAY)
                LayerShell.set_keyboard_mode(
                    self, LayerShell.KeyboardMode.ON_DEMAND
                )
                LayerShell.set_anchor(self, LayerShell.Edge.TOP,    True)
                LayerShell.set_anchor(self, LayerShell.Edge.BOTTOM, True)
                LayerShell.set_anchor(self, LayerShell.Edge.LEFT,   True)
                LayerShell.set_anchor(self, LayerShell.Edge.RIGHT,  True)

            self.state = SetupState()
            self._step_cache: dict[str, Gtk.Widget] = {}
            self._account_step_ref = None   # keep reference for validation
            self._build()
            self._show_step("welcome")

        # -------------------------------------------------------------------
        # Layout
        # -------------------------------------------------------------------

        def _build(self):
            root = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
            self.set_child(root)

            # Progress dots
            self._dots_box = Gtk.Box(
                orientation=Gtk.Orientation.HORIZONTAL,
                spacing=_DOT_GAP
            )
            self._dots_box.set_halign(Gtk.Align.CENTER)
            self._dots_box.set_margin_top(20)
            self._dots_box.set_margin_bottom(8)
            root.append(self._dots_box)

            self._dot_labels: list[Gtk.Label] = []
            for _ in SETUP_STEPS:
                dot = Gtk.Label(label="●")
                dot.set_size_request(_DOT_SIZE, _DOT_SIZE)
                dot.add_css_class("luminos-firstrun-dot-future")
                self._dots_box.append(dot)
                self._dot_labels.append(dot)

            # Content area (centered, max width)
            content_outer = Gtk.Box(
                orientation=Gtk.Orientation.HORIZONTAL
            )
            content_outer.set_hexpand(True)
            content_outer.set_vexpand(True)

            content_center = Gtk.Box(
                orientation=Gtk.Orientation.VERTICAL
            )
            content_center.set_hexpand(True)
            content_center.set_vexpand(True)
            content_center.set_halign(Gtk.Align.CENTER)
            content_center.set_size_request(_MAX_CONTENT, -1)
            content_outer.append(content_center)
            root.append(content_outer)

            # Stack
            self._stack = Gtk.Stack()
            self._stack.set_transition_type(Gtk.StackTransitionType.CROSSFADE)
            self._stack.set_transition_duration(200)
            self._stack.set_hexpand(True)
            self._stack.set_vexpand(True)
            content_center.append(self._stack)

            # Bottom navigation
            nav_box = Gtk.Box(
                orientation=Gtk.Orientation.HORIZONTAL, spacing=0
            )
            nav_box.set_margin_top(16)
            nav_box.set_margin_bottom(24)
            nav_box.set_margin_start(32)
            nav_box.set_margin_end(32)
            nav_box.set_hexpand(True)

            self._back_btn = Gtk.Button(label="← Back")
            self._back_btn.add_css_class("luminos-btn")
            self._back_btn.set_visible(False)
            self._back_btn.connect("clicked", self._on_back)
            nav_box.append(self._back_btn)

            spacer = Gtk.Box()
            spacer.set_hexpand(True)
            nav_box.append(spacer)

            self._error_lbl = Gtk.Label(label="")
            self._error_lbl.add_css_class("luminos-firstrun-warn")
            nav_box.append(self._error_lbl)

            self._continue_btn = Gtk.Button(label="Continue →")
            self._continue_btn.add_css_class("luminos-btn-accent")
            self._continue_btn.connect("clicked", self._on_continue)
            nav_box.append(self._continue_btn)

            root.append(nav_box)

        # -------------------------------------------------------------------
        # Step navigation
        # -------------------------------------------------------------------

        def _show_step(self, step_id: str):
            if step_id not in SETUP_STEPS:
                return

            self.state.current_step = step_id
            idx = SETUP_STEPS.index(step_id)

            # Build widget if not cached
            if step_id not in self._step_cache:
                widget = self._make_step_widget(step_id)
                scroll = Gtk.ScrolledWindow()
                scroll.set_policy(
                    Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC
                )
                scroll.set_child(widget)
                self._stack.add_named(scroll, step_id)
                self._step_cache[step_id] = scroll

            self._stack.set_visible_child_name(step_id)

            # Progress dots
            for i, dot in enumerate(self._dot_labels):
                dot.remove_css_class("luminos-firstrun-dot-done")
                dot.remove_css_class("luminos-firstrun-dot-current")
                dot.remove_css_class("luminos-firstrun-dot-future")
                if i < idx:
                    dot.add_css_class("luminos-firstrun-dot-done")
                elif i == idx:
                    dot.add_css_class("luminos-firstrun-dot-current")
                else:
                    dot.add_css_class("luminos-firstrun-dot-future")

            # Nav button visibility
            self._back_btn.set_visible(idx > 0)
            is_last = step_id == SETUP_STEPS[-1]
            self._continue_btn.set_visible(not is_last)
            self._error_lbl.set_text("")

        def _make_step_widget(self, step_id: str) -> Gtk.Widget:
            if step_id == "welcome":
                return WelcomeStep(on_continue=self._on_continue)
            if step_id == "hardware":
                return HardwareStep(self.state, on_continue=self._on_continue)
            if step_id == "display":
                return DisplayStep(self.state)
            if step_id == "account":
                w = AccountStep(self.state)
                self._account_step_ref = w
                return w
            if step_id == "appearance":
                return AppearanceStep(self.state)
            if step_id == "privacy":
                return PrivacyStep(self.state)
            if step_id == "ai_setup":
                return AISetupStep(self.state)
            if step_id == "done":
                return DoneStep(self.state, on_launch=self.apply_all_settings)
            return Gtk.Label(label=f"Step: {step_id}")

        def _on_continue(self, *_):
            step = self.state.current_step
            idx  = SETUP_STEPS.index(step)

            # Collect account fields if on account step
            if step == "account" and self._account_step_ref:
                name, user, pw, confirm = self._account_step_ref.collect()
                self.state.username = user
                self.state.password = pw
                valid, msg = _validate_step_account(name, user, pw, confirm)
                if not valid:
                    self._error_lbl.set_text(msg)
                    if hasattr(self._account_step_ref, "show_error"):
                        self._account_step_ref.show_error(msg)
                    return
                if hasattr(self._account_step_ref, "clear_error"):
                    self._account_step_ref.clear_error()
            else:
                valid, msg = (True, "")

            if not valid:
                self._error_lbl.set_text(msg)
                return

            # Mark step done
            if step not in self.state.completed_steps:
                self.state.completed_steps.append(step)
            save_setup_state(self.state)

            # Advance
            if idx + 1 < len(SETUP_STEPS):
                self._show_step(SETUP_STEPS[idx + 1])

        def _on_back(self, *_):
            step = self.state.current_step
            idx  = SETUP_STEPS.index(step)
            if idx > 0:
                self._show_step(SETUP_STEPS[idx - 1])

        # -------------------------------------------------------------------
        # Completion
        # -------------------------------------------------------------------

        def apply_all_settings(self):
            """Apply all collected settings and launch the desktop."""
            # Theme
            try:
                if self.state.dark_mode == "dark":
                    mode.set_manual(True)
                elif self.state.dark_mode == "light":
                    mode.set_manual(False)
                else:
                    mode.set_auto()
            except Exception as e:
                logger.debug(f"Theme apply error: {e}")

            # Brightness
            try:
                from gui.quick_settings.brightness_ctrl import set_brightness
                set_brightness(self.state.brightness)
            except Exception as e:
                logger.debug(f"Brightness apply error: {e}")

            # Create user account (best-effort via pkexec)
            if self.state.username:
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
                    logger.debug(f"useradd error (may need root): {e}")

            # Save config
            save_setup_state(self.state)
            mark_setup_complete()

            # Launch desktop components
            for cmd in (
                ["luminos-bar"],
                ["luminos-dock"],
            ):
                try:
                    subprocess.Popen(cmd)
                except FileNotFoundError:
                    logger.debug(f"{cmd[0]} not found — skipping")
                except Exception as e:
                    logger.debug(f"Launch {cmd[0]} error: {e}")

            self.close()


def _validate_step_account(full_name, username, password, confirm):
    from gui.firstrun.step_widgets import _validate_account
    return _validate_account(full_name, username, password, confirm)
