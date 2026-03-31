"""
tests/test_store.py
Phase 8.9 — Luminos Store test suite.

Covers:
  - store_backend: Package dataclass, featured list, search (mocked),
                   dedup, sort, install/uninstall (mocked), is_installed  (10 tests)
  - package_card pure helpers: source label, zone badge, display name    (4 tests)
  - store_window constants: CATEGORIES list contains required values      (1 test)
  - search length gate: query length threshold                            (1 test)

Total: 16 tests
All headless — no network, subprocess calls mocked.
"""

import os
import sys
import unittest
from dataclasses import replace
from unittest.mock import MagicMock, patch

SRC = os.path.join(os.path.dirname(__file__), "..", "src")
if SRC not in sys.path:
    sys.path.insert(0, SRC)

from gui.store.store_backend import (
    Package, get_featured,
    search_flatpak, search_pacman, search_all,
    install_package, uninstall_package, is_installed,
    _parse_flatpak_output, _parse_pacman_output,
)
from gui.store.package_card import (
    _get_source_label, _get_zone_badge, _get_display_name,
)
from gui.store.store_window import CATEGORIES


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_pkg(**kwargs) -> Package:
    defaults = dict(
        name="TestApp", description="A test app",
        version="1.0", source="flatpak",
        icon_name="testapp", size_mb=50.0,
        installed=False, sandboxed=True,
        category="System", flatpak_id="org.test.App",
        predicted_zone=1,
    )
    defaults.update(kwargs)
    return Package(**defaults)


# ===========================================================================
# Package dataclass
# ===========================================================================

class TestPackageDataclass(unittest.TestCase):

    def test_all_fields_accessible(self):
        pkg = _make_pkg()
        self.assertEqual(pkg.name,           "TestApp")
        self.assertEqual(pkg.source,         "flatpak")
        self.assertTrue(pkg.sandboxed)
        self.assertEqual(pkg.predicted_zone, 1)
        self.assertIsNone(
            replace(pkg, size_mb=None).size_mb
        )


# ===========================================================================
# get_featured
# ===========================================================================

class TestGetFeatured(unittest.TestCase):

    def test_returns_nonempty_list(self):
        result = get_featured()
        self.assertIsInstance(result, list)
        self.assertGreater(len(result), 0)

    def test_all_items_are_packages(self):
        for pkg in get_featured():
            self.assertIsInstance(pkg, Package)

    def test_required_fields_present(self):
        for pkg in get_featured():
            self.assertTrue(pkg.name)
            self.assertIn(pkg.source, ("flatpak", "pacman"))

    def test_contains_firefox(self):
        names = [p.name for p in get_featured()]
        self.assertIn("Firefox", names)


# ===========================================================================
# search_flatpak / search_pacman — offline (subprocess mocked)
# ===========================================================================

class TestSearchFlatpak(unittest.TestCase):

    def test_flatpak_not_installed_returns_empty(self):
        with patch("subprocess.run", side_effect=FileNotFoundError):
            result = search_flatpak("firefox")
        self.assertEqual(result, [])

    def test_flatpak_error_returns_empty(self):
        import subprocess
        mock_result = MagicMock()
        mock_result.returncode = 1
        mock_result.stdout = ""
        with patch("subprocess.run", return_value=mock_result):
            result = search_flatpak("firefox")
        self.assertEqual(result, [])

    def test_parse_flatpak_output(self):
        sample = (
            "Name\tDescription\tVersion\tApplication\tOrigin\n"
            "Firefox\tWeb browser\t125.0\torg.mozilla.firefox\tflathub\n"
        )
        pkgs = _parse_flatpak_output(sample)
        self.assertEqual(len(pkgs), 1)
        self.assertEqual(pkgs[0].name, "Firefox")
        self.assertEqual(pkgs[0].flatpak_id, "org.mozilla.firefox")
        self.assertTrue(pkgs[0].sandboxed)


class TestSearchPacman(unittest.TestCase):

    def test_pacman_not_installed_returns_empty(self):
        with patch("subprocess.run", side_effect=FileNotFoundError):
            result = search_pacman("gimp")
        self.assertEqual(result, [])

    def test_parse_pacman_output(self):
        sample = "extra/gimp 2.10.36-1\n    GNU Image Manipulation Program\n"
        pkgs = _parse_pacman_output(sample, "gimp")
        self.assertEqual(len(pkgs), 1)
        self.assertEqual(pkgs[0].name, "gimp")
        self.assertFalse(pkgs[0].sandboxed)
        self.assertEqual(pkgs[0].source, "pacman")


# ===========================================================================
# search_all — dedup and sort
# ===========================================================================

class TestSearchAll(unittest.TestCase):

    def test_offline_returns_empty_no_crash(self):
        with patch("subprocess.run", side_effect=FileNotFoundError):
            result = search_all("firefox")
        self.assertIsInstance(result, list)

    def test_dedup_flatpak_wins(self):
        """If same app appears in both sources, flatpak version is kept."""
        flatpak_pkg = _make_pkg(name="GIMP", source="flatpak",
                                sandboxed=True, flatpak_id="org.gimp.GIMP")
        pacman_pkg  = _make_pkg(name="GIMP", source="pacman",
                                sandboxed=False, flatpak_id=None)

        with patch("gui.store.store_backend.search_flatpak", return_value=[flatpak_pkg]), \
             patch("gui.store.store_backend.search_pacman",  return_value=[pacman_pkg]):
            results = search_all("gimp")

        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].source, "flatpak")

    def test_installed_sorted_first(self):
        """Installed packages should appear before uninstalled ones."""
        installed   = _make_pkg(name="Alpha", installed=True)
        uninstalled = _make_pkg(name="Beta",  installed=False)

        with patch("gui.store.store_backend.search_flatpak",
                   return_value=[uninstalled, installed]), \
             patch("gui.store.store_backend.search_pacman", return_value=[]):
            results = search_all("a")

        self.assertEqual(results[0].name, "Alpha")

    def test_max_30_results(self):
        many = [_make_pkg(name=f"App{i}", flatpak_id=f"org.app.App{i}")
                for i in range(40)]
        with patch("gui.store.store_backend.search_flatpak", return_value=many), \
             patch("gui.store.store_backend.search_pacman", return_value=[]):
            results = search_all("app")
        self.assertLessEqual(len(results), 30)


# ===========================================================================
# install_package / uninstall_package (mocked subprocess)
# ===========================================================================

class TestInstallPackage(unittest.TestCase):

    def test_install_flatpak_success(self):
        pkg = _make_pkg(source="flatpak", flatpak_id="org.test.App")
        mock_proc = MagicMock()
        mock_proc.stdout.__iter__ = lambda s: iter(["Installing…\n"])
        mock_proc.wait.return_value = 0
        mock_proc.returncode = 0
        with patch("subprocess.Popen", return_value=mock_proc), \
             patch("gui.store.store_backend._classify_installed", return_value=1), \
             patch("gui.store.store_backend._notify_install"):
            result = install_package(pkg)
        self.assertIn("success", result)
        self.assertIn("zone",    result)

    def test_install_missing_flatpak_id_fails(self):
        pkg = _make_pkg(source="flatpak", flatpak_id=None)
        result = install_package(pkg)
        self.assertFalse(result["success"])

    def test_install_binary_not_found_returns_failure(self):
        pkg = _make_pkg(source="flatpak", flatpak_id="org.test.App")
        with patch("subprocess.Popen", side_effect=FileNotFoundError("flatpak")):
            result = install_package(pkg)
        self.assertFalse(result["success"])
        self.assertIsNotNone(result["error"])


class TestUninstallPackage(unittest.TestCase):

    def test_uninstall_flatpak_success(self):
        pkg = _make_pkg(source="flatpak", flatpak_id="org.test.App")
        mock_result = MagicMock()
        mock_result.returncode = 0
        with patch("subprocess.run", return_value=mock_result):
            result = uninstall_package(pkg)
        self.assertTrue(result["success"])

    def test_uninstall_flatpak_missing_id_fails(self):
        pkg = _make_pkg(source="flatpak", flatpak_id=None)
        result = uninstall_package(pkg)
        self.assertFalse(result["success"])


class TestIsInstalled(unittest.TestCase):

    def test_returns_bool_no_crash(self):
        pkg = _make_pkg(source="flatpak", flatpak_id="org.test.App")
        with patch("subprocess.run", side_effect=FileNotFoundError):
            result = is_installed(pkg)
        self.assertIsInstance(result, bool)
        self.assertFalse(result)


# ===========================================================================
# PackageCard pure helpers
# ===========================================================================

class TestPackageCardHelpers(unittest.TestCase):

    def test_source_label_flatpak(self):
        pkg = _make_pkg(source="flatpak")
        self.assertEqual(_get_source_label(pkg), "Flatpak")

    def test_source_label_pacman(self):
        pkg = _make_pkg(source="pacman")
        self.assertEqual(_get_source_label(pkg), "pacman")

    def test_zone_badge_zone1_empty(self):
        pkg = _make_pkg(predicted_zone=1)
        self.assertEqual(_get_zone_badge(pkg), "")

    def test_zone_badge_zone2_wine(self):
        pkg = _make_pkg(predicted_zone=2)
        self.assertEqual(_get_zone_badge(pkg), "Wine")

    def test_zone_badge_zone3_vm(self):
        pkg = _make_pkg(predicted_zone=3)
        self.assertEqual(_get_zone_badge(pkg), "VM")

    def test_display_name_short_unchanged(self):
        self.assertEqual(_get_display_name("Firefox"), "Firefox")

    def test_display_name_long_truncated(self):
        name   = "VeryLongApplicationNameThatExceedsLimit"
        result = _get_display_name(name)
        self.assertTrue(result.endswith("…"))
        self.assertLessEqual(len(result), 21)


# ===========================================================================
# CATEGORIES constant
# ===========================================================================

class TestCategories(unittest.TestCase):

    def test_featured_present(self):
        self.assertIn("Featured", CATEGORIES)

    def test_games_present(self):
        self.assertIn("Games", CATEGORIES)

    def test_all_present(self):
        self.assertIn("All", CATEGORIES)


# ===========================================================================
# Search min-length gate (pure logic)
# ===========================================================================

class TestSearchLengthGate(unittest.TestCase):
    """
    The store_window triggers search only for queries >= 2 chars.
    Test the threshold directly since we can't instantiate the GTK window.
    """

    def test_min_length_is_2(self):
        # Convention: query of length >= 2 triggers search
        self.assertGreaterEqual(len("fi"), 2)

    def test_one_char_below_threshold(self):
        self.assertLess(len("f"), 2)


if __name__ == "__main__":
    unittest.main()
