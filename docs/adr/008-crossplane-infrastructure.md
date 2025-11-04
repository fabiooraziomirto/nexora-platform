# ADR-008: Infrastructure Provisioning - Crossplane

## Status
**Accepted** - 2024-01-XX

## Context

Stack4Things v2.0 necessita di:
- Infrastructure as Code (IaC) per provisioning cloud resources
- Kubernetes-native approach
- Multi-cloud support (GCP, AWS, Azure)
- GitOps workflow
- Automated resource management
- Self-service capabilities

## Decision

Utilizzare **Crossplane** per infrastructure provisioning invece di Terraform tradizionale.

Architettura:
```
┌─────────────────────────────────────────┐
│      Git Repository (Infrastructure)     │
│  ┌──────────────────────────────────┐  │
│  │  Crossplane Compositions         │  │
│  │  - Database (PostgreSQL)        │  │
│  │  - Cache (Redis)                 │  │
│  │  - Message Broker (Kafka)        │  │
│  │  - Object Storage (S3)           │  │
│  └──────────────────────────────────┘  │
└──────────────┬──────────────────────────┘
               │ GitOps (ArgoCD/Flux)
               ▼
┌─────────────────────────────────────────┐
│      Kubernetes Cluster                 │
│  ┌──────────────────────────────────┐  │
│  │  Crossplane Controller           │  │
│  │  - GCP Provider                  │  │
│  │  - AWS Provider                  │  │
│  │  - Azure Provider                │  │
│  └──────────────────────────────────┘  │
└──────────────┬──────────────────────────┘
               │ API Calls
               ▼
┌─────────────────────────────────────────┐
│      Cloud Providers                    │
│  GCP │ AWS │ Azure                      │
└─────────────────────────────────────────┘
```

## Motivazioni

### Crossplane Advantages
- ✅ **Kubernetes-Native**: Risorse gestite come K8s resources
- ✅ **Declarative**: Desired state in YAML
- ✅ **GitOps Ready**: Integrazione naturale con ArgoCD/Flux
- ✅ **Multi-Cloud**: Unificato API per tutti i cloud
- ✅ **Self-Service**: Developers possono creare risorse via K8s API
- ✅ **Policy Enforcement**: Policy K8s per governance
- ✅ **No External Tooling**: Tutto in Kubernetes

### vs Terraform
- ✅ Nessun state file esterno
- ✅ Integrazione migliore con K8s
- ✅ Lifecycle management via K8s
- ⚠️ Learning curve se team conosce Terraform

## Implementazione

### Fase 1: Crossplane Setup
- Install Crossplane in cluster
- Configure cloud providers (GCP/AWS/Azure)
- Setup credentials

### Fase 2: Composite Resources
- Creare XRDs (Composite Resource Definitions)
- Creare Compositions per risorse comuni
- Test provisioning

### Fase 3: GitOps Integration
- Integrare con ArgoCD/Flux
- Setup repository infrastructure
- Automated sync

### Fase 4: Self-Service
- Expose Compositions agli sviluppatori
- Policy enforcement
- Cost tracking

## Consequences

### Positive
- ✅ Kubernetes-native workflow
- ✅ GitOps integration naturale
- ✅ Self-service capabilities
- ✅ Policy enforcement via K8s
- ✅ Multi-cloud abstraction

### Negative
- ⚠️ Learning curve per team
- ⚠️ Meno maturo di Terraform
- ⚠️ Community più piccola

### Mitigation
- Training team su Crossplane
- Hybrid approach iniziale (Crossplane + Terraform)
- Gradual migration

## Alternatives Considered

### Terraform
- ✅ Mature e stabile
- ✅ Large community
- ❌ State management esterno
- ❌ Meno integrato con K8s

### Pulumi
- ✅ Multiple languages
- ✅ Better state management
- ❌ Costo per team features
- ❌ Meno Kubernetes-native

### Cloud Provider Specific (CloudFormation, Deployment Manager)
- ✅ Native per provider
- ❌ Vendor lock-in
- ❌ Nessun abstraction multi-cloud

## References

- [Crossplane Documentation](https://docs.crossplane.io/)
- [Crossplane Concepts](https://docs.crossplane.io/latest/concepts/)
- [Crossplane Providers](https://docs.crossplane.io/latest/concepts/providers/)


