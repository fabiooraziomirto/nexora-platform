# Kubernetes Cluster Setup Guide

## Overview

This guide covers setting up a local Kubernetes cluster using k3d for Stack4Things v2.0 development.

## Prerequisites

- Docker installed and running
- kubectl installed
- k3d (will be installed automatically)

## Quick Setup

Run the complete setup script:

```bash
./scripts/kubernetes/setup-all.sh
```

This will:
1. Create k3d cluster
2. Setup namespaces
3. Configure RBAC
4. Install Nginx Ingress Controller
5. Install Cert-Manager

## Manual Setup

### 1. Create k3d Cluster

```bash
./scripts/kubernetes/setup-k3d.sh
```

This creates a k3d cluster with:
- 1 server node
- 2 agent nodes
- Ports: 80, 443, 8080, 8443
- Traefik disabled (we use Nginx)

### 2. Apply Namespaces

```bash
kubectl apply -f infrastructure/kubernetes/base/namespaces.yaml
```

Namespaces created:
- `stack4things`: Main application namespace
- `stack4things-services`: Microservices namespace
- `stack4things-infrastructure`: Infrastructure components
- `stack4things-monitoring`: Monitoring stack
- `stack4things-logging`: Logging stack
- `ingress-nginx`: Ingress controller namespace
- `cert-manager`: Cert-Manager namespace
- `keycloak`: Keycloak namespace

### 3. Setup RBAC

```bash
kubectl apply -f infrastructure/kubernetes/base/rbac/
```

RBAC roles created:
- `stack4things-admin`: Full cluster access
- `stack4things-developer`: Developer access (limited)
- `stack4things-readonly`: Read-only access

### 4. Install Ingress Controller

```bash
./scripts/kubernetes/setup-ingress.sh
```

Installs Nginx Ingress Controller using Helm or kubectl.

### 5. Install Cert-Manager

```bash
./scripts/kubernetes/setup-cert-manager.sh
```

Installs Cert-Manager and creates ClusterIssuers:
- `letsencrypt-staging`: For testing
- `letsencrypt-prod`: For production

## Cluster Access

### Get Cluster Info

```bash
kubectl cluster-info
```

### List Nodes

```bash
kubectl get nodes
```

### Get Namespaces

```bash
kubectl get namespaces
```

## Ingress Configuration

### Create Ingress Resource

Example Ingress resource:

```yaml
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: device-service-ingress
  namespace: stack4things
  annotations:
    cert-manager.io/cluster-issuer: letsencrypt-staging
    nginx.ingress.kubernetes.io/rewrite-target: /
spec:
  ingressClassName: nginx
  tls:
    - hosts:
        - api.stack4things.local
      secretName: device-service-tls
  rules:
    - host: api.stack4things.local
      http:
        paths:
          - path: /
            pathType: Prefix
            backend:
              service:
                name: device-service
                port:
                  number: 80
```

## SSL Certificates

### Create Certificate

```bash
kubectl apply -f infrastructure/kubernetes/base/cert-manager/cluster-issuers.yaml
```

### Check Certificate Status

```bash
kubectl get certificates -n stack4things
kubectl describe certificate stack4things-tls -n stack4things
```

## Troubleshooting

### Cluster Not Starting

```bash
# Check k3d cluster status
k3d cluster list

# Check Docker
docker ps

# Restart cluster
k3d cluster stop stack4things
k3d cluster start stack4things
```

### Ingress Not Working

```bash
# Check ingress controller
kubectl get pods -n ingress-nginx

# Check ingress resources
kubectl get ingress -A

# Check ingress controller logs
kubectl logs -n ingress-nginx -l app.kubernetes.io/component=controller
```

### Cert-Manager Issues

```bash
# Check cert-manager pods
kubectl get pods -n cert-manager

# Check cluster issuers
kubectl get clusterissuers

# Check certificates
kubectl get certificates -A

# Check certificate orders
kubectl get orders -A
```

### RBAC Issues

```bash
# Test with service account
kubectl auth can-i get pods --as=system:serviceaccount:stack4things:stack4things-developer -n stack4things

# Check role bindings
kubectl get rolebindings -n stack4things
kubectl get clusterrolebindings | grep stack4things
```

## Cleanup

### Delete Cluster

```bash
k3d cluster delete stack4things
```

### Remove Resources

```bash
kubectl delete namespace stack4things
kubectl delete namespace ingress-nginx
kubectl delete namespace cert-manager
```

## Local Development

### Port Forwarding

```bash
# Port forward to service
kubectl port-forward -n stack4things svc/device-service 8000:80

# Access at http://localhost:8000
```

### Local DNS

Add to `/etc/hosts`:

```
127.0.0.1 stack4things.local
127.0.0.1 api.stack4things.local
```

## Production Considerations

For production:
1. Use managed Kubernetes (GKE, EKS, AKS)
2. Setup proper network policies
3. Configure pod security policies
4. Enable audit logging
5. Setup backup and disaster recovery
6. Configure resource quotas
7. Setup monitoring and alerting

