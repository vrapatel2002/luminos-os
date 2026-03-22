# STATE.md
# Project Luminos — Current State Snapshot
Last Updated: 2026-03-21

PURPOSE: Paste this at the start of every new chat so the AI has instant context.
Update this after every work session.

---

## ONE-LINE STATUS

**ALL PHASES COMPLETE — ISO build scripts ready. 757/757 tests passing. Pending: real hardware boot test.**

---

## WHAT EXISTS RIGHT NOW

```
✅ Planning documents (Master Plan v1.0 + Volume II AI Integration)
✅ .md skeleton (AGENT_PROTOCOL, MASTER_PLAN, STATE, HANDOFF, CODE_REFERENCE)
✅ Folder structure created
✅ Base files generated (requirements.txt, main.py skeleton, luminos.conf skeleton)
✅ AI dependencies verified (llama-cpp-python CUDA, ONNX Runtime, amd-quark)
✅ Phase 1 daemon (src/daemon/main.py) — 5-type router, ModelManager stubs, real gpu_query, calculate_gpu_layers(), PID file, SIGTERM/SIGINT clean shutdown
✅ systemd service file (systemd/luminos-ai.service) — ready to install to /etc/systemd/system/
✅ Test suite (tests/test_daemon.py) — 10 tests: 6 comms + 4 lifecycle (shutdown, socket cleanup, PID file), all PASS
✅ Real GPU detection: nvidia=True (nvidia-smi, ~4880MB free VRAM), amd=True (/dev/kfd)
✅ Phase 2 classifier (src/classifier/) — feature_extractor.py + zone_rules.py + __init__.py — classify_binary() wired into daemon
✅ Test suite (tests/test_classifier.py) — 21 tests (extractor + rules + end-to-end), all PASS
✅ Phase 3 Sentinel (src/sentinel/) — process_monitor.py + threat_rules.py + __init__.py — assess_process() wired into daemon
✅ Test suite (tests/test_sentinel.py) — 19 tests (rules + live /proc + end-to-end), all PASS
✅ Phase 4 Zone 2 (src/zone2/) — wine_runner.py + prefix_manager.py + __init__.py — run_in_zone2() wired into daemon
✅ Test suite (tests/test_zone2.py) — 34 tests (detect/build/launch + prefix + end-to-end), all PASS
✅ Phase 5 Zone 3 (src/zone3/) — firecracker_runner.py + session_manager.py + __init__.py — run_in_zone3() + vm_cleanup wired into daemon
✅ Test suite (tests/test_zone3.py) — 41 tests (FC detect + KVM + config + launch + session lifecycle + e2e), all PASS (1 skipped)
✅ Phase 6 GPU Manager (src/gpu_manager/) — vram_monitor.py + model_manager.py + process_watcher.py + __init__.py — full lazy-load lifecycle, gaming mode, idle timeout wired into daemon
✅ Test suite (tests/test_gpu_manager.py) — 75 tests (hw probes + model lifecycle + gaming mode + process watcher + daemon routing), all PASS
✅ Phase 7 Power Manager REBUILT as PowerBrain (src/power_manager/) — ac_monitor.py + thermal_monitor.py + process_intelligence.py + powerbrain.py + power_writer.py + __init__.py — one brain, auto+3 manual modes, thermal emergency always overrides, gaming always max, 10s background loop
✅ Test suite (tests/test_powerbrain.py) — 59 tests (AC + thermal + process + set_mode + _auto_decide + thermal override + log cap + status + public API + daemon routing), all PASS
✅ Daemon fully wired — _idle_timeout_loop (60s), _game_watcher_loop (10s); power context now handled entirely by PowerBrain auto-detection
✅ Phase 8 Compositor (src/compositor/) — window_manager.py + upscale_manager.py + compositor_config.py + __init__.py — zone-aware window rules, FSR/NIS upscaling, sway+waybar config generation, wired into daemon
✅ Test suite (tests/test_compositor.py) — 69 tests (zone rules + lifecycle + upscale + config + waybar + daemon routing), all PASS
✅ Phase 8.1 GUI Theme Foundation (src/gui/theme/) — colors.py (DARK+LIGHT 27-token palettes) + spacing.py (RADIUS/SPACING/SIZING/ANIMATION) + gtk_css.py (GTK4 CSS generator) + mode_manager.py (auto time-based dark/light) + icons.py (Papirus→hicolor→bundled) + 6 SVG icons + __init__.py (mode singleton)
✅ Test suite (tests/test_theme.py) — 56 tests (colors + spacing + CSS + mode_manager + icons + SVGs + init), all PASS
✅ Phase 8.2 Luminos Top Bar (src/gui/bar/ + src/gui/common/) — socket_client.py (DaemonClient), subprocess_helpers.py (wifi/bt/volume), tray_widgets.py (pure logic + 6 GTK tray widgets), bar_window.py (LuminosBar: layer-shell top pin, clock, daemon+system polling), bar_app.py (io.luminos.bar)
✅ Test suite (tests/test_bar.py) — 56 tests (clock/date + AI/power/battery/wifi/volume + subprocess helpers), all PASS
✅ Phase 8.3 Luminos Dock (src/gui/dock/) — dock_config.py (load/save/add/remove pinned, ~/.config/luminos/dock.json), dock_item.py (DockItem: zone badges W/⚠, open-state dot, hover magnification), dock_window.py (LuminosDock: layer-shell bottom pill, 3-section layout, 3s window_list poll, dedup logic), dock_app.py (io.luminos.dock)
✅ Test suite (tests/test_dock.py) — 24 tests (config + tooltip/badge + dedup + poll mocked), all PASS
✅ Phase 8.5 App Launcher (src/gui/launcher/) — app_scanner.py (.desktop scan, 60s cache, predict_zone heuristic+classifier, search scoring), launch_history.py (MAX_HISTORY=20, dedup, timestamp), app_result_item.py (zone badge overlay, pure static methods), launcher_window.py (LuminosLauncher: layer-shell OVERLAY keyboard-exclusive, search→FlowBox grid, Escape/Enter/Arrow nav, classify→Popen→window_register), __init__.py (singleton); bar_window.py updated: Super key + menu button → toggle_launcher(), layer-shell ON_DEMAND keyboard mode
✅ Test suite (tests/test_launcher.py) — 28 tests (scan + cache + parse + zone + search + history + name + hint + headless), all PASS
✅ Phase 8.4 Quick Settings Panel (src/gui/quick_settings/) — brightness_ctrl.py (amdgpu_bl1 sysfs, pkexec fallback, clamp 5-100), wifi_panel.py (nmcli network list + connect/disconnect, WiFiPanel GTK widget), bt_panel.py (bluetoothctl devices + battery, BluetoothPanel GTK widget), quick_panel.py (QuickSettingsPanel: greeting/toggles/volume/brightness/power/AI/WiFi/BT sections, pure logic helpers), __init__.py (singleton + toggle_panel()); bar_window.py updated with ⚙ quick settings button
✅ Test suite (tests/test_quick_settings.py) — 29 tests (brightness + wifi + bt + greeting + power + AI summary), all PASS
✅ Phase 8.6 Notification System (src/gui/notifications/) — notification_model.py (Notification dataclass, NotifLevel/NotifCategory enums, 6 constructors), toast_widget.py (ToastWidget, 50ms progress tick, action buttons, pure _calc_progress/_level_css_class/_level_icon), notification_center.py (NotificationCenter: MAX 4 visible, queue, HISTORY_MAX=100, Sentinel action dispatch), toast_overlay.py (layer-shell OVERLAY top-right, 340px wide), __init__.py (singleton, send/send_*/get_unread_count); daemon wired (gaming/model events + "notify" request type)
✅ Test suite (tests/test_notifications.py) — 23 tests (model + toast pure logic + center + headless send), all PASS
✅ Phase 8.7 Video Wallpaper Engine (src/gui/wallpaper/) — wallpaper_config.py (load/save/merge DEFAULT_CONFIG, get_wallpaper_files scan), vaapi_check.py (check_vaapi via vainfo DRM, parse H264/HEVC/VP9/AV1, get_decode_flags), swww_controller.py (is_swww_running/start_swww/kill_swww, set_image_wallpaper, set_color_wallpaper with stdlib 1×1 PNG), video_wallpaper.py (VideoWallpaper: mpv subprocess, SIGSTOP/SIGCONT pause/resume, _build_mpv_cmd pure), wallpaper_manager.py (WallpaperManager: color/image/video apply, on_lock blur via grim+ImageMagick, on_unlock, check_battery_pause <20%), __init__.py (singleton); daemon wired (wallpaper_set/status/files request types, battery pause in game_watcher_loop)
✅ Test suite (tests/test_wallpaper.py) — 28 tests (config + vaapi + swww + mpv cmd + manager + daemon routing), all PASS
✅ Phase 8.9 Luminos Store (src/gui/store/) — store_backend.py (Package dataclass, search_flatpak/apt/all with parallel threads + dedup + sort, get_featured 10 apps, install_package/uninstall_package/is_installed via subprocess, classifier post-install, daemon notification), package_card.py (PackageCard: source/sandboxed/zone/installed badges; pure _get_source_label/_get_zone_badge/_get_display_name), store_window.py (LuminosStore: 200px sidebar + FlowBox grid + detail revealer + progress bar, CATEGORIES list), store_app.py (io.luminos.store), __init__.py; dock_config.py updated (Store added to DEFAULT_PINNED)
✅ Test suite (tests/test_store.py) — 32 tests (dataclass + featured + search parse + dedup + sort + install/uninstall mocked + is_installed + PackageCard helpers + CATEGORIES + length gate), all PASS
✅ Phase 8.8 Lock Screen (src/gui/lockscreen/) — pam_auth.py (PAMAuth: lazy python-pam, get_current_user, is_locked_out, authenticate+backoff 3→30s/5→120s/7→300s, reset; _backoff_for_attempts pure helper), lock_window.py (LuminosLockScreen: layer-shell OVERLAY KEYBOARD_EXCLUSIVE, 4 states clock/auth/error/locked_out, Gtk.PasswordEntry, 1s GLib timer, shake CSS on fail; _format_clock_time/_format_clock_date/_get_initials pure), lock_manager.py (LockManager: lock/unlock, idle daemon thread 30s poll, on_user_activity, get_status), __init__.py (singleton); daemon wired (lock/lock_status/lock_activity request types, battery critical <5% → lock in idle_timeout_loop)
✅ Test suite (tests/test_lockscreen.py) — 28 tests (pam_auth + backoff helper + lock_window helpers + lock_manager + daemon routing), all PASS
✅ Phase 8.11 First Run Setup Wizard (src/gui/firstrun/) — firstrun_state.py (SetupState dataclass 17 fields, SETUP_STEPS 8 entries, is_setup_complete/mark_setup_complete flag at ~/.config/luminos/.setup_complete, save/load JSON), hardware_detector.py (detect_all: cpu/ram/npu/igpu/nvidia/storage/display/wine/fc/kvm, get_readiness_score: score 0-100, grade A/B/C), step_widgets.py (WelcomeStep/HardwareStep/DisplayStep/AccountStep/AppearanceStep/PrivacyStep/AISetupStep/DoneStep + pure helpers), firstrun_window.py (FirstRunWindow: layer-shell OVERLAY fullscreen, progress dots, Gtk.Stack CROSSFADE, Back/Continue nav, _validate_step gate, apply_all_settings useradd+chpasswd+launch), firstrun_app.py (io.luminos.firstrun), __init__.py (should_show_firstrun/launch_firstrun); scripts/luminos-session.sh (first-run check→daemon start→bar+dock+wallpaper)
✅ Test suite (tests/test_firstrun.py) — 39 tests (setup_complete/mark/round-trip/SETUP_STEPS/detect_all shape/readiness A/C/partial/validate_step/password strength/generate_username/validate_account/build_summary/apply_all dry run), all PASS
✅ Phase 8.10 Luminos Settings App (src/gui/settings/) — settings_window.py (LuminosSettings 860×580: 220px sidebar search+11 categories, Gtk.Stack slide transitions; CATEGORIES/_match_category pure), panels/appearance_panel.py (theme radio, 8 accent swatches, font slider, animations; _get_theme_mode/_get_accent_presets pure), panels/display_panel.py (brightness, scaling 100-200%, iGPU upscaling, night light; _parse_resolution pure), panels/power_panel.py (4 mode cards→daemon, live status 3s, sleep/threshold; _get_power_cards/_format_temp pure), panels/zones_panel.py (zone cards, per-app overrides→zones.json, Sentinel toggle; _get_zone_color/_load/_save pure), panels/ai_panel.py (daemon status, HIVE table, NPU status, gaming toggle; _get_daemon_status/_get_hive_models pure), panels/about_panel.py (hw summary, system info, export diagnostics; _get_hardware_info/_export_report pure), settings_app.py (io.luminos.settings), __init__.py (launch_settings); quick_panel.py: "Open Settings…" button; bar_window.py: ⚙ → launch_settings()
✅ Test suite (tests/test_settings.py) — 38 tests (categories + match + theme_mode + accent + scale/upscale/resolution + power_cards/sleep/temp + zone_color/overrides + daemon_status/hive/npu + kernel/hardware/export/uptime), all PASS
✅ Phase 8.12 Wine/Proton OS Integration (scripts/install_compatibility.sh) — Wine64+DXVK 2.3.1+VKD3D-Proton 2.12 baked as OS components at /usr/lib/luminos/compatibility/; system prefix /var/lib/luminos/prefixes/default; DXVK auto-applied per app; WINEESYNC/FSYNC enabled; .exe MIME handler luminos-windows.desktop + luminos-run-windows wrapper registered
✅ Phase 8.12 compatibility_manager.py — get_compat_status() 6-key dict, get_wine_path() COMPAT_BASE-first, get_best_runner() PE byte scan d3d12→vkd3d/d3d11/d3d10/d3d9→dxvk/none→plain wine, build_compat_env() full env dict, ensure_app_prefix() per-app prefix with DXVK auto-apply
✅ Phase 8.12 dxvk_manager.py — is_dxvk_installed(), install_dxvk() (x64+x32 copy + winreg native overrides), get_dxvk_version()
✅ Phase 8.12 wine_runner.py updated — detect_wine() uses get_wine_path() first, build_wine_command() uses get_best_runner()+build_compat_env(); all legacy fallback preserved
✅ Phase 9 ISO Build scripts ready — strip_ubuntu.sh, install_luminos.sh, build_iso.sh, verify_iso.sh, grub.cfg, and project README.md. build outputs added to .gitignore.
❌ No ONNX models yet
❌ No vmlinux + rootfs.ext4 yet (Zone 3 launch stubbed until target hardware)
```

---

## HARDWARE (Development Machine)

```
CPU:  AMD Ryzen AI (with XDNA NPU — 16 TOPS)
NPU:  AMD XDNA — target for Classifier + Sentinel (ONNX/VitisAI)
iGPU: AMD Radeon RDNA3 — target for display + Vulkan compute fallback
GPU:  NVIDIA (6GB GDDR6) — target for gaming + HIVE models (CUDA)
OS:   Windows 11 (dev machine) — Luminos will run on Linux target
IDE:  Firebase Studio (browser) + Claude Code
```

---

## KEY ARCHITECTURE DECISIONS

```
Base OS:        Ubuntu LTS (strip Snap/telemetry/GNOME)
AI Inference:   llama.cpp direct (no Ollama)
  - NVIDIA:     CUDA backend (llama-cpp-python)
  - iGPU:       Vulkan backend (cmake -DGGML_VULKAN=ON)
  - NPU:        ONNX Runtime VitisAI provider
IPC:            Unix socket → /run/luminos/ai.sock
Daemon:         luminos-ai.service (systemd)
Zone 3 VM:      Firecracker microVM (not QEMU)
```

---

## WHAT'S NEXT

- P1-04 — Real model loading with tiered strategy (NPU → NVIDIA → iGPU → CPU) [deferred to when models are ready]
- Phase 2/3 remaining — ONNX model training + NPU deployment (deferred until hardware ready)
- Phase 4 remaining — P4-07/08: real .exe test on Linux target with wine64 installed
- Phase 5 remaining — P5-08/09: build vmlinux + rootfs.ext4, test real VM boot on target
- Phase 9 remaining — Real hardware / VM boot test of the generated ISO

---

## KNOWN ISSUES / BLOCKERS

_None yet — project just started._

---

## LAST SESSION SUMMARY

**2026-03-21:** Planning complete. All .md docs created. Ready to start coding Phase 0.
**2026-03-22:** P0-08 complete. Hello-world daemon written and tested. All tests PASS. Phase 0 fully complete. Ready for Phase 1.
**2026-03-22:** P1-01/02/03/05 complete. Daemon upgraded to full Phase 1 router. ModelManager class added. Real gpu_query using nvidia-smi + /dev/kfd. 6/6 tests PASS.
**2026-03-22:** P1-06/07/08 complete. systemd service file written. PID file, SIGTERM/SIGINT clean shutdown, socket cleanup all added and tested. 10/10 tests PASS.
**2026-03-22:** Phase 2 classifier pipeline complete. feature_extractor.py, zone_rules.py, __init__.py built. classify stub in daemon replaced with real classify_binary(). 21/21 tests PASS.
**2026-03-22:** Phase 3 Sentinel pipeline complete. process_monitor.py (10 /proc signals, stdlib only), threat_rules.py (6 rules), __init__.py built. security stub replaced with real assess_process(). 19/19 tests PASS.
**2026-03-22:** Phase 4 Zone 2 complete. wine_runner.py (detect/build/launch), prefix_manager.py (per-app isolated Wine prefixes with sha256 dir hash), __init__.py (run_in_zone2). Daemon: launch request type + classify launch_hint added. 34/34 tests PASS.
**2026-03-22:** Phase 5 Zone 3 complete. firecracker_runner.py (detect FC+KVM, build_vm_config, stubbed launch_vm), session_manager.py (create/destroy/list/cleanup_old_sessions), __init__.py (run_in_zone3 with session cleanup on failure). Daemon: zone:3 launch + vm_cleanup + classify warning/hint. 41/41 tests PASS (1 skipped).
**2026-03-22:** Phase 6 GPU Manager complete. vram_monitor.py (nvidia-smi + AMD sysfs + NPU accel0/lsmod), model_manager.py (Apple-style: one model at a time, 5min idle timeout, gaming eviction, no preload on exit, auto quant selection), process_watcher.py (GAME_SIGNALS + /proc scan). Daemon: 5 new request types. 75/75 tests PASS.
**2026-03-22:** Phase 7 Power Manager complete. profiles.py (4 dataclass profiles), power_writer.py (/sys governor+EPP+nvidia writes, PermissionError graceful), context_manager.py (ContextManager, CONTEXT_MAP, auto_detect, 20-entry log). gaming_mode now atomically drives GPU eviction + power profile. Daemon: power_set/power_status/power_auto added. 73/73 tests PASS.
**2026-03-22:** P6-06/07 + P7-06/07 wired. Daemon now fully connected: model_request→ai_task power context, model_release→idle power context. Two background threads added to main(): _idle_timeout_loop (60s, daemon=True) checks gpu idle and sets power→idle on eviction; _game_watcher_loop (10s, daemon=True) auto-enters/exits gaming mode + power context based on /proc game scan. 263/263 tests PASS.
**2026-03-22:** Phase 8 Compositor complete. window_manager.py (ZONE_WINDOW_RULES, WindowManager lifecycle), upscale_manager.py (FSR/NIS modes, /sys + xrandr detect_display), compositor_config.py (sway+waybar generation + write_config), __init__.py (singletons). Daemon: 5 new request types + launch auto-registers zone2/3 windows. 69/69 new tests. 332/332 total PASS.
**2026-03-22:** Power manager rebuilt as PowerBrain. Deleted profiles.py + context_manager.py + test_power_manager.py. Created ac_monitor.py, thermal_monitor.py, process_intelligence.py, powerbrain.py. Rewrote __init__.py + power_writer.py (removed apply_profile + profiles import). Daemon: power_set now takes mode (auto/quiet/balanced/max), removed power_auto + legacy power stub, removed all _pwr_set_context calls from model_request/release/gaming_mode/threads. 59/59 tests PASS. 318/318 total PASS.
**2026-03-22:** Phase 8.1 GUI Theme Foundation complete. Created src/gui/theme/: colors.py (DARK+LIGHT 27-token palettes), spacing.py (RADIUS/SPACING/SIZING/ANIMATION), gtk_css.py (full GTK4 CSS from dicts), mode_manager.py (auto 6am-7pm light/7pm-6am dark + manual override), icons.py (Papirus→hicolor→bundled resolver), 6 SVG icons (24×24 currentColor), theme/__init__.py (mode singleton). No display server needed. 56/56 tests PASS. 374/374 total PASS.
**2026-03-22:** Phase 8.2 Luminos Top Bar complete. Created src/gui/common/: socket_client.py (DaemonClient AF_UNIX JSON, never raises), subprocess_helpers.py (nmcli/bluetoothctl/pactl wrappers). Created src/gui/bar/: tray_widgets.py (pure logic + 6 GTK tray widgets with static testable methods), bar_window.py (LuminosBar: layer-shell top, Overlay center clock, GLib timers 1s/5s/10s), bar_app.py (io.luminos.bar, SIGINT/SIGTERM). 56/56 tests PASS. 430/430 total PASS.
**2026-03-22:** Phase 8.3 Luminos Dock complete. Created src/gui/dock/: dock_config.py (JSON persistence ~/.config/luminos/dock.json, DEFAULT_PINNED, load/save/add/remove), dock_item.py (DockItem: W/⚠ zone badge overlay, open-state dot, hover 48→54px, _get_tooltip/_should_show_badge pure statics), dock_window.py (LuminosDock: layer-shell bottom pill, 3-section left/center/right, 3s window_list poll, _sync_dock dedup, get_open_apps_not_pinned() pure helper), dock_app.py (io.luminos.dock). 24/24 tests PASS. 454/454 total PASS.
**2026-03-22:** Phase 8.5 App Launcher complete. Created src/gui/launcher/: app_scanner.py (scan_applications 60s cache + .desktop parse + predict_zone exe-heuristic + search scoring name/comment/cats/exec max 12), launch_history.py (add/get/clear, MAX_HISTORY=20, dedup by exec, ~/.config/luminos/launch_history.json), app_result_item.py (AppResultItem: zone badge overlay, hover highlight, _get_display_name/_get_zone_hint pure statics), launcher_window.py (LuminosLauncher: layer-shell OVERLAY keyboard-exclusive, search entry, FlowBox icon grid, Escape/Enter/Arrow nav, _launch_app classify→Popen→window_register), __init__.py (singleton toggle_launcher). bar_window.py updated: Gdk import, Super_L/Super_R key controller, menu button→toggle_launcher(), layer-shell ON_DEMAND keyboard mode. 28/28 tests PASS. 511/511 total PASS.
**2026-03-22:** Phase 8.4 Quick Settings Panel complete. Created src/gui/quick_settings/: brightness_ctrl.py (amdgpu_bl1 sysfs read/write, PermissionError→pkexec tee fallback, clamp 5-100, up/down helpers), wifi_panel.py (get_wifi_networks/get_active_connection/connect_wifi/disconnect_wifi via nmcli; WiFiPanel GTK widget with toggle + network list), bt_panel.py (get_bt_devices/toggle_bt_device/set_bt_power via bluetoothctl; BluetoothPanel GTK widget with toggle + device list + battery%), quick_panel.py (QuickSettingsPanel Gtk.Window: 8 sections — greeting/toggles/volume/brightness/power-mode/AI-status/WiFi-expand/BT-expand; pure helpers get_greeting/get_power_mode_label/build_ai_summary), __init__.py (singleton get_panel()/toggle_panel()). bar_window.py updated: ⚙ button in right tray → toggle_panel(). 29/29 tests PASS. 483/483 total PASS.
**2026-03-22:** Phase 8.6 Notification System complete. Created src/gui/notifications/: notification_model.py (Notification dataclass, NotifLevel/NotifCategory enums, 6 constructors), toast_widget.py (ToastWidget: 50ms progress tick, action buttons, close button, pure _calc_progress/_level_css_class/_level_icon), notification_center.py (MAX 4 visible, queue, HISTORY_MAX=100, Sentinel action dispatch to daemon), toast_overlay.py (layer-shell OVERLAY top-right, margin 44/12, 340px), __init__.py (singleton, 7 send functions). Daemon wired: gaming on/off + model_request success → notifications; "notify" request type. 23/23 tests PASS. 534/534 total PASS.
**2026-03-22:** Phase 8.7 Video Wallpaper Engine complete (see above).
**2026-03-22:** Phase 8.9 Luminos Store complete. Created src/gui/store/: store_backend.py (Package dataclass, search_flatpak/apt/all parallel threads dedup max-30, get_featured 10, install/uninstall/is_installed subprocess wrappers, _classify_installed post-install, _notify_install daemon), package_card.py (PackageCard + pure helpers), store_window.py (LuminosStore 960×640, sidebar+grid+detail revealer+progress, background search thread), store_app.py (io.luminos.store), __init__.py. dock_config.py: Store added to DEFAULT_PINNED. 32/32 tests PASS. 622/622 total PASS.
**2026-03-22:** Phase 8.11 First Run Setup Wizard complete. Created src/gui/firstrun/: firstrun_state.py (SetupState + SETUP_STEPS + is_setup_complete/mark_setup_complete/save/load), hardware_detector.py (detect_all 11-key + get_readiness_score A/B/C), step_widgets.py (8 GTK step classes + pure helpers), firstrun_window.py (FirstRunWindow layer-shell OVERLAY fullscreen + progress dots + validation gate + apply_all_settings), firstrun_app.py (io.luminos.firstrun), __init__.py (should_show_firstrun/launch_firstrun). scripts/luminos-session.sh created. 39/39 new tests PASS. 699/699 total PASS.
**2026-03-22:** Phase 8.12 Wine/Proton OS Integration complete. Wine+DXVK+VKD3D-Proton baked as OS components. install_compatibility.sh (6-section: WineHQ/DXVK/VKD3D/prefix/Vulkan/verify), compatibility_manager.py (get_compat_status/get_wine_path/get_best_runner/build_compat_env/ensure_app_prefix), dxvk_manager.py (is_dxvk_installed/install_dxvk/get_dxvk_version), wine_runner.py updated (compat_manager first, legacy fallback), install_luminos.sh (main OS installer), luminos-windows.desktop (.exe MIME handler), luminos-run-windows wrapper. 58/58 new tests PASS. 757/757 total PASS.
**2026-03-22:** Phase 8.10 Luminos Settings App complete. Created src/gui/settings/: settings_window.py (LuminosSettings 860×580, 220px sidebar, 11 CATEGORIES, Gtk.Stack slide), panels/appearance_panel.py, panels/display_panel.py, panels/power_panel.py, panels/zones_panel.py, panels/ai_panel.py, panels/about_panel.py, settings_app.py (io.luminos.settings), __init__.py (launch_settings). quick_panel.py: "Open Settings…" button at bottom. bar_window.py: ⚙ tooltip → "Settings", handler → launch_settings(). 38/38 new tests PASS. 660/660 total PASS.
**2026-03-22:** Phase 8.8 Lock Screen complete. Created src/gui/lockscreen/: pam_auth.py (PAMAuth lazy pam import, get_current_user, is_locked_out self-clearing, authenticate+3-tier backoff, reset, _backoff_for_attempts pure helper), lock_window.py (LuminosLockScreen: layer-shell OVERLAY KEYBOARD_EXCLUSIVE, 4-state stack clock/auth/error/locked_out, Gtk.PasswordEntry show-peek, 1s GLib clock+countdown, GestureClick+EventControllerKey, shake CSS, _format_clock_time/_format_clock_date/_get_initials pure), lock_manager.py (LockManager: lock/unlock with wallpaper blur, idle daemon thread 30s poll, on_user_activity, get_status), __init__.py (singleton 5 functions). Daemon: lock/lock_status/lock_activity request types; _idle_timeout_loop checks battery <5% + unplugged → auto-lock. 28/28 tests PASS. 590/590 total PASS. Created src/gui/wallpaper/: wallpaper_config.py (load/save/merge DEFAULT_CONFIG, get_wallpaper_files IMAGE+VIDEO ext scan), vaapi_check.py (vainfo --display drm probe, H264/HEVC/VP9/AV1 detection, get_decode_flags VA-API or CPU), swww_controller.py (pgrep/start/kill swww-daemon, swww img + transition, stdlib 1×1 PNG for color), video_wallpaper.py (VideoWallpaper: mpv subprocess, SIGSTOP/SIGCONT, pure _build_mpv_cmd), wallpaper_manager.py (WallpaperManager: color/image/video dispatch, grim+ImageMagick blur-on-lock, battery-aware pause <20%), __init__.py (singleton, 8 public functions). Daemon: wallpaper_set/status/files request types; check_battery_pause every 10s in game_watcher_loop. 28/28 tests PASS. 562/562 total PASS.

---

END OF STATE.md
