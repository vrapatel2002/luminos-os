import socket
import os
import sys
import json
import logging
import signal
import subprocess
import threading
import time

# Add src/ to path so classifier package is importable
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
try:
    from classifier import classify_binary
    _CLASSIFIER_AVAILABLE = True
except ImportError:
    _CLASSIFIER_AVAILABLE = False

try:
    from sentinel import assess_process
    _SENTINEL_AVAILABLE = True
except ImportError:
    _SENTINEL_AVAILABLE = False

try:
    from zone2 import run_in_zone2
    _ZONE2_AVAILABLE = True
except ImportError:
    _ZONE2_AVAILABLE = False

try:
    from zone3 import run_in_zone3
    from zone3.session_manager import destroy_session as _destroy_session
    _ZONE3_AVAILABLE = True
except ImportError:
    _ZONE3_AVAILABLE = False

try:
    from gpu_manager import (
        get_hardware_status  as _gpu_hardware_status,
        request_model        as _gpu_request_model,
        release_model        as _gpu_release_model,
        enter_gaming_mode    as _gpu_enter_gaming,
        exit_gaming_mode     as _gpu_exit_gaming,
        check_idle_timeout   as _gpu_check_idle_timeout,
        get_status           as _gpu_get_status,
        scan_running_games   as _gpu_scan_games,
    )
    _GPU_MANAGER_AVAILABLE = True
except ImportError:
    _GPU_MANAGER_AVAILABLE = False

try:
    from power_manager import (
        set_mode   as _pwr_set_mode,
        get_status as _pwr_get_status,
        list_modes as _pwr_list_modes,
    )
    _POWER_MANAGER_AVAILABLE = True
except ImportError:
    _POWER_MANAGER_AVAILABLE = False

try:
    from compositor import (
        register_window   as _comp_register_window,
        unregister_window as _comp_unregister_window,
        list_windows      as _comp_list_windows,
        get_zone_summary  as _comp_get_zone_summary,
        set_upscale_mode  as _comp_set_upscale_mode,
        get_display_status as _comp_get_display_status,
        generate_config   as _comp_generate_config,
    )
    _COMPOSITOR_AVAILABLE = True
except ImportError:
    _COMPOSITOR_AVAILABLE = False

try:
    from gui.notifications import (
        send_gaming_on      as _notif_gaming_on,
        send_gaming_off     as _notif_gaming_off,
        send_model_loaded   as _notif_model_loaded,
        send                as _notif_send,
    )
    _NOTIFICATIONS_AVAILABLE = True
except ImportError:
    _NOTIFICATIONS_AVAILABLE = False

try:
    from gui.wallpaper import (
        apply_wallpaper  as _wall_apply,
        get_status       as _wall_status,
        get_files        as _wall_files,
        on_lock          as _wall_on_lock,
        on_unlock        as _wall_on_unlock,
    )
    from gui.wallpaper.wallpaper_manager import _manager as _wall_manager
    _WALLPAPER_AVAILABLE = True
except ImportError:
    _WALLPAPER_AVAILABLE = False

try:
    from gui.lockscreen import (
        lock        as _lock_lock,
        unlock      as _lock_unlock,
        is_locked   as _lock_is_locked,
        get_status  as _lock_status,
        on_activity as _lock_activity,
    )
    _LOCKSCREEN_AVAILABLE = True
except ImportError:
    _LOCKSCREEN_AVAILABLE = False

SOCKET_PATH = "/tmp/luminos-test.sock"
PID_PATH = "/tmp/luminos-ai.pid"

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("luminos-ai")


# ---------------------------------------------------------------------------
# ModelManager — stubs only (no real models loaded yet)
# ---------------------------------------------------------------------------

class ModelManager:
    def __init__(self):
        self._loaded = []

    def load_model(self, name, backend):
        logger.info(f"MODEL: would load {name} on {backend}")
        return True

    def unload_model(self, name):
        logger.info(f"MODEL: would unload {name}")
        return True

    def get_status(self):
        return {
            "loaded_models": list(self._loaded),
            "backends": {"npu": False, "igpu": False, "nvidia": False},
        }

    def calculate_gpu_layers(self, model_size_gb, free_vram_mb):
        free_vram_gb = free_vram_mb / 1024.0
        if free_vram_gb >= model_size_gb:
            return 32
        elif free_vram_gb >= model_size_gb * 0.6:
            return int(32 * 0.6)
        elif free_vram_gb >= model_size_gb * 0.3:
            return int(32 * 0.3)
        else:
            return 0


# ---------------------------------------------------------------------------
# GPU detection (real — no stubs)
# ---------------------------------------------------------------------------

def query_gpu():
    nvidia = False
    free_vram_mb = None

    try:
        result = subprocess.run(
            ["nvidia-smi", "--query-gpu=memory.free", "--format=csv,noheader,nounits"],
            capture_output=True, text=True, timeout=5
        )
        if result.returncode == 0:
            nvidia = True
            lines = result.stdout.strip().splitlines()
            if lines:
                free_vram_mb = int(lines[0].strip())
    except (FileNotFoundError, subprocess.TimeoutExpired, ValueError):
        pass

    amd = os.path.exists("/dev/kfd")

    return {"nvidia": nvidia, "amd": amd, "free_vram_mb": free_vram_mb}


# ---------------------------------------------------------------------------
# Request router
# ---------------------------------------------------------------------------

def route_request(message, model_manager):
    req_type = message.get("type", "unknown")

    if req_type == "ping":
        return {"status": "ok", "service": "luminos-ai"}

    elif req_type == "classify":
        binary_path = message.get("binary")
        if not binary_path:
            return {"status": "error", "message": "missing 'binary' field"}
        if not _CLASSIFIER_AVAILABLE:
            return {"zone": 1, "confidence": 0.99, "reason": "stub - classifier not loaded"}
        try:
            result = classify_binary(binary_path)
            zone = result.get("zone")
            if zone == 2:
                result["launch_hint"] = (
                    f'{{"type": "launch", "exe": "{binary_path}", "zone": 2}}'
                )
            elif zone == 3:
                result["launch_hint"] = (
                    f'{{"type": "launch", "exe": "{binary_path}", "zone": 3}}'
                )
                result["warning"] = (
                    "Zone 3 requires Firecracker + KVM on target system"
                )
            return result
        except FileNotFoundError:
            return {"status": "error", "message": f"binary not found: {binary_path}"}
        except OSError as e:
            return {"status": "error", "message": f"cannot read binary: {e}"}

    elif req_type == "security":
        if not _SENTINEL_AVAILABLE:
            return {"status": "safe", "confidence": 0.99, "note": "stub - sentinel not loaded"}
        pid = message.get("pid")
        if pid is None:
            return {"status": "error", "message": "missing 'pid' field"}
        try:
            pid = int(pid)
        except (TypeError, ValueError):
            return {"status": "error", "message": "'pid' must be an integer"}
        return assess_process(pid)

    elif req_type == "launch":
        exe_path = message.get("exe")
        zone     = message.get("zone")
        if not exe_path:
            return {"status": "error", "message": "missing 'exe' field"}
        if zone == 2:
            if not _ZONE2_AVAILABLE:
                return {"success": False, "error": "Zone 2 runner not available"}
            result = run_in_zone2(exe_path)
            if result.get("success") and _COMPOSITOR_AVAILABLE:
                pid = result.get("pid")
                if pid:
                    result["window"] = _comp_register_window(pid, exe_path, 2)
            return result
        elif zone == 3:
            if not _ZONE3_AVAILABLE:
                return {"success": False, "error": "Zone 3 runner not available"}
            result = run_in_zone3(exe_path)
            if result.get("success") and _COMPOSITOR_AVAILABLE:
                pid = result.get("pid")
                if pid:
                    result["window"] = _comp_register_window(pid, exe_path, 3)
            return result
        return {"status": "error", "message": f"unsupported zone: {zone}"}

    elif req_type == "vm_cleanup":
        session_id = message.get("session_id")
        if not session_id:
            return {"status": "error", "message": "missing 'session_id' field"}
        if not _ZONE3_AVAILABLE:
            return {"status": "error", "message": "Zone 3 not available"}
        destroyed = _destroy_session(session_id)
        return {"destroyed": destroyed, "session_id": session_id}

    elif req_type == "gpu_query":
        if _GPU_MANAGER_AVAILABLE:
            return _gpu_hardware_status()
        return query_gpu()

    elif req_type == "gaming_mode":
        if not _GPU_MANAGER_AVAILABLE:
            return {"status": "error", "message": "GPU manager not available"}
        active = message.get("active")
        if active is True:
            return _gpu_enter_gaming()
        elif active is False:
            return _gpu_exit_gaming()
        return {"status": "error", "message": "'active' must be true or false"}

    elif req_type == "model_request":
        if not _GPU_MANAGER_AVAILABLE:
            return {"status": "error", "message": "GPU manager not available"}
        model_name = message.get("model")
        if not model_name:
            return {"status": "error", "message": "missing 'model' field"}
        result = _gpu_request_model(model_name)
        if result.get("loaded") and _NOTIFICATIONS_AVAILABLE:
            try:
                quant = result.get("quant", "Q4")
                _notif_model_loaded(model_name, quant)
            except Exception:
                pass
        return result

    elif req_type == "model_release":
        if not _GPU_MANAGER_AVAILABLE:
            return {"status": "error", "message": "GPU manager not available"}
        return _gpu_release_model()

    elif req_type == "manager_status":
        if not _GPU_MANAGER_AVAILABLE:
            return {"status": "error", "message": "GPU manager not available"}
        return _gpu_get_status()

    elif req_type == "power_set":
        if not _POWER_MANAGER_AVAILABLE:
            return {"status": "error", "message": "Power manager not available"}
        mode = message.get("mode")
        if not mode:
            return {"status": "error", "message": "missing 'mode' field"}
        return _pwr_set_mode(mode)

    elif req_type == "power_status":
        if not _POWER_MANAGER_AVAILABLE:
            return {"status": "error", "message": "Power manager not available"}
        return _pwr_get_status()

    elif req_type == "power_modes":
        if not _POWER_MANAGER_AVAILABLE:
            return {"status": "error", "message": "Power manager not available"}
        return _pwr_list_modes()

    elif req_type == "window_register":
        if not _COMPOSITOR_AVAILABLE:
            return {"status": "error", "message": "Compositor not available"}
        pid      = message.get("pid")
        exe_path = message.get("exe", "")
        zone     = message.get("zone", 1)
        if pid is None:
            return {"status": "error", "message": "missing 'pid' field"}
        try:
            pid = int(pid)
        except (TypeError, ValueError):
            return {"status": "error", "message": "'pid' must be an integer"}
        return _comp_register_window(pid, exe_path, zone)

    elif req_type == "window_unregister":
        if not _COMPOSITOR_AVAILABLE:
            return {"status": "error", "message": "Compositor not available"}
        pid = message.get("pid")
        if pid is None:
            return {"status": "error", "message": "missing 'pid' field"}
        try:
            pid = int(pid)
        except (TypeError, ValueError):
            return {"status": "error", "message": "'pid' must be an integer"}
        return _comp_unregister_window(pid)

    elif req_type == "window_list":
        if not _COMPOSITOR_AVAILABLE:
            return {"status": "error", "message": "Compositor not available"}
        return {"windows": _comp_list_windows(), "summary": _comp_get_zone_summary()}

    elif req_type == "upscale_set":
        if not _COMPOSITOR_AVAILABLE:
            return {"status": "error", "message": "Compositor not available"}
        mode = message.get("mode")
        if not mode:
            return {"status": "error", "message": "missing 'mode' field"}
        return _comp_set_upscale_mode(mode)

    elif req_type == "display_status":
        if not _COMPOSITOR_AVAILABLE:
            return {"status": "error", "message": "Compositor not available"}
        return _comp_get_display_status()

    elif req_type == "lock":
        if not _LOCKSCREEN_AVAILABLE:
            return {"status": "error", "message": "Lock screen not available"}
        result = _lock_lock()
        return {"status": "ok", "locked": result}

    elif req_type == "lock_status":
        if not _LOCKSCREEN_AVAILABLE:
            return {"status": "error", "message": "Lock screen not available"}
        try:
            return {"status": "ok", **_lock_status()}
        except Exception as e:
            return {"status": "error", "message": str(e)}

    elif req_type == "lock_activity":
        if not _LOCKSCREEN_AVAILABLE:
            return {"status": "ok"}   # silently accept even if unavailable
        try:
            _lock_activity()
        except Exception:
            pass
        return {"status": "ok"}

    elif req_type == "wallpaper_set":
        if not _WALLPAPER_AVAILABLE:
            return {"status": "error", "message": "Wallpaper system not available"}
        wtype = message.get("wallpaper_type")
        value = message.get("value", "")
        if not wtype:
            return {"status": "error", "message": "missing 'wallpaper_type' field"}
        try:
            cfg = {**_wall_status(), "type": wtype, "value": value}
            result = _wall_apply(cfg)
            return {"status": "ok", **result}
        except Exception as e:
            return {"status": "error", "message": str(e)}

    elif req_type == "wallpaper_status":
        if not _WALLPAPER_AVAILABLE:
            return {"status": "error", "message": "Wallpaper system not available"}
        try:
            return {"status": "ok", **_wall_status()}
        except Exception as e:
            return {"status": "error", "message": str(e)}

    elif req_type == "wallpaper_files":
        if not _WALLPAPER_AVAILABLE:
            return {"status": "error", "message": "Wallpaper system not available"}
        try:
            return {"status": "ok", "files": _wall_files()}
        except Exception as e:
            return {"status": "error", "message": str(e)}

    elif req_type == "notify":
        if not _NOTIFICATIONS_AVAILABLE:
            return {"status": "error", "message": "Notification system not available"}
        notif_type = message.get("notif_type", "")
        try:
            if notif_type == "sentinel_alert":
                from gui.notifications.notification_model import sentinel_alert
                _notif_send(sentinel_alert(
                    message.get("process", "unknown"),
                    message.get("threat",  "unknown"),
                ))
            elif notif_type == "gaming_on":
                _notif_gaming_on()
            elif notif_type == "gaming_off":
                _notif_gaming_off()
            elif notif_type == "thermal_warning":
                from gui.notifications import send_thermal_warning
                send_thermal_warning(float(message.get("temp", 0)))
            elif notif_type == "model_loaded":
                _notif_model_loaded(
                    message.get("model", "unknown"),
                    message.get("quant", "Q4"),
                )
            else:
                return {"status": "error", "message": f"unknown notif_type: {notif_type}"}
            return {"status": "ok", "notif_type": notif_type}
        except Exception as e:
            return {"status": "error", "message": str(e)}

    else:
        return {"status": "error", "message": "unknown request type"}


# ---------------------------------------------------------------------------
# Background threads (P6-06, P6-07, P7-07 idle path)
# ---------------------------------------------------------------------------

def _idle_timeout_loop():
    """P6-06: Check GPU idle timeout every 60s. PowerBrain auto-detects mode change.
    Also locks screen on critical battery (<5%)."""
    while True:
        time.sleep(60)
        if _GPU_MANAGER_AVAILABLE:
            result = _gpu_check_idle_timeout()
            if result.get("unloaded") is not None:
                logger.info("[IDLE CHECK] model unloaded")
            else:
                logger.info("[IDLE CHECK] no action needed")

        # Critical battery → lock screen
        if _LOCKSCREEN_AVAILABLE and not _lock_is_locked():
            try:
                from power_manager.ac_monitor import get_ac_status
                ac = get_ac_status()
                pct = ac.get("battery_percent") or 100
                if not ac.get("plugged_in", True) and pct < 5:
                    logger.warning("[BATTERY CRITICAL] locking screen")
                    _lock_lock()
            except Exception:
                pass


def _game_watcher_loop():
    """P6-07: Scan for game processes every 10s. PowerBrain auto-detects gaming."""
    while True:
        time.sleep(10)
        if not _GPU_MANAGER_AVAILABLE:
            continue
        games = _gpu_scan_games()
        status = _gpu_get_status()
        currently_gaming = status.get("gaming_mode", False)

        if games and not currently_gaming:
            name = games[0].get("name", "unknown")
            logger.info(f"[GAME DETECTED] {name} — entering gaming mode")
            _gpu_enter_gaming()
            if _NOTIFICATIONS_AVAILABLE:
                try:
                    _notif_gaming_on()
                except Exception:
                    pass
        elif not games and currently_gaming:
            logger.info("[GAME ENDED] — returning to idle")
            _gpu_exit_gaming()
            if _NOTIFICATIONS_AVAILABLE:
                try:
                    _notif_gaming_off()
                except Exception:
                    pass

        # Battery-aware video wallpaper pause
        if _WALLPAPER_AVAILABLE:
            try:
                _wall_manager.check_battery_pause()
            except Exception:
                pass


# ---------------------------------------------------------------------------
# Socket server
# ---------------------------------------------------------------------------

def setup_socket():
    if os.path.exists(SOCKET_PATH):
        try:
            os.remove(SOCKET_PATH)
        except OSError:
            logger.error(f"Cannot remove existing socket file at {SOCKET_PATH}")
            sys.exit(1)

    os.makedirs(os.path.dirname(SOCKET_PATH), exist_ok=True)

    server_socket = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    try:
        server_socket.bind(SOCKET_PATH)
    except OSError as e:
        logger.error(f"Failed to bind socket: {e}")
        sys.exit(1)

    server_socket.listen(5)
    logger.info(f"Listening on Unix socket: {SOCKET_PATH}")
    return server_socket


def cleanup(server_socket=None, exit_code=0):
    logger.info("luminos-ai shutting down")
    if server_socket:
        server_socket.close()
    if os.path.exists(SOCKET_PATH):
        try:
            os.remove(SOCKET_PATH)
            logger.info(f"Cleaned up socket file {SOCKET_PATH}")
        except OSError:
            logger.error(f"Failed to remove socket file {SOCKET_PATH}")
    if os.path.exists(PID_PATH):
        try:
            os.remove(PID_PATH)
            logger.info(f"Cleaned up PID file {PID_PATH}")
        except OSError:
            logger.error(f"Failed to remove PID file {PID_PATH}")
    sys.exit(exit_code)


def handle_client(client_socket, model_manager):
    try:
        data = client_socket.recv(4096)
        if not data:
            return

        try:
            message = json.loads(data.decode('utf-8'))
        except json.JSONDecodeError:
            response = {"status": "error", "message": "invalid json format"}
            client_socket.sendall(json.dumps(response).encode('utf-8'))
            return

        req_type = message.get("type", "unknown")
        t0 = time.monotonic()
        logger.info(f"REQUEST type={req_type} from client")

        response = route_request(message, model_manager)

        elapsed_ms = (time.monotonic() - t0) * 1000
        logger.info(f"RESPONSE type={req_type} result={json.dumps(response)} in {elapsed_ms:.1f}ms")

        client_socket.sendall(json.dumps(response).encode('utf-8'))
    except Exception as e:
        logger.error(f"Error handling client: {e}")
    finally:
        client_socket.close()


def main():
    model_manager = ModelManager()
    server_socket = setup_socket()

    # Write PID file
    try:
        with open(PID_PATH, 'w') as f:
            f.write(str(os.getpid()))
        logger.info(f"PID {os.getpid()} written to {PID_PATH}")
    except OSError as e:
        logger.error(f"Failed to write PID file: {e}")

    def sig_handler(signum, frame):
        cleanup(server_socket)

    signal.signal(signal.SIGINT, sig_handler)
    signal.signal(signal.SIGTERM, sig_handler)

    # Start background threads (daemon=True — die with main process)
    threading.Thread(target=_idle_timeout_loop, daemon=True,
                     name="luminos-idle-check").start()
    threading.Thread(target=_game_watcher_loop, daemon=True,
                     name="luminos-game-watcher").start()
    logger.info("Background threads started: idle-check (60s), game-watcher (10s)")

    logger.info("Luminos AI Daemon started (Phase 1 — stubs)")

    try:
        while True:
            client_socket, _ = server_socket.accept()
            handle_client(client_socket, model_manager)
    except KeyboardInterrupt:
        cleanup(server_socket)
    except Exception as e:
        logger.error(f"Daemon error: {e}")
        cleanup(server_socket, 1)


if __name__ == "__main__":
    main()
