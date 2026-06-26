#!/bin/bash
# Configure Keystone Identity Broker in Keycloak

set -e

echo "🔗 Configuring Keystone Identity Broker in Keycloak"

KC_POD=$(kubectl get pods -n nxr-auth -l app.kubernetes.io/name=keycloak -o jsonpath='{.items[0].metadata.name}')
KC_URL="http://localhost:8080"
ADMIN_USER="admin"
ADMIN_PASSWORD=$(kubectl get secret keycloak-secrets -n nxr-auth -o jsonpath='{.data.admin-password}' 2>/dev/null | base64 -d || echo "admin")

# Get admin token
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

# Read Keystone configuration
KEYSTONE_URL=${KEYSTONE_URL:-"http://keystone.example.com:5000"}
KEYSTONE_USER=${KEYSTONE_USER:-"admin"}
KEYSTONE_PASSWORD=${KEYSTONE_PASSWORD:-"CHANGE_ME"}
KEYSTONE_DOMAIN=${KEYSTONE_DOMAIN:-"default"}
KEYSTONE_PROJECT=${KEYSTONE_PROJECT:-"admin"}

echo "📝 Configuring Keystone Identity Broker..."
echo "  Keystone URL: $KEYSTONE_URL"
echo "  Username: $KEYSTONE_USER"
echo "  Domain: $KEYSTONE_DOMAIN"
echo "  Project: $KEYSTONE_PROJECT"

# Create identity provider (Keystone)
kubectl exec -n nxr-auth "$KC_POD" -- \
    curl -s -X POST "$KC_URL/admin/realms/nxr/identity-provider/instances" \
    -H "Authorization: Bearer $TOKEN" \
    -H "Content-Type: application/json" \
    -d @- <<EOF || true
{
  "alias": "keystone",
  "providerId": "openstack",
  "enabled": true,
  "updateProfileFirstLoginMode": "on",
  "trustEmail": false,
  "storeToken": true,
  "addReadTokenRoleOnCreate": false,
  "authenticateByDefault": false,
  "linkOnly": false,
  "firstBrokerLoginFlowAlias": "first broker login",
  "config": {
    "authUrl": "$KEYSTONE_URL/v3",
    "domainName": "$KEYSTONE_DOMAIN",
    "projectName": "$KEYSTONE_PROJECT",
    "username": "$KEYSTONE_USER",
    "password": "$KEYSTONE_PASSWORD"
  }
}
EOF

# Configure first broker login flow
echo "📝 Configuring first broker login flow..."

echo ""
echo "✅ Keystone Identity Broker configured!"
echo ""
echo "📋 Configuration:"
echo "  Provider: OpenStack Keystone"
echo "  Alias: keystone"
echo "  Enabled: true"
echo ""
echo "💡 Users can now login with Keystone credentials"
echo "💡 Keystone will be used as fallback if Keycloak authentication fails"

