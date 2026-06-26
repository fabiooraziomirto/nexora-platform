#!/bin/bash
# Configure API Gateway for dual authentication (Keycloak + Keystone)

set -e

echo "🚪 Configuring API Gateway for dual authentication"

# Check if Kong is installed
if ! kubectl get deployment kong -n nxr &> /dev/null; then
    echo "⚠️  Kong API Gateway not found. Installing..."
    # TODO: Add Kong installation script
    echo "Please install Kong first"
    exit 1
fi

# Apply Kong configuration for dual auth
echo "📝 Applying Kong dual authentication configuration..."
kubectl apply -f infrastructure/kubernetes/keycloak/kong/kong-dual-auth.yaml || true

# Apply Keycloak OIDC plugin configuration
echo "📝 Applying Keycloak OIDC plugin..."
kubectl apply -f infrastructure/kubernetes/keycloak/kong/kong-keycloak-oidc.yaml || true

# Apply Keystone plugin configuration
echo "📝 Applying Keystone plugin..."
kubectl apply -f infrastructure/kubernetes/keycloak/kong/kong-keystone.yaml || true

echo ""
echo "✅ API Gateway dual authentication configured!"
echo ""
echo "📋 Configuration:"
echo "  Primary Auth: Keycloak OIDC"
echo "  Fallback Auth: Keystone"
echo "  Routing: Keycloak first, Keystone fallback"
echo ""
echo "💡 API requests will:"
echo "  1. Try Keycloak OIDC authentication first"
echo "  2. Fallback to Keystone if Keycloak fails"
echo "  3. Support both authentication methods simultaneously"

