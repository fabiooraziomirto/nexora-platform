#!/bin/bash
# Complete monitoring stack setup script

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../../.." && pwd)"

echo "📊 Setting up complete monitoring stack for Nxr v2.0"

# Step 1: Prometheus Operator
echo ""
echo "=== Step 1: Installing Prometheus Operator ==="
"$SCRIPT_DIR/setup-prometheus.sh"

# Step 2: Grafana
echo ""
echo "=== Step 2: Installing Grafana ==="
"$SCRIPT_DIR/setup-grafana.sh"

# Step 3: Tempo
echo ""
echo "=== Step 3: Installing Tempo ==="
"$SCRIPT_DIR/setup-tempo.sh"

# Step 4: Loki
echo ""
echo "=== Step 4: Installing Loki ==="
"$SCRIPT_DIR/setup-loki.sh"

# Step 5: Alertmanager
echo ""
echo "=== Step 5: Setting up Alertmanager ==="
"$SCRIPT_DIR/setup-alertmanager.sh"

# Step 6: Configure Grafana datasources
echo ""
echo "=== Step 6: Configuring Grafana datasources ==="
kubectl apply -f "$PROJECT_ROOT/infrastructure/kubernetes/monitoring/grafana/datasources.yaml" || true

# Step 7: Import Grafana dashboards
echo ""
echo "=== Step 7: Importing Grafana dashboards ==="
kubectl apply -f "$PROJECT_ROOT/infrastructure/kubernetes/monitoring/grafana/dashboards.yaml" || true

# Summary
echo ""
echo "🎉 Monitoring stack setup complete!"
echo ""
echo "📋 Summary:"
echo "  ✅ Prometheus Operator installed"
echo "  ✅ Grafana installed"
echo "  ✅ Tempo installed"
echo "  ✅ Loki installed"
echo "  ✅ Alertmanager configured"
echo ""
echo "🔗 Access URLs:"
echo "  Prometheus: kubectl port-forward -n nxr-monitoring svc/prometheus-kube-prometheus-prometheus 9090:9090"
echo "  Grafana:    kubectl port-forward -n nxr-monitoring svc/grafana 3000:80"
echo "  Tempo:      kubectl port-forward -n nxr-monitoring svc/tempo-distributed-distributor 4317:4317"
echo "  Alertmanager: kubectl port-forward -n nxr-monitoring svc/alertmanager-operated 9093:9093"
echo ""
echo "📝 Grafana credentials:"
echo "  Username: admin"
echo "  Password: admin (change on first login)"

