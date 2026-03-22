"""
src/gui/store/store_backend.py
Unified package search + install backend for Luminos Store.

Sources:
  - Flatpak / Flathub  (flatpak search / install)
  - apt                (apt-cache search / apt install via pkexec)

The zone classifier runs after every install to determine which execution
zone the installed app belongs to, and a notification is sent to the daemon.

All search functions return [] on error — never raise.
"""

import logging
import subprocess
import threading
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)

_DEVNULL = subprocess.DEVNULL

# ---------------------------------------------------------------------------
# Package dataclass
# ---------------------------------------------------------------------------

@dataclass
class Package:
    name:           str
    description:    str
    version:        str
    source:         str             # "flatpak" or "apt"
    icon_name:      str             # for icon resolver
    size_mb:        float | None    # None if unknown
    installed:      bool
    sandboxed:      bool            # True for Flatpak
    category:       str             # "Games", "Development", etc.
    flatpak_id:     str | None      # e.g. "org.mozilla.firefox"
    predicted_zone: int = 1         # 1/2/3 from classifier


# ---------------------------------------------------------------------------
# Featured list (hardcoded — no network required)
# ---------------------------------------------------------------------------

_FEATURED: list[Package] = [
    Package("Firefox",      "Fast, private web browser",
            "latest",       "flatpak", "firefox",                0.0, False, True,  "Internet",    "org.mozilla.firefox",           1),
    Package("VS Code",      "Code editor",
            "latest",       "flatpak", "com.visualstudio.code",  0.0, False, True,  "Development", "com.visualstudio.code",         1),
    Package("Steam",        "Gaming platform",
            "latest",       "flatpak", "com.valvesoftware.Steam",0.0, False, True,  "Games",       "com.valvesoftware.Steam",       1),
    Package("Discord",      "Voice and text chat",
            "latest",       "flatpak", "com.discordapp.Discord",  0.0, False, True,  "Internet",    "com.discordapp.Discord",        1),
    Package("Obsidian",     "Markdown knowledge base",
            "latest",       "flatpak", "md.obsidian.Obsidian",    0.0, False, True,  "Office",      "md.obsidian.Obsidian",          1),
    Package("GIMP",         "Image editor",
            "latest",       "flatpak", "org.gimp.GIMP",           0.0, False, True,  "Graphics",    "org.gimp.GIMP",                 1),
    Package("VLC",          "Media player",
            "latest",       "flatpak", "org.videolan.VLC",        0.0, False, True,  "Multimedia",  "org.videolan.VLC",              1),
    Package("Blender",      "3D creation suite",
            "latest",       "flatpak", "org.blender.Blender",     0.0, False, True,  "Graphics",    "org.blender.Blender",           1),
    Package("LibreOffice",  "Office suite",
            "latest",       "apt",     "libreoffice",             0.0, False, False, "Office",      None,                            1),
    Package("OBS Studio",   "Screen recorder and streamer",
            "latest",       "flatpak", "com.obsproject.Studio",   0.0, False, True,  "Multimedia",  "com.obsproject.Studio",         1),
]


def get_featured() -> list[Package]:
    """Return the hardcoded featured package list — no network required."""
    return list(_FEATURED)


# ---------------------------------------------------------------------------
# Search helpers
# ---------------------------------------------------------------------------

def search_flatpak(query: str) -> list[Package]:
    """
    Search Flathub via `flatpak search`.
    Returns [] if flatpak is not installed or the search fails.
    """
    try:
        result = subprocess.run(
            [
                "flatpak", "search", query,
                "--columns=name,description,version,application,origin",
            ],
            capture_output=True,
            text=True,
            timeout=15,
        )
        if result.returncode != 0 or not result.stdout.strip():
            return []
        return _parse_flatpak_output(result.stdout)
    except FileNotFoundError:
        logger.debug("search_flatpak: flatpak not installed")
        return []
    except Exception as e:
        logger.debug(f"search_flatpak: error — {e}")
        return []


def _parse_flatpak_output(output: str) -> list[Package]:
    packages = []
    for line in output.strip().splitlines():
        # skip header line
        if line.startswith("Name") and "Description" in line:
            continue
        parts = [p.strip() for p in line.split("\t")]
        if len(parts) < 4:
            continue
        name        = parts[0] if len(parts) > 0 else ""
        description = parts[1] if len(parts) > 1 else ""
        version     = parts[2] if len(parts) > 2 else "unknown"
        app_id      = parts[3] if len(parts) > 3 else None
        if not name:
            continue
        packages.append(Package(
            name           = name,
            description    = description,
            version        = version,
            source         = "flatpak",
            icon_name      = (app_id or name).lower().replace(" ", "-"),
            size_mb        = None,
            installed      = False,
            sandboxed      = True,
            category       = "Unknown",
            flatpak_id     = app_id,
            predicted_zone = 1,
        ))
    return packages


def search_apt(query: str) -> list[Package]:
    """
    Search apt via `apt-cache search`.
    Returns [] if apt is not available or the search fails.
    """
    try:
        result = subprocess.run(
            ["apt-cache", "search", query],
            capture_output=True,
            text=True,
            timeout=15,
        )
        if result.returncode != 0 or not result.stdout.strip():
            return []
        return _parse_apt_output(result.stdout, query)
    except FileNotFoundError:
        logger.debug("search_apt: apt-cache not found")
        return []
    except Exception as e:
        logger.debug(f"search_apt: error — {e}")
        return []


def _parse_apt_output(output: str, query: str) -> list[Package]:
    packages = []
    for line in output.strip().splitlines()[:30]:
        if " - " not in line:
            continue
        name, _, description = line.partition(" - ")
        name        = name.strip()
        description = description.strip()
        if not name:
            continue
        packages.append(Package(
            name           = name,
            description    = description,
            version        = "unknown",
            source         = "apt",
            icon_name      = name.lower(),
            size_mb        = None,
            installed      = False,
            sandboxed      = False,
            category       = "Unknown",
            flatpak_id     = None,
            predicted_zone = 1,
        ))
    return packages


def search_all(query: str) -> list[Package]:
    """
    Search both Flatpak and apt in parallel threads.

    Deduplication: if the same app name appears in both sources,
    the Flatpak version wins (sandboxed preferred).

    Sorting: installed first, then name-match score.

    Returns at most 30 results.
    """
    flatpak_results: list[Package] = []
    apt_results:     list[Package] = []
    errors: list[str] = []

    def _run_flatpak():
        try:
            flatpak_results.extend(search_flatpak(query))
        except Exception as e:
            errors.append(str(e))

    def _run_apt():
        try:
            apt_results.extend(search_apt(query))
        except Exception as e:
            errors.append(str(e))

    t1 = threading.Thread(target=_run_flatpak, daemon=True)
    t2 = threading.Thread(target=_run_apt,     daemon=True)
    t1.start(); t2.start()
    t1.join(timeout=20)
    t2.join(timeout=20)

    # Merge — flatpak wins on name collision
    seen: dict[str, Package] = {}
    for pkg in flatpak_results:
        seen[pkg.name.lower()] = pkg
    for pkg in apt_results:
        key = pkg.name.lower()
        if key not in seen:
            seen[key] = pkg
        # else flatpak version already stored — apt version silently dropped

    combined = list(seen.values())

    # Sort: installed first, then score name match
    q_lower = query.lower()
    def _score(pkg: Package) -> tuple:
        installed_score = 0 if pkg.installed else 1
        name_lower = pkg.name.lower()
        if name_lower == q_lower:
            name_score = 0
        elif name_lower.startswith(q_lower):
            name_score = 1
        elif q_lower in name_lower:
            name_score = 2
        else:
            name_score = 3
        return (installed_score, name_score, pkg.name.lower())

    combined.sort(key=_score)
    return combined[:30]


# ---------------------------------------------------------------------------
# Install / uninstall
# ---------------------------------------------------------------------------

def install_package(
    pkg: Package,
    progress_cb=None,
    daemon_client=None,
) -> dict:
    """
    Install a package via Flatpak or apt.

    Args:
        pkg:           Package to install.
        progress_cb:   Optional callable(line: str) for streaming output.
        daemon_client: Optional DaemonClient for post-install notification.

    Returns:
        {"success": bool, "zone": int, "error": str | None}
    """
    try:
        if pkg.source == "flatpak":
            if not pkg.flatpak_id:
                return {"success": False, "zone": 1,
                        "error": "No flatpak_id available"}
            cmd = ["flatpak", "install", "-y", "flathub", pkg.flatpak_id]
        else:
            cmd = ["pkexec", "apt", "install", "-y", pkg.name]

        proc = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
        )
        for line in proc.stdout:
            if progress_cb:
                try:
                    progress_cb(line.rstrip())
                except Exception:
                    pass

        proc.wait()
        if proc.returncode != 0:
            return {"success": False, "zone": 1,
                    "error": f"Install failed (exit {proc.returncode})"}

        # Run classifier on installed binary
        zone = _classify_installed(pkg)

        # Send notification
        _notify_install(pkg, zone, daemon_client)

        return {"success": True, "zone": zone, "error": None}

    except FileNotFoundError as e:
        return {"success": False, "zone": 1, "error": str(e)}
    except Exception as e:
        logger.warning(f"install_package: {e}")
        return {"success": False, "zone": 1, "error": str(e)}


def uninstall_package(pkg: Package) -> dict:
    """
    Uninstall a package via Flatpak or apt.

    Returns:
        {"success": bool, "error": str | None}
    """
    try:
        if pkg.source == "flatpak":
            if not pkg.flatpak_id:
                return {"success": False, "error": "No flatpak_id available"}
            cmd = ["flatpak", "uninstall", "-y", pkg.flatpak_id]
        else:
            cmd = ["pkexec", "apt", "remove", "-y", pkg.name]

        result = subprocess.run(cmd, capture_output=True, timeout=120)
        if result.returncode == 0:
            return {"success": True, "error": None}
        return {
            "success": False,
            "error": result.stderr.decode(errors="replace").strip() or "Uninstall failed",
        }
    except FileNotFoundError as e:
        return {"success": False, "error": str(e)}
    except Exception as e:
        logger.warning(f"uninstall_package: {e}")
        return {"success": False, "error": str(e)}


def is_installed(pkg: Package) -> bool:
    """
    Check whether a package is currently installed.
    Returns False on any error.
    """
    try:
        if pkg.source == "flatpak" and pkg.flatpak_id:
            result = subprocess.run(
                ["flatpak", "list", "--app"],
                capture_output=True, text=True, timeout=10,
            )
            return pkg.flatpak_id in result.stdout
        else:
            result = subprocess.run(
                ["dpkg", "-l", pkg.name],
                capture_output=True, text=True, timeout=10,
            )
            return any(
                line.startswith("ii ") and pkg.name in line
                for line in result.stdout.splitlines()
            )
    except Exception:
        return False


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _classify_installed(pkg: Package) -> int:
    """
    Run the zone classifier on the installed binary.
    Falls back to zone 1 on any error.
    """
    try:
        import shutil
        binary = shutil.which(pkg.name.lower().replace(" ", "-"))
        if binary:
            import sys, os
            src = os.path.join(os.path.dirname(__file__), "..", "..", "..")
            if src not in sys.path:
                import sys
                sys.path.insert(0, src)
            from classifier import classify_binary
            result = classify_binary(binary)
            return result.get("zone", 1)
    except Exception as e:
        logger.debug(f"_classify_installed: {e}")
    return 1


def _notify_install(pkg: Package, zone: int, daemon_client) -> None:
    """Send an install-complete notification via the daemon socket."""
    if daemon_client is None:
        return
    try:
        daemon_client.send({
            "type":       "notify",
            "notif_type": "model_loaded",   # reuse success level
            "title":      f"{pkg.name} installed",
            "body":       f"Zone {zone} · Ready to launch",
            "level":      "success",
        })
    except Exception as e:
        logger.debug(f"_notify_install: {e}")
