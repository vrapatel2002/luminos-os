"""
src/gui/store/package_card.py
PackageCard widget — one tile in the store grid.

Pure logic helpers are module-level so they can be tested headlessly.
GTK class is guarded by _GTK_AVAILABLE.
"""

import logging

logger = logging.getLogger(__name__)

try:
    import gi
    gi.require_version("Gtk", "4.0")
    from gi.repository import Gtk
    _GTK_AVAILABLE = True
except (ImportError, ValueError):
    _GTK_AVAILABLE = False

from gui.store.store_backend import Package

_DISPLAY_NAME_MAX = 20


# ---------------------------------------------------------------------------
# Pure helpers — testable without GTK
# ---------------------------------------------------------------------------

def _get_source_label(pkg: Package) -> str:
    """Return the source badge label: 'Flatpak' or 'apt'."""
    return "Flatpak" if pkg.source == "flatpak" else "apt"


def _get_zone_badge(pkg: Package) -> str:
    """
    Return the zone badge text.
    Zone 1 → "" (native, no badge needed)
    Zone 2 → "Wine"
    Zone 3 → "VM"
    """
    return {1: "", 2: "Wine", 3: "VM"}.get(pkg.predicted_zone, "")


def _get_display_name(name: str) -> str:
    """Truncate long package names with an ellipsis."""
    if len(name) <= _DISPLAY_NAME_MAX:
        return name
    return name[:_DISPLAY_NAME_MAX] + "…"


def _get_initials(name: str) -> str:
    """Get up to 2 initials for the fallback icon circle."""
    parts = name.split()
    if not parts:
        return "?"
    if len(parts) >= 2:
        return (parts[0][0] + parts[1][0]).upper()
    return parts[0][0].upper()


# ---------------------------------------------------------------------------
# GTK widget
# ---------------------------------------------------------------------------

if _GTK_AVAILABLE:
    class PackageCard(Gtk.Box):
        """
        A single package card in the store grid.

        Layout (vertical, centered):
          [Icon / Initials circle]
          [Name — bold]
          [Description — 2 line max, ellipsis]
          [Source badge] [Zone badge] [Installed ✓]

        Click anywhere → on_select(pkg) callback.
        """

        def __init__(self, pkg: Package, on_select):
            super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=6)
            self.pkg       = pkg
            self.on_select = on_select

            self.set_size_request(160, 200)
            self.set_margin_start(8)
            self.set_margin_end(8)
            self.set_margin_top(8)
            self.set_margin_bottom(8)
            self.add_css_class("luminos-panel")
            self.add_css_class("store-card")

            self._build()

            click = Gtk.GestureClick()
            click.connect("pressed", self._on_click)
            self.add_controller(click)

        def _build(self):
            # Icon / initials
            self._icon_area = self._make_icon()
            self.append(self._icon_area)

            # Name
            name_lbl = Gtk.Label(label=_get_display_name(self.pkg.name))
            name_lbl.set_halign(Gtk.Align.CENTER)
            name_lbl.add_css_class("store-card-name")
            self.append(name_lbl)

            # Description (2 lines max)
            desc_lbl = Gtk.Label(label=self.pkg.description)
            desc_lbl.set_halign(Gtk.Align.CENTER)
            desc_lbl.set_wrap(True)
            desc_lbl.set_max_width_chars(22)
            desc_lbl.set_lines(2)
            desc_lbl.set_ellipsize(3)   # Pango.EllipsizeMode.END = 3
            desc_lbl.add_css_class("store-card-desc")
            self.append(desc_lbl)

            # Badge row
            badge_row = Gtk.Box(
                orientation=Gtk.Orientation.HORIZONTAL, spacing=4
            )
            badge_row.set_halign(Gtk.Align.CENTER)

            # Source badge
            src_lbl = Gtk.Label(label=_get_source_label(self.pkg))
            src_lbl.add_css_class(
                "store-badge-flatpak" if self.pkg.sandboxed
                else "store-badge-apt"
            )
            badge_row.append(src_lbl)

            # Sandboxed label
            if self.pkg.sandboxed:
                sand_lbl = Gtk.Label(label="Sandboxed")
                sand_lbl.add_css_class("store-badge-sandboxed")
                badge_row.append(sand_lbl)

            # Zone badge
            zone_text = _get_zone_badge(self.pkg)
            if zone_text:
                zone_lbl = Gtk.Label(label=zone_text)
                zone_lbl.add_css_class(
                    "store-badge-wine" if self.pkg.predicted_zone == 2
                    else "store-badge-vm"
                )
                badge_row.append(zone_lbl)

            # Installed badge
            if self.pkg.installed:
                inst_lbl = Gtk.Label(label="✓ Installed")
                inst_lbl.add_css_class("store-badge-installed")
                badge_row.append(inst_lbl)

            self.append(badge_row)

        def _make_icon(self) -> Gtk.Widget:
            """Try icon resolver; fall back to initials circle."""
            try:
                from gui.theme.icons import find_icon
                pixbuf = find_icon(self.pkg.icon_name, 64)
                if pixbuf:
                    img = Gtk.Image.new_from_pixbuf(pixbuf)
                    img.set_pixel_size(64)
                    img.set_halign(Gtk.Align.CENTER)
                    return img
            except Exception:
                pass
            # Fallback: initials label in a styled box
            fallback = Gtk.Label(label=_get_initials(self.pkg.name))
            fallback.set_size_request(64, 64)
            fallback.set_halign(Gtk.Align.CENTER)
            fallback.add_css_class("store-icon-fallback")
            return fallback

        def _on_click(self, *_):
            self.on_select(self.pkg)

        # -----------------------------------------------------------------------
        # Pure-logic mirrors
        # -----------------------------------------------------------------------

        @staticmethod
        def _get_source_label(pkg: Package) -> str:
            return _get_source_label(pkg)

        @staticmethod
        def _get_zone_badge(pkg: Package) -> str:
            return _get_zone_badge(pkg)

        @staticmethod
        def _get_display_name(name: str) -> str:
            return _get_display_name(name)
