# Secret Management Guide

## Overview

Stack4Things v2.0 supports two secret management approaches:

1. **Kubernetes Secrets** (default, recommended for development)
2. **HashiCorp Vault** (recommended for production)

## Architecture

### Kubernetes Secrets

```
┌─────────────────────────────────────────┐
│         Application Pods                │
└──────────────┬──────────────────────────┘
               │
┌──────────────▼──────────────────────────┐
│      Kubernetes Secrets API              │
│  - Secrets stored in etcd                │
│  - Base64 encoded                        │
│  - RBAC controlled                        │
└─────────────────────────────────────────┘
```

### HashiCorp Vault

```
┌─────────────────────────────────────────┐
│         Application Pods                │
└──────────────┬──────────────────────────┘
               │
        ┌──────┴──────┐
        │             │
┌───────▼──────┐  ┌──▼──────────────┐
│ Vault Agent  │  │  Kubernetes     │
│  Injector    │  │  Auth Method     │
└───────┬──────┘  └─────────────────┘
        │
┌───────▼──────────────────────────┐
│      HashiCorp Vault               │
│  - Encrypted storage                │
│  - Dynamic secrets                   │
│  - Secret rotation                   │
└───────────────────────────────────┘
```

## Quick Setup

### Kubernetes Secrets (Default)

```bash
# Setup Kubernetes Secrets
./scripts/kubernetes/secrets/setup-secrets.sh
```

### HashiCorp Vault (Optional)

```bash
# Setup Vault
./scripts/kubernetes/vault/setup-vault.sh

# Setup Vault secrets engine
./scripts/kubernetes/vault/setup-vault-secrets.sh
```

## Secret Types

### Database Secrets

- **mysql-credentials**: MySQL/MariaDB connection credentials
- **redis-credentials**: Redis connection credentials
- **kafka-credentials**: Kafka connection credentials

### Application Secrets

- **app-secrets**: Application-level secrets (JWT, encryption keys)
- **api-gateway-secrets**: API Gateway secrets (API keys, JWT)
- **keycloak-secrets**: Keycloak admin credentials

### Infrastructure Secrets

- **openstack-credentials**: OpenStack integration credentials

## Secret Rotation

### Manual Rotation

```bash
# Rotate a specific secret
./scripts/kubernetes/secrets/rotate-secret.sh mysql-credentials stack4things-infrastructure

# Rotate app secrets
./scripts/kubernetes/secrets/rotate-secret.sh app-secrets stack4things
```

### Automatic Rotation

A CronJob checks secrets weekly for rotation needs:

```bash
# Check rotation status
kubectl get cronjob secret-rotation-check -n stack4things-infrastructure

# View rotation logs
kubectl logs -n stack4things-infrastructure -l job-name=secret-rotation-check --tail=50
```

## Using Secrets in Applications

### Kubernetes Secrets

#### Environment Variables

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: device-service
spec:
  template:
    spec:
      containers:
      - name: device-service
        env:
        - name: DATABASE_URL
          valueFrom:
            secretKeyRef:
              name: mysql-credentials
              key: connection-string
        - name: REDIS_PASSWORD
          valueFrom:
            secretKeyRef:
              name: redis-credentials
              key: password
```

#### Volume Mounts

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: device-service
spec:
  template:
    spec:
      containers:
      - name: device-service
        volumeMounts:
        - name: secrets
          mountPath: /etc/secrets
          readOnly: true
      volumes:
      - name: secrets
        secret:
          secretName: app-secrets
```

### HashiCorp Vault

#### Vault Agent Injector

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: device-service
  annotations:
    vault.hashicorp.com/agent-inject: "true"
    vault.hashicorp.com/role: "stack4things-service"
    vault.hashicorp.com/agent-inject-secret-database: "stack4things/database"
    vault.hashicorp.com/agent-inject-template-database: |
      {{- with secret "stack4things/database" }}
      export DATABASE_URL="mysql+pymysql://{{ .Data.data.username }}:{{ .Data.data.password }}@mariadb:3306/{{ .Data.data.database }}"
      {{- end }}
spec:
  template:
    spec:
      serviceAccountName: stack4things-service
      containers:
      - name: device-service
        # Vault agent injects secrets as files or env vars
```

## Secret Templates

Secret templates are available in `infrastructure/kubernetes/secrets/secret-templates.yaml`:

- All secrets have `CHANGE_ME` placeholders
- Setup scripts automatically generate secure values
- Templates include rotation annotations

## Security Best Practices

### 1. RBAC

- Use ServiceAccounts with minimal permissions
- Limit secret access to specific namespaces
- Use RoleBindings instead of ClusterRoleBindings

### 2. Secret Rotation

- Rotate secrets regularly (30-90 days)
- Document rotation procedures
- Test rotation in staging first

### 3. Encryption

- Enable encryption at rest for etcd (Kubernetes Secrets)
- Use Vault for production environments
- Enable TLS for secret transmission

### 4. Audit

- Enable audit logging for secret access
- Monitor secret access patterns
- Alert on unusual access

## Troubleshooting

### Secret Not Found

```bash
# Check if secret exists
kubectl get secrets -n stack4things-infrastructure

# Check secret details
kubectl describe secret mysql-credentials -n stack4things-infrastructure
```

### Permission Denied

```bash
# Check ServiceAccount
kubectl get serviceaccount stack4things-service -n stack4things

# Check RoleBinding
kubectl get rolebinding stack4things-secrets-reader -n stack4things

# Check permissions
kubectl auth can-i get secrets --namespace=stack4things --as=system:serviceaccount:stack4things:stack4things-service
```

### Vault Connection Issues

```bash
# Check Vault pod
kubectl get pods -n stack4things-vault | grep vault

# Check Vault logs
kubectl logs -n stack4things-vault vault-0

# Test Vault connection
kubectl exec -it vault-0 -n stack4things-vault -- vault status
```

## Production Considerations

### Kubernetes Secrets

**Pros:**
- Simple setup
- Native Kubernetes integration
- Good for development/testing

**Cons:**
- Base64 encoded (not encrypted)
- Stored in etcd
- Limited rotation capabilities

**Recommendation:** Use for development and staging.

### HashiCorp Vault

**Pros:**
- Encrypted storage
- Dynamic secrets
- Advanced rotation
- Audit logging
- Fine-grained access control

**Cons:**
- More complex setup
- Additional infrastructure
- Learning curve

**Recommendation:** Use for production environments.

## Migration from Kubernetes Secrets to Vault

1. **Setup Vault** (see Vault setup guide)
2. **Migrate secrets** to Vault KV store
3. **Update applications** to use Vault agent injector
4. **Verify** all secrets are accessible
5. **Remove** Kubernetes secrets (after verification)

## References

- [Kubernetes Secrets](https://kubernetes.io/docs/concepts/configuration/secret/)
- [HashiCorp Vault](https://www.vaultproject.io/)
- [Vault Kubernetes Auth](https://www.vaultproject.io/docs/auth/kubernetes)

