#!/bin/bash
# Secret rotation script

set -e

SECRET_NAME=$1
NAMESPACE=${2:-nxr-infrastructure}

if [ -z "$SECRET_NAME" ]; then
    echo "❌ Usage: $0 <secret-name> [namespace]"
    echo "Example: $0 mysql-credentials nxr-infrastructure"
    exit 1
fi

echo "🔄 Rotating secret: $SECRET_NAME in namespace $NAMESPACE"

# Function to generate random password
generate_password() {
    openssl rand -base64 32 | tr -d "=+/" | cut -c1-25
}

# Check if secret exists
if ! kubectl get secret "$SECRET_NAME" -n "$NAMESPACE" &> /dev/null; then
    echo "❌ Secret $SECRET_NAME not found in namespace $NAMESPACE"
    exit 1
fi

# Backup current secret
echo "📦 Backing up current secret..."
kubectl get secret "$SECRET_NAME" -n "$NAMESPACE" -o yaml > "/tmp/${SECRET_NAME}-backup-$(date +%Y%m%d-%H%M%S).yaml"
echo "✅ Backup saved to /tmp/${SECRET_NAME}-backup-$(date +%Y%m%d-%H%M%S).yaml"

# Generate new password based on secret type
case "$SECRET_NAME" in
    mysql-credentials|mariadb-credentials)
        NEW_PASSWORD=$(generate_password)
        echo "🔄 Rotating MySQL password..."
        kubectl create secret generic "$SECRET_NAME" \
            --from-literal=username=nxr \
            --from-literal=password="$NEW_PASSWORD" \
            --from-literal=database=nxr \
            --namespace="$NAMESPACE" \
            --dry-run=client -o yaml | kubectl apply -f -
        
        echo "⚠️  IMPORTANT: Update database password manually or restart MySQL pods"
        echo "New password: $NEW_PASSWORD"
        ;;
    
    redis-credentials)
        NEW_PASSWORD=$(generate_password)
        echo "🔄 Rotating Redis password..."
        kubectl create secret generic "$SECRET_NAME" \
            --from-literal=password="$NEW_PASSWORD" \
            --namespace="$NAMESPACE" \
            --dry-run=client -o yaml | kubectl apply -f -
        
        echo "⚠️  IMPORTANT: Update Redis password manually or restart Redis pods"
        echo "New password: $NEW_PASSWORD"
        ;;
    
    app-secrets|api-gateway-secrets)
        NEW_JWT_SECRET=$(openssl rand -hex 32)
        NEW_ENCRYPTION_KEY=$(openssl rand -hex 32)
        echo "🔄 Rotating app secrets..."
        kubectl create secret generic "$SECRET_NAME" \
            --from-literal=jwt-secret="$NEW_JWT_SECRET" \
            --from-literal=encryption-key="$NEW_ENCRYPTION_KEY" \
            --namespace="$NAMESPACE" \
            --dry-run=client -o yaml | kubectl apply -f -
        
        echo "⚠️  IMPORTANT: Restart all pods using this secret"
        echo "New JWT secret: $NEW_JWT_SECRET"
        echo "New encryption key: $NEW_ENCRYPTION_KEY"
        ;;
    
    *)
        echo "⚠️  Unknown secret type. Please rotate manually."
        echo "To rotate a custom secret:"
        echo "  kubectl create secret generic $SECRET_NAME --from-literal=key=value --dry-run=client -o yaml | kubectl apply -f -"
        exit 1
        ;;
esac

# Restart pods using this secret (optional, commented out for safety)
# echo "🔄 Restarting pods using this secret..."
# kubectl rollout restart deployment -n "$NAMESPACE" --selector=app.kubernetes.io/name=nxr

echo ""
echo "✅ Secret rotation complete!"
echo ""
echo "📝 Next steps:"
echo "  1. Verify secret was updated:"
echo "     kubectl get secret $SECRET_NAME -n $NAMESPACE -o yaml"
echo ""
echo "  2. Restart pods using this secret:"
echo "     kubectl rollout restart deployment -n $NAMESPACE"

