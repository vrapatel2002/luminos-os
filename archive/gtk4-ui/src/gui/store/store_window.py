"""
src/gui/store/store_window.py
Luminos Store main window — GTK4 ApplicationWindow.

Layout:
  Horizontal pane:
    LEFT (200px) — search + category sidebar + "Installed" link
    RIGHT        — header bar + package FlowBox + detail panel

All subprocess I/O happens on background threads to keep the UI responsive.
"""

import logging
import threading

logger = logging.getLogger(__name__)

try:
    import gi
    gi.require_version("Gtk", "4.0")
    from gi.repository import Gtk, GLib
    _GTK_AVAILABLE = True
except (ImportError, ValueError):
    _GTK_AVAILABLE = False

from gui.store.store_backend import (
    Package, get_featured, search_all,
    install_package, uninstall_package, is_installed,
)

CATEGORIES = [
    "All", "Featured", "Games", "Development",
    "Internet", "Multimedia", "Office",
    "Graphics", "System", "Education",
]

_SORT_OPTIONS = ["Relevance", "Name", "Size"]
_FILTER_OPTIONS = ["All", "Flatpak", "pacman"]


if _GTK_AVAILABLE:
    class LuminosStore(Gtk.ApplicationWindow):
        """
        Full Luminos Store window.

        States:
          - Featured  — hardcoded get_featured() on open
          - Category  — filtered by selected category
          - Search    — results from search_all(query)
          - Detail    — sliding panel for a selected package
        """

        def __init__(self, app):
            super().__init__(application=app)
            self.set_title("Luminos Store")
            self.set_default_size(960, 640)
            self.add_css_class("luminos-panel")

            self.current_category = "Featured"
            self.search_query     = ""
            self.packages:  list[Package] = []
            self._selected: Package | None = None
            self._sort     = "Relevance"
            self._filter   = "All"

            self._build()
            self._load_featured()

        # -------------------------------------------------------------------
        # UI construction
        # -------------------------------------------------------------------

        def _build(self):
            # Root: horizontal box
            root = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=0)
            self.set_child(root)

            # LEFT SIDEBAR
            sidebar = self._build_sidebar()
            root.append(sidebar)

            # Separator
            sep = Gtk.Separator(orientation=Gtk.Orientation.VERTICAL)
            root.append(sep)

            # RIGHT CONTENT
            right = self._build_right()
            right.set_hexpand(True)
            root.append(right)

        def _build_sidebar(self) -> Gtk.Box:
            sidebar = Gtk.Box(
                orientation=Gtk.Orientation.VERTICAL, spacing=0
            )
            sidebar.set_size_request(200, -1)
            sidebar.add_css_class("store-sidebar")

            # Search entry
            self._search_entry = Gtk.SearchEntry()
            self._search_entry.set_placeholder_text("Search apps…")
            self._search_entry.set_margin_start(8)
            self._search_entry.set_margin_end(8)
            self._search_entry.set_margin_top(12)
            self._search_entry.set_margin_bottom(8)
            self._search_entry.connect("search-changed", self._on_search_changed)
            sidebar.append(self._search_entry)

            # Category list
            self._cat_rows: dict[str, Gtk.Box] = {}
            for cat in CATEGORIES:
                row = self._make_cat_row(cat)
                self._cat_rows[cat] = row
                sidebar.append(row)

            sidebar.append(Gtk.Separator())

            # Installed shortcut
            installed_btn = Gtk.Button(label="✓  Installed")
            installed_btn.add_css_class("store-installed-btn")
            installed_btn.set_margin_start(8)
            installed_btn.set_margin_end(8)
            installed_btn.set_margin_top(8)
            installed_btn.connect("clicked", self._on_installed_click)
            sidebar.append(installed_btn)

            self._highlight_category("Featured")
            return sidebar

        def _make_cat_row(self, cat: str) -> Gtk.Box:
            row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
            row.set_margin_start(8)
            row.set_margin_end(8)
            row.set_margin_top(2)
            row.set_margin_bottom(2)
            row.add_css_class("store-cat-row")

            lbl = Gtk.Label(label=cat)
            lbl.set_halign(Gtk.Align.START)
            lbl.set_hexpand(True)
            row.append(lbl)

            click = Gtk.GestureClick()
            click.connect("pressed", lambda *_: self._on_category_click(cat))
            row.add_controller(click)
            return row

        def _build_right(self) -> Gtk.Box:
            right = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)

            # Header bar
            header = Gtk.Box(
                orientation=Gtk.Orientation.HORIZONTAL, spacing=8
            )
            header.set_margin_start(16)
            header.set_margin_end(16)
            header.set_margin_top(12)
            header.set_margin_bottom(8)

            self._header_title = Gtk.Label(label="Featured")
            self._header_title.add_css_class("store-header-title")
            self._header_title.set_hexpand(True)
            self._header_title.set_halign(Gtk.Align.START)
            header.append(self._header_title)

            # Sort dropdown
            sort_label = Gtk.Label(label="Sort:")
            header.append(sort_label)
            sort_combo = Gtk.DropDown.new_from_strings(_SORT_OPTIONS)
            sort_combo.connect("notify::selected", self._on_sort_changed)
            header.append(sort_combo)

            # Filter pills
            filter_box = Gtk.Box(
                orientation=Gtk.Orientation.HORIZONTAL, spacing=4
            )
            self._filter_btns: dict[str, Gtk.ToggleButton] = {}
            for opt in _FILTER_OPTIONS:
                btn = Gtk.ToggleButton(label=opt)
                btn.add_css_class("store-filter-pill")
                if opt == "All":
                    btn.set_active(True)
                btn.connect("toggled", self._on_filter_toggle, opt)
                filter_box.append(btn)
                self._filter_btns[opt] = btn
            header.append(filter_box)

            right.append(header)
            right.append(Gtk.Separator())

            # Spinner (shown during search)
            self._spinner = Gtk.Spinner()
            self._spinner.set_visible(False)
            self._spinner.set_halign(Gtk.Align.CENTER)
            self._spinner.set_margin_top(16)
            right.append(self._spinner)

            # Scrolled package grid
            scroll = Gtk.ScrolledWindow()
            scroll.set_vexpand(True)
            scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)

            self._flow = Gtk.FlowBox()
            self._flow.set_homogeneous(False)
            self._flow.set_column_spacing(8)
            self._flow.set_row_spacing(8)
            self._flow.set_margin_start(16)
            self._flow.set_margin_end(16)
            self._flow.set_margin_top(8)
            self._flow.set_max_children_per_line(4)
            self._flow.set_min_children_per_line(2)
            self._flow.set_selection_mode(Gtk.SelectionMode.NONE)
            scroll.set_child(self._flow)
            right.append(scroll)

            # Detail panel (hidden by default)
            self._detail_revealer = Gtk.Revealer()
            self._detail_revealer.set_transition_type(
                Gtk.RevealerTransitionType.SLIDE_UP
            )
            self._detail_revealer.set_reveal_child(False)
            detail = self._build_detail_panel()
            self._detail_revealer.set_child(detail)
            right.append(self._detail_revealer)

            return right

        def _build_detail_panel(self) -> Gtk.Box:
            panel = Gtk.Box(
                orientation=Gtk.Orientation.VERTICAL, spacing=8
            )
            panel.set_margin_start(16)
            panel.set_margin_end(16)
            panel.set_margin_top(8)
            panel.set_margin_bottom(16)
            panel.add_css_class("store-detail-panel")

            sep = Gtk.Separator()
            panel.append(sep)

            # Header row
            header_row = Gtk.Box(
                orientation=Gtk.Orientation.HORIZONTAL, spacing=16
            )

            self._detail_icon = Gtk.Label(label="?")
            self._detail_icon.set_size_request(64, 64)
            self._detail_icon.add_css_class("store-icon-fallback")
            header_row.append(self._detail_icon)

            info_col = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
            info_col.set_hexpand(True)

            self._detail_name = Gtk.Label(label="")
            self._detail_name.add_css_class("store-detail-name")
            self._detail_name.set_halign(Gtk.Align.START)
            info_col.append(self._detail_name)

            self._detail_desc = Gtk.Label(label="")
            self._detail_desc.set_halign(Gtk.Align.START)
            self._detail_desc.set_wrap(True)
            self._detail_desc.add_css_class("store-detail-desc")
            info_col.append(self._detail_desc)

            self._detail_meta = Gtk.Label(label="")
            self._detail_meta.set_halign(Gtk.Align.START)
            self._detail_meta.add_css_class("store-card-desc")
            info_col.append(self._detail_meta)

            header_row.append(info_col)

            # Install / Uninstall button
            self._install_btn = Gtk.Button(label="Install")
            self._install_btn.add_css_class("store-install-btn")
            self._install_btn.connect("clicked", self._on_install_click)
            header_row.append(self._install_btn)

            panel.append(header_row)

            # Progress bar (hidden until install)
            self._install_progress = Gtk.ProgressBar()
            self._install_progress.set_visible(False)
            self._install_progress.set_pulse_step(0.1)
            panel.append(self._install_progress)

            return panel

        # -------------------------------------------------------------------
        # Data loading
        # -------------------------------------------------------------------

        def _load_featured(self):
            self.packages = get_featured()
            self._header_title.set_label("Featured")
            self._render_packages(self.packages)

        def _render_packages(self, pkgs: list[Package]):
            # Remove existing children
            child = self._flow.get_first_child()
            while child:
                next_child = child.get_next_sibling()
                self._flow.remove(child)
                child = next_child

            from gui.store.package_card import PackageCard
            for pkg in pkgs:
                filtered = self._apply_filter(pkg)
                if not filtered:
                    continue
                card = PackageCard(pkg, on_select=self._on_package_selected)
                self._flow.append(card)

            count = len([p for p in pkgs if self._apply_filter(p)])
            self._header_title.set_label(
                f"{self.current_category} ({count})"
                if self.current_category != "Featured" else "Featured"
            )

        def _apply_filter(self, pkg: Package) -> bool:
            if self._filter == "Flatpak" and pkg.source != "flatpak":
                return False
            if self._filter == "pacman" and pkg.source != "pacman":
                return False
            return True

        # -------------------------------------------------------------------
        # Event handlers
        # -------------------------------------------------------------------

        def _on_search_changed(self, entry):
            query = entry.get_text()
            self.search_query = query
            if len(query) >= 2:
                self._spinner.set_visible(True)
                self._spinner.start()
                threading.Thread(
                    target=self._search_thread,
                    args=(query,),
                    daemon=True,
                ).start()
            elif query == "":
                self._load_featured()

        def _search_thread(self, query: str):
            results = search_all(query)
            GLib.idle_add(self._on_search_done, results, query)

        def _on_search_done(self, results: list[Package], query: str):
            self._spinner.stop()
            self._spinner.set_visible(False)
            if query != self.search_query:
                return   # stale result
            self.packages = results
            self.current_category = f'Search: "{query}"'
            self._render_packages(results)
            return False   # one-shot idle

        def _on_category_click(self, cat: str):
            self._search_entry.set_text("")
            self.current_category = cat
            self._highlight_category(cat)
            if cat == "Featured":
                self._load_featured()
            else:
                pkgs = [
                    p for p in get_featured()
                    if cat == "All" or p.category == cat
                ]
                self._render_packages(pkgs)

        def _on_installed_click(self, *_):
            self.current_category = "Installed"
            pkgs = [p for p in get_featured() if p.installed]
            self._render_packages(pkgs)

        def _highlight_category(self, active: str):
            for cat, row in self._cat_rows.items():
                if cat == active:
                    row.add_css_class("store-cat-active")
                else:
                    row.remove_css_class("store-cat-active")

        def _on_sort_changed(self, dropdown, _pspec):
            idx = dropdown.get_selected()
            if 0 <= idx < len(_SORT_OPTIONS):
                self._sort = _SORT_OPTIONS[idx]
                self._render_packages(self.packages)

        def _on_filter_toggle(self, btn: Gtk.ToggleButton, opt: str):
            if btn.get_active():
                self._filter = opt
                # Deactivate other pills
                for o, b in self._filter_btns.items():
                    if o != opt:
                        b.set_active(False)
                self._render_packages(self.packages)

        def _on_package_selected(self, pkg: Package):
            self._selected = pkg
            self._detail_name.set_label(pkg.name)
            self._detail_desc.set_label(pkg.description)
            self._detail_icon.set_label(pkg.name[0].upper() if pkg.name else "?")
            version_str = pkg.version or "unknown"
            size_str = f" · {pkg.size_mb:.1f} MB" if pkg.size_mb else ""
            source_str = "Flatpak (Sandboxed)" if pkg.sandboxed else "pacman"
            zone_str = {1: "Zone 1 (Native)", 2: "Zone 2 (Wine)", 3: "Zone 3 (VM)"}.get(
                pkg.predicted_zone, "Zone 1"
            )
            self._detail_meta.set_label(
                f"v{version_str}{size_str} · {source_str} · {zone_str}"
            )

            # Check installed state
            installed = is_installed(pkg)
            self._install_btn.set_label(
                "Uninstall" if installed else "Install"
            )
            self._install_btn.set_sensitive(True)
            self._install_progress.set_visible(False)
            self._detail_revealer.set_reveal_child(True)

        def _on_install_click(self, *_):
            if self._selected is None:
                return
            pkg = self._selected
            installed = is_installed(pkg)

            self._install_btn.set_sensitive(False)
            self._install_progress.set_visible(True)

            def _run():
                if installed:
                    uninstall_package(pkg)
                else:
                    install_package(
                        pkg,
                        progress_cb=lambda line: GLib.idle_add(
                            self._install_progress.pulse
                        ),
                    )
                GLib.idle_add(self._on_install_done, pkg)

            threading.Thread(target=_run, daemon=True).start()

        def _on_install_done(self, pkg: Package):
            self._install_progress.set_visible(False)
            installed_now = is_installed(pkg)
            self._install_btn.set_label(
                "Uninstall" if installed_now else "Install"
            )
            self._install_btn.set_sensitive(True)
            return False
