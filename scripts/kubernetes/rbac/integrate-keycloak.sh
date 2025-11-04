#!/bin/bash
# Integrate RBAC with Keycloak

set -e

echo "🔗 Integrating RBAC with Keycloak"

KC_POD=$(kubectl get pods -n stack4things-auth -l app.kubernetes.io/name=keycloak -o jsonpath='{.items[0].metadata.name}' 2>/dev/null || echo "")
KC_URL="http://localhost:8080"
ADMIN_USER="admin"
ADMIN_PASSWORD=$(kubectl get secret keycloak-secrets -n stack4things-auth -o jsonpath='{.data.admin-password}' 2>/dev/null | base64 -d || echo "admin")

if [ -z "$KC_POD" ]; then
    echo "❌ Keycloak not found. Please install Keycloak first."
    exit 1
fi

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

# Read roles from ConfigMap
OPENSTACK_ROLES=$(kubectl get configmap rbac-roles -n stack4things -o jsonpath='{.data.openstack-roles\.yaml}')
STACK4THINGS_ROLES=$(kubectl get configmap stack4things-roles -n stack4things -o jsonpath='{.data.custom-roles\.yaml}')

# Create OpenStack roles in Keycloak
echo "📝 Creating OpenStack roles in Keycloak..."
for role in admin member reader service; do
    kubectl exec -n stack4things-auth "$KC_POD" -- \
        curl -s -X POST "$KC_URL/admin/realms/stack4things/roles" \
        -H "Authorization: Bearer $TOKEN" \
        -H "Content-Type: application/json" \
        -d "{\"name\":\"$role\",\"description\":\"OpenStack $role role\"}" || true
done

# Create Stack4Things custom roles
echo "📝 Creating Stack4Things custom roles in Keycloak..."
for role in device-admin fleet-manager network-admin plugin-developer execution-operator auditor; do
    kubectl exec -n stack4things-auth "$KC_POD" -- \
        curl -s -X POST "$KC_URL/admin/realms/stack4things/roles" \
        -H "Authorization: Bearer $TOKEN" \
        -H "Content-Type: application/json" \
        -d "{\"name\":\"$role\",\"description\":\"Stack4Things $role role\"}" || true
done

# Create role mappings
echo "📝 Creating role mappings..."
kubectl apply -f infrastructure/kubernetes/rbac/keycloak-integration/ || true

echo ""
echo "✅ Keycloak integration complete!"
echo ""
echo "📋 Roles synchronized:"
echo "  OpenStack: admin, member, reader, service"
echo "  Stack4Things: device-admin, fleet-manager, network-admin, plugin-developer, execution-operator, auditor"

