# Crossplane Infrastructure Provisioning Guide

## Overview

Stack4Things v2.0 uses Crossplane for GitOps-based infrastructure provisioning across multiple cloud providers.

## Architecture

```
┌─────────────────────────────────────────┐
│         Git Repository                  │
│    (Infrastructure as Code)             │
└──────────────┬──────────────────────────┘
               │
        ┌──────┴──────┐
        │             │
┌───────▼──────┐  ┌──▼──────────────┐
│   ArgoCD      │  │   Flux          │
│   (GitOps)    │  │   (GitOps)      │
└───────┬──────┘  └─────────────────┘
        │
┌───────▼──────────────────────────┐
│         Crossplane                 │
│  - XRDs (Composite Resources)      │
│  - Compositions                     │
│  - Providers                        │
└──────────────┬─────────────────────┘
               │
        ┌──────┴──────┐
        │             │
┌───────▼──────┐  ┌──▼──────────────┐
│    GCP       │  │   AWS/Azure      │
│  Provider    │  │   Providers      │
└──────────────┘  └─────────────────┘
```

## Quick Setup

```bash
# Complete Crossplane setup
./scripts/kubernetes/crossplane/setup-all.sh

# Or step by step:
./scripts/kubernetes/crossplane/setup-crossplane.sh
./scripts/kubernetes/crossplane/setup-provider.sh gcp
./scripts/kubernetes/crossplane/setup-compositions.sh
./scripts/kubernetes/crossplane/setup-gitops.sh argocd
```

## Components

### 1. Crossplane Core

- **Namespace**: `crossplane-system`
- **Function**: Kubernetes-native control plane for cloud infrastructure
- **CRDs**: Composite Resources, Compositions, Claims

### 2. Cloud Providers

Supported providers:
- **GCP**: Google Cloud Platform
- **AWS**: Amazon Web Services
- **Azure**: Microsoft Azure

### 3. Composite Resources

#### XRDs (Composite Resource Definitions)

- **XStackDatabase**: Database resources (MySQL, PostgreSQL)
- **XStackCache**: Cache resources (Redis, Memcached)
- **XStackMessaging**: Messaging resources (Kafka, Pub/Sub)
- **XStackStorage**: Object storage (S3, GCS)
- **XStackLoadBalancer**: Load balancer resources

### 4. Compositions

Pre-configured compositions for:
- MySQL/MariaDB (Cloud SQL, RDS)
- Redis Cache (Memorystore, ElastiCache)
- Kafka/Messaging (Pub/Sub, MSK)
- Object Storage (GCS, S3)
- Load Balancers

## Provider Configuration

### GCP Setup

```bash
# Create GCP service account
gcloud iam service-accounts create crossplane-sa \
  --display-name="Crossplane Service Account"

# Grant required permissions
gcloud projects add-iam-policy-binding PROJECT_ID \
  --member="serviceAccount:crossplane-sa@PROJECT_ID.iam.gserviceaccount.com" \
  --role="roles/cloudsql.admin"

# Create JSON key
gcloud iam service-accounts keys create gcp-key.json \
  --iam-account=crossplane-sa@PROJECT_ID.iam.gserviceaccount.com

# Create secret
kubectl create secret generic gcp-creds \
  -n crossplane-system \
  --from-file=creds=gcp-key.json

# Apply ProviderConfig
kubectl apply -f infrastructure/crossplane/providers/providerconfigs.yaml
```

### AWS Setup

```bash
# Create AWS IAM user
aws iam create-user --user-name crossplane-user

# Create access key
aws iam create-access-key --user-name crossplane-user > aws-key.json

# Create secret
kubectl create secret generic aws-creds \
  -n crossplane-system \
  --from-file=creds=aws-key.json

# Apply ProviderConfig
kubectl apply -f infrastructure/crossplane/providers/providerconfigs.yaml
```

## Usage Examples

### Provision Database

```bash
# Create database claim
kubectl apply -f - <<EOF
apiVersion: database.stack4things.io/v1alpha1
kind: DatabaseClaim
metadata:
  name: stack4things-db
  namespace: stack4things-infrastructure
spec:
  parameters:
    storageGB: 20
    instanceClass: db-f1-micro
    region: us-central1
EOF

# Check status
kubectl get databaseclaim stack4things-db -n stack4things-infrastructure

# Get connection details
kubectl get secret mysql-connection -n crossplane-system -o yaml
```

### Provision Redis Cache

```bash
# Create cache claim
kubectl apply -f - <<EOF
apiVersion: cache.stack4things.io/v1alpha1
kind: CacheClaim
metadata:
  name: stack4things-redis
  namespace: stack4things-infrastructure
spec:
  parameters:
    memoryGB: 1
    region: us-central1
EOF
```

### Provision Object Storage

```bash
# Create storage claim
kubectl apply -f - <<EOF
apiVersion: storage.stack4things.io/v1alpha1
kind: StorageClaim
metadata:
  name: stack4things-storage
  namespace: stack4things-infrastructure
spec:
  parameters:
    storageGB: 100
    region: us-central1
    storageClass: STANDARD
EOF
```

## GitOps Integration

### ArgoCD

```bash
# Install ArgoCD
./scripts/kubernetes/crossplane/setup-gitops.sh argocd

# Create application
kubectl apply -f infrastructure/gitops/argocd/applications/
```

### Flux

```bash
# Install Flux
./scripts/kubernetes/crossplane/setup-gitops.sh flux

# Bootstrap repository
flux bootstrap github \
  --owner=your-org \
  --repository=stack4things-infrastructure \
  --path=infrastructure/gitops/flux
```

## Monitoring

### Check Crossplane Status

```bash
# Check Crossplane pods
kubectl get pods -n crossplane-system

# Check providers
kubectl get providers

# Check XRDs
kubectl get crd | grep stack4things

# Check compositions
kubectl get compositions
```

### Check Resource Status

```bash
# Check claims
kubectl get databaseclaims,cacheclaims,messagingclaims,storageclaims -A

# Check composite resources
kubectl get xstackdatabase,xstackcache,xstackmessaging,xstackstorage -A

# Check managed resources
kubectl get managed
```

## Troubleshooting

### Provider Not Ready

```bash
# Check provider status
kubectl describe provider provider-gcp

# Check provider logs
kubectl logs -n crossplane-system -l pkg.crossplane.io/provider=provider-gcp
```

### Claim Not Provisioning

```bash
# Check claim status
kubectl describe databaseclaim stack4things-db -n stack4things-infrastructure

# Check events
kubectl get events -n stack4things-infrastructure --sort-by='.lastTimestamp'

# Check composite resource
kubectl get xstackdatabase -o yaml
```

### Credentials Issues

```bash
# Verify secret exists
kubectl get secret gcp-creds -n crossplane-system

# Check ProviderConfig
kubectl get providerconfig gcp-provider -o yaml
```

## Production Considerations

1. **Security**: Use IRSA (AWS) or Workload Identity (GCP) for credentials
2. **High Availability**: Deploy Crossplane in HA mode
3. **Monitoring**: Monitor Crossplane metrics and resource provisioning
4. **Backup**: Backup Crossplane configuration and claims
5. **Cost Management**: Monitor cloud resource costs
6. **Compliance**: Ensure compliance with organizational policies
7. **Documentation**: Document custom compositions and XRDs

## References

- [Crossplane Documentation](https://docs.crossplane.io/)
- [Crossplane Providers](https://marketplace.upbound.io/)
- [ArgoCD Documentation](https://argo-cd.readthedocs.io/)
- [Flux Documentation](https://fluxcd.io/docs/)
