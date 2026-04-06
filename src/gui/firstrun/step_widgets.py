"""
src/gui/firstrun/step_widgets.py
Phase 5.9 — Four first-run screens.

Screens:
  WelcomeScreen   — wordmark + tagline + "Get Started"
  AccountScreen   — name + optional password
  WallpaperScreen — 6 thumbnail grid (3×2)
  ReadyScreen     — animated checkmark + staggered text

Pure helpers are headless-testable:
  validate_account(name, pw, confirm) → (bool, str)

GTK guard: widget classes defined only when _GTK_AVAILABLE.
"""

import logging
import os
import re
import sys

logger = logging.getLogger("luminos.firstrun.steps")

try:
    import gi
    gi.require_version("Gtk", "4.0")
    from gi.repository import Gtk, GLib, Gdk, Pango
    _GTK_AVAILABLE = True
except (ImportError, ValueError):
    _GTK_AVAILABLE = False

_SRC = os.path.join(os.path.dirname(__file__), "..", "..")
if _SRC not in sys.path:
    sys.path.insert(0, _SRC)

from gui.firstrun.firstrun_state import FirstRunState, SCREENS
from gui.theme import (
    BG_BASE, BG_SURFACE, BG_ELEVATED, BG_OVERLAY,
    ACCENT, ACCENT_HOVER, ACCENT_PRESSED, ACCENT_SUBTLE,
    TEXT_PRIMARY, TEXT_SECONDARY, TEXT_DISABLED,
    BORDER, BORDER_FOCUS,
    COLOR_ERROR, COLOR_SUCCESS,
    FONT_FAMILY,
    SPACE_2, SPACE_3, SPACE_4, SPACE_6, SPACE_8, SPACE_12,
)


# ===========================================================================
# Pure helpers
# ===========================================================================

def validate_account(name: str, password: str, confirm: str) -> tuple:
    """
    Validate account screen inputs.

    Args:
        name:     Display name entered by user.
        password: Password string (may be empty — it's optional).
        confirm:  Confirm password string.

    Returns:
        (valid: bool, error_msg: str)
    """
    if not name.strip():
        return (False, "Please enter your name.")
    if password and password != confirm:
        return (False, "Passwords don't match.")
    return (True, "")


# ===========================================================================
# Wallpaper definitions (6 items shown in 3×2 grid)
# ===========================================================================

_WALLPAPER_ITEMS = [
    {
        "label": "Dark Space",
        "type":  "static",
        "value": "/usr/share/luminos/wallpapers/dark_space.jpg",
        "color": "#0A0A1F",
    },
    {
        "label": "Minimal Dark",
        "type":  "static",
        "value": "/usr/share/luminos/wallpapers/minimal_dark.jpg",
        "color": "#0F0F0F",
    },
    {
        "label": "Ocean Drift",
        "type":  "video",
        "value": "/usr/share/luminos/wallpapers/ocean_drift.mp4",
        "color": "#003355",
    },
    {
        "label": "City Night",
        "type":  "video",
        "value": "/usr/share/luminos/wallpapers/city_night.mp4",
        "color": "#1A1A2E",
    },
    {
        "label": "Geometric",
        "type":  "live",
        "value": "geometric",
        "color": "#0A1628",
    },
    {
        "label": "Aurora",
        "type":  "live",
        "value": "aurora",
        "color": "#051A12",
    },
]

_TYPE_BADGE = {
    "static": "",
    "video":  "▶",
    "live":   "◈",
}


# ===========================================================================
# CSS for first-run screens
# ===========================================================================

FIRSTRUN_CSS = f"""
/* ---- First Run Window ---- */
.fr-root {{
    background-color: {BG_BASE};
    color: {TEXT_PRIMARY};
    font-family: "Inter", system-ui, sans-serif;
}}

/* ---- Welcome Screen ---- */
.fr-wordmark {{
    color: {TEXT_PRIMARY};
    font-family: "Inter", system-ui, sans-serif;
    font-size: 48px;
    font-weight: 300;
    letter-spacing: -1px;
}}

.fr-tagline {{
    color: {TEXT_SECONDARY};
    font-size: 16px;
    font-weight: 400;
}}

/* ---- Screen Titles ---- */
.fr-title {{
    color: {TEXT_PRIMARY};
    font-size: 24px;
    font-weight: 600;
    letter-spacing: -0.3px;
}}

/* ---- Buttons ---- */
.fr-btn-primary {{
    background-color: {ACCENT};
    color: #FFFFFF;
    border-radius: 8px;
    border: none;
    padding: 10px 32px;
    font-size: 15px;
    font-weight: 500;
    min-height: 40px;
    transition: background-color 100ms ease;
}}
.fr-btn-primary:hover {{
    background-color: {ACCENT_HOVER};
}}
.fr-btn-primary:active {{
    background-color: {ACCENT_PRESSED};
}}

.fr-btn-secondary {{
    background-color: rgba(255,255,255,0.06);
    color: {TEXT_PRIMARY};
    border-radius: 8px;
    border: 1px solid {BORDER};
    padding: 10px 24px;
    font-size: 15px;
    font-weight: 400;
    min-height: 40px;
    transition: background-color 100ms ease;
}}
.fr-btn-secondary:hover {{
    background-color: rgba(255,255,255,0.10);
}}

/* ---- Inputs ---- */
.fr-input {{
    background-color: rgba(255,255,255,0.06);
    color: {TEXT_PRIMARY};
    border-radius: 8px;
    border: 1px solid {BORDER};
    padding: 0 12px;
    font-size: 14px;
    min-height: 42px;
    transition: border-color 150ms ease;
}}
.fr-input:focus {{
    border-color: {BORDER_FOCUS};
}}

/* ---- Skip link ---- */
.fr-skip {{
    color: {TEXT_SECONDARY};
    font-size: 13px;
    background: none;
    border: none;
    padding: 4px 8px;
    text-decoration: underline;
    cursor: pointer;
}}
.fr-skip:hover {{
    color: {TEXT_PRIMARY};
}}

/* ---- Error label ---- */
.fr-error {{
    color: {COLOR_ERROR};
    font-size: 13px;
}}

/* ---- Wallpaper thumbnail ---- */
.fr-thumb {{
    border-radius: 10px;
    border: 2px solid transparent;
    transition: border-color 150ms ease;
    overflow: hidden;
    cursor: pointer;
}}
.fr-thumb-selected {{
    border-color: {ACCENT};
}}
.fr-thumb-label {{
    color: {TEXT_SECONDARY};
    font-size: 12px;
    font-weight: 400;
    margin-top: 4px;
}}

/* ---- Progress dots ---- */
.fr-dot {{
    font-size: 8px;
    color: {TEXT_DISABLED};
    transition: color 200ms ease;
}}
.fr-dot-current {{
    color: {ACCENT};
    font-size: 10px;
}}
.fr-dot-done {{
    color: {TEXT_SECONDARY};
}}

/* ---- Ready screen ---- */
.fr-checkmark {{
    color: {ACCENT};
    font-size: 72px;
    font-weight: 300;
}}
.fr-ready-title {{
    color: {TEXT_PRIMARY};
    font-size: 32px;
    font-weight: 600;
    letter-spacing: -0.5px;
}}
.fr-ready-line {{
    color: {TEXT_SECONDARY};
    font-size: 15px;
    font-weight: 400;
}}
"""


if _GTK_AVAILABLE:

    # =======================================================================
    # Screen 1 — Welcome
    # =======================================================================

    class WelcomeScreen(Gtk.Box):
        """
        Welcome screen — wordmark, tagline, Get Started button.
        Background: solid dark (live wallpaper runs behind window if available).
        """

        def __init__(self, on_get_started):
            super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=0)
            self.set_halign(Gtk.Align.CENTER)
            self.set_valign(Gtk.Align.CENTER)
            self.set_hexpand(True)
            self.set_vexpand(True)

            # Wordmark — "luminos" in Inter 48px weight 300
            wordmark = Gtk.Label(label="luminos")
            wordmark.add_css_class("fr-wordmark")
            wordmark.set_margin_bottom(SPACE_3)
            self.append(wordmark)

            # Tagline
            tagline = Gtk.Label(
                label="Everything works. Nothing gets in the way."
            )
            tagline.add_css_class("fr-tagline")
            tagline.set_margin_bottom(SPACE_12)
            self.append(tagline)

            # Get Started button
            btn = Gtk.Button(label="Get Started")
            btn.add_css_class("fr-btn-primary")
            btn.set_halign(Gtk.Align.CENTER)
            btn.connect("clicked", lambda *_: on_get_started())
            self.append(btn)


    # =======================================================================
    # Screen 2 — Account
    # =======================================================================

    class AccountScreen(Gtk.Box):
        """
        Account screen — name + optional password with confirm.
        """

        def __init__(self, state: FirstRunState):
            super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=SPACE_4)
            self._state = state
            self.set_halign(Gtk.Align.CENTER)
            self.set_valign(Gtk.Align.CENTER)
            self.set_hexpand(True)
            self.set_vexpand(True)
            self.set_size_request(400, -1)

            # Title
            title = Gtk.Label(label="Who's using this?")
            title.add_css_class("fr-title")
            title.set_halign(Gtk.Align.START)
            title.set_margin_bottom(SPACE_2)
            self.append(title)

            # Name input
            self._name_entry = Gtk.Entry()
            self._name_entry.set_placeholder_text("Your name")
            self._name_entry.add_css_class("fr-input")
            self._name_entry.set_hexpand(True)
            if state.username:
                self._name_entry.set_text(state.username)
            self.append(self._name_entry)

            # Password input
            self._pw_entry = Gtk.Entry()
            self._pw_entry.set_placeholder_text("Password (optional)")
            self._pw_entry.set_visibility(False)
            self._pw_entry.add_css_class("fr-input")
            self._pw_entry.set_hexpand(True)
            if state.password:
                self._pw_entry.set_text(state.password)
            self.append(self._pw_entry)

            # Confirm password — hidden until password has content
            self._confirm_entry = Gtk.Entry()
            self._confirm_entry.set_placeholder_text("Confirm password")
            self._confirm_entry.set_visibility(False)
            self._confirm_entry.add_css_class("fr-input")
            self._confirm_entry.set_hexpand(True)
            self._confirm_entry.set_visible(bool(state.password))
            self.append(self._confirm_entry)

            # Show/hide confirm on password text change
            self._pw_entry.connect("changed", self._on_pw_changed)

            # Error label
            self._error_lbl = Gtk.Label(label="")
            self._error_lbl.add_css_class("fr-error")
            self._error_lbl.set_halign(Gtk.Align.START)
            self._error_lbl.set_visible(False)
            self.append(self._error_lbl)

            # Skip link
            skip_btn = Gtk.Button(label="Skip — I'll set one later")
            skip_btn.add_css_class("fr-skip")
            skip_btn.set_halign(Gtk.Align.START)
            skip_btn.connect("clicked", self._on_skip)
            self.append(skip_btn)

        def _on_pw_changed(self, entry):
            has_text = bool(entry.get_text())
            self._confirm_entry.set_visible(has_text)

        def _on_skip(self, *_):
            self._pw_entry.set_text("")
            self._confirm_entry.set_text("")
            self._confirm_entry.set_visible(False)

        def collect(self) -> tuple:
            """Return (name, password, confirm)."""
            return (
                self._name_entry.get_text().strip(),
                self._pw_entry.get_text(),
                self._confirm_entry.get_text(),
            )

        def show_error(self, msg: str) -> None:
            self._error_lbl.set_text(msg)
            self._error_lbl.set_visible(bool(msg))

        def clear_error(self) -> None:
            self._error_lbl.set_text("")
            self._error_lbl.set_visible(False)


    # =======================================================================
    # Screen 3 — Wallpaper
    # =======================================================================

    class WallpaperScreen(Gtk.Box):
        """
        Wallpaper picker — 3×2 grid of 6 thumbnails.
        Applies the selection to desktop immediately via swww/live-wallpaper.
        """

        def __init__(self, state: FirstRunState):
            super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=SPACE_4)
            self._state = state
            self._selected = state.wallpaper_index
            self._thumb_frames: list[Gtk.Frame] = []

            self.set_halign(Gtk.Align.CENTER)
            self.set_valign(Gtk.Align.CENTER)
            self.set_hexpand(True)
            self.set_vexpand(True)
            self.set_size_request(540, -1)

            # Title
            title = Gtk.Label(label="Make it yours")
            title.add_css_class("fr-title")
            title.set_halign(Gtk.Align.START)
            title.set_margin_bottom(SPACE_2)
            self.append(title)

            # 3×2 grid
            grid = Gtk.Grid()
            grid.set_row_spacing(SPACE_4)
            grid.set_column_spacing(SPACE_4)
            grid.set_hexpand(True)
            self.append(grid)

            for i, item in enumerate(_WALLPAPER_ITEMS):
                col = i % 3
                row = i // 3
                card = self._make_thumb(i, item)
                grid.attach(card, col, row, 1, 1)

            # Skip link
            skip_btn = Gtk.Button(label="Skip — I'll choose later")
            skip_btn.add_css_class("fr-skip")
            skip_btn.set_halign(Gtk.Align.START)
            skip_btn.connect("clicked", self._on_skip)
            self.append(skip_btn)

        def _make_thumb(self, idx: int, item: dict) -> Gtk.Box:
            """Build one thumbnail card (colored box + label)."""
            outer = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=SPACE_2)
            outer.set_hexpand(True)

            # Frame for border selection
            frame = Gtk.Frame()
            frame.add_css_class("fr-thumb")
            if idx == self._selected:
                frame.add_css_class("fr-thumb-selected")
            self._thumb_frames.append(frame)

            # Colored drawing area as preview
            da = Gtk.DrawingArea()
            da.set_size_request(160, 100)
            da.set_hexpand(True)

            # Parse color for Cairo
            color_hex = item["color"].lstrip("#")
            r = int(color_hex[0:2], 16) / 255
            g = int(color_hex[2:4], 16) / 255
            b = int(color_hex[4:6], 16) / 255

            badge = _TYPE_BADGE.get(item["type"], "")
            label_text = item["label"]

            def draw_fn(widget, cr, w, h, _r=r, _g=g, _b=b, _badge=badge, _label=label_text):
                # Background
                cr.set_source_rgb(_r, _g, _b)
                cr.rectangle(0, 0, w, h)
                cr.fill()
                # Badge icon (video/live indicator)
                if _badge:
                    cr.set_source_rgba(1, 1, 1, 0.6)
                    cr.select_font_face("Inter", 0, 0)
                    cr.set_font_size(18)
                    cr.move_to(8, 24)
                    cr.show_text(_badge)
                # Label text centered
                cr.set_source_rgba(1, 1, 1, 0.7)
                cr.select_font_face("Inter", 0, 0)
                cr.set_font_size(12)
                ext = cr.text_extents(_label)
                cr.move_to((w - ext.width) / 2, h - 10)
                cr.show_text(_label)

            da.set_draw_func(draw_fn)
            frame.set_child(da)

            # Click via gesture
            click = Gtk.GestureClick()
            click.connect("pressed", lambda *a, i=idx: self._on_select(i))
            frame.add_controller(click)

            outer.append(frame)
            return outer

        def _on_select(self, idx: int) -> None:
            # Update border on previously selected
            if self._selected >= 0 and self._selected < len(self._thumb_frames):
                self._thumb_frames[self._selected].remove_css_class("fr-thumb-selected")
            self._selected = idx
            self._thumb_frames[idx].add_css_class("fr-thumb-selected")

            # Update state
            item = _WALLPAPER_ITEMS[idx]
            self._state.wallpaper_index = idx
            self._state.wallpaper_type  = item["type"]
            self._state.wallpaper_value = item["value"]

            # Apply immediately in background
            self._apply_wallpaper(item)

        def _on_skip(self, *_) -> None:
            # Clear selection
            if self._selected >= 0 and self._selected < len(self._thumb_frames):
                self._thumb_frames[self._selected].remove_css_class("fr-thumb-selected")
            self._selected = -1
            self._state.wallpaper_index = -1

        def _apply_wallpaper(self, item: dict) -> None:
            """Apply selected wallpaper to desktop immediately (best-effort)."""
            import subprocess
            try:
                if item["type"] == "static" and os.path.isfile(item["value"]):
                    subprocess.Popen(
                        ["swww", "img", item["value"],
                         "--transition-type", "fade",
                         "--transition-duration", "1"],
                        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                    )
                elif item["type"] == "live":
                    subprocess.Popen(
                        ["luminos-live-wallpaper", "--preset", item["value"],
                         "--intensity", "low"],
                        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                    )
                elif item["type"] == "video" and os.path.isfile(item["value"]):
                    subprocess.Popen(
                        ["mpvpaper", "-o", "loop", "*", item["value"]],
                        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                    )
            except Exception as e:
                logger.debug(f"Wallpaper apply error: {e}")


    # =======================================================================
    # Screen 4 — Ready
    # =======================================================================

    class ReadyScreen(Gtk.Box):
        """
        Ready screen — animated checkmark + staggered text lines.
        Checkmark draws itself in via scale animation over 600ms.
        """

        _LINES = [
            "Your Windows apps open automatically.",
            "AI runs in the background — not in your face.",
            "Everything is private. Always.",
        ]

        def __init__(self, on_go_to_desktop):
            super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=SPACE_4)
            self.set_halign(Gtk.Align.CENTER)
            self.set_valign(Gtk.Align.CENTER)
            self.set_hexpand(True)
            self.set_vexpand(True)
            self._on_go = on_go_to_desktop
            self._line_labels: list[Gtk.Label] = []
            self._build()

        def _build(self):
            # Checkmark
            self._check_lbl = Gtk.Label(label="✓")
            self._check_lbl.add_css_class("fr-checkmark")
            self._check_lbl.set_halign(Gtk.Align.CENTER)
            self._check_lbl.set_opacity(0.0)
            self._check_lbl.set_margin_bottom(SPACE_4)
            self.append(self._check_lbl)

            # Title
            self._title_lbl = Gtk.Label(label="You're ready.")
            self._title_lbl.add_css_class("fr-ready-title")
            self._title_lbl.set_halign(Gtk.Align.CENTER)
            self._title_lbl.set_opacity(0.0)
            self._title_lbl.set_margin_bottom(SPACE_4)
            self.append(self._title_lbl)

            # Three lines
            for line in self._LINES:
                lbl = Gtk.Label(label=line)
                lbl.add_css_class("fr-ready-line")
                lbl.set_halign(Gtk.Align.CENTER)
                lbl.set_opacity(0.0)
                self._line_labels.append(lbl)
                self.append(lbl)

            # Go to Desktop button
            self._go_btn = Gtk.Button(label="Go to Desktop")
            self._go_btn.add_css_class("fr-btn-primary")
            self._go_btn.set_halign(Gtk.Align.CENTER)
            self._go_btn.set_opacity(0.0)
            self._go_btn.set_margin_top(SPACE_6)
            self._go_btn.connect("clicked", lambda *_: self._on_go())
            self.append(self._go_btn)

        def start_animations(self):
            """Call when this screen becomes visible to start animations."""
            # Checkmark fades+scales in over 600ms
            GLib.timeout_add(50,  self._fade_in, self._check_lbl)
            GLib.timeout_add(200, self._fade_in, self._title_lbl)
            # Three lines staggered: 400, 600, 800ms
            for i, lbl in enumerate(self._line_labels):
                GLib.timeout_add(400 + i * 200, self._fade_in, lbl)
            GLib.timeout_add(1200, self._fade_in, self._go_btn)

        def _fade_in(self, widget: Gtk.Widget) -> bool:
            """Smooth fade-in using GLib timer steps."""
            current = widget.get_opacity()
            if current >= 1.0:
                widget.set_opacity(1.0)
                return GLib.SOURCE_REMOVE
            widget.set_opacity(min(current + 0.08, 1.0))
            return GLib.SOURCE_CONTINUE
