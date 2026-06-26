# ADR-0001: Lightningrod Gateway and Execution Pipeline

**Status**: Accepted  
**Date**: 2026-03-28

## Context

The legacy IoTronic stack uses WAMP/Crossbar.io for cloud-to-edge communication
and oslo.messaging RPC for internal coordination.  These transports are tightly
coupled to OpenStack and are difficult to operate outside that ecosystem.

Nxr v2.0 needs a cloud-to-edge command pipeline that is:
- Decoupled from OpenStack infrastructure
- Observable (metrics, tracing, audit logs)
- Resilient to partial outages (Kafka down, agent offline)

## Decision

1. **Execution lifecycle** is managed by `execution-service` via REST
   (create → dispatch → callback).
2. **Dispatch events** are published to Kafka topic
   `nxr.execution.dispatched`.
3. **Lightningrod Gateway** consumes dispatch events from Kafka, caches them,
   and delivers them to edge agents via the `/deliver` endpoint.
4. **Edge agents** send results back via `POST /executions/{id}/callback`
   directly to the execution-service.
5. A **state machine** enforces valid transitions
   (queued→dispatched→running→succeeded/failed/timeout/cancelled).

## Consequences

- **Kafka dependency**: the dispatch path requires Kafka; graceful degradation
  keeps create/query operational when Kafka is unavailable.
- **Gateway scaling**: the gateway is stateless (in-memory session cache) and
  can be horizontally scaled behind a load balancer.
- **Timeout enforcement**: a background loop in execution-service marks stale
  dispatched/running executions as `timeout`.
- **No WAMP**: agents must use HTTP.  Existing Lightning Rod agents using
  Autobahn/WAMP are not directly compatible and need a thin HTTP adapter.

---

## Update 2026-06 — Redis-backed session and dispatch store

### Context

The original decision described the gateway as "stateless" and "horizontally
scalable behind a load balancer", but the implementation used plain Python dicts
(`agent_sessions`, `dispatch_cache`) that lived in-process.  With two or more
gateway replicas, a registration request landing on replica A would be invisible
to replica B, so delivery requests or heartbeats routed to a different replica
would return 404.  The gateway was effectively sticky to a single instance.

### Decision

Migrate `agent_sessions` and `dispatch_cache` (and the ancillary
`delivery_attempts` / `delivery_last_error` fields, now embedded in the dispatch
blob) from in-process dicts to Redis, using the following key schema:

- `gateway:session:{device_id}` — JSON session blob, TTL = `SESSION_TTL_SECONDS`
  (default 300 s).  Every heartbeat call resets the TTL, so a session expires
  only if no heartbeat is received within the window.
- `gateway:dispatch:{execution_id}` — JSON dispatch blob (including
  `delivery_attempts` and `delivery_last_error`), TTL = `DISPATCH_TTL_SECONDS`
  (default 3600 s, matching `EXECUTION_RUNNING_TIMEOUT_SECONDS` in
  execution-service).

The Redis dependency follows the same `REDIS_ENABLED` / `REDIS_REQUIRED` pattern
already used for Kafka:

- `REDIS_ENABLED=true, REDIS_REQUIRED=false` (default): Redis is used when
  available; on connection failure the gateway falls back to local in-memory
  dicts and logs a warning.
- `REDIS_ENABLED=true, REDIS_REQUIRED=true`: startup fails if Redis is
  unreachable.
- `REDIS_ENABLED=false`: local dicts are always used (single-instance mode,
  useful for fast local testing without Redis).

### Consequences

- **Horizontal scaling now viable**: any gateway replica can read and write
  shared session/dispatch state from Redis.  A load balancer no longer needs
  sticky sessions for the session-management or delivery endpoints.
- **Session TTL-based expiry**: agent sessions expire automatically after
  `SESSION_TTL_SECONDS` without a heartbeat, replacing the previously implicit
  "session lives until process restart" behaviour.
- **Dispatch TTL-based cleanup**: orphaned dispatch entries (e.g. for executions
  that time out before the agent delivers) are garbage-collected by Redis TTL
  rather than accumulating in memory.
- **Residual HA limitations**:
  - Redis itself is a single point of failure in the default compose/k8s setup.
    For full HA, Redis Sentinel or Redis Cluster is required.
  - `_dispatch_count_for_device` performs an O(N) scan over all dispatch keys
    (Redis `KEYS gateway:dispatch:*` + N GET calls).  At research/emulator scale
    this is acceptable; at production scale replace with a per-device Redis Set.
  - The in-memory fallback path restores single-instance behaviour silently.
    When running multiple replicas, `REDIS_REQUIRED=true` should be set to
    prevent split-brain operations going undetected.
