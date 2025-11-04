#!/bin/bash
# Complete cache and message broker setup script

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../../.." && pwd)"

echo "📦 Setting up Cache & Message Broker infrastructure for Stack4Things v2.0"

# Step 1: Redis Cluster
echo ""
echo "=== Step 1: Installing Redis Cluster ==="
"$SCRIPT_DIR/../redis/setup-redis.sh"

# Step 2: Kafka Cluster
echo ""
echo "=== Step 2: Installing Kafka Cluster ==="
"$SCRIPT_DIR/setup-kafka.sh"

# Summary
echo ""
echo "🎉 Cache & Message Broker setup complete!"
echo ""
echo "📋 Summary:"
echo "  ✅ Redis Cluster installed (HA with Sentinel)"
echo "  ✅ Kafka Cluster installed (3 brokers)"
echo "  ✅ Base Kafka topics created"
echo ""
echo "📝 Redis Connection Info:"
echo "  Host: redis-master.stack4things-infrastructure.svc.cluster.local"
echo "  Port: 6379"
echo "  Sentinel: redis-sentinel.stack4things-infrastructure.svc.cluster.local:26379"
echo ""
echo "📝 Kafka Connection Info:"
echo "  Bootstrap Servers: kafka.stack4things-infrastructure.svc.cluster.local:9092"
echo "  Zookeeper: kafka-zookeeper.stack4things-infrastructure.svc.cluster.local:2181"
echo ""
echo "📝 Next steps:"
echo "  1. Verify Redis:"
echo "     kubectl exec -it redis-master-0 -n stack4things-infrastructure -- redis-cli -a redispassword PING"
echo ""
echo "  2. List Kafka topics:"
echo "     kubectl exec -it kafka-0 -n stack4things-infrastructure -- kafka-topics.sh --list --bootstrap-server localhost:9092"

