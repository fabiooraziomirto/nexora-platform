#!/bin/bash
# Complete authentication setup script

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "🔐 Setting up complete authentication infrastructure for Nxr v2.0"

# Step 1: Setup Keycloak
echo ""
echo "=== Step 1: Installing Keycloak ==="
"$SCRIPT_DIR/setup-keycloak.sh"

# Step 2: Configure realm
echo ""
echo "=== Step 2: Configuring Keycloak realm ==="
"$SCRIPT_DIR/configure-realm.sh"

# Step 3: Create OAuth2/OIDC clients
echo ""
echo "=== Step 3: Creating OAuth2/OIDC clients ==="
"$SCRIPT_DIR/create-clients.sh"

# Step 4: Configure Keystone broker
echo ""
echo "=== Step 4: Configuring Keystone Identity Broker ==="
"$SCRIPT_DIR/configure-keystone-broker.sh"

# Step 5: Configure API Gateway
echo ""
echo "=== Step 5: Configuring API Gateway dual auth ==="
"$SCRIPT_DIR/configure-api-gateway.sh"

# Step 6: Configure MFA (optional)
echo ""
read -p "Do you want to enable MFA? (y/n) " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    echo "=== Step 6: Configuring MFA ==="
    "$SCRIPT_DIR/configure-mfa.sh"
fi

# Summary
echo ""
echo "🎉 Authentication setup complete!"
echo ""
echo "📋 Summary:"
echo "  ✅ Keycloak installed and configured"
echo "  ✅ Nxr realm created"
echo "  ✅ OAuth2/OIDC clients configured"
echo "  ✅ Keystone Identity Broker configured"
echo "  ✅ API Gateway dual auth configured"
echo "  ✅ MFA configured (if enabled)"
echo ""
echo "📝 Access:"
echo "  Keycloak Admin: kubectl port-forward -n nxr-auth svc/keycloak 8080:8080"
echo "  Admin Username: admin"
echo "  Admin Password: Check keycloak-secrets secret"

