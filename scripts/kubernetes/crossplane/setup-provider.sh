#!/bin/bash
# Setup cloud provider for Crossplane

set -e

PROVIDER=${1:-gcp}

if [[ ! "$PROVIDER" =~ ^(gcp|aws|azure)$ ]]; then
    echo "❌ Invalid provider. Use: gcp, aws, or azure"
    exit 1
fi

echo "☁️  Setting up $PROVIDER provider for Crossplane"

# Check if Crossplane is installed
if ! kubectl get deployment crossplane -n crossplane-system &> /dev/null; then
    echo "❌ Crossplane not found. Installing..."
    ./scripts/kubernetes/crossplane/setup-crossplane.sh
fi

case "$PROVIDER" in
    gcp)
        echo "📦 Installing GCP provider..."
        
        # Install GCP provider
        kubectl apply -f - <<EOF
apiVersion: pkg.crossplane.io/v1
kind: Provider
metadata:
  name: provider-gcp
spec:
  package: xpkg.upbound.io/upbound/provider-gcp:v0.46.0
EOF
        
        echo "⏳ Waiting for GCP provider to be ready..."
        kubectl wait --for=condition=healthy provider/provider-gcp --timeout=300s
        
        echo "📝 Configure GCP credentials:"
        echo "  1. Create GCP service account with required permissions"
        echo "  2. Create JSON key for service account"
        echo "  3. Run: kubectl create secret generic gcp-creds -n crossplane-system --from-file=creds=gcp-key.json"
        echo "  4. Apply ProviderConfig:"
        echo "     kubectl apply -f infrastructure/crossplane/providers/gcp-providerconfig.yaml"
        ;;
    
    aws)
        echo "📦 Installing AWS provider..."
        
        # Install AWS provider
        kubectl apply -f - <<EOF
apiVersion: pkg.crossplane.io/v1
kind: Provider
metadata:
  name: provider-aws
spec:
  package: xpkg.upbound.io/upbound/provider-aws:v0.47.0
EOF
        
        echo "⏳ Waiting for AWS provider to be ready..."
        kubectl wait --for=condition=healthy provider/provider-aws --timeout=300s
        
        echo "📝 Configure AWS credentials:"
        echo "  1. Create AWS IAM user with required permissions"
        echo "  2. Create access key for IAM user"
        echo "  3. Run: kubectl create secret generic aws-creds -n crossplane-system --from-file=creds=aws-key.json"
        echo "  4. Apply ProviderConfig:"
        echo "     kubectl apply -f infrastructure/crossplane/providers/aws-providerconfig.yaml"
        ;;
    
    azure)
        echo "📦 Installing Azure provider..."
        
        # Install Azure provider
        kubectl apply -f - <<EOF
apiVersion: pkg.crossplane.io/v1
kind: Provider
metadata:
  name: provider-azure
spec:
  package: xpkg.upbound.io/upbound/provider-azure:v0.50.0
EOF
        
        echo "⏳ Waiting for Azure provider to be ready..."
        kubectl wait --for=condition=healthy provider/provider-azure --timeout=300s
        
        echo "📝 Configure Azure credentials:"
        echo "  1. Create Azure Service Principal"
        echo "  2. Create secret with credentials:"
        echo "     kubectl create secret generic azure-creds -n crossplane-system --from-literal=creds=azure-secret"
        echo "  3. Apply ProviderConfig:"
        echo "     kubectl apply -f infrastructure/crossplane/providers/azure-providerconfig.yaml"
        ;;
esac

echo ""
echo "✅ $PROVIDER provider setup complete!"
echo ""
echo "📋 Provider Status:"
kubectl get providers

