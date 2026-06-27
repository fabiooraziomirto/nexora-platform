# Architecture One-Pager

## What Nexora Is
Nexora is a microservice-first control plane for distributed edge/IoT operations. It gives operators one place to onboard devices, execute actions, observe status, and produce audit evidence.

## Core Runtime
- UI: React/Vite dashboard with Keycloak OIDC login.
- Identity: Keycloak realm `nxr`, public UI client, pilot users, role-aware frontend.
- Control services: device, plugin, execution, network, DNS, webservice, fleet, AI pipeline.
- Edge path: Kafka dispatch events consumed by `nexora-edge`, with device emulator support for demos.
- Data backbone: MySQL, Redis, Kafka, Zookeeper.

## Demo Flow
1. Operator signs in with Keycloak.
2. Device appears in pairing/onboarding workflow.
3. Operator approves and runs a command.
4. Execution lifecycle moves through queued, dispatched, running, terminal state.
5. Audit evidence is listed and exportable.

## Why It Is Credible
- Services expose health/readiness/metrics endpoints.
- Docker Compose dev stack runs all core services.
- Execution pipeline includes state validation, queue limits, timeout handling, callback handling, and audit events.
- GTM baseline includes dispatch latency and synthetic onboarding metrics.

## Near-Term Hardening
- OpenAPI coverage for every core service.
- Evidence export and reliability gate in the demo path.
- More complete CI for compose smoke, UI build, and API contracts.
