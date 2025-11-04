# Stack4Things v2.0 - Project Structure

```
Stack4Things_v2.0/
│
├── README.md                    # Overview progetto
├── CONTRIBUTING.md              # Guide per contribuire
├── TODO_LIST.md                 # TODO list completa
│
├── services/                    # Microservizi
│   ├── device-service/          # Device management service
│   │   ├── src/
│   │   │   └── device_service/
│   │   │       ├── main.py
│   │   │       ├── api/
│   │   │       ├── core/
│   │   │       ├── models/
│   │   │       └── services/
│   │   ├── tests/
│   │   ├── Dockerfile
│   │   ├── pyproject.toml
│   │   └── k8s/
│   │
│   ├── plugin-service/         # Plugin management service
│   ├── execution-service/      # Command execution service
│   ├── network-service/         # Network management service
│   ├── dns-service/            # DNS management service
│   ├── webservice-service/     # Webservice management service
│   └── fleet-service/          # Fleet management service
│
├── libraries/                   # Librerie condivise
│   ├── common/                 # Utilities comuni
│   │   ├── src/common/
│   │   │   ├── database.py
│   │   │   ├── events.py
│   │   │   ├── logging.py
│   │   │   └── config.py
│   │   └── pyproject.toml
│   │
│   └── sdk/                    # Client SDK
│       ├── src/sdk/
│       │   ├── client.py
│       │   └── models.py
│       └── pyproject.toml
│
├── infrastructure/              # Infrastructure as Code
│   ├── kubernetes/             # Kubernetes manifests
│   │   ├── base/
│   │   ├── overlays/
│   │   └── kustomization.yaml
│   │
│   ├── terraform/              # Terraform configs
│   │   ├── gcp/
│   │   ├── aws/
│   │   └── azure/
│   │
│   └── helm/                   # Helm charts
│       ├── device-service/
│       └── ...
│
├── docs/                       # Documentazione
│   ├── adr/                    # Architecture Decision Records
│   ├── api/                    # API documentation
│   ├── deployment/             # Deployment guides
│   ├── developer/              # Developer guides
│   └── architecture/           # Architecture diagrams
│
├── scripts/                    # Utility scripts
│   ├── setup-dev.sh
│   ├── migrate.sh
│   └── deploy.sh
│
├── docker-compose.dev.yml      # Local development
├── pyproject.toml              # Root project config
└── .gitignore                  # Git ignore rules
```

## Servizi Principali

### Device Service
Gestisce dispositivi IoT: CRUD, status, sessioni, configurazione.

### Plugin Service
Gestisce plugin: registry, versioning, storage, validazione.

### Execution Service
Esegue comandi su dispositivi: job queue, retry, result tracking.

### Network Service
Gestisce rete: porte Neutron, VIF, network configuration.

### DNS Service
Gestisce DNS: records, zone, certificati Let's Encrypt.

### Webservice Service
Gestisce webservices: enable/disable, proxy, certificati.

### Fleet Service
Gestisce fleet: grouping, bulk operations.

## Librerie

### Common
Utilities condivise: database, events, logging, config.

### SDK
Client SDK per integrazione esterna.

## Infrastructure

### Kubernetes
Manifests per deploy su Kubernetes.

### Terraform
Infrastructure as Code per cloud providers.

### Helm
Helm charts per packaging e deployment.

