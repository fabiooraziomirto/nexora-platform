# Quick Start Guide

## Prerequisites

- Python 3.11+
- Bash
- (Optional) Poetry, Docker, kubectl

## Setup

```bash
# 1. Verify setup
./scripts/verify-setup.sh

# 2. Test imports
./scripts/test-imports.sh

# 3. Run all tests
./scripts/test-all.sh
```

## Verify Everything Works

```bash
# Quick verification
./scripts/verify-setup.sh && ./scripts/test-imports.sh
```

## Troubleshooting

See [REPRODUCIBILITY.md](./REPRODUCIBILITY.md) for detailed troubleshooting.

## Next Steps

- Review [TESTING.md](./TESTING.md) for testing guide
- Review [README.md](../README.md) for project overview
- Review [TODO_LIST.md](../TODO_LIST.md) for implementation status

