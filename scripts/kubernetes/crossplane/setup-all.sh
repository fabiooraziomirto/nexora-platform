#!/bin/bash
# Complete Crossplane setup script

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "☁️  Setting up complete Crossplane infrastructure for Stack4Things v2.0"

# Step 1: Install Crossplane
echo ""
echo "=== Step 1: Installing Crossplane ==="
"$SCRIPT_DIR/setup-crossplane.sh"

# Step 2: Setup provider (default: GCP)
echo ""
echo "=== Step 2: Setting up cloud provider ==="
read -p "Choose provider (gcp/aws/azure) [gcp]: " PROVIDER
PROVIDER=${PROVIDER:-gcp}
"$SCRIPT_DIR/setup-provider.sh" "$PROVIDER"

# Step 3: Setup compositions
echo ""
echo "=== Step 3: Setting up Compositions ==="
"$SCRIPT_DIR/setup-compositions.sh"

# Step 4: Setup GitOps (optional)
echo ""
read -p "Do you want to setup GitOps integration? (y/n) " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    echo "=== Step 4: Setting up GitOps ==="
    read -p "Choose GitOps tool (argocd/flux) [argocd]: " GITOPS
    GITOPS=${GITOPS:-argocd}
    "$SCRIPT_DIR/setup-gitops.sh" "$GITOPS"
fi

# Step 5: Test provisioning (optional)
echo ""
read -p "Do you want to test provisioning? (y/n) " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    echo "=== Step 5: Testing provisioning ==="
    "$SCRIPT_DIR/test-provisioning.sh"
fi

# Summary
echo ""
echo "🎉 Crossplane setup complete!"
echo ""
echo "📋 Summary:"
echo "  ✅ Crossplane installed"
echo "  ✅ Provider configured ($PROVIDER)"
echo "  ✅ XRDs and Compositions created"
if [[ $REPLY =~ ^[Yy]$ ]]; then
    echo "  ✅ GitOps integration configured ($GITOPS)"
fi
echo ""
echo "📝 Next steps:"
echo "  1. Configure provider credentials:"
echo "     kubectl create secret generic ${PROVIDER}-creds -n crossplane-system --from-file=creds=credentials.json"
echo ""
echo "  2. Create infrastructure claims:"
echo "     kubectl apply -f infrastructure/crossplane/examples/claims.yaml"
echo ""
echo "  3. Monitor provisioning:"
echo "     kubectl get databaseclaims,cacheclaims,messagingclaims,storageclaims"

