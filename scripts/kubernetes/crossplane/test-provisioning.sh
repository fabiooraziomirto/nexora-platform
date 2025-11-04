#!/bin/bash
# Test Crossplane provisioning

set -e

echo "🧪 Testing Crossplane provisioning"

# Check if Crossplane is installed
if ! kubectl get deployment crossplane -n crossplane-system &> /dev/null; then
    echo "❌ Crossplane not found. Installing..."
    ./scripts/kubernetes/crossplane/setup-crossplane.sh
fi

# Check if providers are installed
PROVIDERS=$(kubectl get providers -o jsonpath='{.items[*].metadata.name}')
if [ -z "$PROVIDERS" ]; then
    echo "⚠️  No providers installed. Installing GCP provider..."
    ./scripts/kubernetes/crossplane/setup-provider.sh gcp
fi

# Check if XRDs are installed
XRDS=$(kubectl get crd | grep stack4things.io | wc -l)
if [ "$XRDS" -eq 0 ]; then
    echo "⚠️  No XRDs found. Installing..."
    ./scripts/kubernetes/crossplane/setup-compositions.sh
fi

# Test database claim
echo "📝 Testing database claim..."
kubectl apply -f - <<EOF
apiVersion: database.stack4things.io/v1alpha1
kind: DatabaseClaim
metadata:
  name: test-database
  namespace: stack4things-infrastructure
spec:
  parameters:
    storageGB: 10
    instanceClass: db-f1-micro
    region: us-central1
EOF

# Wait for claim to be ready
echo "⏳ Waiting for database claim to be ready..."
timeout=300
elapsed=0
while [ $elapsed -lt $timeout ]; do
    STATUS=$(kubectl get databaseclaim test-database -n stack4things-infrastructure -o jsonpath='{.status.conditions[?(@.type=="Ready")].status}' 2>/dev/null || echo "Unknown")
    if [ "$STATUS" == "True" ]; then
        echo "✅ Database claim ready!"
        break
    fi
    echo "  Status: $STATUS (waiting...)"
    sleep 5
    elapsed=$((elapsed + 5))
done

if [ $elapsed -ge $timeout ]; then
    echo "⚠️  Timeout waiting for database claim"
fi

# Check resources
echo ""
echo "📋 Database Claim Status:"
kubectl get databaseclaim test-database -n stack4things-infrastructure || true

echo ""
echo "📋 Composite Resources:"
kubectl get xstackdatabase || true

echo ""
echo "📋 Managed Resources:"
kubectl get managed || true

# Cleanup (optional)
read -p "Do you want to delete the test database? (y/n) " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    echo "🗑️  Deleting test database..."
    kubectl delete databaseclaim test-database -n stack4things-infrastructure || true
fi

echo ""
echo "✅ Crossplane provisioning test complete!"

