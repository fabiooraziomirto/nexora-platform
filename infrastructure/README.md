# Infrastructure GitOps Repository

This repository contains Crossplane infrastructure definitions for Stack4Things v2.0.

## Structure

```
infrastructure/
├── crossplane/
│   ├── xrds/          # Composite Resource Definitions
│   ├── compositions/   # Compositions for different providers
│   ├── providers/      # Provider configurations
│   └── examples/       # Example claims
├── gitops/
│   ├── argocd/         # ArgoCD applications
│   └── flux/           # Flux Kustomizations
└── README.md           # This file
```

## Usage

### ArgoCD

ArgoCD will automatically sync this repository and apply Crossplane resources.

### Flux

Flux will continuously sync this repository and apply changes.

## Adding New Infrastructure

1. Create claim in `crossplane/examples/`
2. Commit and push to Git
3. GitOps tool will automatically apply changes

## Monitoring

Monitor infrastructure provisioning via:
- Crossplane status
- Cloud provider console
- Resource claims in Kubernetes

