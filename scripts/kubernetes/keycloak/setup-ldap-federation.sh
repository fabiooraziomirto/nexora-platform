#!/bin/bash
# Setup LDAP/AD user federation in Keycloak

set -e

echo "🔗 Setting up LDAP/AD user federation in Keycloak"

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

# Read LDAP configuration
LDAP_URL=${LDAP_URL:-"ldap://ldap.example.com:389"}
LDAP_BASE_DN=${LDAP_BASE_DN:-"dc=example,dc=com"}
LDAP_BIND_DN=${LDAP_BIND_DN:-"cn=admin,dc=example,dc=com"}
LDAP_BIND_PASSWORD=${LDAP_BIND_PASSWORD:-"CHANGE_ME"}
LDAP_USER_DN=${LDAP_USER_DN:-"ou=users,dc=example,dc=com"}

echo "📝 Configuring LDAP user federation..."
echo "  LDAP URL: $LDAP_URL"
echo "  Base DN: $LDAP_BASE_DN"
echo "  Bind DN: $LDAP_BIND_DN"
echo "  User DN: $LDAP_USER_DN"

# Create LDAP user federation
kubectl exec -n nxr-auth "$KC_POD" -- \
    curl -s -X POST "$KC_URL/admin/realms/nxr/user-federations/ldap" \
    -H "Authorization: Bearer $TOKEN" \
    -H "Content-Type: application/json" \
    -d @- <<EOF || true
{
  "name": "ldap",
  "providerId": "ldap",
  "providerType": "org.keycloak.storage.UserStorageProvider",
  "config": {
    "connectionUrl": ["$LDAP_URL"],
    "usersDn": ["$LDAP_USER_DN"],
    "bindDn": ["$LDAP_BIND_DN"],
    "bindCredential": ["$LDAP_BIND_PASSWORD"],
    "customUserSearchFilter": ["(uid={0})"],
    "searchScope": ["1"],
    "editMode": ["READ_ONLY"],
    "syncRegistrations": ["false"],
    "importEnabled": ["true"],
    "enabled": ["true"]
  }
}
EOF

# Sync users from LDAP
echo "📝 Syncing users from LDAP..."
kubectl exec -n nxr-auth "$KC_POD" -- \
    curl -s -X POST "$KC_URL/admin/realms/nxr/user-federations/ldap/sync?action=triggerFullSync" \
    -H "Authorization: Bearer $TOKEN" || true

echo ""
echo "✅ LDAP user federation configured!"
echo ""
echo "📋 Configuration:"
echo "  Provider: LDAP"
echo "  Connection URL: $LDAP_URL"
echo "  User DN: $LDAP_USER_DN"
echo "  Enabled: true"
echo ""
echo "💡 Users from LDAP can now login to Nxr"

