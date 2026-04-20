# DAEMON_ARCHITECTURE.md — Luminos OS Daemon Technical Blueprint
# Created: April 2026 | By: claude-code
# Decision: 13 — Go/Python Split Architecture
# This is the authoritative spec for all daemon implementation work.

---

## Component Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│                     USER / KDE PLASMA / Qt APPS                 │
└──────────────┬──────────────────────────────────────────────────┘
               │ Unix socket (JSON)
               ▼
┌─────────────────────────────────────────────────────────────────┐
│              luminos-ai  (Go)  /run/luminos/ai.sock             │
│  Main daemon: request routing, session mgmt, health checks      │
│  Spawns / supervises all sub-daemons on startup                 │
└────┬──────────────┬──────────────┬──────────────┬──────────────┘
     │              │              │              │
     ▼              ▼              ▼              ▼
┌─────────┐  ┌──────────┐  ┌──────────┐  ┌────────────┐
│luminos- │  │luminos-  │  │luminos-  │  │GPU         │
│power    │  │sentinel  │  │router    │  │lifecycle   │
│(Go)     │  │(Go)      │  │(Go)      │  │manager     │
│         │  │          │  │          │  │(Go)        │
│sysfs:   │  │/proc     │  │PE header │  │VRAM state  │
│governor │  │scanner   │  │rules     │  │idle/gaming │
│NVIDIA   │  │kill proc │  │cache     │  │eviction    │
│asusctl  │  │notify    │  │          │  │            │
└─────────┘  └────┬─────┘  └────┬─────┘  └─────┬──────┘
                  │              │               │
         Unix socket    Unix socket      Unix socket
         (JSON)         (JSON)           (JSON)
                  │              │               │
                  ▼              ▼               ▼
        ┌──────────────┐ ┌──────────────┐ ┌──────────────┐
        │ luminos-npu  │ │ luminos-     │ │ llama-server │
        │ (Python)     │ │ classifier   │ │ (Python)     │
        │              │ │ (Python)     │ │              │
        │ ONNX/VitisAI │ │ ONNX model   │ │ llama-cpp-   │
        │ NPU sentinel │ │ edge-case    │ │ python       │
        │ NPU router   │ │ routing      │ │ HIVE agents  │
        │ AMD XDNA     │ │ CPU-based    │ │ NVIDIA dGPU  │
        └──────────────┘ └──────────────┘ └──────────────┘
```

---

## Go vs Python Split — Reasoning

| Component | Language | Why |
|-----------|----------|-----|
| luminos-ai socket server | Go | Pure routing, no ML. Static binary. |
| luminos-power | Go | Reads /sys, writes sysfs, no ML. |
| luminos-sentinel (scanner + rules) | Go | /proc polling, kill(), notify-send. No ML. |
| luminos-router (rule engine + cache) | Go | PE header parsing, deterministic rules. |
| GPU lifecycle state machine | Go | Policy logic only, no inference. |
| NPU inference service | Python | ONNX VitisAI has no Go bindings. |
| Classifier ML edge cases | Python | ONNX model requires onnxruntime + numpy. |
| HIVE / llama.cpp serving | Python | llama-cpp-python is the standard binding. |

**Rule**: If a daemon touches ONNX, VitisAI, llama.cpp, or numpy → Python.
Everything else → Go.

---

## Socket Paths

| Service | Socket Path | Protocol | Owner |
|---------|------------|----------|-------|
| luminos-ai | `/run/luminos/ai.sock` | JSON, one request/response | root |
| luminos-power | `/run/luminos/power.sock` | JSON | root |
| luminos-sentinel | `/run/luminos/sentinel.sock` | JSON | root |
| luminos-router | `$XDG_RUNTIME_DIR/luminos-router.sock` | newline-delimited JSON | user |
| luminos-npu (Python) | `/run/luminos/npu.sock` | JSON | root |
| luminos-classifier (Python) | `/run/luminos/classifier.sock` | JSON | root |
| llama-server (Python) | `/run/luminos/llama.sock` | JSON | user |

---

## Startup Order

Phase 1 (Go only — no AI required):
```
1. luminos-power    → Apply initial power mode (AC/battery detect)
2. luminos-sentinel → Start /proc scanner with rule-only mode
3. luminos-router   → Start PE rule engine, cache ready
4. luminos-ai       → Main socket open, routes to sub-services
```

Phase 2+ (add Python inference):
```
5. luminos-npu (Python)        → Load ONNX models onto NPU
6. luminos-classifier (Python) → Load edge-case model (CPU)
7. llama-server (Python)       → llama.cpp ready (lazy — loads on first request)
```

Sentinel and router fall back to rule-only mode if their Python inference
services are not yet available. luminos-ai returns `"mode": "rules_only"` in
status until Python services are online.

---

## Build Phases

### Phase 1 — Go Foundation
**Goal**: All system daemons running, no NPU or AI models required.
**Deliverables**:
- `src/go/luminos-ai/` — main daemon, socket server, ping/health/status
- `src/go/luminos-power/` — AC monitor, thermal monitor, CPU governor writer, NVIDIA power limit
- `src/go/luminos-sentinel/` — /proc scanner, threat rule engine, notify-send, SIGKILL
- `src/go/luminos-router/` — PE header parser, rule-based classification, JSON cache

**Test independently**:
```bash
# Each daemon: start, send ping, get response
echo '{"type":"ping"}' | nc -U /run/luminos/ai.sock
echo '{"type":"status"}' | nc -U /run/luminos/power.sock
echo '{"type":"classify","path":"/path/to/app.exe"}' | nc -U $XDG_RUNTIME_DIR/luminos-router.sock
```
Phase 1 passes when: all 4 Go daemons start, accept connections, return sensible responses.
Phase 1 works with: no GPU, no NPU, no Python, no AI models.

---

### Phase 2 — Compat Router Complete
**Goal**: Full .exe → zone routing including AI edge cases.
**Depends on**: Phase 1
**Deliverables**:
- `src/python/classifier/` — ONNX inference service for edge-case classification
- luminos-router (Go) updated to call Python classifier service for uncertain cases
- Cache layer: per-exe JSON result files in `~/.cache/luminos/router/`
- systemd service: `luminos-classifier.service`

**Test independently**:
```bash
# Test rule path (fast, no ML)
echo '{"type":"classify","path":"/game/game.exe"}' | nc -U $XDG_RUNTIME_DIR/luminos-router.sock
# Expect: zone 4 (has anticheat), answered by rules in <50ms

# Test ML path (slower, needs Python service)
echo '{"type":"classify","path":"/app/unusual.exe"}' | nc -U $XDG_RUNTIME_DIR/luminos-router.sock
# Expect: zone + confidence, answered in <3s
```
Phase 2 passes when: any .exe classifies to a zone, rule cases answer in <50ms,
edge cases answer in <3s, result is cached on second call (instant).

---

### Phase 3 — NPU + Sentinel ML
**Goal**: Sentinel uses AMD XDNA NPU for ML threat classification.
**Depends on**: Phase 1
**REQUIRES**: Real G14 hardware — NPU must be present.
**Deliverables**:
- `src/python/npu/` — ONNX VitisAI inference service
- sentinel ONNX model trained and converted (.onnx)
- router ONNX model trained and converted (.onnx)
- luminos-sentinel (Go) updated to call npu service for suspicious processes
- NPU priority queue: sentinel yields to router (sentinel paused ≤3s)
- systemd service: `luminos-npu.service`

**Test independently**:
```bash
# Verify NPU is detected
python3 -c "import onnxruntime as ort; print('VitisAI' in ort.get_available_providers())"
# Should print: True

# Test NPU sentinel inference
echo '{"type":"classify_process","pid":1234,"syscalls":["execve","connect"]}' \
  | nc -U /run/luminos/npu.sock
# Expect: {"classification":"normal","confidence":0.95}
```
Phase 3 passes when: NPU detected on real G14, sentinel model loads, inference returns
in <100ms, Sentinel daemon classifies processes using NPU instead of rules-only.

---

### Phase 4 — HIVE + llama.cpp
**Goal**: HIVE agents (Nexus, Bolt, Nova, Eye) available via GPU inference.
**Depends on**: Phase 1
**Deliverables**:
- `src/python/hive/` — llama-cpp-python server, one model at a time
- luminos-ai (Go) model manager updated to request/evict via llama-server socket
- Gaming mode integration: luminos-ai gets gaming_mode event, tells llama-server to evict
- HIVE models downloaded: 4x ~4GB Q4 models in `/opt/luminos/models/`
- Idle eviction: model unloaded after 5 minutes, NVIDIA idles
- systemd service: `luminos-llama.service` (user session, not root)

**Test independently**:
```bash
# Request HIVE model
echo '{"type":"model_request","model":"bolt"}' | nc -U /run/luminos/ai.sock
# Expect: {"loaded":"bolt","quantization":"Q4","layers":32}

# Confirm eviction on gaming
echo '{"type":"gaming_mode","active":true}' | nc -U /run/luminos/ai.sock
echo '{"type":"manager_status"}' | nc -U /run/luminos/ai.sock
# Expect: active_model: null, gaming_mode: true
```
Phase 4 passes when: any HIVE model loads, inference returns valid text, gaming mode
evicts model immediately, idle timeout unloads after 5 minutes.

---

## Go Daemon Skeleton (Standard Pattern)

Every Go daemon follows this pattern:

```go
package main

import (
    "encoding/json"
    "log"
    "net"
    "os"
    "os/signal"
    "syscall"
)

const socketPath = "/run/luminos/DAEMON.sock"

func main() {
    // Remove stale socket
    os.Remove(socketPath)

    l, err := net.Listen("unix", socketPath)
    if err != nil {
        log.Fatalf("listen: %v", err)
    }
    defer l.Close()

    // Clean up on signal
    c := make(chan os.Signal, 1)
    signal.Notify(c, syscall.SIGINT, syscall.SIGTERM)
    go func() {
        <-c
        os.Remove(socketPath)
        os.Exit(0)
    }()

    log.Printf("DAEMON listening on %s", socketPath)
    for {
        conn, err := l.Accept()
        if err != nil {
            continue
        }
        go handleConn(conn)
    }
}

func handleConn(conn net.Conn) {
    defer conn.Close()
    dec := json.NewDecoder(conn)
    enc := json.NewEncoder(conn)

    var req map[string]interface{}
    if err := dec.Decode(&req); err != nil {
        return
    }

    resp := route(req)
    enc.Encode(resp)
}
```

---

## Python Inference Service Skeleton (Standard Pattern)

```python
#!/usr/bin/env python3
"""
Inference service skeleton. Listens on Unix socket, responds to JSON requests.
Never imports Go code. Pure inference + numpy + onnxruntime.
"""
import json, os, socket, logging

SOCKET_PATH = "/run/luminos/INFERENCE.sock"
logger = logging.getLogger("luminos.inference")

def handle(req: dict) -> dict:
    if req.get("type") == "ping":
        return {"status": "ok"}
    # ... inference logic
    return {"error": "unknown request"}

def main():
    if os.path.exists(SOCKET_PATH):
        os.unlink(SOCKET_PATH)
    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as srv:
        srv.bind(SOCKET_PATH)
        os.chmod(SOCKET_PATH, 0o600)
        srv.listen(4)
        while True:
            conn, _ = srv.accept()
            with conn:
                data = conn.recv(65536)
                req = json.loads(data)
                resp = handle(req)
                conn.sendall(json.dumps(resp).encode() + b"\n")

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    main()
```

---

## Source Layout (Target)

```
src/
  go/
    luminos-ai/         Phase 1 — main socket server
    luminos-power/      Phase 1 — power daemon
    luminos-sentinel/   Phase 1 — process scanner + rules
    luminos-router/     Phase 1 — PE analysis + rule engine
  python/
    npu/                Phase 3 — ONNX VitisAI inference service
    classifier/         Phase 2 — edge-case ONNX model
    hive/               Phase 4 — llama-cpp-python HIVE server
  (legacy Python — read-only reference, do not run)
    daemon/             Replaced by src/go/luminos-ai/
    power_manager/      Replaced by src/go/luminos-power/
    sentinel/           Replaced by src/go/luminos-sentinel/ + src/python/npu/
    classifier/         Replaced by src/go/luminos-router/ + src/python/classifier/
    gpu_manager/        Replaced by src/go/luminos-ai/ + src/python/hive/
    npu/                Replaced by src/python/npu/
```

---

*Last updated: 2026-04-20 | By: claude-code*
*Implements: Decision 13 — Go/Python Split Architecture*
