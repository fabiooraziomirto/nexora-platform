# Multi-Architecture Support

Stack4Things v2.0 è completamente compatibile con processori **ARM64** (oltre che AMD64).

## Architetture Supportate

- ✅ **amd64** (x86_64): Intel/AMD processors
- ✅ **arm64** (aarch64): ARM processors (Apple Silicon, AWS Graviton, Raspberry Pi 4+, etc.)

## Build Multi-Architettura

### Docker Buildx

```bash
# Setup buildx
docker buildx create --use --name multiarch

# Build per entrambe le architetture
docker buildx build \
  --platform linux/amd64,linux/arm64 \
  -t stack4things/device-service:latest \
  --push \
  .
```

### CI/CD

Le pipeline CI/CD costruiscono automaticamente immagini per entrambe le architetture:
- **GitHub Actions**: Build multi-arch automatico
- **GitLab CI**: Build multi-arch con QEMU

## Deployment

### Kubernetes

I pod possono essere schedulati su nodi AMD64 o ARM64:

```yaml
spec:
  affinity:
    nodeAffinity:
      preferredDuringSchedulingIgnoredDuringExecution:
        - weight: 100
          preference:
            matchExpressions:
              - key: kubernetes.io/arch
                operator: In
                values: ["amd64", "arm64"]
```

## Compatibilità

### Base Images

Tutte le immagini base supportano ARM64:
- `python:3.11-slim` ✅
- `mysql:8.0` ✅
- `redis:7-alpine` ✅
- `nginx:alpine` ✅

### Dependencies

Tutte le dipendenze Python sono compatibili ARM64.

## Testing

Test su ARM64 vengono eseguiti automaticamente nella CI/CD pipeline.

## Vantaggi ARM64

- **Efficienza energetica**: Consumo energetico inferiore
- **Costo**: Istanze ARM spesso più economiche (AWS Graviton)
- **Performance**: Performance competitive per molti workload

