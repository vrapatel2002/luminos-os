import socket
import json
import time
import sys
import os
import subprocess
import signal

SOCKET_PATH = "/tmp/luminos-ai.sock"
PID_PATH = "/tmp/luminos-ai.pid"
DAEMON_SCRIPT = os.path.join(os.path.dirname(__file__), "..", "src", "daemon", "main.py")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def start_daemon():
    """Launch daemon subprocess. Wait up to 3s for socket to appear."""
    proc = subprocess.Popen(
        [sys.executable, DAEMON_SCRIPT],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    for _ in range(30):
        if os.path.exists(SOCKET_PATH):
            return proc
        time.sleep(0.1)
    proc.kill()
    proc.wait()
    raise RuntimeError("Daemon socket did not appear within 3 seconds")


def send_request(req_dict):
    client = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    try:
        client.connect(SOCKET_PATH)
        client.sendall(json.dumps(req_dict).encode('utf-8'))
        data = client.recv(4096)
        return json.loads(data.decode('utf-8'))
    finally:
        client.close()


# ---------------------------------------------------------------------------
# Socket comms tests (run against a live daemon)
# ---------------------------------------------------------------------------

def test_ping():
    print("Testing ping...")
    resp = send_request({"type": "ping"})
    print(f"  Response: {resp}")
    assert resp.get("status") == "ok", f"Expected status 'ok', got {resp.get('status')}"
    assert resp.get("service") == "luminos-ai", f"Expected service 'luminos-ai', got {resp.get('service')}"
    print("  PASS")


def test_classify():
    print("Testing classify...")
    resp = send_request({"type": "classify", "binary": "/path/to/app.exe"})
    print(f"  Response: {resp}")
    assert "zone" in resp, "Expected 'zone' key in response"
    assert "confidence" in resp, "Expected 'confidence' key in response"
    assert "reason" in resp, "Expected 'reason' key in response"
    print("  PASS")


def test_security():
    print("Testing security...")
    resp = send_request({"type": "security", "pid": 1234, "process": "app.exe"})
    print(f"  Response: {resp}")
    assert resp.get("status") == "safe", f"Expected status 'safe', got {resp.get('status')}"
    assert "confidence" in resp, "Expected 'confidence' key in response"
    print("  PASS")


def test_gpu_query():
    print("Testing gpu_query...")
    resp = send_request({"type": "gpu_query"})
    print(f"  Response: {resp}")
    assert "nvidia" in resp, "Expected 'nvidia' key in response"
    assert "amd" in resp, "Expected 'amd' key in response"
    assert isinstance(resp["nvidia"], bool), "Expected 'nvidia' to be bool"
    assert isinstance(resp["amd"], bool), "Expected 'amd' to be bool"
    print("  PASS")


def test_power():
    print("Testing power...")
    resp = send_request({"type": "power", "context": "gaming"})
    print(f"  Response: {resp}")
    assert "profile" in resp, "Expected 'profile' key in response"
    print("  PASS")


def test_unknown():
    print("Testing unknown type...")
    resp = send_request({"type": "unknown_xyz"})
    print(f"  Response: {resp}")
    assert resp.get("status") == "error", f"Expected status 'error', got {resp.get('status')}"
    assert "unknown request type" in resp.get("message", ""), \
        f"Expected 'unknown request type' in message, got {resp.get('message')}"
    print("  PASS")


# ---------------------------------------------------------------------------
# Lifecycle tests (manage their own subprocess)
# ---------------------------------------------------------------------------

def test_pid_file_exists_while_running():
    print("Testing PID file exists while daemon is running...")
    proc = start_daemon()
    try:
        assert os.path.exists(PID_PATH), f"Expected PID file at {PID_PATH} while daemon is running"
        with open(PID_PATH) as f:
            pid_in_file = int(f.read().strip())
        assert pid_in_file == proc.pid, \
            f"PID file contains {pid_in_file}, expected {proc.pid}"
        print(f"  PID file present, PID={pid_in_file}")
        print("  PASS")
    finally:
        proc.terminate()
        proc.wait(timeout=5)


def test_clean_shutdown_sigterm():
    print("Testing clean shutdown via SIGTERM...")
    proc = start_daemon()
    proc.send_signal(signal.SIGTERM)
    try:
        exit_code = proc.wait(timeout=3)
    except subprocess.TimeoutExpired:
        proc.kill()
        proc.wait()
        raise AssertionError("Daemon did not exit within 3 seconds after SIGTERM")
    assert exit_code == 0, f"Expected exit code 0, got {exit_code}"
    print(f"  Daemon exited with code {exit_code}")
    print("  PASS")


def test_socket_cleanup_after_shutdown():
    print("Testing socket file removed after shutdown...")
    proc = start_daemon()
    assert os.path.exists(SOCKET_PATH), "Socket file should exist while daemon is running"
    proc.send_signal(signal.SIGTERM)
    proc.wait(timeout=3)
    assert not os.path.exists(SOCKET_PATH), \
        f"Socket file {SOCKET_PATH} should be removed after shutdown"
    print("  PASS")


def test_pid_file_cleanup_after_shutdown():
    print("Testing PID file removed after shutdown...")
    proc = start_daemon()
    assert os.path.exists(PID_PATH), "PID file should exist while daemon is running"
    proc.send_signal(signal.SIGTERM)
    proc.wait(timeout=3)
    assert not os.path.exists(PID_PATH), \
        f"PID file {PID_PATH} should be removed after shutdown"
    print("  PASS")


# ---------------------------------------------------------------------------
# Runner
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    # Phase A: socket comms tests — start one daemon, run all, then stop it
    print("=" * 50)
    print("PHASE A: Socket communication tests")
    print("=" * 50)

    comms_tests = [
        test_ping,
        test_classify,
        test_security,
        test_gpu_query,
        test_power,
        test_unknown,
    ]

    passed = 0
    failed = 0

    proc = start_daemon()
    try:
        for test in comms_tests:
            try:
                test()
                passed += 1
            except AssertionError as e:
                print(f"  FAIL: {e}")
                failed += 1
            except Exception as e:
                print(f"  FAIL (exception): {e}")
                failed += 1
    finally:
        proc.terminate()
        proc.wait(timeout=5)

    # Phase B: lifecycle tests — each manages its own subprocess
    print()
    print("=" * 50)
    print("PHASE B: Lifecycle / shutdown tests")
    print("=" * 50)

    lifecycle_tests = [
        test_pid_file_exists_while_running,
        test_clean_shutdown_sigterm,
        test_socket_cleanup_after_shutdown,
        test_pid_file_cleanup_after_shutdown,
    ]

    for test in lifecycle_tests:
        try:
            test()
            passed += 1
        except AssertionError as e:
            print(f"  FAIL: {e}")
            failed += 1
        except Exception as e:
            print(f"  FAIL (exception): {e}")
            failed += 1

    print()
    print("=" * 50)
    print(f"Results: {passed} passed, {failed} failed")
    if failed:
        print("OVERALL: FAIL")
        sys.exit(1)
    else:
        print("OVERALL: PASS")
