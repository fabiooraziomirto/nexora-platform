# Multi-Architecture Build Support

Stack4Things v2.0 supports multi-architecture builds for both **AMD64** (x86_64) and **ARM64** (aarch64) processors.

## Supported Architectures

- **amd64**: Intel/AMD x86_64 processors
- **arm64**: ARM64 processors (Apple Silicon, AWS Graviton, Raspberry Pi 4+, etc.)

## Docker Build

### Single Architecture Build

```bash
# Build for current platform
docker build -t stack4things/device-service:latest .

# Build for specific architecture
docker build --platform linux/amd64 -t stack4things/device-service:latest .
docker build --platform linux/arm64 -t stack4things/device-service:latest .
```

### Multi-Architecture Build

```bash
# Create builder instance
docker buildx create --name multiarch --use

# Build and push for multiple architectures
docker buildx build \
  --platform linux/amd64,linux/arm64 \
  -t stack4things/device-service:latest \
  --push \
  .
```

## CI/CD Multi-Arch Build

### GitHub Actions

The CI/CD pipeline automatically builds for both architectures:

```yaml
- name: Build and push Docker image (multi-arch)
  uses: docker/build-push-action@v5
  with:
    platforms: linux/amd64,linux/arm64
    push: true
```

### GitLab CI

```yaml
build:device-service:
  before_script:
    - docker run --rm --privileged multiarch/qemu-user-static --reset -p yes
    - docker buildx create --use --name multiarch-builder
  script:
    - docker buildx build --platform linux/amd64,linux/arm64 ...
```

## Local Development

### ARM64 Development (Apple Silicon)

```bash
# Run on ARM64 Mac
docker run --platform linux/arm64 stack4things/device-service:latest

# Or build directly
docker build --platform linux/arm64 -t stack4things/device-service:latest .
```

### AMD64 Development

```bash
# Run on AMD64
docker run --platform linux/amd64 stack4things/device-service:latest

# Or build directly
docker build --platform linux/amd64 -t stack4things/device-service:latest .
```

## Kubernetes Deployment

### Node Selectors

For architecture-specific deployments:

```yaml
spec:
  nodeSelector:
    kubernetes.io/arch: amd64
  # or
  nodeSelector:
    kubernetes.io/arch: arm64
```

### Tolerations

Allow pods to run on any architecture:

```yaml
spec:
  tolerations:
    - key: kubernetes.io/arch
      operator: Exists
```

## Base Images

All base images are multi-arch compatible:

- `python:3.11-slim`: Supports amd64 and arm64
- `mysql:8.0`: Supports amd64 and arm64
- `redis:7-alpine`: Supports amd64 and arm64
- `nginx:alpine`: Supports amd64 and arm64

## Testing

### Test on Different Architectures

```bash
# Test on ARM64 using QEMU emulation
docker run --platform linux/arm64 --rm stack4things/device-service:latest pytest

# Test on AMD64
docker run --platform linux/amd64 --rm stack4things/device-service:latest pytest
```

### Verify Architecture

```bash
# Check image architecture
docker inspect stack4things/device-service:latest | jq '.[0].Architecture'

# Check running container architecture
docker exec <container> uname -m
```

## Performance Considerations

### ARM64 Benefits

- **Energy Efficiency**: Lower power consumption
- **Cost**: ARM-based instances often cheaper (AWS Graviton, etc.)
- **Performance**: Competitive performance for many workloads

### AMD64 Benefits

- **Compatibility**: Broader software compatibility
- **Mature Ecosystem**: More tested and optimized

## Production Deployment

### Cloud Providers

- **AWS**: Use Graviton2/Graviton3 instances for ARM64
- **GCP**: Use Tau T2A instances for ARM64
- **Azure**: Use Ampere Altra instances for ARM64

### Hybrid Clusters

Deploy across both architectures:

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: device-service
spec:
  template:
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

## Troubleshooting

### Build Issues

```bash
# Enable buildx
docker buildx create --use

# Inspect platform support
docker buildx inspect
```

### Runtime Issues

```bash
# Check node architecture
kubectl get nodes -o wide

# Check pod architecture
kubectl get pod <pod-name> -o jsonpath='{.spec.nodeSelector}'
```

## References

- [Docker Multi-Platform Builds](https://docs.docker.com/build/building/multi-platform/)
- [Kubernetes Node Architecture](https://kubernetes.io/docs/reference/labels-annotations-taints/#kubernetes-io-arch)
- [ARM64 Support](https://www.arm.com/architecture/armv8)

