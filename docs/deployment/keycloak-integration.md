# Keycloak + Keystone Integration Guide

## 🎯 Overview

Stack4Things v2.0 utilizza **Keycloak come autenticazione primaria** con **Keystone come fallback** per compatibilità con OpenStack.

## 🏗️ Architettura

```
┌─────────────────────────────────────────────────────────────┐
│                    API Gateway (Kong)                       │
│  ┌──────────────────────────────────────────────────────┐  │
│  │  Authentication Plugin                              │  │
│  │  1. Try Keycloak (Primary)                          │  │
│  │  2. Fallback to Keystone (Legacy)                   │  │
│  └──────────────────────────────────────────────────────┘  │
└──────────────┬───────────────────────┬──────────────────────┘
               │                       │
       ┌───────▼────────┐     ┌────────▼────────┐
       │   Keycloak     │     │    Keystone     │
       │   (Primary)    │     │   (Fallback)    │
       │                │     │                 │
       │  ┌──────────┐ │     │  ┌──────────┐   │
       │  │ Identity │ │◄────┤  │ Identity │   │
       │  │ Brokering│ │     │  │ Provider │   │
       │  └──────────┘ │     │  └──────────┘   │
       └──────────────┘     └─────────────────┘
```

## 🔧 Setup Keycloak

### 1. Deploy Keycloak in Kubernetes

```yaml
# infrastructure/kubernetes/keycloak/deployment.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: keycloak
  namespace: stack4things-auth
spec:
  replicas: 2
  selector:
    matchLabels:
      app: keycloak
  template:
    metadata:
      labels:
        app: keycloak
    spec:
      containers:
      - name: keycloak
        image: quay.io/keycloak/keycloak:23.0
        args:
          - start
          - --optimized
          - --hostname-strict=false
          - --hostname-strict-https=false
        env:
        - name: KEYCLOAK_ADMIN
          valueFrom:
            secretKeyRef:
              name: keycloak-admin
              key: username
        - name: KEYCLOAK_ADMIN_PASSWORD
          valueFrom:
            secretKeyRef:
              name: keycloak-admin
              key: password
        - name: KC_DB
          value: postgres
        - name: KC_DB_URL
          value: jdbc:postgresql://postgresql:5432/keycloak
        - name: KC_DB_USERNAME
          valueFrom:
            secretKeyRef:
              name: keycloak-db
              key: username
        - name: KC_DB_PASSWORD
          valueFrom:
            secretKeyRef:
              name: keycloak-db
              key: password
        - name: KC_HOSTNAME
          value: auth.stack4things.local
        ports:
        - containerPort: 8080
        livenessProbe:
          httpGet:
            path: /health/live
            port: 8080
        readinessProbe:
          httpGet:
            path: /health/ready
            port: 8080
---
apiVersion: v1
kind: Service
metadata:
  name: keycloak
  namespace: stack4things-auth
spec:
  selector:
    app: keycloak
  ports:
  - port: 8080
    targetPort: 8080
```

### 2. Configurare Realm Stack4Things

```bash
# Via Keycloak Admin CLI o Admin Console
# Creare realm "stack4things"
# Configurare:
# - OAuth2/OIDC settings
# - Client "stack4things-api"
# - Client "stack4things-ui"
# - User roles
# - Identity Brokering con Keystone
```

### 3. Identity Brokering con Keystone

```yaml
# Configurazione Keycloak Identity Broker per Keystone
# Via Admin Console:
# Identity Providers → Add provider → OpenID Connect v1.0
# Configurare:
# - Alias: keystone
# - Authorization URL: http://keystone:5000/v3/OS-FEDERATION/identity_providers/keystone/protocols/openid/auth
# - Token URL: http://keystone:5000/v3/OS-FEDERATION/identity_providers/keystone/protocols/openid/token
# - Client ID: <keystone-client-id>
# - Client Secret: <keystone-client-secret>
```

## 🔌 Kong Integration

### Kong Plugin per Keycloak

```yaml
# infrastructure/kubernetes/kong/keycloak-plugin.yaml
apiVersion: configuration.konghq.com/v1
kind: KongPlugin
metadata:
  name: keycloak-auth
  namespace: stack4things
config:
  issuer: http://keycloak.stack4things-auth:8080/realms/stack4things
  client_id: stack4things-api
  client_secret: <client-secret>
  verify_signature: true
  verify_claims: true
  verify_expiry: true
  verify_not_before: true
  verify_iss: true
  verify_aud: true
  run_on_preflight: true
plugin: oidc
---
apiVersion: configuration.konghq.com/v1
kind: KongPlugin
metadata:
  name: keystone-auth-fallback
  namespace: stack4things
config:
  keystone_host: keystone.stack4things-auth
  keystone_port: 5000
  token_cache_ttl: 300
  hide_credentials: true
plugin: keystone
```

### Kong Route con Dual Auth

```yaml
# infrastructure/kubernetes/kong/route.yaml
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: stack4things-api
  namespace: stack4things
  annotations:
    konghq.com/plugins: keycloak-auth,keystone-auth-fallback
    konghq.com/override: keycloak-primary
spec:
  ingressClassName: kong
  rules:
  - host: api.stack4things.local
    http:
      paths:
      - path: /
        pathType: Prefix
        backend:
          service:
            name: api-gateway
            port:
              number: 80
```

## 🔐 Kong Plugin Custom per Dual Auth

```lua
-- plugins/dual-auth/handler.lua
local DualAuth = {
  PRIORITY = 1000,
  VERSION = "1.0.0"
}

function DualAuth:access(conf)
  local ok, err = pcall(function()
    -- Try Keycloak first
    local keycloak_plugin = require("kong.plugins.oidc.handler")
    local keycloak_result = keycloak_plugin.access(self, conf.keycloak_config)
    
    if keycloak_result then
      kong.log.info("Authenticated via Keycloak")
      return
    end
    
    -- Fallback to Keystone
    kong.log.info("Keycloak auth failed, trying Keystone")
    local keystone_plugin = require("kong.plugins.keystone.handler")
    local keystone_result = keystone_plugin.access(self, conf.keystone_config)
    
    if keystone_result then
      kong.log.info("Authenticated via Keystone")
      return
    end
    
    -- Both failed
    return kong.response.exit(401, { message = "Authentication failed" })
  end)
  
  if not ok then
    kong.log.err("Dual auth error: ", err)
    return kong.response.exit(500, { message = "Internal authentication error" })
  end
end

return DualAuth
```

## 📝 Configuration

### Keycloak Client Configuration

```json
{
  "clientId": "stack4things-api",
  "enabled": true,
  "clientAuthenticatorType": "client-secret",
  "secret": "<secret>",
  "redirectUris": [
    "http://api.stack4things.local/*"
  ],
  "webOrigins": [
    "*"
  ],
  "protocol": "openid-connect",
  "publicClient": false,
  "standardFlowEnabled": true,
  "directAccessGrantsEnabled": true,
  "serviceAccountsEnabled": true,
  "attributes": {
    "access.token.lifespan": "3600"
  }
}
```

### Keystone Fallback Config

```yaml
# config/keystone-fallback.yaml
keystone:
  enabled: true
  endpoint: http://keystone:5000/v3
  # Routes che usano solo Keystone
  legacy_only:
    - /v1/*
    - /openstack/*
  # Service accounts che usano Keystone
  service_accounts:
    - iotronic-service
    - conductor-service
```

## 🔄 Migration Strategy

### Fase 1: Parallel Running
- Keycloak attivo per nuove API
- Keystone mantenuto per compatibilità
- Monitoring di entrambi i sistemi

### Fase 2: Identity Brokering
- Keycloak federato con Keystone
- Unico punto di accesso
- Trasparente per utenti

### Fase 3: Complete Migration
- Tutti i servizi su Keycloak
- Keystone solo per OpenStack services
- Deprecation timeline definito

## 🧪 Testing

### Test Keycloak Auth

```bash
# Get token from Keycloak
TOKEN=$(curl -X POST http://keycloak:8080/realms/stack4things/protocol/openid-connect/token \
  -d "client_id=stack4things-api" \
  -d "client_secret=<secret>" \
  -d "grant_type=client_credentials" | jq -r '.access_token')

# Use token
curl -H "Authorization: Bearer $TOKEN" \
  http://api.stack4things.local/api/v2/devices
```

### Test Keystone Fallback

```bash
# Get token from Keystone
TOKEN=$(openstack token issue -f value -c id)

# Use token
curl -H "X-Auth-Token: $TOKEN" \
  http://api.stack4things.local/api/v2/devices
```

## 📚 References

- [Keycloak Documentation](https://www.keycloak.org/documentation)
- [Keycloak Identity Brokering](https://www.keycloak.org/docs/latest/server_admin/#_identity_broker)
- [Kong OIDC Plugin](https://docs.konghq.com/hub/kong-inc/oidc/)
- [Keystone OpenID Connect](https://docs.openstack.org/keystone/latest/admin/federation/)


