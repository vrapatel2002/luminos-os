"""
src/gui/firstrun/step_widgets.py
One GTK widget class per First Run Setup step.

Pure static methods are extracted for headless testing:
  WelcomeStep._get_tagline()
  AccountStep._generate_username(full_name)
  AccountStep._check_password_strength(pw)
  AccountStep._validate_account(name, user, pw, confirm)
  DoneStep._build_summary(state)

GTK guard: all widget classes defined only when _GTK_AVAILABLE.
Headless stubs allow import without display server.
"""

import logging
import os
import re
import sys

logger = logging.getLogger("luminos-ai.gui.firstrun.steps")

try:
    import gi
    gi.require_version("Gtk", "4.0")
    from gi.repository import Gtk, GLib, Pango
    _GTK_AVAILABLE = True
except (ImportError, ValueError):
    _GTK_AVAILABLE = False

_SRC = os.path.join(os.path.dirname(__file__), "..", "..")
if _SRC not in sys.path:
    sys.path.insert(0, _SRC)

from gui.firstrun.firstrun_state import SetupState, SETUP_STEPS


# ===========================================================================
# Pure helpers — testable without GTK
# ===========================================================================

def _get_tagline() -> str:
    """Return the Luminos tagline shown on the Welcome step."""
    return "AI-native. Security-first. Yours."


def _generate_username(full_name: str) -> str:
    """
    Auto-generate a Unix username from a full name.

    Converts to lowercase, removes non-alphanumeric characters,
    collapses spaces. Falls back to 'luminos' if empty.

    Args:
        full_name: Display name entered by the user.

    Returns:
        Sanitized lowercase username string.
    """
    name = full_name.strip().lower()
    # Take first word as username base
    first = name.split()[0] if name.split() else ""
    # Remove non-alphanumeric
    sanitized = re.sub(r"[^a-z0-9]", "", first)
    return sanitized or "luminos"


def _check_password_strength(password: str) -> str:
    """
    Rate password strength based on length and complexity.

    Args:
        password: The password string to evaluate.

    Returns:
        One of: "Weak", "Fair", "Strong", "Very Strong".
    """
    length  = len(password)
    has_upper  = bool(re.search(r"[A-Z]", password))
    has_lower  = bool(re.search(r"[a-z]", password))
    has_digit  = bool(re.search(r"\d",    password))
    has_symbol = bool(re.search(r"[^A-Za-z0-9]", password))

    complexity = sum([has_upper, has_lower, has_digit, has_symbol])

    if length < 6 or complexity < 2:
        return "Weak"
    # Fair: short and not all complexity types present
    if complexity < 4 and length < 8:
        return "Fair"
    # Very Strong: long and maximally complex
    if length >= 12 and complexity >= 4:
        return "Very Strong"
    # Strong: long enough OR all 4 complexity types
    if length >= 8 or complexity >= 4:
        return "Strong"
    return "Fair"


def _validate_account(full_name: str, username: str,
                       password: str, confirm: str) -> tuple:
    """
    Validate account step inputs.

    Args:
        full_name: User's display name.
        username:  Unix username.
        password:  Password.
        confirm:   Password confirmation.

    Returns:
        Tuple of (valid: bool, error_msg: str).
    """
    if not full_name.strip():
        return (False, "Full name cannot be empty.")
    if not username.strip():
        return (False, "Username cannot be empty.")
    if re.search(r"[^a-z0-9_-]", username):
        return (False, "Username may only contain lowercase letters, digits, _ and -.")
    if len(password) < 6:
        return (False, "Password must be at least 6 characters.")
    if password != confirm:
        return (False, "Passwords do not match.")
    return (True, "")


def _build_summary(state: SetupState) -> str:
    """
    Build the completion summary text shown on the Done step.

    Args:
        state: The final SetupState with all user choices.

    Returns:
        Multi-line summary string.
    """
    grade = getattr(state, "_hw_grade", "B")
    lines = [
        f"Account:     {state.username or '(not set)'}",
        f"Theme:       {state.dark_mode.capitalize()}",
        f"Accent:      {state.accent_color}",
        f"Scaling:     {state.scaling}",
        f"HIVE AI:     {'Enabled' if state.hive_enabled else 'Disabled'}",
        f"Telemetry:   {'On' if state.telemetry_enabled else 'Off (recommended)'}",
        f"NPU:         {'Detected' if state.npu_detected else 'Not found'}",
        f"GPU:         {'Detected' if state.nvidia_detected else 'Not found'}",
        f"HW Grade:    {grade}",
    ]
    return "\n".join(lines)


# ===========================================================================
# Accent color presets (shared across Appearance and Account steps)
# ===========================================================================

_ACCENT_PRESETS = [
    "#0a84ff", "#30d158", "#ff453a", "#ff9f0a",
    "#bf5af2", "#64d2ff", "#ff375f", "#ffd60a",
]

_AVATAR_COLORS = [
    "#0a84ff", "#30d158", "#ff453a", "#ff9f0a",
    "#bf5af2", "#64d2ff", "#ac8e68", "#6c6c70",
]


# ===========================================================================
# GTK Widgets
# ===========================================================================

if _GTK_AVAILABLE:

    # -----------------------------------------------------------------------
    # WelcomeStep
    # -----------------------------------------------------------------------

    class WelcomeStep(Gtk.Box):
        """
        Step 1 — Full-screen welcome with Luminos branding.
        """

        @staticmethod
        def _get_tagline() -> str:
            return _get_tagline()

        def __init__(self, on_continue):
            super().__init__(
                orientation=Gtk.Orientation.VERTICAL, spacing=24
            )
            self.set_halign(Gtk.Align.CENTER)
            self.set_valign(Gtk.Align.CENTER)
            self.set_margin_top(60)
            self.set_margin_bottom(60)

            # Logo
            logo = Gtk.Label(label="◉")
            logo.add_css_class("luminos-firstrun-logo")
            self.append(logo)

            # Title
            title = Gtk.Label(label="Welcome to Luminos")
            title.add_css_class("luminos-firstrun-title")
            self.append(title)

            # Tagline
            tag = Gtk.Label(label=_get_tagline())
            tag.add_css_class("luminos-firstrun-tagline")
            self.append(tag)

            # Body
            body = Gtk.Label(
                label=(
                    "Luminos is an AI-native operating system built for\n"
                    "security, performance, and total user control.\n"
                    "Let's take a few minutes to set things up your way."
                )
            )
            body.set_justify(Gtk.Justification.CENTER)
            body.add_css_class("luminos-firstrun-body")
            self.append(body)

            # CTA button
            btn = Gtk.Button(label="Get Started →")
            btn.add_css_class("luminos-firstrun-cta")
            btn.set_halign(Gtk.Align.CENTER)
            btn.connect("clicked", lambda *_: on_continue())
            self.append(btn)

    # -----------------------------------------------------------------------
    # HardwareStep
    # -----------------------------------------------------------------------

    class HardwareStep(Gtk.Box):
        """
        Step 2 — Hardware detection with progress spinner then results grid.
        """

        def __init__(self, state: SetupState, on_continue):
            super().__init__(
                orientation=Gtk.Orientation.VERTICAL, spacing=20
            )
            self.set_halign(Gtk.Align.CENTER)
            self.set_valign(Gtk.Align.CENTER)
            self._state = state
            self._hw    = None
            self._on_continue = on_continue
            self._build_scanning_view()

        def _build_scanning_view(self):
            self._spinner_box = Gtk.Box(
                orientation=Gtk.Orientation.VERTICAL, spacing=16
            )
            self._spinner_box.set_halign(Gtk.Align.CENTER)

            self._spinner = Gtk.Spinner()
            self._spinner.set_size_request(48, 48)
            self._spinner.start()
            self._spinner_box.append(self._spinner)

            scanning_lbl = Gtk.Label(label="Detecting your hardware…")
            scanning_lbl.add_css_class("luminos-firstrun-subtitle")
            self._spinner_box.append(scanning_lbl)

            self.append(self._spinner_box)
            self._results_box = Gtk.Box(
                orientation=Gtk.Orientation.VERTICAL, spacing=12
            )
            self._results_box.set_visible(False)
            self.append(self._results_box)

            # Start detection in background thread
            import threading
            t = threading.Thread(target=self._do_detect, daemon=True)
            t.start()

        def _do_detect(self):
            from gui.firstrun.hardware_detector import detect_all, get_readiness_score
            hw    = detect_all()
            score = get_readiness_score(hw)
            GLib.idle_add(self._show_results, hw, score)

        def _show_results(self, hw: dict, score: dict):
            self._hw = hw
            self._spinner.stop()
            self._spinner_box.set_visible(False)

            # Update state
            self._state.npu_detected    = score["npu_ready"]
            self._state.nvidia_detected = score["ai_ready"]
            setattr(self._state, "_hw_grade", score["grade"])

            title = Gtk.Label(label="Hardware Detected")
            title.add_css_class("luminos-firstrun-subtitle")
            title.set_halign(Gtk.Align.START)
            self._results_box.append(title)

            grid = Gtk.Grid()
            grid.set_row_spacing(8)
            grid.set_column_spacing(32)

            rows = [
                ("CPU",    hw["cpu"]["name"],
                 f"{hw['cpu']['cores']} cores",    True),
                ("RAM",    f"{hw['ram']['total_gb']} GB", "", True),
                ("NPU",    hw["npu"]["name"] or "Not found",
                 f"{hw['npu']['tops']} TOPS" if hw["npu"]["detected"] else "",
                 hw["npu"]["detected"]),
                ("iGPU",   hw["igpu"]["name"] or "Not found",
                 hw["igpu"]["driver"] or "", hw["igpu"]["detected"]),
                ("GPU",    hw["nvidia"]["name"] or "Not found",
                 f"{hw['nvidia']['vram_gb']} GB" if hw["nvidia"]["detected"] else "",
                 hw["nvidia"]["detected"]),
                ("Storage",f"{hw['storage']['total_gb']} GB ({hw['storage']['type']})",
                 f"{hw['storage']['free_gb']} GB free", True),
                ("Zone 2", "Wine64 ready" if hw["wine_available"] else "Not available",
                 "", hw["wine_available"]),
                ("Zone 3", "KVM + Firecracker" if hw["zone3_ready"] else "Not available",
                 "", hw.get("zone3_ready", False)),
            ]

            # Patch zone3_ready into hw for the row lookup
            hw["zone3_ready"] = score["zone3_ready"]
            rows[-1] = ("Zone 3",
                        "KVM + Firecracker" if score["zone3_ready"] else "Not available",
                        "", score["zone3_ready"])

            for r, (label, value, detail, ok) in enumerate(rows):
                key_lbl = Gtk.Label(label=label)
                key_lbl.add_css_class("luminos-qs-dim")
                key_lbl.set_halign(Gtk.Align.START)
                grid.attach(key_lbl, 0, r, 1, 1)

                val_text = value + (f"  {detail}" if detail else "")
                val_lbl = Gtk.Label(label=val_text)
                val_lbl.set_halign(Gtk.Align.START)
                grid.attach(val_lbl, 1, r, 1, 1)

                badge = Gtk.Label(label="✓" if ok else "✗")
                badge.add_css_class("luminos-firstrun-ok" if ok else "luminos-firstrun-warn")
                grid.attach(badge, 2, r, 1, 1)

            self._results_box.append(grid)

            # Grade badge
            grade_lbl = Gtk.Label(
                label=f"Hardware Grade: {score['grade']}  (Score: {score['score']}/100)"
            )
            grade_lbl.add_css_class("luminos-firstrun-grade")
            grade_lbl.set_halign(Gtk.Align.START)
            self._results_box.append(grade_lbl)

            # Issues
            if score["issues"]:
                issues_lbl = Gtk.Label(
                    label="\n".join(f"⚠ {i}" for i in score["issues"])
                )
                issues_lbl.add_css_class("luminos-firstrun-warn")
                issues_lbl.set_halign(Gtk.Align.START)
                self._results_box.append(issues_lbl)

            self._results_box.set_visible(True)

    # -----------------------------------------------------------------------
    # DisplayStep
    # -----------------------------------------------------------------------

    class DisplayStep(Gtk.Box):
        """Step 3 — Brightness and scaling setup."""

        def __init__(self, state: SetupState):
            super().__init__(
                orientation=Gtk.Orientation.VERTICAL, spacing=20
            )
            self.set_halign(Gtk.Align.CENTER)
            self.set_valign(Gtk.Align.CENTER)
            self._state = state
            self._build()

        def _build(self):
            title = Gtk.Label(label="Display Setup")
            title.add_css_class("luminos-firstrun-subtitle")
            title.set_halign(Gtk.Align.START)
            self.append(title)

            # Brightness
            bright_lbl = Gtk.Label(label="Brightness")
            bright_lbl.set_halign(Gtk.Align.START)
            self.append(bright_lbl)

            bright_row = Gtk.Box(
                orientation=Gtk.Orientation.HORIZONTAL, spacing=12
            )
            self._bright_slider = Gtk.Scale.new_with_range(
                Gtk.Orientation.HORIZONTAL, 5, 100, 1
            )
            self._bright_slider.set_value(self._state.brightness)
            self._bright_slider.set_hexpand(True)
            self._bright_slider.set_draw_value(True)
            self._bright_slider.connect("value-changed", self._on_bright)
            bright_row.append(self._bright_slider)
            self.append(bright_row)

            self.append(Gtk.Separator())

            # Scaling
            scale_lbl = Gtk.Label(label="Display Scaling")
            scale_lbl.set_halign(Gtk.Align.START)
            self.append(scale_lbl)

            scale_opts = ["100%", "125%", "150%", "200%"]
            scale_row  = Gtk.Box(
                orientation=Gtk.Orientation.HORIZONTAL, spacing=8
            )
            self._scale_btns: dict[str, Gtk.Button] = {}
            for opt in scale_opts:
                btn = Gtk.Button(label=opt)
                btn.add_css_class(
                    "luminos-btn-accent"
                    if opt == self._state.scaling
                    else "luminos-btn"
                )
                btn.connect("clicked", self._on_scale, opt)
                scale_row.append(btn)
                self._scale_btns[opt] = btn
            self.append(scale_row)

            self.append(Gtk.Separator())

            # Night light placeholder
            night_row = Gtk.Box(
                orientation=Gtk.Orientation.HORIZONTAL, spacing=0
            )
            night_row.set_hexpand(True)
            night_lbl = Gtk.Label(label="Night Light")
            night_lbl.set_hexpand(True)
            night_lbl.set_halign(Gtk.Align.START)
            night_sw = Gtk.Switch()
            night_sw.set_active(False)
            night_sw.set_sensitive(False)
            night_sw.set_tooltip_text("Coming soon")
            night_row.append(night_lbl)
            night_row.append(night_sw)
            self.append(night_row)

        def _on_bright(self, slider):
            self._state.brightness = int(slider.get_value())

        def _on_scale(self, _btn, opt: str):
            self._state.scaling = opt
            for o, btn in self._scale_btns.items():
                if o == opt:
                    btn.remove_css_class("luminos-btn")
                    btn.add_css_class("luminos-btn-accent")
                else:
                    btn.remove_css_class("luminos-btn-accent")
                    btn.add_css_class("luminos-btn")

    # -----------------------------------------------------------------------
    # AccountStep
    # -----------------------------------------------------------------------

    class AccountStep(Gtk.Box):
        """Step 4 — User account creation with avatar, username, password."""

        @staticmethod
        def _generate_username(full_name: str) -> str:
            return _generate_username(full_name)

        @staticmethod
        def _check_password_strength(pw: str) -> str:
            return _check_password_strength(pw)

        @staticmethod
        def _validate_account(full_name, username, password, confirm):
            return _validate_account(full_name, username, password, confirm)

        def __init__(self, state: SetupState):
            super().__init__(
                orientation=Gtk.Orientation.VERTICAL, spacing=16
            )
            self.set_halign(Gtk.Align.CENTER)
            self.set_valign(Gtk.Align.CENTER)
            self._state = state
            self._build()

        def _build(self):
            title = Gtk.Label(label="Create Your Account")
            title.add_css_class("luminos-firstrun-subtitle")
            title.set_halign(Gtk.Align.START)
            self.append(title)

            # Avatar color picker + initials preview
            avatar_row = Gtk.Box(
                orientation=Gtk.Orientation.HORIZONTAL, spacing=16
            )
            self._avatar_preview = Gtk.Label(label="?")
            self._avatar_preview.set_size_request(72, 72)
            self._avatar_preview.add_css_class("luminos-firstrun-avatar")
            avatar_row.append(self._avatar_preview)

            color_grid = Gtk.FlowBox()
            color_grid.set_max_children_per_line(4)
            color_grid.set_selection_mode(Gtk.SelectionMode.NONE)
            for color in _AVATAR_COLORS:
                swatch = Gtk.Button()
                swatch.set_size_request(28, 28)
                swatch.set_tooltip_text(color)
                swatch.add_css_class("luminos-accent-swatch")
                swatch._color = color
                swatch.connect("clicked", self._on_avatar_color, color)
                color_grid.append(swatch)
            avatar_row.append(color_grid)
            self.append(avatar_row)

            # Full name
            self._name_entry = Gtk.Entry()
            self._name_entry.set_placeholder_text("Full Name")
            self._name_entry.connect("changed", self._on_name_changed)
            self.append(self._name_entry)

            # Username
            self._user_entry = Gtk.Entry()
            self._user_entry.set_placeholder_text("Username")
            self._user_entry.connect("changed", self._on_user_changed)
            self.append(self._user_entry)

            # Password
            self._pw_entry = Gtk.PasswordEntry()
            self._pw_entry.set_show_peek_icon(True)
            self._pw_entry.set_placeholder_text("Password")
            self._pw_entry.connect("changed", self._on_pw_changed)
            self.append(self._pw_entry)

            # Password confirm
            self._confirm_entry = Gtk.PasswordEntry()
            self._confirm_entry.set_show_peek_icon(True)
            self._confirm_entry.set_placeholder_text("Confirm Password")
            self.append(self._confirm_entry)

            # Password strength
            self._strength_lbl = Gtk.Label(label="")
            self._strength_lbl.set_halign(Gtk.Align.START)
            self._strength_lbl.add_css_class("luminos-qs-dim")
            self.append(self._strength_lbl)

            # Error label
            self._error_lbl = Gtk.Label(label="")
            self._error_lbl.set_halign(Gtk.Align.START)
            self._error_lbl.add_css_class("luminos-firstrun-warn")
            self.append(self._error_lbl)

        def _on_avatar_color(self, _btn, color: str):
            self._state.avatar_color = color

        def _on_name_changed(self, entry):
            name = entry.get_text()
            self._state.username = _generate_username(name)
            self._user_entry.set_text(self._state.username)
            self._update_avatar_initials(name)

        def _update_avatar_initials(self, name: str):
            parts = name.strip().split()
            if len(parts) >= 2:
                initials = parts[0][0].upper() + parts[-1][0].upper()
            elif parts:
                initials = parts[0][0].upper()
            else:
                initials = "?"
            self._avatar_preview.set_text(initials)

        def _on_user_changed(self, entry):
            text = entry.get_text()
            # Enforce lowercase/no spaces
            cleaned = re.sub(r"[^a-z0-9_-]", "", text.lower())
            if cleaned != text:
                entry.set_text(cleaned)
                entry.set_position(-1)
            self._state.username = cleaned

        def _on_pw_changed(self, entry):
            pw = entry.get_text()
            strength = _check_password_strength(pw)
            self._strength_lbl.set_text(f"Strength: {strength}")

        def show_error(self, msg: str):
            self._error_lbl.set_text(msg)

        def clear_error(self):
            self._error_lbl.set_text("")

        def collect(self) -> tuple:
            """Return (full_name, username, password, confirm) from entries."""
            return (
                self._name_entry.get_text(),
                self._user_entry.get_text(),
                self._pw_entry.get_text(),
                self._confirm_entry.get_text(),
            )

    # -----------------------------------------------------------------------
    # AppearanceStep
    # -----------------------------------------------------------------------

    class AppearanceStep(Gtk.Box):
        """Step 5 — Dark/light/auto theme + accent color."""

        def __init__(self, state: SetupState):
            super().__init__(
                orientation=Gtk.Orientation.VERTICAL, spacing=20
            )
            self.set_halign(Gtk.Align.CENTER)
            self.set_valign(Gtk.Align.CENTER)
            self._state = state
            self._build()

        def _build(self):
            title = Gtk.Label(label="Choose Your Look")
            title.add_css_class("luminos-firstrun-subtitle")
            title.set_halign(Gtk.Align.START)
            self.append(title)

            # Mode cards
            cards_box = Gtk.Box(
                orientation=Gtk.Orientation.HORIZONTAL, spacing=16
            )
            self._mode_btns: dict[str, Gtk.Button] = {}
            for icon, label, mode_id in (
                ("🌙", "Dark",  "dark"),
                ("☀",  "Light", "light"),
                ("🔄", "Auto",  "auto"),
            ):
                btn = self._make_mode_card(icon, label, mode_id)
                cards_box.append(btn)
                self._mode_btns[mode_id] = btn
            self.append(cards_box)
            self._select_mode(self._state.dark_mode)

            self.append(Gtk.Separator())

            # Accent colors
            accent_lbl = Gtk.Label(label="Accent Color")
            accent_lbl.set_halign(Gtk.Align.START)
            self.append(accent_lbl)

            accent_row = Gtk.Box(
                orientation=Gtk.Orientation.HORIZONTAL, spacing=8
            )
            for color in _ACCENT_PRESETS:
                swatch = Gtk.Button()
                swatch.set_size_request(32, 32)
                swatch.set_tooltip_text(color)
                swatch.add_css_class("luminos-accent-swatch")
                swatch.connect("clicked", self._on_accent, color)
                accent_row.append(swatch)
            self.append(accent_row)

        def _make_mode_card(self, icon: str, label: str, mode_id: str) -> Gtk.Button:
            btn = Gtk.Button()
            btn.add_css_class("luminos-power-card")
            inner = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
            inner.set_margin_top(20)
            inner.set_margin_bottom(20)
            inner.set_margin_start(20)
            inner.set_margin_end(20)
            icon_lbl = Gtk.Label(label=icon)
            name_lbl = Gtk.Label(label=label)
            name_lbl.add_css_class("luminos-power-card-name")
            inner.append(icon_lbl)
            inner.append(name_lbl)
            btn.set_child(inner)
            btn.connect("clicked", self._on_mode, mode_id)
            return btn

        def _select_mode(self, mode_id: str):
            self._state.dark_mode = mode_id
            for mid, btn in self._mode_btns.items():
                if mid == mode_id:
                    btn.add_css_class("luminos-btn-accent")
                else:
                    btn.remove_css_class("luminos-btn-accent")

        def _on_mode(self, _btn, mode_id: str):
            self._select_mode(mode_id)

        def _on_accent(self, _btn, color: str):
            self._state.accent_color = color

    # -----------------------------------------------------------------------
    # PrivacyStep
    # -----------------------------------------------------------------------

    class PrivacyStep(Gtk.Box):
        """Step 6 — Privacy principles + opt-in telemetry toggle."""

        def __init__(self, state: SetupState):
            super().__init__(
                orientation=Gtk.Orientation.VERTICAL, spacing=16
            )
            self.set_halign(Gtk.Align.CENTER)
            self.set_valign(Gtk.Align.CENTER)
            self._state = state
            self._build()

        def _build(self):
            title = Gtk.Label(label="Your Privacy Is Protected")
            title.add_css_class("luminos-firstrun-subtitle")
            title.set_halign(Gtk.Align.START)
            self.append(title)

            principles = [
                "✓ Zero telemetry — nothing is sent anywhere",
                "✓ No account required — ever",
                "✓ AI runs locally — never cloud, never shared",
                "✓ Open source — audit every line",
            ]
            for p in principles:
                lbl = Gtk.Label(label=p)
                lbl.set_halign(Gtk.Align.START)
                lbl.add_css_class("luminos-firstrun-principle")
                self.append(lbl)

            self.append(Gtk.Separator())

            # Opt-in telemetry
            toggle_row = Gtk.Box(
                orientation=Gtk.Orientation.HORIZONTAL, spacing=0
            )
            toggle_row.set_hexpand(True)
            tel_lbl = Gtk.Label(
                label="Help improve Luminos\n(crash reports only — anonymous)"
            )
            tel_lbl.set_hexpand(True)
            tel_lbl.set_halign(Gtk.Align.START)
            self._telemetry_switch = Gtk.Switch()
            self._telemetry_switch.set_active(False)  # off by default
            self._telemetry_switch.connect("state-set", self._on_telemetry)
            toggle_row.append(tel_lbl)
            toggle_row.append(self._telemetry_switch)
            self.append(toggle_row)

            # Source code note
            note = Gtk.Label(label="We mean it — verify our source code on GitHub")
            note.add_css_class("luminos-qs-dim")
            note.set_halign(Gtk.Align.START)
            self.append(note)

        def _on_telemetry(self, _sw, state: bool) -> bool:
            self._state.telemetry_enabled = state
            return False

    # -----------------------------------------------------------------------
    # AISetupStep
    # -----------------------------------------------------------------------

    class AISetupStep(Gtk.Box):
        """Step 7 — NPU status + HIVE AI toggle."""

        def __init__(self, state: SetupState):
            super().__init__(
                orientation=Gtk.Orientation.VERTICAL, spacing=20
            )
            self.set_halign(Gtk.Align.CENTER)
            self.set_valign(Gtk.Align.CENTER)
            self._state = state
            self._build()

        def _build(self):
            title = Gtk.Label(label="AI & Intelligence Setup")
            title.add_css_class("luminos-firstrun-subtitle")
            title.set_halign(Gtk.Align.START)
            self.append(title)

            # NPU status card
            npu_card = Gtk.Box(
                orientation=Gtk.Orientation.VERTICAL, spacing=6
            )
            npu_card.add_css_class("luminos-power-card")
            npu_card.set_margin_top(4)
            npu_card.set_margin_bottom(4)

            npu_title = Gtk.Label(
                label="AMD XDNA NPU" if self._state.npu_detected else "NPU"
            )
            npu_title.add_css_class("luminos-power-card-name")
            npu_title.set_halign(Gtk.Align.START)
            npu_card.append(npu_title)

            if self._state.npu_detected:
                npu_body = (
                    "Detected — Sentinel + Classifier will run at ~5W, always on."
                )
            else:
                npu_body = (
                    "Not detected — AI classification will use CPU (slower)."
                )
            npu_desc = Gtk.Label(label=npu_body)
            npu_desc.add_css_class("luminos-qs-dim")
            npu_desc.set_wrap(True)
            npu_desc.set_halign(Gtk.Align.START)
            npu_card.append(npu_desc)
            self.append(npu_card)

            self.append(Gtk.Separator())

            # HIVE toggle
            hive_row = Gtk.Box(
                orientation=Gtk.Orientation.HORIZONTAL, spacing=0
            )
            hive_row.set_hexpand(True)

            hive_text = "Enable HIVE AI models (requires 4 GB+ VRAM)"
            if self._state.nvidia_detected:
                hive_text += " ✓"
            hive_lbl = Gtk.Label(label=hive_text)
            hive_lbl.set_hexpand(True)
            hive_lbl.set_halign(Gtk.Align.START)

            self._hive_switch = Gtk.Switch()
            self._hive_switch.set_active(self._state.hive_enabled)
            self._hive_switch.set_sensitive(self._state.nvidia_detected)
            self._hive_switch.connect("state-set", self._on_hive)
            hive_row.append(hive_lbl)
            hive_row.append(self._hive_switch)
            self.append(hive_row)

            note = Gtk.Label(
                label="AI models load on demand — zero VRAM usage when idle."
            )
            note.add_css_class("luminos-qs-dim")
            note.set_halign(Gtk.Align.START)
            self.append(note)

        def _on_hive(self, _sw, state: bool) -> bool:
            self._state.hive_enabled = state
            return False

    # -----------------------------------------------------------------------
    # DoneStep
    # -----------------------------------------------------------------------

    class DoneStep(Gtk.Box):
        """Step 8 — Completion screen with summary and launch button."""

        @staticmethod
        def _build_summary(state: SetupState) -> str:
            return _build_summary(state)

        def __init__(self, state: SetupState, on_launch):
            super().__init__(
                orientation=Gtk.Orientation.VERTICAL, spacing=20
            )
            self.set_halign(Gtk.Align.CENTER)
            self.set_valign(Gtk.Align.CENTER)
            self._state = state
            self._build(on_launch)

        def _build(self, on_launch):
            # Checkmark
            check = Gtk.Label(label="✓")
            check.add_css_class("luminos-firstrun-checkmark")
            self.append(check)

            # Title
            name_str = self._state.username or "there"
            title = Gtk.Label(label=f"You're all set, {name_str}!")
            title.add_css_class("luminos-firstrun-subtitle")
            self.append(title)

            # Summary
            summary_text = _build_summary(self._state)
            summary_lbl = Gtk.Label(label=summary_text)
            summary_lbl.add_css_class("luminos-qs-dim")
            summary_lbl.set_halign(Gtk.Align.START)
            summary_lbl.set_selectable(True)
            self.append(summary_lbl)

            # Launch button
            btn = Gtk.Button(label="Launch Luminos →")
            btn.add_css_class("luminos-firstrun-cta")
            btn.set_halign(Gtk.Align.CENTER)
            btn.connect("clicked", lambda *_: on_launch())
            self.append(btn)


# ===========================================================================
# Headless stubs
# ===========================================================================

else:
    class WelcomeStep:  # type: ignore[no-redef]
        @staticmethod
        def _get_tagline() -> str:
            return _get_tagline()

    class HardwareStep:  # type: ignore[no-redef]
        pass

    class DisplayStep:  # type: ignore[no-redef]
        pass

    class AccountStep:  # type: ignore[no-redef]
        @staticmethod
        def _generate_username(full_name: str) -> str:
            return _generate_username(full_name)

        @staticmethod
        def _check_password_strength(pw: str) -> str:
            return _check_password_strength(pw)

        @staticmethod
        def _validate_account(full_name, username, password, confirm):
            return _validate_account(full_name, username, password, confirm)

    class AppearanceStep:  # type: ignore[no-redef]
        pass

    class PrivacyStep:  # type: ignore[no-redef]
        pass

    class AISetupStep:  # type: ignore[no-redef]
        pass

    class DoneStep:  # type: ignore[no-redef]
        @staticmethod
        def _build_summary(state: SetupState) -> str:
            return _build_summary(state)
