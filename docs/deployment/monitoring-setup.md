# Monitoring Stack Setup Guide

## Overview

Stack4Things v2.0 uses a comprehensive monitoring stack:

- **Prometheus**: Metrics collection and storage
- **Grafana**: Visualization and dashboards
- **Tempo**: Distributed tracing
- **Loki**: Log aggregation
- **Alertmanager**: Alert management

## Quick Setup

Run the complete monitoring stack setup:

```bash
./scripts/kubernetes/monitoring/setup-all.sh
```

This will install all components automatically.

## Manual Setup

### 1. Prometheus Operator

```bash
./scripts/kubernetes/monitoring/setup-prometheus.sh
```

Installs:
- Prometheus Operator
- Prometheus server
- ServiceMonitor CRD
- PrometheusRule CRD

### 2. Grafana

```bash
./scripts/kubernetes/monitoring/setup-grafana.sh
```

Installs:
- Grafana server
- Pre-configured datasources (Prometheus, Loki, Tempo)
- Stack4Things dashboards

### 3. Tempo

```bash
./scripts/kubernetes/monitoring/setup-tempo.sh
```

Installs:
- Tempo distributed tracing backend
- Query frontend
- Ingester and compactor

### 4. Loki

```bash
./scripts/kubernetes/monitoring/setup-loki.sh
```

Installs:
- Loki log aggregation
- Promtail log collector

### 5. Alertmanager

```bash
./scripts/kubernetes/monitoring/setup-alertmanager.sh
```

Configures:
- Alert routing
- Notification channels
- Alert rules

## Accessing UIs

### Prometheus

```bash
kubectl port-forward -n stack4things-monitoring svc/prometheus-kube-prometheus-prometheus 9090:9090
```

Open: http://localhost:9090

### Grafana

```bash
kubectl port-forward -n stack4things-monitoring svc/grafana 3000:80
```

Open: http://localhost:3000
- Username: `admin`
- Password: `admin` (change on first login)

### Alertmanager

```bash
kubectl port-forward -n stack4things-monitoring svc/alertmanager-operated 9093:9093
```

Open: http://localhost:9093

## Service Monitoring

### ServiceMonitor

Create a ServiceMonitor to scrape metrics from your services:

```yaml
apiVersion: monitoring.coreos.com/v1
kind: ServiceMonitor
metadata:
  name: device-service
  namespace: stack4things
spec:
  selector:
    matchLabels:
      app: device-service
  endpoints:
    - port: http
      path: /metrics
      interval: 30s
```

### PodMonitor

For pod-level monitoring:

```yaml
apiVersion: monitoring.coreos.com/v1
kind: PodMonitor
metadata:
  name: device-service-pods
  namespace: stack4things
spec:
  selector:
    matchLabels:
      app: device-service
  podMetricsEndpoints:
    - port: metrics
      interval: 30s
```

## Logging

### Log Collection

Promtail automatically collects logs from all pods in the cluster.

### Query Logs in Grafana

1. Open Grafana
2. Go to Explore
3. Select Loki datasource
4. Query: `{namespace="stack4things"}`

## Tracing

### Instrument Services

Add OpenTelemetry instrumentation to your services:

```python
from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor

trace.set_tracer_provider(TracerProvider())
tracer = trace.get_tracer(__name__)

otlp_exporter = OTLPSpanExporter(
    endpoint="tempo-distributed-distributor.stack4things-monitoring:4317"
)
span_processor = BatchSpanProcessor(otlp_exporter)
trace.get_tracer_provider().add_span_processor(span_processor)
```

### View Traces

1. Open Grafana
2. Go to Explore
3. Select Tempo datasource
4. Search for traces

## Alerting

### Alert Rules

Alert rules are defined in `infrastructure/kubernetes/monitoring/prometheus/prometheus-rules.yaml`

### Configure Notifications

Edit `infrastructure/kubernetes/monitoring/alertmanager/alertmanager-config.yaml`:

```yaml
receivers:
  - name: 'critical-alerts'
    email_configs:
      - to: 'ops-team@stack4things.io'
        subject: 'CRITICAL: {{ .GroupLabels.alertname }}'
```

## Dashboards

### Pre-configured Dashboards

- Stack4Things Overview
- Service Metrics
- Resource Usage

### Create Custom Dashboards

1. Open Grafana
2. Go to Dashboards → New
3. Import JSON or create manually
4. Add datasources: Prometheus, Loki, Tempo

## Troubleshooting

### Prometheus Not Scraping

```bash
# Check ServiceMonitor
kubectl get servicemonitor -n stack4things

# Check Prometheus targets
kubectl port-forward -n stack4things-monitoring svc/prometheus-kube-prometheus-prometheus 9090:9090
# Open http://localhost:9090/targets
```

### Loki Not Collecting Logs

```bash
# Check Promtail logs
kubectl logs -n stack4things-monitoring -l app.kubernetes.io/name=promtail

# Check Loki
kubectl get pods -n stack4things-monitoring | grep loki
```

### Grafana Not Loading Dashboards

```bash
# Check datasources
kubectl get configmap grafana-datasources -n stack4things-monitoring -o yaml

# Check Grafana logs
kubectl logs -n stack4things-monitoring -l app.kubernetes.io/name=grafana
```

## Production Considerations

1. **Storage**: Configure persistent volumes for Prometheus and Loki
2. **Retention**: Set appropriate retention policies
3. **Scalability**: Scale Prometheus/Loki horizontally if needed
4. **Security**: Enable authentication for Grafana
5. **Backup**: Backup Prometheus and Grafana data regularly

