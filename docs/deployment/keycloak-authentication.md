# Keycloak Authentication Setup Guide

## Overview

Stack4Things v2.0 uses Keycloak as the primary authentication system with Keystone as a fallback for OpenStack integration.

## Architecture

```
┌─────────────────────────────────────────┐
│         Application Services            │
└──────────────┬──────────────────────────┘
               │
┌──────────────▼──────────────────────────┐
│         API Gateway (Kong)               │
│  - Primary: Keycloak OIDC                │
│  - Fallback: Keystone                   │
└──────────────┬──────────────────────────┘
               │
        ┌──────┴──────┐
        │             │
┌───────▼──────┐  ┌──▼──────────────┐
│   Keycloak    │  │   Keystone      │
│  (Primary)    │  │   (Fallback)    │
└───────┬──────┘  └─────────────────┘
        │
┌───────▼──────────┐
│  LDAP/AD (Opt)   │
└──────────────────┘
```

## Quick Setup

```bash
# Complete authentication setup
./scripts/kubernetes/keycloak/setup-all.sh

# Or step by step:
./scripts/kubernetes/keycloak/setup-keycloak.sh
./scripts/kubernetes/keycloak/configure-realm.sh
./scripts/kubernetes/keycloak/create-clients.sh
./scripts/kubernetes/keycloak/configure-keystone-broker.sh
./scripts/kubernetes/keycloak/configure-api-gateway.sh
```

## Components

### 1. Keycloak

- **Primary Authentication**: OAuth2/OIDC provider
- **Storage**: PostgreSQL backend
- **Persistence**: Persistent volumes (10Gi)
- **Admin Console**: Available via port-forward

### 2. Keycloak Realm

- **Realm**: `stack4things`
- **Access Token Lifespan**: 3600s (1 hour)
- **SSO Session**: 1800s idle, 36000s max
- **Brute Force Protection**: Enabled

### 3. OAuth2/OIDC Clients

- **api-gateway**: API Gateway client
- **device-service**: Device Service client
- **web-ui**: Web UI client

### 4. Keystone Integration

- **Identity Broker**: Configured in Keycloak
- **Fallback**: Automatic via API Gateway
- **OpenStack Compatibility**: Full support

### 5. API Gateway Dual Auth

- **Primary**: Keycloak OIDC
- **Fallback**: Keystone
- **Routing**: Keycloak first, Keystone fallback

## Configuration

### Keycloak Realm

Realm configuration is available in `infrastructure/kubernetes/keycloak/realm/realm-config.json`

### OAuth2/OIDC Clients

Client secrets are stored in `keycloak-clients` secret:

```bash
kubectl get secret keycloak-clients -n stack4things-auth -o yaml
```

### Keystone Broker

Configured via `configure-keystone-broker.sh` script:

```bash
KEYSTONE_URL=http://keystone.example.com:5000 \
KEYSTONE_USER=admin \
KEYSTONE_PASSWORD=password \
./scripts/kubernetes/keycloak/configure-keystone-broker.sh
```

## User Federation

### LDAP/AD Setup

```bash
LDAP_URL=ldap://ldap.example.com:389 \
LDAP_BASE_DN=dc=example,dc=com \
LDAP_BIND_DN=cn=admin,dc=example,dc=com \
LDAP_BIND_PASSWORD=password \
./scripts/kubernetes/keycloak/setup-ldap-federation.sh
```

## Multi-Factor Authentication (MFA)

### Enable MFA

```bash
./scripts/kubernetes/keycloak/configure-mfa.sh
```

### MFA Methods

- **TOTP**: Time-based One-Time Password (Google Authenticator, etc.)
- **Email OTP**: One-time password via email

### MFA Configuration

- **TOTP Algorithm**: SHA1
- **Digits**: 6
- **Period**: 30 seconds
- **Email OTP**: 60 seconds

## Single Sign-On (SSO)

SSO is automatically configured:

- **SSO Session Idle Timeout**: 1800s (30 minutes)
- **SSO Session Max Lifespan**: 36000s (10 hours)
- **Cross-Service SSO**: Enabled via shared session

## Usage Examples

### OAuth2/OIDC Flow

```python
from authlib.integrations.requests_client import OAuth2Session

# Initialize OAuth2 client
client = OAuth2Session(
    client_id='api-gateway',
    client_secret='client-secret',
    scope='openid profile email roles'
)

# Get authorization URL
authorization_url, state = client.authorization_url(
    'http://keycloak.stack4things-auth.svc.cluster.local:8080/realms/stack4things/protocol/openid-connect/auth'
)

# After user authorization, exchange code for token
token = client.fetch_token(
    'http://keycloak.stack4things-auth.svc.cluster.local:8080/realms/stack4things/protocol/openid-connect/token',
    authorization_response=callback_url
)
```

### Service-to-Service Authentication

```python
import requests

# Get service account token
token_response = requests.post(
    'http://keycloak.stack4things-auth.svc.cluster.local:8080/realms/stack4things/protocol/openid-connect/token',
    data={
        'grant_type': 'client_credentials',
        'client_id': 'device-service',
        'client_secret': 'client-secret'
    }
)

access_token = token_response.json()['access_token']

# Use token for API calls
response = requests.get(
    'http://api-gateway.stack4things.svc.cluster.local/api/v2/devices',
    headers={'Authorization': f'Bearer {access_token}'}
)
```

## Troubleshooting

### Keycloak Not Accessible

```bash
# Check Keycloak pods
kubectl get pods -n stack4things-auth | grep keycloak

# Check Keycloak logs
kubectl logs -n stack4things-auth -l app.kubernetes.io/name=keycloak

# Port-forward for testing
kubectl port-forward -n stack4things-auth svc/keycloak 8080:8080
```

### Authentication Failures

```bash
# Check realm configuration
kubectl exec -it keycloak-0 -n stack4things-auth -- \
  curl http://localhost:8080/admin/realms/stack4things \
  -H "Authorization: Bearer $TOKEN"

# Check client configuration
kubectl exec -it keycloak-0 -n stack4things-auth -- \
  curl http://localhost:8080/admin/realms/stack4things/clients \
  -H "Authorization: Bearer $TOKEN"
```

### Keystone Broker Issues

```bash
# Test Keystone connection
curl -X POST http://keystone.example.com:5000/v3/auth/tokens \
  -H "Content-Type: application/json" \
  -d '{
    "auth": {
      "identity": {
        "methods": ["password"],
        "password": {
          "user": {
            "name": "admin",
            "password": "password"
          }
        }
      }
    }
  }'
```

## Production Considerations

1. **High Availability**: Deploy Keycloak in HA mode
2. **Security**: Enable TLS/SSL for all connections
3. **Monitoring**: Monitor authentication metrics
4. **Backup**: Regular backups of Keycloak database
5. **Performance**: Tune Keycloak based on user load
6. **MFA**: Require MFA for sensitive operations
7. **Audit**: Enable audit logging for authentication events

## References

- [Keycloak Documentation](https://www.keycloak.org/documentation)
- [OAuth2/OIDC](https://oauth.net/2/)
- [OpenStack Keystone](https://docs.openstack.org/keystone/)

