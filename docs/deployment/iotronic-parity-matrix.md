# IoTronic / Lightning Rod — Functional Parity Matrix

> **Important**: Nxr v2.0 provides **functional parity** with the
> legacy IoTronic + Lightning Rod stack.  It does **not** replicate the WAMP
> protocol, Crossbar.io transport, or oslo.messaging RPC layer.  The same
> operational concepts are implemented using HTTP REST APIs and Apache Kafka.

## Concept Mapping

| Legacy (IoTronic / LR) | v2.0 Equivalent | Notes |
|-------------------------|-----------------|-------|
| Board / node identity | `device-service` — `/api/v2/devices` | UUID-based, REST CRUD |
| Board registration (WAMP `wamp.session.on_join`) | `POST /api/v2/agents/register` | Bootstrap token auth replaces WAMP realm auth |
| Session keepalive / conductor heartbeat | `POST /api/v2/agents/{id}/heartbeat` | Periodic HTTP POST instead of WAMP ping |
| `oslo.messaging` RPC call to board | `POST /api/v2/executions` + `/dispatch` | Kafka envelope replaces AMQP cast/call |
| Lightning Rod result callback | `POST /api/v2/executions/{id}/callback` | Strict field validation, state machine |
| Plugin injection | `plugin-service` — `/api/v2/plugins` | REST CRUD, injection via execution pipeline |
| Fleet / group management | `fleet-service` — `/api/v2/fleets` | REST CRUD with member management |
| VPN / network tunnels | `network-service` — `/api/v2/ports` | Abstracted networking endpoints |
| DNS auto-registration | `dns-service` — `/api/v2/dns/records` | REST CRUD for DNS records |
| Webservice exposure | `webservice-service` — `/api/v2/webservices` | Port-based service exposure |
| Crossbar.io session transport | `nexora-edge` | Kafka consumer + HTTP delivery, in-memory sessions |
| OpenStack Keystone auth | Keycloak (primary) + Keystone (fallback) | JWT-based, configurable |

## What Is NOT Replicated

- WAMP topic subscriptions and pub/sub patterns
- `oslo.messaging` conductor RPC topology
- Autobahn/Twisted reactor loop in the agent
- Direct board-to-board communication via Crossbar
