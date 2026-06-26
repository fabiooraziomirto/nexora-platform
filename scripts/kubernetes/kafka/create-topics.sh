#!/bin/bash
# Script to create base Kafka topics

set -e

echo "📝 Creating base Kafka topics for Nxr v2.0"

# Check if Kafka is running
if ! kubectl get pods -n nxr-infrastructure -l app.kubernetes.io/name=kafka | grep -q Running; then
    echo "❌ Kafka pods are not running. Please wait for Kafka to be ready."
    exit 1
fi

KAFKA_POD=$(kubectl get pods -n nxr-infrastructure -l app.kubernetes.io/name=kafka -o jsonpath='{.items[0].metadata.name}')
BOOTSTRAP_SERVER="localhost:9092"

# Function to create topic if it doesn't exist
create_topic() {
    local topic=$1
    local partitions=${2:-3}
    local replication_factor=${3:-3}
    
    echo "Creating topic: $topic (partitions: $partitions, replication: $replication_factor)"
    
    kubectl exec -n nxr-infrastructure "$KAFKA_POD" -- \
        kafka-topics.sh \
        --create \
        --topic "$topic" \
        --bootstrap-server "$BOOTSTRAP_SERVER" \
        --partitions "$partitions" \
        --replication-factor "$replication_factor" \
        --if-not-exists || true
}

# Base topics for Nxr
echo "Creating base topics..."

# Device events
create_topic "nxr.device.created" 3 3
create_topic "nxr.device.updated" 3 3
create_topic "nxr.device.deleted" 3 3
create_topic "nxr.device.status-changed" 3 3

# Plugin events
create_topic "nxr.plugin.created" 3 3
create_topic "nxr.plugin.updated" 3 3
create_topic "nxr.plugin.deleted" 3 3

# Execution events
create_topic "nxr.execution.started" 3 3
create_topic "nxr.execution.completed" 3 3
create_topic "nxr.execution.failed" 3 3

# Network events
create_topic "nxr.network.created" 3 3
create_topic "nxr.network.updated" 3 3
create_topic "nxr.network.deleted" 3 3

# DNS events
create_topic "nxr.dns.created" 3 3
create_topic "nxr.dns.updated" 3 3
create_topic "nxr.dns.deleted" 3 3

# Fleet events
create_topic "nxr.fleet.created" 3 3
create_topic "nxr.fleet.updated" 3 3
create_topic "nxr.fleet.deleted" 3 3

# WAMP events
create_topic "nxr.wamp.connected" 3 3
create_topic "nxr.wamp.disconnected" 3 3
create_topic "nxr.wamp.message" 3 3

# System events
create_topic "nxr.system.health" 3 3
create_topic "nxr.system.metrics" 3 3

# Dead letter queue
create_topic "nxr.dlq" 6 3

echo ""
echo "✅ Base Kafka topics created!"
echo ""
echo "📋 List all topics:"
kubectl exec -n nxr-infrastructure "$KAFKA_POD" -- \
    kafka-topics.sh --list --bootstrap-server "$BOOTSTRAP_SERVER"

