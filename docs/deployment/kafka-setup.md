# Kafka Cluster Setup Guide

## Overview

Stack4Things v2.0 uses Apache Kafka for event-driven architecture and message streaming.

## Architecture

```
┌─────────────────────────────────────────┐
│         Application Services            │
│        (Producers/Consumers)           │
└──────────────┬──────────────────────────┘
               │
┌──────────────▼──────────────────────────┐
│         Kafka Brokers (3)                │
│  - kafka-0:9092                         │
│  - kafka-1:9092                         │
│  - kafka-2:9092                         │
└──────────────┬──────────────────────────┘
               │
┌──────────────▼──────────────────────────┐
│      Zookeeper Ensemble (3)             │
│  - zookeeper-0:2181                    │
│  - zookeeper-1:2181                    │
│  - zookeeper-2:2181                    │
└─────────────────────────────────────────┘
```

## Quick Setup

```bash
# Setup Kafka Cluster
./scripts/kubernetes/kafka/setup-kafka.sh

# Create base topics
./scripts/kubernetes/kafka/create-topics.sh

# Or setup everything
./scripts/kubernetes/kafka/setup-all.sh
```

## Components

### 1. Kafka Brokers

- **Replicas**: 3 Kafka brokers
- **Persistence**: Persistent volumes (20Gi each)
- **Replication Factor**: 3 (for HA)

### 2. Zookeeper Ensemble

- **Replicas**: 3 Zookeeper nodes
- **Persistence**: Persistent volumes (10Gi each)
- **Function**: Coordination and metadata management

## Connection Strings

### Bootstrap Servers

```
kafka.stack4things-infrastructure.svc.cluster.local:9092
```

### Individual Brokers

```
kafka-0.stack4things-infrastructure.svc.cluster.local:9092
kafka-1.stack4things-infrastructure.svc.cluster.local:9092
kafka-2.stack4things-infrastructure.svc.cluster.local:9092
```

### Zookeeper

```
kafka-zookeeper.stack4things-infrastructure.svc.cluster.local:2181
```

## Base Topics

### Device Events

- `stack4things.device.created` - Device created event
- `stack4things.device.updated` - Device updated event
- `stack4things.device.deleted` - Device deleted event
- `stack4things.device.status-changed` - Device status changed event

### Plugin Events

- `stack4things.plugin.created` - Plugin created event
- `stack4things.plugin.updated` - Plugin updated event
- `stack4things.plugin.deleted` - Plugin deleted event

### Execution Events

- `stack4things.execution.started` - Execution started event
- `stack4things.execution.completed` - Execution completed event
- `stack4things.execution.failed` - Execution failed event

### Network Events

- `stack4things.network.created` - Network created event
- `stack4things.network.updated` - Network updated event
- `stack4things.network.deleted` - Network deleted event

### DNS Events

- `stack4things.dns.created` - DNS record created event
- `stack4things.dns.updated` - DNS record updated event
- `stack4things.dns.deleted` - DNS record deleted event

### Fleet Events

- `stack4things.fleet.created` - Fleet created event
- `stack4things.fleet.updated` - Fleet updated event
- `stack4things.fleet.deleted` - Fleet deleted event

### WAMP Events

- `stack4things.wamp.connected` - WAMP connection event
- `stack4things.wamp.disconnected` - WAMP disconnection event
- `stack4things.wamp.message` - WAMP message event

### System Events

- `stack4things.system.health` - System health events
- `stack4things.system.metrics` - System metrics events

### Dead Letter Queue

- `stack4things.dlq` - Dead letter queue for failed messages

## Usage Examples

### Producer (Python)

```python
from kafka import KafkaProducer
import json

producer = KafkaProducer(
    bootstrap_servers=['kafka.stack4things-infrastructure.svc.cluster.local:9092'],
    value_serializer=lambda v: json.dumps(v).encode('utf-8')
)

# Publish device created event
event = {
    'device_id': 'device-123',
    'name': 'Device Name',
    'type': 'sensor',
    'timestamp': '2024-01-01T00:00:00Z'
}

producer.send('stack4things.device.created', event)
producer.flush()
```

### Consumer (Python)

```python
from kafka import KafkaConsumer
import json

consumer = KafkaConsumer(
    'stack4things.device.created',
    bootstrap_servers=['kafka.stack4things-infrastructure.svc.cluster.local:9092'],
    value_deserializer=lambda m: json.loads(m.decode('utf-8')),
    group_id='device-service'
)

for message in consumer:
    event = message.value
    print(f"Received event: {event}")
    # Process event
```

### Async Producer (aiokafka)

```python
from aiokafka import AIOKafkaProducer
import asyncio
import json

async def produce():
    producer = AIOKafkaProducer(
        bootstrap_servers='kafka.stack4things-infrastructure.svc.cluster.local:9092',
        value_serializer=lambda v: json.dumps(v).encode('utf-8')
    )
    await producer.start()
    
    try:
        event = {
            'device_id': 'device-123',
            'status': 'online'
        }
        await producer.send_and_wait('stack4things.device.status-changed', event)
    finally:
        await producer.stop()

asyncio.run(produce())
```

## Topic Management

### List Topics

```bash
kubectl exec -it kafka-0 -n stack4things-infrastructure -- \
  kafka-topics.sh --list --bootstrap-server localhost:9092
```

### Create Custom Topic

```bash
kubectl exec -it kafka-0 -n stack4things-infrastructure -- \
  kafka-topics.sh --create \
  --topic my-custom-topic \
  --bootstrap-server localhost:9092 \
  --partitions 3 \
  --replication-factor 3
```

### Describe Topic

```bash
kubectl exec -it kafka-0 -n stack4things-infrastructure -- \
  kafka-topics.sh --describe \
  --topic stack4things.device.created \
  --bootstrap-server localhost:9092
```

### Delete Topic

```bash
kubectl exec -it kafka-0 -n stack4things-infrastructure -- \
  kafka-topics.sh --delete \
  --topic my-custom-topic \
  --bootstrap-server localhost:9092
```

## Monitoring

### Metrics

Kafka metrics are exposed via Prometheus:
- Message rate (produce/consume)
- Bytes in/out
- Request rate
- Partition count
- Consumer lag

### ServiceMonitor

ServiceMonitors are configured in `infrastructure/kubernetes/kafka/monitoring.yaml`

## Troubleshooting

### Connection Issues

```bash
# Check Kafka pods
kubectl get pods -n stack4things-infrastructure | grep kafka

# Check Kafka logs
kubectl logs -n stack4things-infrastructure kafka-0

# Test connection
kubectl exec -it kafka-0 -n stack4things-infrastructure -- \
  kafka-topics.sh --list --bootstrap-server localhost:9092
```

### Zookeeper Issues

```bash
# Check Zookeeper pods
kubectl get pods -n stack4things-infrastructure | grep zookeeper

# Check Zookeeper logs
kubectl logs -n stack4things-infrastructure kafka-zookeeper-0

# Test Zookeeper connection
kubectl exec -it kafka-zookeeper-0 -n stack4things-infrastructure -- \
  zkCli.sh -server localhost:2181 ls /
```

### Consumer Lag

```bash
# Check consumer lag
kubectl exec -it kafka-0 -n stack4things-infrastructure -- \
  kafka-consumer-groups.sh \
  --bootstrap-server localhost:9092 \
  --group device-service \
  --describe
```

## Production Considerations

1. **High Availability**: 3 brokers with replication factor 3
2. **Persistence**: Persistent volumes for data durability
3. **Monitoring**: Enable detailed Kafka and Zookeeper monitoring
4. **Retention**: Configure appropriate retention policies per topic
5. **Performance**: Tune based on message volume and latency requirements
6. **Security**: Enable SASL/SSL if needed
7. **Backup**: Regularly backup Kafka data volumes
8. **Scaling**: Scale brokers horizontally based on load

