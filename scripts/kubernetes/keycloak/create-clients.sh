#!/bin/bash
# Create OAuth2/OIDC clients in Keycloak

set -e

echo "🔐 Creating OAuth2/OIDC clients in Keycloak"

KC_POD=$(kubectl get pods -n stack4things-auth -l app.kubernetes.io/name=keycloak -o jsonpath='{.items[0].metadata.name}')
KC_URL="http://localhost:8080"
ADMIN_USER="admin"
ADMIN_PASSWORD=$(kubectl get secret keycloak-secrets -n stack4things-auth -o jsonpath='{.data.admin-password}' 2>/dev/null | base64 -d || echo "admin")

# Get admin token
TOKEN=$(kubectl exec -n stack4things-auth "$KC_POD" -- \
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

# Function to create client
create_client() {
    local client_id=$1
    local client_secret=$2
    local redirect_uris=$3
    local description=$4
    
    echo "Creating client: $client_id"
    
    kubectl exec -n stack4things-auth "$KC_POD" -- \
        curl -s -X POST "$KC_URL/admin/realms/stack4things/clients" \
        -H "Authorization: Bearer $TOKEN" \
        -H "Content-Type: application/json" \
        -d @- <<EOF || true
{
  "clientId": "$client_id",
  "enabled": true,
  "clientAuthenticatorType": "client-secret",
  "secret": "$client_secret",
  "redirectUris": $redirect_uris,
  "webOrigins": ["*"],
  "protocol": "openid-connect",
  "publicClient": false,
  "standardFlowEnabled": true,
  "implicitFlowEnabled": false,
  "directAccessGrantsEnabled": true,
  "serviceAccountsEnabled": true,
  "description": "$description"
}
EOF
}

# Generate client secrets
API_GATEWAY_SECRET=$(openssl rand -hex 32)
DEVICE_SERVICE_SECRET=$(openssl rand -hex 32)
WEB_UI_SECRET=$(openssl rand -hex 32)

# Create API Gateway client
create_client "api-gateway" "$API_GATEWAY_SECRET" \
    '["http://localhost:8000/auth/callback", "https://api.stack4things.io/auth/callback"]' \
    "API Gateway OAuth2 client"

# Create Device Service client
create_client "device-service" "$DEVICE_SERVICE_SECRET" \
    '["http://localhost:8001/auth/callback"]' \
    "Device Service OAuth2 client"

# Create Web UI client
create_client "web-ui" "$WEB_UI_SECRET" \
    '["http://localhost:3000/auth/callback", "https://app.stack4things.io/auth/callback"]' \
    "Web UI OAuth2 client"

# Store client secrets
kubectl create secret generic keycloak-clients \
    --from-literal=api-gateway-secret="$API_GATEWAY_SECRET" \
    --from-literal=device-service-secret="$DEVICE_SERVICE_SECRET" \
    --from-literal=web-ui-secret="$WEB_UI_SECRET" \
    --namespace=stack4things-auth \
    --dry-run=client -o yaml | kubectl apply -f -

echo ""
echo "✅ OAuth2/OIDC clients created!"
echo ""
echo "📋 Client Secrets (stored in keycloak-clients secret):"
echo "  API Gateway: $API_GATEWAY_SECRET"
echo "  Device Service: $DEVICE_SERVICE_SECRET"
echo "  Web UI: $WEB_UI_SECRET"

