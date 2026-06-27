# ADR-0006: WebSocket Reverse Tunnel and Push Delivery

**Status**: Accepted  
**Date**: 2026-06-27

## Context

ADR-0001 established an HTTP-poll dispatch pipeline: edge agents periodically call
`GET /api/v2/executions` to find pending commands, then call `POST /api/v2/deliver/{id}`
to retrieve the Kafka-cached dispatch and signal readiness.

This design has three problems relevant to the FGCS research goal:

1. **Latency floor**: the poll cycle (default 4 s) adds irreducible queuing wait to every
   command's end-to-end latency, making sub-100 ms p99 unachievable.
2. **NAT / intermittency**: agents behind NAT or experiencing connectivity churn cannot
   accept inbound connections; the outbound WS tunnel removes this constraint.
3. **Pull semantics unsuited to push requirements**: command delivery requires the cloud
   to push work to the edge, not the edge to pull — the poll model inverts this.

## Decision

Extend `nexora-edge` with a native **WebSocket reverse-tunnel** plane alongside the
existing HTTP REST plane (which is retained for backward compatibility and as a fallback
delivery path).

### Endpoint

```
WS /api/v2/agents/ws/{device_id}
```

Agents open **one persistent outbound WebSocket** per device, maintained across NAT
rebinds by the reconnect-on-error loop in the emulator.

### Message protocol (JSON, type-tagged)

| Direction     | Type          | Purpose                                              |
|---------------|---------------|------------------------------------------------------|
| gateway→agent | `control`     | Command push delivery (replaces HTTP poll + deliver) |
| agent→gateway | `ack`         | Delivery acknowledgement; triggers dispatch deletion |
| agent→gateway | `heartbeat`   | Session keepalive without a separate HTTP call       |
| bidirectional | `ping`/`pong` | Connection health check                              |
| reserved      | `interactive` | Reverse shell / remote access (future work)          |

### At-least-once delivery (reconnect / resume)

The dispatch entry in Redis is **not deleted** until the agent sends an explicit `ack`.
On reconnect, `_ws_replay_pending()` scans Redis for any un-ACKed dispatches belonging
to the reconnecting device and replays them immediately. This ensures commands survive:

- Agent crash and restart
- NAT rebind (forced WS reconnect)
- Intermittent connectivity

### Connection-affinity routing across replicas (cross-replica push)

Kafka consumer events may arrive at any gateway replica, but only one replica holds the
agent's WebSocket. Cross-replica delivery uses **Redis Pub/Sub**:

1. Kafka consumer receives dispatch → stores in Redis dispatch cache → publishes to
   `nxr:push:{device_id}`.
2. The gateway replica that owns the WS for `device_id` has subscribed to that channel
   via `_ws_pubsub_listener`.
3. It receives the pub/sub message and calls `_ws_push_dispatch()` over the local WS.

No sticky load-balancer sessions are required. Two or more replicas sharing a Redis
instance provide full horizontal scaling.

**Single-instance fallback** (Redis disabled): the Kafka consumer checks `_ws_connections`
(per-process dict) and pushes directly if the WS is local.

### Session state

The existing Redis-backed session registry (ADR-0001 update) is extended with:
- `ws_connected: bool` — true while a WS connection is open
- `gateway_instance: str` — `GATEWAY_INSTANCE_ID` (hostname by default) of the owning
  replica

### Emulator updates

`nexora-device-emulator` gains `--ws-mode` (env: `WS_MODE=true`) which replaces the
HTTP-poll loop with a WS push receiver. Intermittency scenarios:

- `--reconnect-interval N` — forces WS disconnect/reconnect every N seconds (simulates
  NAT rebind, link flap, or planned churn)
- `--kill-after N` (existing) — hard-exits the board after N seconds
- `--fail-rate P` (existing) — injects callback failures

Heartbeats to `device-service` continue via HTTP on a background thread even in WS mode.

## Consequences

- **Dispatch latency**: p99 end-to-end drops from `O(POLL_SECONDS)` to
  `O(Kafka_ingestion + WS_push)` — measurably sub-100 ms on a local stack.
- **Resilience**: un-ACKed dispatches survive agent reconnects without data loss.
- **Horizontal scaling**: 2+ gateway replicas share session/dispatch state via Redis and
  route pushes via Pub/Sub.
- **Backward compat**: `POST /api/v2/deliver/{id}` (HTTP) remains operational for agents
  not yet on the WS tunnel.
- **Residual limitations**:
  - Redis Pub/Sub is at-most-once at the pub/sub layer; if the subscriber is down when
    the publish fires, the message is lost. The replay-on-reconnect path compensates.
  - The `interactive` stream type is defined in the protocol but not implemented.
  - Single-instance fallback path restores non-HA behaviour; set `REDIS_REQUIRED=true`
    in multi-replica deployments.

## Tests added

`services/nexora-edge/tests/test_ws_tunnel.py` (12 tests):

- WS connect creates / updates session (`ws_connected=True`)
- Disconnect marks `ws_connected=False`
- Pending dispatches replayed immediately on connect
- Replay sends only dispatches belonging to the connecting device
- ACK deletes dispatch from cache
- Un-ACKed dispatch survives disconnect and is replayed on reconnect
- Ping/pong keepalive
- WS heartbeat refreshes `last_seen`
- Rapid connect/disconnect churn leaves `_ws_connections` empty and sessions clean
- Same-device rapid reconnect replays consistently
