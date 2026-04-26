# HIVE Architecture — Native Linux Implementation

## 1. Directory Structure

HIVE is integrated directly into the Luminos OS source tree:

```
luminos-os/
├── agents/             # [REASONING] Specialist agent prompts and profiles
├── cmd/                # [CONTROL] Go-based system daemons
├── internal/           # [CONTROL] Shared IPC and socket logic
├── modelfiles/         # [DATA] GGUF/ONNX model metadata
├── orchestrator/       # [REASONING] Python routing and logic controller
├── src/                # [CORE] Hardware managers and security kernels
├── systemd/            # [LIFECYCLE] Native Linux service units
└── tools/              # [ACTION] Sandboxed agent capabilities
```

## 2. Boot Sequence

The HIVE lifecycle is managed by the native OS layer:

1. **Service Init:** `systemd` starts `luminos-ai.service` (the IPC coordinator).
2. **Resource Audit:** `luminos-power` audits VRAM and NPU availability.
3. **Control Plane:** The Go `luminos-router` initializes the rule-based classification cache.
4. **Data Plane:** The Sentinel kernel is loaded into the XDNA NPU memory space via HATS.
5. **Orchestration:** The Python `Brain` binds to the IPC socket, ready to dispatch requests to `llama-server`.

## 3. Data Flow (Intent-Based Routing)

1. **User Input:** Prompt received via IPC socket or CLI.
2. **Intent Analysis:** The **Nexus** profile analyzes the prompt for specialist requirements (Code, Logic, Security).
3. **Hardware Dispatch:**
   - **Code/General:** Routed to **Nexus/Bolt** on GPU.
   - **Deep Reasoning:** Routed to **Nova** on CPU threads.
   - **Security Signals:** Routed to **Sentinel** on NPU.
4. **Execution:** `llama.cpp` executes the inference. 
5. **VRAM Guard:** Throughout execution, the `VRAM Watchdog` monitors system health, ready to evict models if GPU contention occurs.

## 4. Hardware Utilization Matrix

| Logic Tier | Hardware | Target Precision |
|------------|----------|------------------|
| Coordinator| dGPU (RTX 4050) | Q4_K_M (GGUF) |
| Coding | dGPU (RTX 4050) | Q4_K_M (GGUF) |
| Reasoning | CPU (Ryzen 7) | Q4_K_S (GGUF) |
| Security | NPU (XDNA 1) | INT8 (HATS) |

## 5. Known Gaps (Phase 3 Roadmap)

- **Recursive Tooling:** Orchestrator currently supports single-shot tool usage; recursive logic required for complex debugging.
- **IPC Latency:** Current Python/Go socket handoff adds ~5ms overhead; planned migration of reasoning logic to Go.
- **NPU Batching:** HATS kernel currently serializes requests; async batching required for multi-app monitoring.
