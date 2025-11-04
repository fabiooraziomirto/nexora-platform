#!/bin/bash
# Script to create base Kafka topics

set -e

echo "📝 Creating base Kafka topics for Stack4Things v2.0"

# Check if Kafka is running
if ! kubectl get pods -n stack4things-infrastructure -l app.kubernetes.io/name=kafka | grep -q Running; then
    echo "❌ Kafka pods are not running. Please wait for Kafka to be ready."
    exit 1
fi

KAFKA_POD=$(kubectl get pods -n stack4things-infrastructure -l app.kubernetes.io/name=kafka -o jsonpath='{.items[0].metadata.name}')
BOOTSTRAP_SERVER="localhost:9092"

# Function to create topic if it doesn't exist
create_topic() {
    local topic=$1
    local partitions=${2:-3}
    local replication_factor=${3:-3}
    
    echo "Creating topic: $topic (partitions: $partitions, replication: $replication_factor)"
    
    kubectl exec -n stack4things-infrastructure "$KAFKA_POD" -- \
        kafka-topics.sh \
        --create \
        --topic "$topic" \
        --bootstrap-server "$BOOTSTRAP_SERVER" \
        --partitions "$partitions" \
        --replication-factor "$replication_factor" \
        --if-not-exists || true
}

# Base topics for Stack4Things
echo "Creating base topics..."

# Device events
create_topic "stack4things.device.created" 3 3
create_topic "stack4things.device.updated" 3 3
create_topic "stack4things.device.deleted" 3 3
create_topic "stack4things.device.status-changed" 3 3

# Plugin events
create_topic "stack4things.plugin.created" 3 3
create_topic "stack4things.plugin.updated" 3 3
create_topic "stack4things.plugin.deleted" 3 3

# Execution events
create_topic "stack4things.execution.started" 3 3
create_topic "stack4things.execution.completed" 3 3
create_topic "stack4things.execution.failed" 3 3

# Network events
create_topic "stack4things.network.created" 3 3
create_topic "stack4things.network.updated" 3 3
create_topic "stack4things.network.deleted" 3 3

# DNS events
create_topic "stack4things.dns.created" 3 3
create_topic "stack4things.dns.updated" 3 3
create_topic "stack4things.dns.deleted" 3 3

# Fleet events
create_topic "stack4things.fleet.created" 3 3
create_topic "stack4things.fleet.updated" 3 3
create_topic "stack4things.fleet.deleted" 3 3

# WAMP events
create_topic "stack4things.wamp.connected" 3 3
create_topic "stack4things.wamp.disconnected" 3 3
create_topic "stack4things.wamp.message" 3 3

# System events
create_topic "stack4things.system.health" 3 3
create_topic "stack4things.system.metrics" 3 3

# Dead letter queue
create_topic "stack4things.dlq" 6 3

echo ""
echo "✅ Base Kafka topics created!"
echo ""
echo "📋 List all topics:"
kubectl exec -n stack4things-infrastructure "$KAFKA_POD" -- \
    kafka-topics.sh --list --bootstrap-server "$BOOTSTRAP_SERVER"

