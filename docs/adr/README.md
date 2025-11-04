# Stack4Things v2.0 - Architecture Decision Records

Questo documento contiene le Architecture Decision Records (ADR) per Stack4Things v2.0.

## Cos'è un ADR?

Un ADR è un documento che cattura una decisione architetturale importante insieme al suo contesto e conseguenze.

## Template ADR

Ogni ADR segue questo formato:

```markdown
# ADR-XXX: [Titolo]

## Status
[Proposed | Accepted | Deprecated | Superseded]

## Context
[Background e motivazione]

## Decision
[Decisione presa]

## Consequences
[Pros e cons]

## Alternatives Considered
[Alternative valutate]
```

## ADR Index

- [ADR-001: Linguaggio di Programmazione - Python 3.11+](./adr/001-python-language.md)
- [ADR-002: Framework Web - FastAPI](./adr/002-fastapi-framework.md)
- [ADR-003: Orchestration - Kubernetes](./adr/003-kubernetes-orchestration.md)
- [ADR-004: Database - MySQL/MariaDB (OpenStack Compatible)](./adr/004-mysql-database.md)
- [ADR-005: Message Broker - Kafka](./adr/005-kafka-message-broker.md)
- [ADR-006: API Gateway - Kong](./adr/006-kong-api-gateway.md)
- [ADR-007: Autenticazione - Keycloak + Keystone](./adr/007-keycloak-authentication.md)
- [ADR-008: Infrastructure Provisioning - Crossplane](./adr/008-crossplane-infrastructure.md)
- [ADR-009: RBAC - Role-Based Access Control](./adr/009-rbac-management.md)
- [ADR-010: Virtual Networking - WireGuard](./adr/010-wireguard-networking.md)
- [ADR-011: Fleet Management - Advanced Features](./adr/011-fleet-management.md)

---

## Come Creare un Nuovo ADR

1. Crea un nuovo file `adr/XXX-short-title.md`
2. Usa il template sopra
3. Aggiungi alla lista ADR Index
4. Commit e PR

