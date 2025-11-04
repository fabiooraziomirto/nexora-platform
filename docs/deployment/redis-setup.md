# Redis Cluster Setup Guide

## Overview

Stack4Things v2.0 uses Redis Cluster with High Availability (HA) configuration, including Sentinel for failover.

## Architecture

```
┌─────────────────────────────────────────┐
│         Application Services            │
└──────────────┬──────────────────────────┘
               │
        ┌──────┴──────┐
        │             │
┌───────▼──────┐  ┌──▼──────────────┐
│   Redis      │  │  Redis Sentinel  │
│   Master     │  │  (3 instances)   │
└───────┬──────┘  └──────────────────┘
        │
┌───────▼──────────┐
│  Redis Replicas  │
│  (3 replicas)     │
└──────────────────┘
```

## Quick Setup

```bash
# Setup Redis Cluster
./scripts/kubernetes/redis/setup-redis.sh
```

## Components

### 1. Redis Master

- **Primary**: Master Redis server
- **Persistence**: RDB + AOF enabled
- **Storage**: Persistent volume (10Gi)

### 2. Redis Replicas

- **Replicas**: 3 read replicas
- **Persistence**: RDB + AOF enabled
- **Storage**: Persistent volume (10Gi each)

### 3. Redis Sentinel

- **Instances**: 3 Sentinel instances
- **Quorum**: 2 (for failover)
- **Function**: Automatic failover and monitoring

## Connection Strings

### Direct Redis Connection

```python
import redis

# Direct connection to master
r = redis.Redis(
    host='redis-master.stack4things-infrastructure.svc.cluster.local',
    port=6379,
    password='redispassword',
    decode_responses=True
)
```

### Sentinel Connection (Recommended for HA)

```python
from redis.sentinel import Sentinel

sentinel = Sentinel([
    ('redis-sentinel-0.stack4things-infrastructure.svc.cluster.local', 26379),
    ('redis-sentinel-1.stack4things-infrastructure.svc.cluster.local', 26379),
    ('redis-sentinel-2.stack4things-infrastructure.svc.cluster.local', 26379),
], socket_timeout=0.1)

# Get master connection
master = sentinel.master_for('mymaster', password='redispassword', decode_responses=True)

# Get slave connection
slave = sentinel.slave_for('mymaster', password='redispassword', decode_responses=True)
```

### Connection URL

```
redis://:redispassword@redis-master.stack4things-infrastructure.svc.cluster.local:6379
```

## Persistence

### RDB (Redis Database Backup)

- **Snapshots**: Automatic snapshots based on time and key changes
- **Configuration**: 
  - Save after 900s if at least 1 key changed
  - Save after 300s if at least 10 keys changed
  - Save after 60s if at least 10000 keys changed

### AOF (Append Only File)

- **Enabled**: Yes
- **Sync**: Every second (`appendfsync everysec`)
- **Auto-rewrite**: Enabled (100% growth, 64MB min size)

## Configuration

### Redis Config

Custom configuration is available in `infrastructure/kubernetes/redis/redis-config.yaml`:

- **Memory**: 4GB max memory
- **Eviction Policy**: `allkeys-lru`
- **Persistence**: RDB + AOF
- **Replication**: Diskless sync disabled

## Monitoring

### Metrics

Redis metrics are exposed via Prometheus:
- Memory usage
- Connected clients
- Commands processed
- Keyspace statistics
- Replication lag

### ServiceMonitor

ServiceMonitor is configured in `infrastructure/kubernetes/redis/redis-config.yaml`

## Usage Examples

### Basic Operations

```python
import redis

r = redis.Redis(
    host='redis-master.stack4things-infrastructure.svc.cluster.local',
    port=6379,
    password='redispassword',
    decode_responses=True
)

# Set value
r.set('key', 'value')

# Get value
value = r.get('key')

# Set with expiration
r.setex('key', 3600, 'value')  # Expires in 1 hour

# Check if key exists
exists = r.exists('key')
```

### Caching

```python
# Cache device data
device_data = {
    'id': 'device-123',
    'name': 'Device Name',
    'status': 'online'
}

r.setex(
    f'device:{device_data["id"]}',
    3600,  # 1 hour TTL
    json.dumps(device_data)
)

# Retrieve cached device
cached = r.get(f'device:{device_data["id"]}')
if cached:
    device = json.loads(cached)
```

### Session Storage

```python
# Store session
session_id = 'session-123'
session_data = {'user_id': 'user-456', 'role': 'admin'}
r.setex(
    f'session:{session_id}',
    1800,  # 30 minutes
    json.dumps(session_data)
)

# Retrieve session
session = r.get(f'session:{session_id}')
if session:
    data = json.loads(session)
```

## Troubleshooting

### Connection Issues

```bash
# Check Redis pods
kubectl get pods -n stack4things-infrastructure | grep redis

# Check Redis logs
kubectl logs -n stack4things-infrastructure redis-master-0

# Test connection
kubectl exec -it redis-master-0 -n stack4things-infrastructure -- \
  redis-cli -a redispassword PING
```

### Sentinel Issues

```bash
# Check Sentinel pods
kubectl get pods -n stack4things-infrastructure | grep sentinel

# Check Sentinel status
kubectl exec -it redis-sentinel-0 -n stack4things-infrastructure -- \
  redis-cli -p 26379 SENTINEL masters
```

### Persistence Issues

```bash
# Check persistence status
kubectl exec -it redis-master-0 -n stack4things-infrastructure -- \
  redis-cli -a redispassword INFO persistence

# Check AOF status
kubectl exec -it redis-master-0 -n stack4things-infrastructure -- \
  redis-cli -a redispassword CONFIG GET appendonly
```

## Production Considerations

1. **High Availability**: Sentinel provides automatic failover
2. **Persistence**: RDB + AOF for data durability
3. **Monitoring**: Enable detailed Redis monitoring
4. **Memory Management**: Configure appropriate maxmemory and eviction policy
5. **Security**: Use strong passwords and enable TLS if needed
6. **Backup**: Regularly backup Redis data volumes
7. **Performance**: Monitor and tune based on workload

