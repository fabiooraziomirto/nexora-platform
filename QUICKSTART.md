# Stack4Things v2.0 - Quick Start Guide

## Prerequisites

- Python 3.11+
- Poetry
- Docker & Docker Compose
- Kubernetes cluster (optional)
- MySQL/MariaDB 10.11+
- Redis
- Kafka

## Setup Development Environment

### 1. Clone Repository

```bash
git clone <repository-url>
cd Stack4Things_v2.0
```

### 2. Setup Device Service

```bash
cd services/device-service
poetry install
cp .env.example .env
# Edit .env with your configuration
```

### 3. Setup Database

```bash
# Create database
mysql -u root -p -e "CREATE DATABASE stack4things CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;"

# Run migrations
cd services/device-service
poetry run alembic upgrade head
```

### 4. Start Infrastructure Services

```bash
# Start MySQL, Redis, Kafka with Docker Compose
docker-compose up -d
```

### 5. Run Device Service

```bash
cd services/device-service
poetry run uvicorn device_service.main:app --reload
```

### 6. Test API

```bash
# Health check
curl http://localhost:8000/health

# Create device
curl -X POST http://localhost:8000/api/v2/devices \
  -H "Content-Type: application/json" \
  -d '{"name": "test-device", "device_type": "raspberry-pi"}'

# List devices
curl http://localhost:8000/api/v2/devices
```

## Running Tests

```bash
cd services/device-service
poetry run pytest
```

## Docker Build

```bash
cd services/device-service
docker build -t stack4things/device-service:latest .
```

## Kubernetes Deployment

```bash
# Apply manifests
kubectl apply -f services/device-service/k8s/

# Check status
kubectl get pods -n stack4things
```

## Next Steps

1. Setup Keycloak authentication
2. Configure API Gateway (Kong)
3. Setup Crossplane for infrastructure provisioning
4. Implement other microservices (Plugin Service, Execution Service, etc.)

