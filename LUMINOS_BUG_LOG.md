# Luminos Bug Log

## BUG-001 — Dock center screen positioning
Date: April 2026
Status: FIXED
Problem: Dock appeared center screen instead of bottom center
Root cause: Missing LEFT and RIGHT layer-shell anchors
Fix: Added GtkLayerShell.set_anchor LEFT=True RIGHT=True
Files: src/gui/dock/dock_window.py

## BUG-002 — Dock layer wrong (TOP instead of BOTTOM)
Date: April 2026
Status: FIXED
Problem: Dock set to Layer.TOP, causing it to render above all windows and reserve screen space
Root cause: Layer.TOP was used instead of Layer.BOTTOM; exclusive_zone was DOCK_HEIGHT+DOCK_BOTTOM_MARGIN instead of -1
Fix: Set Layer.BOTTOM and exclusive_zone=-1 (floating pill, no reserved zone)
Files: src/gui/dock/dock_window.py

## BUG-003 — Bar/dock not autostarting
Date: April 2026
Status: FIXED
Problem: Bar and dock not launching reliably on boot
Root cause: exec-once without env vars — GTK/Wayland init fails silently when WAYLAND_DISPLAY not set
Fix: Systemd user services with explicit Environment= vars; dock delayed 2s after bar
Files: ~/.config/systemd/user/luminos-bar.service, ~/.config/systemd/user/luminos-dock.service

## BUG-004 — Wrong apps pinned to dock
Date: April 2026
Status: FIXED
Problem: Dock defaulted to nautilus/foot/luminos-store which are not installed on target hardware
Root cause: DEFAULT_PINNED not updated for ROG G14 target environment
Fix: Updated DEFAULT_PINNED to dolphin, firefox, kitty, settings_app.py
Files: src/gui/dock/dock_config.py

## BUG-005 — MemPalace Python 3.14 incompatibility
Date: April 2026
Status: FIXED
Problem: chromadb pydantic v1 broken on Python 3.14
Root cause: Arch ships Python 3.14, pydantic v1 not updated yet
Fix: uv + Python 3.12 venv at ~/mempalace-venv
Files: ~/mempalace-venv/

## BUG-007 — Bar/dock services running but nothing visible on screen
Date: April 2026
Status: FIXED
Problem: luminos-bar and luminos-dock systemd services showed as active/running but bar and dock were invisible; services were crash-looping with "ERROR: GTK4 not available"
Root cause: /opt/luminos/venv/pyvenv.cfg had include-system-site-packages = false. PyGObject (the `gi` module) is a system package and cannot be pip-installed into a venv; the venv Python could not import it, so the GTK4 availability check failed immediately on every launch
Fix: Set include-system-site-packages = true in /opt/luminos/venv/pyvenv.cfg — one line change, no rebuild required
Files: /opt/luminos/venv/pyvenv.cfg

## BUG-008 — Python venv system packages missing
Date: April 2026
Status: RESOLVED (root cause retired)
Problem: Multiple UI bugs traced back to Python venv not finding system packages (GTK4, PyGObject)
Root cause: Python venv packaging is fundamentally fragile — include-system-site-packages, Python 3.14 breaking pydantic, pip vs system package conflicts
Fix: Retired Python for all UI work. Stack migrated to AGS/JS (bar/dock) and Go + libadwaita (settings/login). Prevents recurrence entirely.
Files: All src/gui/ Python files — being replaced

## BUG-006 — MemPalace normalize.py sender field
Date: April 2026
Status: FIXED
Problem: Only 3 drawers mined instead of 837 from Claude.ai export
Root cause: Claude.ai privacy exports use "sender" field not "role"; _try_claude_ai_json only checked "role"
Fix: Added sender fallback: item.get("role", "") or item.get("sender", "")
Files: ~/mempalace/mempalace/normalize.py
