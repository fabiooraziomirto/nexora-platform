#!/bin/bash
# Setup GitOps integration with ArgoCD or Flux

set -e

GITOPS_TOOL=${1:-argocd}

if [[ ! "$GITOPS_TOOL" =~ ^(argocd|flux)$ ]]; then
    echo "❌ Invalid GitOps tool. Use: argocd or flux"
    exit 1
fi

echo "🔄 Setting up GitOps with $GITOPS_TOOL for Stack4Things"

case "$GITOPS_TOOL" in
    argocd)
        echo "📦 Installing ArgoCD..."
        
        # Create namespace
        kubectl create namespace argocd --dry-run=client -o yaml | kubectl apply -f -
        
        # Install ArgoCD
        kubectl apply -n argocd -f https://raw.githubusercontent.com/argoproj/argo-cd/stable/manifests/install.yaml
        
        # Wait for ArgoCD to be ready
        echo "⏳ Waiting for ArgoCD to be ready..."
        kubectl wait --for=condition=available deployment/argocd-server -n argocd --timeout=300s
        
        # Get admin password
        ARGOCD_PASSWORD=$(kubectl -n argocd get secret argocd-initial-admin-secret -o jsonpath="{.data.password}" | base64 -d)
        
        echo ""
        echo "✅ ArgoCD installed!"
        echo ""
        echo "📋 ArgoCD Info:"
        echo "  Namespace: argocd"
        echo "  Admin Username: admin"
        echo "  Admin Password: $ARGOCD_PASSWORD"
        echo ""
        echo "📝 Access ArgoCD UI:"
        echo "  kubectl port-forward -n argocd svc/argocd-server 8080:443"
        echo "  Open https://localhost:8080"
        echo ""
        echo "📝 Next steps:"
        echo "  1. Create application:"
        echo "     kubectl apply -f infrastructure/gitops/argocd/applications/"
        ;;
    
    flux)
        echo "📦 Installing Flux..."
        
        # Install Flux CLI
        if ! command -v flux &> /dev/null; then
            echo "Installing Flux CLI..."
            curl -s https://fluxcd.io/install.sh | bash
        fi
        
        # Install Flux
        flux install --namespace=flux-system
        
        # Wait for Flux to be ready
        echo "⏳ Waiting for Flux to be ready..."
        kubectl wait --for=condition=ready pod -l app=helm-controller -n flux-system --timeout=300s
        
        echo ""
        echo "✅ Flux installed!"
        echo ""
        echo "📋 Flux Info:"
        echo "  Namespace: flux-system"
        echo ""
        echo "📝 Next steps:"
        echo "  1. Bootstrap Git repository:"
        echo "     flux bootstrap github --owner=<org> --repository=<repo> --path=infrastructure/gitops/flux"
        echo ""
        echo "  2. Create sources and Kustomizations:"
        echo "     kubectl apply -f infrastructure/gitops/flux/"
        ;;
esac

# Setup Crossplane GitOps integration
echo "📝 Setting up Crossplane GitOps integration..."
kubectl apply -f infrastructure/gitops/${GITOPS_TOOL}/crossplane/ || true

echo ""
echo "✅ GitOps integration complete!"

