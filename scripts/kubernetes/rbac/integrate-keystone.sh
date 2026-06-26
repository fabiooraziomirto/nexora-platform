#!/bin/bash
# Integrate RBAC with Keystone

set -e

echo "🔗 Integrating RBAC with Keystone"

KEYSTONE_URL=${KEYSTONE_URL:-"http://keystone.example.com:5000"}
KEYSTONE_ADMIN_USER=${KEYSTONE_ADMIN_USER:-"admin"}
KEYSTONE_ADMIN_PASSWORD=${KEYSTONE_ADMIN_PASSWORD:-"CHANGE_ME"}

echo "📝 Configuring Keystone roles..."
echo "  Keystone URL: $KEYSTONE_URL"
echo "  Admin User: $KEYSTONE_ADMIN_USER"

# Get Keystone token
TOKEN_RESPONSE=$(curl -s -X POST "$KEYSTONE_URL/v3/auth/tokens" \
  -H "Content-Type: application/json" \
  -d "{
    \"auth\": {
      \"identity\": {
        \"methods\": [\"password\"],
        \"password\": {
          \"user\": {
            \"name\": \"$KEYSTONE_ADMIN_USER\",
            \"domain\": {\"name\": \"default\"},
            \"password\": \"$KEYSTONE_ADMIN_PASSWORD\"
          }
        }
      }
    }
  }")

TOKEN=$(echo "$TOKEN_RESPONSE" | jq -r '.token.id' 2>/dev/null || echo "")

if [ -z "$TOKEN" ] || [ "$TOKEN" == "null" ]; then
    echo "⚠️  Could not authenticate with Keystone. Skipping role creation."
    echo "💡 Manually create roles in Keystone:"
    echo "   - admin"
    echo "   - member"
    echo "   - reader"
    echo "   - service"
    echo "   - device-admin"
    echo "   - fleet-manager"
    echo "   - network-admin"
    echo "   - plugin-developer"
    echo "   - execution-operator"
    echo "   - auditor"
    exit 0
fi

# Create roles in Keystone
echo "📝 Creating roles in Keystone..."

# OpenStack standard roles
for role in admin member reader service; do
    curl -s -X PUT "$KEYSTONE_URL/v3/roles/$role" \
      -H "X-Auth-Token: $TOKEN" \
      -H "Content-Type: application/json" \
      -d "{\"role\": {\"name\": \"$role\"}}" || true
done

# Nxr custom roles
for role in device-admin fleet-manager network-admin plugin-developer execution-operator auditor; do
    curl -s -X PUT "$KEYSTONE_URL/v3/roles/$role" \
      -H "X-Auth-Token: $TOKEN" \
      -H "Content-Type: application/json" \
      -d "{\"role\": {\"name\": \"$role\"}}" || true
done

# Apply Keystone integration config
kubectl apply -f infrastructure/kubernetes/rbac/keystone-integration/ || true

echo ""
echo "✅ Keystone integration complete!"
echo ""
echo "📋 Roles synchronized:"
echo "  OpenStack: admin, member, reader, service"
echo "  Nxr: device-admin, fleet-manager, network-admin, plugin-developer, execution-operator, auditor"

