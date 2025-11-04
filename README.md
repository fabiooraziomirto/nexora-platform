# Stack4Things v2.0

**Modern IoT Device Management Platform** - Cloud-Native Microservices Architecture

## 🎯 Vision

Stack4Things v2.0 è una completa reingegnerizzazione della piattaforma IoTronic/Stack4Things con un'architettura moderna basata su microservizi cloud-native.

## 🏗️ Architettura

```
┌─────────────────────────────────────────────────────────────┐
│                     API Gateway (Kong)                      │
└─────────────────────────┬───────────────────────────────────┘
                          │
        ┌─────────────────┼─────────────────┐
        │                 │                 │
┌───────▼────────┐  ┌────▼──────┐  ┌───────▼────────┐
│  API Service   │  │  Web UI   │  │  gRPC Gateway  │
│   (FastAPI)    │  │  (React)   │  │   (gRPC-Web)   │
└───────┬────────┘  └───────────┘  └────────────────┘
        │
        │ Event Bus (Kafka/NATS)
        │
┌───────▼───────────────────────────────────────────────────┐
│                    Core Microservices                     │
├────────────────────────────────────────────────────────────┤
│  Device │ Plugin │ Execution │ Network │ DNS │ Webservice│
│  Fleet  │        │           │         │     │           │
└───────┬───────────────────────────────────────────────────┘
        │
        │ WAMP Broker (Crossbar/NATS)
        │
┌───────▼───────────────────────────────────────────────────┐
│          WAMP Agent Pool (Stateless, Auto-Scaling)        │
└───────┬───────────────────────────────────────────────────┘
        │
        │ WSS/TLS
        │
┌───────▼───────────────────────────────────────────────────┐
│              IoT Devices (Lightning Rod)                   │
└────────────────────────────────────────────────────────────┘
```

## 🛠️ Stack Tecnologico

- **Runtime**: Python 3.11+
- **Framework**: FastAPI
- **Orchestration**: Kubernetes
- **Infrastructure**: Crossplane (GitOps)
- **Database**: MySQL/MariaDB 10.11+ (OpenStack Compatible)
- **Cache**: Redis Cluster
- **Message Broker**: Kafka / NATS
- **API Gateway**: Kong / Envoy
- **Authentication**: Keycloak (primary) + Keystone (fallback)
- **OpenStack**: Full compatibility (2024.1 Antelope+)
- **Monitoring**: Prometheus + Grafana + Tempo + Loki
- **CI/CD**: GitLab CI / GitHub Actions
- **Architectures**: AMD64 + ARM64 (multi-arch support)

## 📁 Struttura Progetto

```
Stack4Things_v2.0/
├── services/              # Microservizi
│   ├── device-service/
│   ├── plugin-service/
│   ├── execution-service/
│   ├── network-service/
│   ├── dns-service/
│   ├── webservice-service/
│   └── fleet-service/
├── libraries/            # Librerie condivise
│   ├── common/           # Utilities comuni
│   └── sdk/              # Client SDK
├── infrastructure/       # Infrastructure as Code
│   ├── kubernetes/      # K8s manifests
│   ├── terraform/        # Terraform configs
│   └── helm/            # Helm charts
├── docs/                # Documentazione
├── scripts/             # Utility scripts
└── docker-compose.dev.yml  # Local development
```

## 🚀 Quick Start

### Prerequisiti

- Python 3.11+
- Docker & Docker Compose
- Kubernetes cluster (minikube/kind per sviluppo)
- kubectl

### Setup Locale

```bash
# Clone repository
git clone <repository-url>
cd Stack4Things_v2.0

# Setup Python environment
poetry install

# Start local Kubernetes
minikube start

# Deploy infrastructure
kubectl apply -f infrastructure/kubernetes/

# Run services locally
docker-compose -f docker-compose.dev.yml up
```

## 📋 TODO List

Vedi [TODO_LIST.md](./TODO_LIST.md) per la lista completa delle attività.

## 📚 Documentazione

- [Architecture Decision Records](./docs/adr/)
- [API Documentation](./docs/api/)
- [Deployment Guide](./docs/deployment/)
- [Developer Guide](./docs/developer/)
- [Repository Setup Guide](./docs/REPOSITORY_SETUP.md)

## 🤝 Contribuire

1. Leggi [CONTRIBUTING.md](./CONTRIBUTING.md)
2. Leggi [Repository Setup Guide](./docs/REPOSITORY_SETUP.md) per configurare il repository Git
3. Crea un branch per la feature
4. Commit changes seguendo [Conventional Commits](https://www.conventionalcommits.org/)
5. Push e crea Pull Request/Merge Request

## 📄 Licenza

Apache License 2.0

## 🔗 Link Utili

- [Documentazione Completa](./docs/)
- [TODO List](./TODO_LIST.md)
- [Issue Tracker](link-to-issues)

---

**Status**: 🚧 In Development
**Version**: 2.0.0-alpha

