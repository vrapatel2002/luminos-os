# CODE_REFERENCE.md
# Project Luminos — File Map & Architecture Reference
Last Updated: 2026-03-22 (Phase 8.12 — Wine/Proton OS Integration complete)

---

## CURRENT FILE MAP

```
C:\Users\vrati\VSCODE\Luminos\
│
├── README.md                      ← [EXISTS] Phase 9 — Project summary, hardware requirements, and ISO build instructions
├── AGENT_PROTOCOL.md              ← Agent rules (read before every task)
│
├── docs/
│   ├── MASTER_PLAN.md             ← Phase tracker, decisions log
│   ├── STATE.md                   ← Current state snapshot
│   ├── HANDOFF.md                 ← New chat template
│   ├── CODE_REFERENCE.md          ← THIS FILE — file map
│   └── CONFIGURATION.md           ← Config values reference
│
├── build/
│   └── grub.cfg                   ← [EXISTS] Phase 9 — complete GRUB boot menu for ISO
│
├── systemd/
│   └── luminos-ai.service         ← [EXISTS] systemd unit file — install to /etc/systemd/system/
│
├── src/
│   ├── daemon/
│   │   └── main.py                ← [EXISTS] luminos-ai daemon — 27-type router (ping/classify/security/launch/vm_cleanup/gpu_query/gaming_mode/model_request/model_release/manager_status/power_set/power_status/power_modes/window_register/window_unregister/window_list/upscale_set/display_status/wallpaper_set/wallpaper_status/wallpaper_files/notify + unknown), ModelManager stubs, PID file, SIGTERM/SIGINT clean shutdown, _idle_timeout_loop thread (60s), _game_watcher_loop thread (10s, battery-aware wallpaper pause)
│   │
│   ├── classifier/
│   │   ├── __init__.py            ← [EXISTS] public API — classify_binary(path) → {zone, confidence, reason}
│   │   ├── feature_extractor.py   ← [EXISTS] extract_features(path) — reads binary, returns 8 feature flags
│   │   └── zone_rules.py          ← [EXISTS] classify(features) — 6 priority rules → zone 1/2/3 decision
│   │
│   ├── sentinel/
│   │   ├── __init__.py            ← [EXISTS] public API — assess_process(pid) → {status, confidence, flags, action}
│   │   ├── process_monitor.py     ← [EXISTS] get_process_signals(pid) — 10 live /proc signals, no psutil
│   │   └── threat_rules.py        ← [EXISTS] assess(signals) — 6 priority rules → safe/suspicious/dangerous + action
│   │
│   ├── zone1/                     ← [NOT BUILT] native Linux integration
│   ├── zone2/
│   │   ├── __init__.py            ← [EXISTS] public API — run_in_zone2(exe_path) → {success, pid, runner, cmd, prefix}
│   │   ├── wine_runner.py         ← [EXISTS] detect_wine() (COMPAT_BASE first via compat_manager, then Proton+legacy fallback), build_wine_command() (get_best_runner+build_compat_env, legacy fallback), launch_windows_app() — non-blocking Popen
│   │   ├── prefix_manager.py      ← [EXISTS] get_prefix_path(), ensure_prefix_exists(), list_prefixes() — ~/.luminos/prefixes/
│   │   ├── compatibility_manager.py ← [EXISTS] Phase 8.12 — get_compat_status() (6-key: wine64/dxvk/vkd3d/vulkan/system_prefix/overall_ready), get_wine_path() (COMPAT_BASE→/usr/bin/wine64→/usr/bin/wine), get_best_runner() (PE byte scan: d3d12→vkd3d/d3d11/d3d10/d3d9→dxvk/none→plain), build_compat_env() (WINEPREFIX/WINEDEBUG/WINEARCH/DXVK_HUD/WINEESYNC/WINEFSYNC/cache paths), ensure_app_prefix() (per-app prefix + DXVK auto-apply)
│   │   └── dxvk_manager.py        ← [EXISTS] Phase 8.12 — DXVK_DLLS_64/32 (6 DLLs), is_dxvk_installed() (system32 check), install_dxvk() (copy x64+x32 + winreg native overrides → {success, dlls_installed}), get_dxvk_version() (version file reader → str|None)
│   ├── zone3/
│   │   ├── __init__.py            ← [EXISTS] public API — run_in_zone3(exe_path) → {success, session_id, error, ...}
│   │   ├── firecracker_runner.py  ← [EXISTS] detect_firecracker(), detect_kvm(), build_vm_config(), launch_vm() stub
│   │   └── session_manager.py     ← [EXISTS] create/destroy/list/cleanup_old_sessions — /tmp/luminos-vms/
│   ├── gpu_manager/
│   │   ├── __init__.py            ← [EXISTS] public API — get_hardware_status, request_model, release_model, enter/exit_gaming_mode, check_idle_timeout, get_status
│   │   ├── vram_monitor.py        ← [EXISTS] get_nvidia_vram (nvidia-smi), get_amd_vram (sysfs), get_npu_status (/dev/accel/accel0 + lsmod), get_full_hardware_status
│   │   ├── model_manager.py       ← [EXISTS] ModelManager — one model at a time, 5min idle timeout, gaming eviction, quant/layer selection
│   │   └── process_watcher.py     ← [EXISTS] is_gaming_process(), scan_running_games() — GAME_SIGNALS + /proc scan
│   ├── power_manager/
│   │   ├── __init__.py            ← [EXISTS] public API — set_mode, get_status, force_apply, list_modes
│   │   ├── powerbrain.py          ← [EXISTS] PowerBrain — MANUAL_PROFILES (quiet/balanced/max), _auto_decide, apply_current_decision, 10s background loop, _brain singleton
│   │   ├── ac_monitor.py          ← [EXISTS] get_ac_status() — /sys/class/power_supply/ AC+BAT reads (plugged_in, battery_percent, discharge_rate_w, minutes_remaining)
│   │   ├── thermal_monitor.py     ← [EXISTS] get_cpu_temp, get_gpu_temp, get_thermal_level — THRESHOLDS (warn=75/throttle=85/emergency=95°C)
│   │   ├── process_intelligence.py ← [EXISTS] has_audio(pid), is_gaming_running(), get_foreground_pid() — /proc fd + cmdline reads
│   │   └── power_writer.py        ← [EXISTS] set_cpu_governor, set_energy_preference, set_nvidia_power_limit, read_current_governor — /sys writes
│   │   [REMOVED] profiles.py      ← Deleted — replaced by MANUAL_PROFILES in powerbrain.py
│   │   [REMOVED] context_manager.py ← Deleted — replaced by PowerBrain class
│   ├── gui/
│   │   ├── __init__.py            ← [EXISTS] gui package root
│   │   ├── theme/
│   │   │   ├── __init__.py        ← [EXISTS] clean exports + module-level `mode` ModeManager singleton
│   │   │   ├── colors.py          ← [EXISTS] DARK + LIGHT palettes (27 tokens each), get_colors(dark)
│   │   │   ├── spacing.py         ← [EXISTS] RADIUS (5) + SPACING (6) + SIZING (14) + ANIMATION (3) constants
│   │   │   ├── gtk_css.py         ← [EXISTS] generate_css(dark) → complete GTK4 CSS string
│   │   │   ├── mode_manager.py    ← [EXISTS] ModeManager — auto (6am-7pm light/7pm-6am dark), manual override, get_css/get_colors
│   │   │   ├── icons.py           ← [EXISTS] find_icon(name, size), get_system_icons() — Papirus→hicolor→bundled search
│   │   │   └── luminos_icons/     ← [EXISTS] 6 SVG icons (24×24 currentColor): ai_idle, ai_active, ai_gaming, ai_offline, zone2_badge, zone3_badge
│   │   ├── common/
│   │   │   ├── __init__.py        ← [EXISTS] shared GUI utilities package marker
│   │   │   ├── socket_client.py   ← [EXISTS] DaemonClient — AF_UNIX JSON client, send(request) → dict, ping() → bool; never raises
│   │   │   └── subprocess_helpers.py ← [EXISTS] run_cmd, get_wifi_info (nmcli), get_bluetooth_powered (bluetoothctl), get_volume/set_volume/toggle_mute (pactl)
│   │   ├── bar/
│   │   │   ├── __init__.py        ← [EXISTS] bar package marker
│   │   │   ├── tray_widgets.py    ← [EXISTS] pure logic: get_ai_state/label, get_power_mode_label/color_key, get_battery_icon/color, get_wifi_icon/color_key, get_volume_icon; GTK: AIIndicator, PowerIndicator, BatteryIndicator, WiFiIndicator, BluetoothIndicator, VolumeIndicator
│   │   │   ├── bar_window.py      ← [EXISTS] LuminosBar(Gtk.ApplicationWindow) — layer-shell top bar, left/center/right overlay layout, format_clock/format_date helpers, daemon+system polling, ⚙ quick settings button
│   │   │   └── bar_app.py         ← [EXISTS] LuminosBarApp(Gtk.Application) + main() — APP_ID io.luminos.bar, SIGINT/SIGTERM via GLib.unix_signal_add
│   │   ├── launcher/
│   │   │   ├── __init__.py        ← [EXISTS] singleton get_launcher()/toggle_launcher() — creates LuminosLauncher on demand
│   │   │   ├── app_scanner.py     ← [EXISTS] scan_applications() (SEARCH_PATHS, .desktop parse, 60s cache), predict_zone() (exe heuristic + classifier fallback), search_apps() (score 100/80/50/40/20, max 12)
│   │   │   ├── launch_history.py  ← [EXISTS] add_to_history/get_recent/clear_history — ~/.config/luminos/launch_history.json, MAX_HISTORY=20, dedup by exec, timestamp
│   │   │   ├── app_result_item.py ← [EXISTS] AppResultItem(Gtk.Box) — zone badge overlay, hover highlight, _get_display_name/_get_zone_hint static pure methods
│   │   │   └── launcher_window.py ← [EXISTS] LuminosLauncher(Gtk.Window) — layer-shell OVERLAY + keyboard exclusive, search entry, FlowBox grid, Escape/Enter/Arrow nav, _launch_app (classify→Popen→window_register), show_launcher/toggle
│   │   ├── quick_settings/
│   │   │   ├── __init__.py        ← [EXISTS] singleton get_panel()/toggle_panel() — creates QuickSettingsPanel on demand
│   │   │   ├── brightness_ctrl.py ← [EXISTS] get_brightness/set_brightness/brightness_up/brightness_down — amdgpu_bl1 sysfs + pkexec fallback; clamps 5-100
│   │   │   ├── wifi_panel.py      ← [EXISTS] get_wifi_networks/get_active_connection/connect_wifi/disconnect_wifi (nmcli); WiFiPanel(Gtk.Box) — toggle + scrollable network list
│   │   │   ├── bt_panel.py        ← [EXISTS] get_bt_devices/toggle_bt_device/set_bt_power (bluetoothctl); BluetoothPanel(Gtk.Box) — toggle + paired device list + battery %
│   │   │   └── quick_panel.py     ← [EXISTS] QuickSettingsPanel(Gtk.Window) — greeting/toggles/volume/brightness/power/AI/WiFi/BT; get_greeting/get_power_mode_label/build_ai_summary pure helpers; singleton via __init__.py
│   │   └── dock/
│   │       ├── __init__.py        ← [EXISTS] dock package marker
│   │       ├── dock_config.py     ← [EXISTS] load/save/add/remove_pinned — ~/.config/luminos/dock.json, DEFAULT_PINNED (Files/Terminal/Firefox/Store/Settings), fallback on missing/corrupt
│   │       ├── dock_item.py       ← [EXISTS] DockItem(Gtk.Box) — zone badge overlay (W/⚠), open-state dot, hover magnification 48→54px; _get_tooltip/_should_show_badge static pure methods
│   │       ├── dock_window.py     ← [EXISTS] LuminosDock(Gtk.ApplicationWindow) — layer-shell bottom pin, 3-section pill (pinned|open|utils), 3s window_list poll, _sync_dock, add/remove_running_app; get_open_apps_not_pinned() pure helper
│   │       └── dock_app.py        ← [EXISTS] LuminosDockApp(Gtk.Application) + main() — APP_ID io.luminos.dock, SIGINT/SIGTERM via GLib.unix_signal_add
│   │   ├── store/
│   │   │   ├── __init__.py        ← [EXISTS] empty package marker
│   │   │   ├── store_backend.py   ← [EXISTS] Package dataclass; search_flatpak/search_apt/_parse_*; search_all (parallel threads, flatpak dedup wins, max 30); get_featured (10 hardcoded); install_package (progress_cb, classifier, daemon notify); uninstall_package; is_installed
│   │   │   ├── package_card.py    ← [EXISTS] PackageCard(Gtk.Box): icon/initials fallback, source badge (Flatpak/apt), sandboxed badge, zone badge (Wine/VM), installed ✓; pure _get_source_label/_get_zone_badge/_get_display_name/_get_initials
│   │   │   ├── store_window.py    ← [EXISTS] LuminosStore(Gtk.ApplicationWindow): 960×640, 200px sidebar (search+CATEGORIES+installed), FlowBox grid, detail Revealer (sliding), install progress bar, sort dropdown, filter pills, background search thread; CATEGORIES constant
│   │   │   └── store_app.py       ← [EXISTS] LuminosStoreApp(Gtk.Application): io.luminos.store, theme CSS, win.present(); main() entry point
│   │   ├── lockscreen/
│   │   │   ├── __init__.py        ← [EXISTS] singleton _manager; lock/unlock/is_locked/get_status/on_activity
│   │   │   ├── pam_auth.py        ← [EXISTS] PAMAuth: lazy python-pam, get_current_user, is_locked_out (self-clearing), authenticate+backoff (3→30s/5→120s/7→300s), reset; _backoff_for_attempts pure helper
│   │   │   ├── lock_window.py     ← [EXISTS] LuminosLockScreen(Gtk.Window): layer-shell OVERLAY KEYBOARD_EXCLUSIVE, 4-state stack (clock/auth/error/locked_out), Gtk.PasswordEntry+show-peek, 1s GLib timer (clock+countdown+hint blink), GestureClick+EventControllerKey (always consumes input), shake CSS on fail; pure _format_clock_time/_format_clock_date/_get_initials
│   │   │   └── lock_manager.py    ← [EXISTS] LockManager: lock() (wallpaper blur + window present), unlock(), idle daemon thread (30s poll), on_user_activity(), get_status()
│   │   ├── firstrun/
│   │   │   ├── __init__.py          ← [EXISTS] should_show_firstrun() / launch_firstrun()
│   │   │   ├── firstrun_state.py    ← [EXISTS] SetupState dataclass (17 fields); SETUP_STEPS (8 entries); is_setup_complete/mark_setup_complete (SETUP_FLAG ~/.config/luminos/.setup_complete); save_setup_state/load_setup_state (JSON, fallback to defaults)
│   │   │   ├── hardware_detector.py ← [EXISTS] detect_all() → 11-key dict (cpu/ram/npu/igpu/nvidia/storage/display/wine/firecracker/kvm); get_readiness_score() → score 0-100 / grade A-C / zone2_ready / zone3_ready / npu_ready / ai_ready / issues
│   │   │   ├── step_widgets.py      ← [EXISTS] WelcomeStep/HardwareStep/DisplayStep/AccountStep/AppearanceStep/PrivacyStep/AISetupStep/DoneStep (GTK); headless stubs; pure _get_tagline/_generate_username/_check_password_strength/_validate_account/_build_summary
│   │   │   ├── firstrun_window.py   ← [EXISTS] FirstRunWindow(Gtk.Window): no-decor fullscreen, layer-shell OVERLAY, progress dots (8 steps), Gtk.Stack CROSSFADE 200ms, Back/Continue nav, _validate_step gate (hardware always passes), apply_all_settings (theme/brightness/useradd+chpasswd via pkexec/mark_setup_complete/launch bar+dock)
│   │   │   └── firstrun_app.py      ← [EXISTS] FirstRunApp(Gtk.Application): io.luminos.firstrun, single window, destroy→quit; main() entry point
│   │   ├── settings/
│   │   │   ├── __init__.py        ← [EXISTS] launch_settings() — subprocess.Popen("luminos-settings") with Python fallback
│   │   │   ├── settings_window.py ← [EXISTS] LuminosSettings(Gtk.ApplicationWindow): 860×580, 220px sidebar (search+ListBox 11 categories+icons), Gtk.Stack slide transitions; CATEGORIES/CATEGORY_IDS/_match_category pure
│   │   │   ├── settings_app.py    ← [EXISTS] LuminosSettingsApp(Gtk.Application): io.luminos.settings, single window, present on activate; main() entry point
│   │   │   └── panels/
│   │   │       ├── __init__.py          ← [EXISTS] empty marker
│   │   │       ├── appearance_panel.py  ← [EXISTS] AppearancePanel: theme radio (dark/light/auto), 8 accent swatches, font size slider, animations toggle; pure _get_theme_mode/_get_accent_presets
│   │   │       ├── display_panel.py     ← [EXISTS] DisplayPanel: brightness slider (amdgpu_bl1), scaling dropdown 100-200%, iGPU upscaling (None/Bilinear/FSR/NIS), night light placeholder; pure _parse_resolution/_get_scale_options/_get_upscale_modes
│   │   │       ├── power_panel.py       ← [EXISTS] PowerPanel: 4 mode cards (Quiet/Auto/Balanced/Max)→daemon power_set, live CPU/GPU/battery status (3s GLib timer), sleep dropdown, charge limit slider; pure _get_power_cards/_get_sleep_options/_format_temp
│   │   │       ├── zones_panel.py       ← [EXISTS] ZonesPanel: 3 zone overview cards, per-app override table (add/remove→~/.config/luminos/zones.json), Sentinel alert toggle; pure _get_zone_color/_load_zone_overrides/_save_zone_override
│   │   │       ├── ai_panel.py          ← [EXISTS] AIPanel: daemon status grid (3s update), HIVE model table (Nexus/Bolt/Nova/Eye), NPU status (/dev/accel/accel0), gaming mode toggle→daemon; pure _get_daemon_status/_get_hive_models/_get_npu_status
│   │   │       └── about_panel.py       ← [EXISTS] AboutPanel: Luminos version, hardware summary (/proc+lspci+nvidia-smi), system info (kernel/compositor/uptime), export diagnostics button; pure _get_kernel_version/_get_hardware_info/_get_system_info/_export_report/_format_uptime
│   │   ├── notifications/
│   │   │   ├── __init__.py        ← [EXISTS] singleton _overlay; send/send_sentinel_alert/send_gaming_on/off/send_thermal_warning/send_model_loaded/get_unread_count
│   │   │   ├── notification_model.py ← [EXISTS] Notification dataclass (auto id+timestamp), NotifLevel(INFO/SUCCESS/WARNING/DANGER), NotifCategory(SYSTEM/SENTINEL/AI/POWER/NETWORK/GAMING/ZONE), 6 constructors
│   │   │   ├── toast_widget.py    ← [EXISTS] ToastWidget(Gtk.Box): 50ms progress tick auto-dismiss, action buttons, close button; pure _calc_progress/_level_css_class/_level_icon
│   │   │   ├── notification_center.py ← [EXISTS] NotificationCenter: MAX_VISIBLE_TOASTS=4, HISTORY_MAX=100, _active/_queue/_history pure Python; enqueue/dismiss/handle_action; Sentinel→daemon dispatch
│   │   │   └── toast_overlay.py   ← [EXISTS] ToastOverlay(Gtk.Window): layer-shell OVERLAY top-right, margin top=44/right=12, 340px wide; delegates to NotificationCenter
│   │   ├── wallpaper/
│   │   │   ├── __init__.py        ← [EXISTS] singleton _manager; apply_wallpaper/set_video/set_image/set_color/on_lock/on_unlock/get_status/get_files
│   │   │   ├── wallpaper_config.py ← [EXISTS] CONFIG_PATH, WALLPAPER_DIRS, DEFAULT_CONFIG (type/value/video_loop/mute/speed/blur_on_lock/dim/transition/transition_ms); load_config/save_config/get_wallpaper_files (IMAGE+VIDEO exts)
│   │   │   ├── vaapi_check.py     ← [EXISTS] check_vaapi() probes /dev/dri/renderD128 via vainfo --display drm; parses H264/HEVC/VP9/AV1; get_decode_flags() → VA-API or CPU mpv flags
│   │   │   ├── swww_controller.py ← [EXISTS] is_swww_running(pgrep)/start_swww(Popen+2s wait)/kill_swww(pkill); set_image_wallpaper(swww img+transition); set_color_wallpaper(stdlib 1×1 PNG via zlib+struct)
│   │   │   ├── video_wallpaper.py ← [EXISTS] VideoWallpaper: _build_mpv_cmd (loop/mute/speed/decode flags, no empty strings), start(Popen)/stop(terminate+wait)/pause(SIGSTOP)/resume(SIGCONT)/is_running
│   │   │   └── wallpaper_manager.py ← [EXISTS] WallpaperManager: apply(color/image/video dispatch), on_lock(pause+blur via grim+ImageMagick), on_unlock(resume+reapply), check_battery_pause(<20%+unplugged→pause), get_status
│   └── compositor/
│       ├── __init__.py            ← [EXISTS] public API — register_window, unregister_window, focus_window, list_windows, get_zone_summary, set_upscale_mode, get_display_status, generate_config; singletons _wm + _upm
│       ├── window_manager.py      ← [EXISTS] ZONE_WINDOW_RULES (zone→border/xwayland/label/opacity), WindowManager (register/unregister/focus/list/get_zone_summary)
│       ├── upscale_manager.py     ← [EXISTS] UPSCALE_MODES (off/quality/balanced/performance), UpscaleManager (set_mode/get_status), detect_display() via /sys/class/drm + xrandr fallback
│       └── compositor_config.py   ← [EXISTS] generate_sway_config(output_name), write_config(path), generate_waybar_config() — sway+waybar config generation
│
├── models/
│   ├── classifier.onnx            ← [NOT BUILT] zone classifier
│   └── sentinel.onnx              ← [NOT BUILT] security model
│
│
│
└── tests/
    ├── test_daemon.py             ← [EXISTS] daemon test suite — 10 tests: 6 comms (all types) + 4 lifecycle (shutdown, socket cleanup, PID file)
    ├── test_classifier.py         ← [EXISTS] classifier test suite — 21 tests: 8 extractor + 7 rule + 6 end-to-end
    ├── test_sentinel.py           ← [EXISTS] sentinel test suite — 19 tests: 10 rules + 5 live /proc + 4 end-to-end
    ├── test_zone2.py              ← [EXISTS] zone2 test suite — 34 tests: 5 detect + 8 build + 4 launch + 6 prefix_path + 3 ensure + 4 list + 4 e2e
    ├── test_zone3.py              ← [EXISTS] zone3 test suite — 41 tests: 4 FC detect + 4 KVM + 10 config + 7 launch + 5 session lifecycle + 4 list + 3 cleanup + 4 e2e
    ├── test_gpu_manager.py        ← [EXISTS] gpu_manager test suite — 75 tests: 6 nvidia + 5 amd + 6 npu + 2 hw_full + 5 layers + 5 quant + 9 request_model + 4 idle + 9 gaming + 4 status + 10 process_watcher + 8 daemon routing
    ├── test_powerbrain.py         ← [EXISTS] PowerBrain test suite — 59 tests: 6 AC + 7 thermal + 6 process + 8 set_mode + 11 _auto_decide + 2 thermal_override + 3 log + 5 status + 4 public_api + 7 daemon routing
    [REMOVED] test_power_manager.py ← Deleted — replaced by test_powerbrain.py
    ├── test_compositor.py         ← [EXISTS] compositor test suite — 69 tests: 10 zone rules + 12 lifecycle + 10 upscale_set + 6 status/detect + 9 sway_config + 4 write_config + 7 waybar + 11 daemon routing
    ├── test_theme.py              ← [EXISTS] theme test suite — 56 tests: 9 colors + 9 spacing + 11 gtk_css + 12 mode_manager + 8 icons + 3 SVG + 4 init
    ├── test_bar.py                ← [EXISTS] bar test suite — 56 tests: 6 format_clock + 4 format_date + 11 ai_state/label + 6 power_mode + 8 battery + 8 wifi + 5 volume + 4 wifi_info + 2 bluetooth + 2 volume_parse
    ├── test_dock.py               ← [EXISTS] dock test suite — 24 tests: 4 load + 1 save + 2 add + 2 remove + 4 tooltip + 3 badge + 4 dedup + 2 window_info + 2 poll_mocked
    ├── test_quick_settings.py     ← [EXISTS] quick settings test suite — 29 tests: 7 brightness + 3 wifi + 3 bt + 5 greeting + 2 power + 5 ai_summary
    ├── test_launcher.py           ← [EXISTS] launcher test suite — 28 tests: 3 scan + 3 parse + 4 predict_zone + 6 search + 5 history + 3 display_name + 3 zone_hint + 1 headless_toggle
    ├── test_notifications.py      ← [EXISTS] notification test suite — 23 tests: 7 model dataclass/constructors + 5 calc_progress + 5 level helpers + 5 center queue/history/sentinel + 1 headless_send
    ├── test_wallpaper.py          ← [EXISTS] wallpaper test suite — 28 tests: 5 config + 5 vaapi + 3 swww + 7 mpv cmd + 1 is_running + 5 manager + 3 daemon routing
    ├── test_store.py              ← [EXISTS] store test suite — 32 tests: 1 dataclass + 4 featured + 5 search_flatpak/apt parse + 4 search_all + 3 install + 2 uninstall + 1 is_installed + 7 PackageCard helpers + 3 CATEGORIES + 2 length gate
    ├── test_lockscreen.py         ← [EXISTS] lock screen test suite — 28 tests: 1 get_user + 3 is_locked_out + 3 backoff + 3 authenticate + 5 backoff_helper + 5 lock_window helpers + 5 lock_manager + 3 daemon routing
    ├── test_settings.py           ← [EXISTS] settings test suite — 38 tests: 2 CATEGORIES + 1 match + 6 theme_mode + 2 accent_presets + 4 display helpers + 5 power helpers + 6 zones helpers + 6 ai helpers + 5 about helpers
    ├── test_firstrun.py           ← [EXISTS] firstrun test suite — 39 tests: 3 setup_complete + 3 save/load + 1 SETUP_STEPS + 3 detect_all shape + 5 readiness score + 2 welcome + 5 generate_username + 4 password_strength + 6 validate_account + 3 build_summary + 4 validate_step + 1 apply_all dry run
    └── test_compatibility.py      ← [EXISTS] Phase 8.12 test suite — 58 tests: 9 compat_status (shape+no-crash+overall_ready) + 5 get_wine_path (priority+fallbacks) + 9 get_best_runner (d3d12/11/10/9/none/uppercase/both/missing/keys) + 11 build_compat_env (all keys+cache paths) + 4 ensure_app_prefix + 5 is_dxvk_installed + 3 install_dxvk + 3 get_dxvk_version + 2 wine_runner uses compat_manager + 6 .desktop file: 3 setup_complete + 3 save/load + 1 SETUP_STEPS + 3 detect_all shape + 5 readiness score + 2 welcome + 5 generate_username + 4 password_strength + 6 validate_account + 3 build_summary + 4 validate_step + 1 apply_all dry run
```

├── scripts/
│   ├── luminos-session.sh         ← [EXISTS] login session script: first-run check → daemon start → bar + dock + wallpaper launch; chmod +x
│   ├── install_luminos.sh         ← [EXISTS] Phase 9 — main OS installer (complete rewrite): base deps, source deploy, systemd service, compat layer, Firecracker, luminos-run-windows, MIME registration, wallpaper setup
│   ├── install_compatibility.sh   ← [EXISTS] Phase 8.12 — Wine/DXVK/VKD3D-Proton OS-level installer: WineHQ stable repo+install, DXVK 2.3.1, VKD3D-Proton 2.12, system prefix wineboot init, Vulkan runtime
│   ├── build_iso.sh               ← [EXISTS] Phase 9 — Master ISO build script: bootstraps Ubuntu chroot, strips, installs Sway stack+Luminos, builds squashfs & ISO via xorriso
│   ├── strip_ubuntu.sh            ← [EXISTS] Phase 9 — Base OS stripper: removes snap, telemetry, GNOME; installs Sway+Flatpak+fonts stack
│   └── verify_iso.sh              ← [EXISTS] Phase 9 — Post-build validator: loop-mounts ISO and squashfs to verify all required binaries and config files exist
│
├── config/
│   ├── luminos.conf               ← [EXISTS — skeleton] main config
│   └── luminos-windows.desktop    ← [EXISTS] Phase 8.12 — MIME handler for .exe/.msi/.lnk → luminos-run-windows %f; NoDisplay=true; StartupNotify=true

---

## KEY INTERFACES

### Unix Socket
```
Path:     /run/luminos/ai.sock
Protocol: JSON over Unix domain socket
Requests:
  { "type": "classify",   "binary": "/path/to/app.exe" }
  { "type": "security",   "pid": 1234, "process": "game.exe" }
  { "type": "launch",     "exe": "/path/to/app.exe", "zone": 2 }
  { "type": "launch",     "exe": "/path/to/app.exe", "zone": 3 }
  { "type": "vm_cleanup", "session_id": "abc12345" }
  { "type": "gpu_query" }
  { "type": "power",      "context": "gaming" }
  { "type": "shell",            "command": "natural language string" }
  { "type": "window_register",  "pid": N, "exe": "path", "zone": 1|2|3 }
  { "type": "window_unregister","pid": N }
  { "type": "window_list" }
  { "type": "upscale_set",      "mode": "off|quality|balanced|performance" }
  { "type": "display_status" }
```

### Classifier Output
```
{ "zone": 1, "confidence": 0.97, "reason": "native ELF binary" }
{ "zone": 2, "confidence": 0.89, "reason": "Win32 API only, no kernel drivers",
  "launch_hint": "{\"type\": \"launch\", \"exe\": \"/path/to/app.exe\", \"zone\": 2}" }
{ "zone": 3, "confidence": 0.76, "reason": "kernel-level driver detected" }
```

### Sentinel Output
```
{ "status": "safe", "confidence": 0.94, "flags": [], "action": "allow" }
{ "status": "suspicious", "confidence": 0.75, "flags": ["suspicious_cmdline"], "action": "warn" }
{ "status": "dangerous", "confidence": 0.95, "flags": ["elevated+suspicious_cmd"], "action": "block" }
```

### Zone 2 Launch Output
```
{ "success": true,  "pid": 12345, "runner": "wine"|"proton", "cmd": [...], "prefix": "~/.luminos/prefixes/game_abc12345/" }
{ "success": false, "error": "Wine/Proton not installed", "install_hint": "sudo apt install wine64", "prefix": "..." }
```

### Zone 3 Launch Output
```
{ "success": false, "error": "VM kernel not found", "note": "Real launch requires vmlinux + rootfs — stub",
  "session_id": "a1b2c3d4", "config": {...} }
{ "success": false, "error": "Firecracker not installed", "install_hint": "See https://firecracker-microvm.github.io",
  "session_id": "a1b2c3d4" }
{ "success": false, "error": "KVM not available", "reason": "...", "session_id": "a1b2c3d4" }
```

### VM Cleanup Output
```
{ "destroyed": true,  "session_id": "a1b2c3d4" }
{ "destroyed": false, "session_id": "a1b2c3d4" }
```

### GPU Hardware Status (gpu_query)
```
{ "nvidia":   {"available": true, "total_mb": 6144, "free_mb": 4880, "used_mb": 1264, "gpu_utilization_percent": 0.0},
  "amd_igpu": {"available": true, "total_mb": 512, "used_mb": 128, "free_mb": 384},
  "npu":      {"available": true, "device": "/dev/accel/accel0", "driver_loaded": true},
  "timestamp": 12345.67 }
```

### Model Request / Release / Status
```
{ "type": "model_request", "model": "nexus" }
→ {"loaded": "nexus", "quantization": "Q4", "layers": 32, "previously_unloaded": null}

{ "type": "model_release" }
→ {"unloaded": "nexus", "reason": "explicit release — NVIDIA idled"}

{ "type": "gaming_mode", "active": true }
→ {"unloaded": "nexus", "vram_freed_mb": 4096.0, "message": "NVIDIA freed for gaming"}

{ "type": "gaming_mode", "active": false }
→ {"message": "Gaming mode off — NVIDIA idle until needed"}

{ "type": "manager_status" }
→ {"active_model": null, "gaming_mode": false, "nvidia_active": false,
   "idle_timeout_seconds": 300, "seconds_since_last_use": null}
```

---

## AI INFERENCE BACKENDS

```
BACKEND          HARDWARE        FORMAT    LIBRARY
─────────────────────────────────────────────────────
llama.cpp CUDA   NVIDIA 6GB      GGUF      llama-cpp-python
llama.cpp Vulkan AMD iGPU RDNA3  GGUF      build from source -DGGML_VULKAN=ON
ONNX VitisAI     AMD XDNA NPU    ONNX      onnxruntime + amd-quark
```

---

## HIVE MODELS (when gaming finishes)

```
Model     Role              VRAM (Q4)  Location
──────────────────────────────────────────────────
Nexus     Orchestrator      ~4GB       /usr/lib/luminos/models/nexus-Q4.gguf
Bolt      Code              ~4GB       /usr/lib/luminos/models/bolt-Q4.gguf
Nova      Writing/Research  ~4GB       /usr/lib/luminos/models/nova-Q4.gguf
Eye       Vision            ~4GB       /usr/lib/luminos/models/eye-Q4.gguf
```

---

## AGENT UPDATE RULES

When you modify files, update this doc:
- Add new files with their purpose
- Change [NOT BUILT] to [EXISTS] when implemented
- Update interfaces if signatures change
- Never delete entries — mark as [REMOVED] with reason

---

END OF CODE_REFERENCE.md
