# ADR-0005: IoT FaaS — Edge-Native Function Execution (WASM/WASI)

**Status**: Accepted  
**Date**: 2026-06-25  
**Branch**: `feature/faas-edge`

---

## Context

Nexora dispatches opaque `command` strings to edge devices via its execution
pipeline. This works for scripting but provides no primitives for:

- **Code distribution**: getting versioned code to devices at scale
- **Reproducibility**: the same function, same inputs → same deterministic output
- **Input contracts**: no schema validation, no typed arguments
- **Supply chain security**: no integrity check on what runs on the device
- **Lifecycle management**: no install/rollback/deprecate primitives

An IoT platform intended for multi-tenant smart buildings needs more than remote
shell execution. Facility operators need to deploy business logic (sensor
aggregation, anomaly detection, actuator control) to heterogeneous device fleets
without embedding that logic in the agent firmware.

---

## Decision

Add a **FaaS (Function as a Service) layer** to Nexora using **WebAssembly/WASI**
as the universal execution substrate, with functions deployed and invoked through
the existing execution pipeline.

The design principle: **no new orchestration layer**. FaaS is an overlay on the
existing execution state machine (queued → dispatched → running → succeeded), not
a parallel protocol.

---

## Architecture

```
Control Plane                          Edge Device
─────────────                          ───────────
plugin-service                         nexora-function-runtime
  └─ function registry                   └─ WASM/WASI sandbox
       (metadata + artifact_uri)               ├─ install: download + verify SHA256
                                               ├─ invoke: run in WASM sandbox
execution-service                              └─ permissions: WasiConfig
  └─ execution_type: function.install               ├─ fs_read
     execution_type: function.invoke                ├─ network (opt-in)
     dispatch enrichment: plugin metadata           └─ inherit_env (opt-in)
  └─ HTTP shortcuts:
     POST /api/v2/functions/{id}/invoke
     POST /api/v2/devices/{id}/functions/{id}/invoke

lightningrod-gateway
  └─ no changes — passes enriched dispatch payload transparently
```

---

## Key Decisions

### 1. WASM/WASI as runtime — why not containers?

| Criteria | WASM/WASI | OCI Containers |
|---|---|---|
| **Cold start** | ~1ms (module load) | ~100ms–1s (container startup) |
| **Binary size** | KB–MB (single .wasm) | MB–GB (image layers) |
| **Isolation** | Capability-based WASI sandbox | Kernel namespaces + cgroups |
| **Architecture** | Cross-platform binary | Architecture-specific or QEMU |
| **IoT fit** | Runs on ARM Cortex-M, RISC-V | Requires Linux + container runtime |
| **Dependencies** | Compiled into .wasm | Layer-pulled at runtime |

WASM/WASI is the right choice for constrained edge devices. A Cortex-M microcontroller
cannot run Docker. A WASM module compiled from Python (via Py2WASM) or Rust runs
everywhere wasmtime is available.

### 2. Artifact URL vs inline blob

Functions are stored as external artifacts (`artifact_uri`) rather than DB blobs:

- **DB blob limit**: MySQL TEXT column is 65 KB; MEDIUMBLOB required for real functions
- **CDN-friendly**: artifact_uri can point to a CDN edge for fast device-local delivery
- **Immutability**: URL + SHA256 checksum = content-addressed, cacheable
- **Independence**: plugin-service doesn't need to handle GB of binary data at scale

### 3. Extend execution pipeline rather than adding a parallel protocol

The execution state machine (queued → dispatched → running → succeeded/failed) already
provides: idempotency, timeout enforcement, audit logging, Kafka event streaming, and
privacy-aware result visibility. Reusing it for FaaS means:

- No new message bus or orchestration layer
- FaaS invocations appear in execution history alongside command executions
- The same ownership/privacy model (ADR-0004) applies to function payloads
- The gateway already delivers arbitrarily structured dispatch envelopes

### 4. Dispatch enrichment in execution-service (not in gateway)

When dispatching a function execution, execution-service fetches plugin metadata from
plugin-service and embeds it in the Kafka event. Alternative: gateway enriches on
delivery.

**Rationale**: execution-service is the single source of truth for what was dispatched
(for audit). Enrichment at dispatch time means the Kafka event is self-contained: if
plugin-service is later unavailable, the event can be replayed from the broker. The
gateway remains a pure relay (no outbound HTTP calls).

### 5. Capability gate: explicit device opt-in

Function executions require `wasm_wasi: true` in device capabilities. This prevents
silent failures when a dispatch reaches a device that cannot execute WASM. The gate
is enforced in execution-service at dispatch time (400 if capability missing), not
at queue time (better UX: error at the point of user action).

### 6. Permission model: deny-by-default WASI capabilities

WASM/WASI modules have no ambient authority. Permissions are declared in the function
registry and applied per-invocation in `WasiConfig`. Allowed permissions:

| Permission | WasiConfig effect |
|---|---|
| `fs_read` | `preopen_dir("/tmp", "/tmp")` |
| `fs_write` | `preopen_dir("/var/nexora/data", "/data")` |
| `network` | `inherit_network()` |
| `inherit_env` | `inherit_env()` |

Secrets are never embedded in function payloads. Functions access secrets via
environment variables pre-configured by the operator on the runtime host.

### 7. Graceful degradation: execution stub

`nexora-function-runtime` tries wasmtime first. If wasmtime is not installed
(emulator, CI, edge device not yet upgraded), it falls back to a stub that verifies
the artifact file exists and returns a synthetic result. This allows the emulator
and integration tests to exercise the full dispatch path without requiring wasmtime
to be present in every environment.

---

## Privacy and Tenant Isolation

Function invocations are Execution records with `execution_type=function.invoke`.
The privacy model from ADR-0004 applies:

- `function_result` (structured JSON output) is treated as **level 4 payload** —
  visible only to the owner and platform operators
- Non-owner callers in the same tenant see command metadata but not `function_result`
- Cross-tenant callers receive 404

---

## Comparison with Related Systems

| System | Deployment | Runtime | Scope |
|---|---|---|---|
| AWS Lambda@Edge | Cloud + CDN PoPs | V8 isolates | HTTP trigger only |
| Azure IoT Edge | On-premise | Docker containers | Full Linux required |
| OpenFaaS | K8s | Containers | Cloud/on-premise |
| Fission | K8s | Containers | Cloud-native only |
| **Nexora FaaS** | Edge device | WASM/WASI | Constrained IoT + on-premise |

Nexora's differentiator: runs on constrained hardware without Kubernetes or Docker,
integrates with an existing IoT management control plane, and enforces multi-tenant
ownership boundaries native to the device identity model.

---

## Consequences

### Positive
- Functions run on devices with <1 MB available RAM (WASM overhead)
- Cross-architecture: same .wasm runs on x86_64 and ARM64 without recompilation
- Immutable, content-addressed artifacts with SHA256 integrity verification
- Zero changes to lightningrod-gateway (delivery path unchanged)
- FaaS executions appear in full audit/history alongside command executions

### Negative / Limitations
- WASM modules cannot call arbitrary host syscalls (by design, but limits some use cases)
- `wasmtime-py` bindings are not yet available for all edge architectures (e.g. ARMv6)
- No hot reloading: function update requires explicit `function.install` + old version deactivation
- Sync invocation (`mode=sync`) is bounded by `REQUEST_TIMEOUT_SECONDS` — long-running
  functions must use async and poll the execution result

### Future Work
- Fleet-level deploy and rollout (Feature 8 in plan)
- Event-driven triggers: `execution.succeeded` → trigger downstream function (Feature 7)
- Cold start metrics: instrument wasm module load time separately from execution time
- Function-to-function calls via execution-service (chaining)
- GDPR Art. 17: function uninstall as part of device right-to-erasure flow
