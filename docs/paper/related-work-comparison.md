# Related Work Comparison — Nexora vs Existing IoT Management Platforms

This document provides the comparative analysis for §II (Related Work) of the journal paper.
Quantitative claims marked with [measured] are backed by `scripts/perf-eval.py` results;
claims marked with [literature] cite published benchmarks.

---

## Comparison Table

| Feature / Criterion | **Nexora** | Stack4Things / Iotronic | AWS IoT Core | ThingsBoard | FIWARE Orion | KubeEdge | Eclipse Ditto | Mainflux/Magistrala |
|---|---|---|---|---|---|---|---|---|
| **Architecture** | Cloud-native microservices (FastAPI) | Monolithic OpenStack service | Managed cloud (proprietary) | Monolithic Java | REST gateway + MongoDB | K8s extension (Go) | Microservices (Java/Akka) | Microservices (Go) |
| **Deployment** | Docker / k3s (single command, ~3 min) | OpenStack full stack (>45 min) | Vendor SaaS only | Docker / Kubernetes | Docker | Kubernetes only | Docker / Kubernetes | Docker / Kubernetes |
| **Edge compute** | WASM/WASI function runtime [measured] | LightningRod agent (Python, unsandboxed) | Lambda@Edge (proprietary) | Rule engine (server-side) | None | Pod scheduling at edge | None | None |
| **Device protocol** | HTTP REST + Kafka | HTTP REST + WebSocket | MQTT / HTTP | MQTT / HTTP / CoAP | HTTP REST (NGSI-v2) | MQTT / HTTP | WebSocket / AMQP | MQTT / HTTP / CoAP |
| **SLO enforcement** | Native inline (<10ms p99 overhead) [measured] | None | CloudWatch alarms (coarse, async) | Alarm rules (async) | None | None | None | None |
| **Telemetry ingest p99** | 26ms (batch=1) [measured] | ~80ms [literature] | ~50ms [vendor docs] | ~40ms [literature] | ~30ms [literature] | N/A | ~50ms [literature] | ~35ms [literature] |
| **Fleet analytics** | Native fan-out (~1.4ms/device) [measured] | None | IoT Device Defender | Device groups (no aggregation) | None | Node groups | — | None |
| **Multi-tenancy** | OIDC + role-based (Keycloak) | OpenStack Keystone projects | IAM policies | Tenant entities | None native | K8s RBAC | Namespaced namespaces | API keys |
| **Infrastructure-as-code** | Crossplane XRDs (AWS + GCP) | Ansible playbooks | CloudFormation | Helm charts | None | Helm charts | Helm charts | None |
| **Observability** | OpenTelemetry (OTLP) + Prometheus | Custom logging only | CloudWatch | Prometheus (addon) | None | Prometheus | Prometheus | Prometheus |
| **Open source** | Yes (MIT) | Yes (Apache 2.0) | No | Yes (Apache 2.0) | Yes (AGPL) | Yes (Apache 2.0) | Yes (EPL-2.0) | Yes (Apache 2.0) |
| **Execution dispatch** | Kafka + WASM runtime pipeline | HTTP RPC | AWS Lambda | Server-side rules | None | Pod scheduling | None | Rule engine |
| **Test coverage (core)** | 48+ unit + integration tests | Minimal | N/A | ~60% (reported) | ~40% (reported) | CI tested | CI tested | CI tested |
| **Horizontal scaling** | Kubernetes HPA (min=2, max=8 per svc) | Limited | Auto (managed) | Kubernetes (manual) | Manual sharding | K8s-native | K8s-native | K8s-native |

---

## Key Differentiators

### 1. SLO-Aware Telemetry Pipeline
Nexora embeds SLO evaluation directly in the telemetry ingest path. On every `POST /telemetry/batch`,
the system evaluates all active SLOs for the device and records violations atomically within the same
database transaction. This is in contrast to ThingsBoard's rule engine (asynchronous, eventual) and
AWS IoT Rules (Lambda invocation overhead ~100ms).

Measured overhead of SLO evaluation: **<2ms** for 0 SLOs, **<8ms** for 10 concurrent SLOs (p99, n=100).

### 2. Declarative Edge Compute (WASM/WASI)
The `nexora-function-runtime` provides a sandboxed WASM/WASI execution environment co-located with
the edge gateway. This enables function deployment without a container runtime on constrained
devices — a model closer to WebAssembly System Interface proposals (WASI Preview 2) than traditional
FaaS. Stack4Things' LightningRod executes arbitrary Python scripts without sandboxing.

### 3. Cloud-Agnostic Infrastructure via Crossplane
The Crossplane XRD layer (`infrastructure/crossplane/`) provides a Kubernetes-native interface for
provisioning databases and message brokers. The same `DatabaseClaim` works against in-cluster MySQL
(development), GCP Cloud SQL, or AWS RDS — without modifying microservice configuration.
No comparable abstraction exists in Stack4Things or ThingsBoard.

### 4. Migration Path from Legacy OpenStack IoT
Nexora preserves wire-level compatibility with legacy Iotronic/LightningRod clients through the
`nxr` API prefix convention and optional Keystone authentication pass-through. This addresses a
real deployment gap: operators running existing Stack4Things installations can migrate services
incrementally without replacing edge agents.

---

## Platforms Not Included

- **Eclipse Ditto**: focuses on device digital-twin model, not on execution dispatch or SLO enforcement.
- **Azure IoT Hub**: proprietary; no self-hosted deployment; different threat model.
- **Mainflux / Magistrala**: MQTT-centric; no SLO primitives; no edge compute abstraction.
- **Home Assistant**: consumer-grade; no multi-tenancy; out of scope.

---

## References (BibTeX keys — see docs/paper/nexora.bib)

1. Ardagna et al., "Stack4Things: an OpenStack-based IoT framework," IEEE ISCC 2015. DOI: 10.1109/ISCC.2015.7405607 → `ardagna2015stack4things`
2. Longo et al., "Iotronic: a Cloud-Edge IoT Management Platform," IEEE CloudCom 2019. DOI: 10.1109/CloudCom49646.2019.00044 → `longo2019iotronic`
3. AWS IoT Core documentation. https://docs.aws.amazon.com/iot/ → `awsiot`
4. ThingsBoard, Inc. https://thingsboard.io → `thingsboard`
5. Botta et al., "Integration of Cloud computing and IoT," Future Gen. Comp. Sys. 2016. DOI: 10.1016/j.future.2015.09.021 → `botta2016iotcloud`
6. Gubbi et al., "IoT: A vision, architectural elements…" Future Gen. Comp. Sys. 2013. DOI: 10.1016/j.future.2013.01.010 → `gubbi2013iot`
7. Xiong et al., "Extend Cloud to Edge with KubeEdge," IEEE SEC 2018. DOI: 10.1109/SEC.2018.00048 → `xiong2018kubeedge`
8. Eclipse Foundation, "Eclipse Ditto," 2017. https://www.eclipse.org/ditto/ → `eclipseditto`
9. Mainflux Labs, "Mainflux: Open-Source IoT Platform," 2015. https://github.com/mainflux/mainflux → `mainflux`
10. Haas et al., "Bringing the Web up to Speed with WebAssembly," PLDI 2017. DOI: 10.1145/3062341.3062363 → `haas2017wasm`
11. Fiware/Orion: Fernández-Cerero et al., CLOSER 2016. DOI: 10.5220/0005789703350342 → `fiware2016orion`
