# ADR-0001: Lightningrod Gateway and Execution Pipeline

**Status**: Accepted  
**Date**: 2026-03-28

## Context

The legacy IoTronic stack uses WAMP/Crossbar.io for cloud-to-edge communication
and oslo.messaging RPC for internal coordination.  These transports are tightly
coupled to OpenStack and are difficult to operate outside that ecosystem.

Stack4Things v2.0 needs a cloud-to-edge command pipeline that is:
- Decoupled from OpenStack infrastructure
- Observable (metrics, tracing, audit logs)
- Resilient to partial outages (Kafka down, agent offline)

## Decision

1. **Execution lifecycle** is managed by `execution-service` via REST
   (create → dispatch → callback).
2. **Dispatch events** are published to Kafka topic
   `stack4things.execution.dispatched`.
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
