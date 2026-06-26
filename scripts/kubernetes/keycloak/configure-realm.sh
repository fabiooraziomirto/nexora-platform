#!/bin/bash
# Configure Keycloak realm for Nxr

set -e

echo "🔐 Configuring Keycloak realm for Nxr"

KC_POD=$(kubectl get pods -n nxr-auth -l app.kubernetes.io/name=keycloak -o jsonpath='{.items[0].metadata.name}')
KC_URL="http://localhost:8080"
ADMIN_USER="admin"
ADMIN_PASSWORD=$(kubectl get secret keycloak-secrets -n nxr-auth -o jsonpath='{.data.admin-password}' 2>/dev/null | base64 -d || echo "admin")

# Wait for Keycloak to be ready
kubectl wait --for=condition=ready pod \
    -l app.kubernetes.io/name=keycloak \
    -n nxr-auth \
    --timeout=300s

# Get admin token
echo "🔑 Getting admin token..."
TOKEN=$(kubectl exec -n nxr-auth "$KC_POD" -- \
    curl -s -X POST "$KC_URL/realms/master/protocol/openid-connect/token" \
    -H "Content-Type: application/x-www-form-urlencoded" \
    -d "username=$ADMIN_USER" \
    -d "password=$ADMIN_PASSWORD" \
    -d "grant_type=password" \
    -d "client_id=admin-cli" | \
    jq -r '.access_token')

if [ "$TOKEN" == "null" ] || [ -z "$TOKEN" ]; then
    echo "❌ Failed to get admin token"
    exit 1
fi

# Create Nxr realm
echo "📝 Creating Nxr realm..."
kubectl exec -n nxr-auth "$KC_POD" -- \
    curl -s -X POST "$KC_URL/admin/realms" \
    -H "Authorization: Bearer $TOKEN" \
    -H "Content-Type: application/json" \
    -d @- <<EOF || true
{
  "realm": "nxr",
  "enabled": true,
  "displayName": "Nxr",
  "displayNameHtml": "<div class=\"kc-logo-text\"><span>Nxr</span></div>",
  "loginTheme": "nxr",
  "accountTheme": "nxr",
  "emailTheme": "nxr",
  "accessTokenLifespan": 3600,
  "accessTokenLifespanForImplicitFlow": 900,
  "ssoSessionIdleTimeout": 1800,
  "ssoSessionMaxLifespan": 36000,
  "offlineSessionIdleTimeout": 2592000,
  "accessCodeLifespan": 60,
  "accessCodeLifespanUserAction": 300,
  "accessCodeLifespanLogin": 1800,
  "actionTokenGeneratedByAdminLifespan": 43200,
  "actionTokenGeneratedByUserLifespan": 300,
  "enabled": true,
  "sslRequired": "external",
  "registrationAllowed": false,
  "registrationEmailAsUsername": false,
  "rememberMe": true,
  "verifyEmail": false,
  "loginWithEmailAllowed": true,
  "duplicateEmailsAllowed": false,
  "resetPasswordAllowed": true,
  "editUsernameAllowed": false,
  "bruteForceProtected": true,
  "permanentLockout": false,
  "maxFailureWaitSeconds": 900,
  "minimumQuickLoginWaitSeconds": 60,
  "waitIncrementSeconds": 60,
  "quickLoginCheckMilliSeconds": 1000,
  "maxDeltaTimeSeconds": 43200,
  "failureFactor": 30,
  "defaultRole": {
    "name": "user",
    "description": "Default role for all users"
  }
}
EOF

# Import realm configuration if available
if [ -f "infrastructure/kubernetes/keycloak/realm/realm-config.json" ]; then
    echo "📝 Importing realm configuration..."
    kubectl exec -i -n nxr-auth "$KC_POD" -- \
        curl -s -X POST "$KC_URL/admin/realms/nxr" \
        -H "Authorization: Bearer $TOKEN" \
        -H "Content-Type: application/json" \
        -d @- < infrastructure/kubernetes/keycloak/realm/realm-config.json || true
fi

# Create OAuth2/OIDC clients
echo "📝 Creating OAuth2/OIDC clients..."
./scripts/kubernetes/keycloak/create-clients.sh

echo ""
echo "✅ Keycloak realm configuration complete!"
echo ""
echo "📋 Realm Info:"
echo "  Realm: nxr"
echo "  Access Token Lifespan: 3600s (1 hour)"
echo "  SSO Session Idle Timeout: 1800s (30 minutes)"
echo "  SSO Session Max Lifespan: 36000s (10 hours)"

