# ADR-0004 — Device Ownership Model and Privacy-by-Design

**Status**: Accepted  
**Date**: 2026-06-25  
**Scope**: `device-service` — ownership, pairing, and privacy consent subsystem

---

## Context

Stack4Things / IoTronic assumes that the platform operator and the physical device owner are the same entity — an OpenStack project tenant. This assumption breaks down in the smart building scenario, where a single infrastructure (managed by a building operator) hosts devices owned by multiple independent parties: facility companies, security contractors, individual tenants.

Concretely:

| Actor | Role | Should see |
|---|---|---|
| Building manager (platform operator) | Manages network, servers, Nexora | Device topology, health aggregate |
| Facility Company A | Installed HVAC sensors | Only their own device data |
| Security Company B | Manages access control | Only their own device data |
| Corporate Tenant C | Has IoT devices in their office | Only their own device data |

The platform operator must not be able to read the command history or payload of a device owned by Facility Company A. This is both a business requirement (NDA, contractual isolation) and a legal requirement (GDPR Article 25 — privacy by design and by default).

---

## Decision

### 1. Ownership model

The `Device` model is extended with:
- `owner_id` — Keycloak `sub` claim of the user who claimed the device
- `tenant_id` — Keycloak group of the owner (first group, used as organizational boundary)
- `privacy_level` — integer 0–4, the maximum level the device advertises to its owner

Tenant isolation is enforced at the API layer: non-operator callers receive only devices in their `tenant_id`. Operators receive topology (device count, types, health) but not application data.

### 2. Device pairing — RFC 8628 Device Authorization Grant

New devices go through a pairing flow before becoming operational:

```
[Device powers on]
    │
    ▼
POST /api/v2/devices/announce          (unauthenticated)
    │ ← {device_code, user_code, expires_in, poll_interval}
    │
    ├── Device polls GET /api/v2/devices/announce/poll?device_code=X
    │       every poll_interval seconds
    │
    └── Owner sees user_code on device label / display
            │
            ▼
        GET  /api/v2/devices/pending   (authenticated)
        POST /api/v2/devices/{id}/claim  (authenticated)
            │ ← Device is registered, bootstrap_token issued
            │
            ▼
        Device next poll: status=approved + bootstrap_token
            │
            ▼
        POST /api/v2/agents/register   (normal registration flow)
```

The flow implements RFC 8628 (OAuth 2.0 Device Authorization Grant), the same protocol used by Chromecast, Apple TV, and smart TV pairing. No credentials are required from the device at announcement time — trust is established when an authenticated human owner approves.

**Discovery expiry**: 15 minutes (configurable via `DISCOVERY_EXPIRY_SECONDS`). Expired discoveries are garbage-collected by periodic status checks.

### 3. Privacy levels — opt-in tiers

| Level | Name | Data exposed | Legal basis | Delegatable |
|---|---|---|---|---|
| 0 | Operational | device_id, online/offline, last heartbeat | Contract necessity | No (always on) |
| 1 | Fleet visibility | name, type, zone, aggregate status | Explicit consent | Yes |
| 2 | Health metrics | uptime %, command success rate, delivery failures | Explicit consent | Yes |
| 3 | Command history | action, status, timestamp (no payload) | Explicit consent | Yes |
| 4 | Full payload | command content and responses | Explicit consent | No (owner only) |

**Default**: Level 0 only — privacy by default (GDPR Article 25).

**Opt-in**: owner explicitly enables each level for specific actors via `POST /api/v2/devices/{id}/privacy/consent`.

**Level 4 is non-delegatable**: it cannot be shared via the consent API. Only the owner (`owner_id == caller.user_id`) can access full command payload.

### 4. Consent revocation — immediate effect

Consent is stored as a `DeviceConsent` row with `is_active: bool`. Revocation sets `is_active=False` and `revoked_at=now()`. The access layer reads `is_active` at query time — no TTL, no grace period, no caching of access decisions.

This satisfies GDPR Article 7(3): "The data subject shall have the right to withdraw his or her consent at any time. [...] It shall be as easy to withdraw consent as to give it."

### 5. Audit log

All ownership and consent events are written to the `ownership_events` table:
- `paired` — device claimed by owner
- `unpaired` — device removed (future: ownership transfer)
- `consent_granted` — level N granted to actor X
- `consent_revoked` — consent withdrawn
- `level_changed` — owner changes base privacy level

The owner can query `GET /api/v2/devices/{id}/privacy/events` to see the full history. This implements GDPR Article 15 (right of access) at the application layer.

---

## Roles

Three distinct roles replace the single "project member" model of Stack4Things:

| Role | Keycloak role name | Access |
|---|---|---|
| Platform operator | `platform-operator` | Device topology, health; no application data |
| Device owner | (any authenticated user) | Full access to own devices, consent management |
| Tenant viewer | Granted by owner via consent level 1 | Fleet visibility in same tenant |

2FA is delegated to Keycloak at the authentication step — not implemented at the application layer.

---

## Alternatives considered

| Alternative | Why rejected |
|---|---|
| QR code + HMAC pairing | Non-standard; weaker against replay attacks without a nonce mechanism |
| Application-level 2FA (TOTP in device-service) | Duplicates Keycloak's responsibility; harder to audit |
| Opt-out privacy model | Incompatible with GDPR Article 25 "privacy by default" for personal data |
| HTTP call to rbac-service for each authorization | rbac-service is not integrated by any service; adds latency for every request with no benefit over inline JWT claim checks at current scale |
| `X-Tenant-Id` header for tenant context | Headers are falsifiable; tenant must come from the signed JWT |

---

## Consequences

**Positive**
- Physical device owner and platform operator are distinct, enforceable identities.
- Device cannot be used until an authenticated human approves it — eliminates the "device appears and is automatically operational" pattern of Stack4Things.
- Privacy is opt-in and revocable — defensible under GDPR Articles 7, 25.
- Audit trail gives owners visibility into who did what with their device — defensible under GDPR Article 15.
- The pairing protocol (RFC 8628) is an IETF standard, independently reviewable.

**Negative / limitations**
- `tenant_id` is derived from the first Keycloak group — requires Keycloak group configuration to be consistent. A device owner not in any group gets `tenant_id="global"`, which means they see all globally-scoped devices.
- Privacy enforcement at level 2–4 is in device-service only; execution-service command history is a separate data store not yet filtered by consent. The full privacy story requires consent checks in execution-service as a follow-up.
- The one-time bootstrap token from pairing is returned in the poll response in plaintext — in production this must be over TLS; the token should be short-lived (1 hour, as implemented) and single-use.

---

## Commit references

| Commit | Content |
|---|---|
| ff95ac0 | Ownership schema: owner_id, tenant_id, privacy_level + device_discoveries, device_consents, ownership_events tables |
| 2c06409 | Auth dependency (CurrentUser), tenant isolation, ownership enforcement in existing CRUD |
| 9aa725a | RFC 8628 pairing API + privacy consent API (29/29 tests pass) |

---

## GDPR article mapping

| GDPR Article | Implementation |
|---|---|
| Art. 5(1)(c) — Data minimisation | Level 0 by default; higher levels require explicit opt-in |
| Art. 7 — Conditions for consent | Explicit grant per actor per level; revocable at any time |
| Art. 7(3) — Withdrawal of consent | Immediate effect; `is_active` read at query time |
| Art. 15 — Right of access | Owner can query full ownership event log |
| Art. 17 — Right to erasure | Unpair flow (future) removes device and associated consents |
| Art. 25 — Privacy by design | Level 0 default; operator cannot access application data |
