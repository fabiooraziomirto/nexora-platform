# Reproducibility Guide

This document ensures that Stack4Things v2.0 can be easily reproduced on any system.

## Prerequisites

### Required Tools

- **Python 3.11+**: Required for all Python code
- **Bash**: Required for setup scripts

### Optional Tools

- **Poetry**: Recommended for dependency management
- **Docker**: Required for containerized services
- **kubectl**: Required for Kubernetes deployment
- **yamllint**: Recommended for YAML validation

## Quick Start

### 1. Clone Repository

```bash
git clone <repository-url>
cd Stack4Things_v2.0
```

### 2. Verify Setup

```bash
./scripts/verify-setup.sh
```

This script checks:
- Python version (>= 3.11)
- Required tools
- Directory structure
- Critical files
- Python syntax

### 3. Setup Development Environment

```bash
./scripts/setup-dev.sh
```

This script:
- Sets up Python virtual environment
- Installs Poetry (if not present)
- Installs dependencies
- Sets up pre-commit hooks

### 4. Test Libraries

```bash
# Test imports
./scripts/test-imports.sh

# Run all tests
./scripts/test-all.sh

# Test reproducibility
./scripts/test-reproducibility.sh
```

## Library Setup

### Common Library

```bash
cd libraries/common
poetry install
```

### SDK Library

```bash
cd libraries/sdk
poetry install
```

## Testing

### Import Tests

Test that all libraries can be imported:

```bash
./scripts/test-imports.sh
```

### Comprehensive Tests

Run all tests:

```bash
./scripts/test-all.sh
```

This tests:
- Python syntax
- YAML syntax
- Shell scripts
- Library imports
- Dependencies
- Documentation

## Reproducibility Checklist

- [ ] Python 3.11+ installed
- [ ] All required files present
- [ ] Scripts are executable
- [ ] Python syntax valid
- [ ] Libraries can be imported
- [ ] Dependencies defined in pyproject.toml
- [ ] Documentation present

## Docker Environment

For consistent environment:

```bash
# Build development image
docker build -t stack4things-dev -f Dockerfile.dev .

# Run tests in container
docker run --rm stack4things-dev ./scripts/test-all.sh
```

## CI/CD Integration

### GitHub Actions

```yaml
- name: Verify Setup
  run: ./scripts/verify-setup.sh

- name: Test Imports
  run: ./scripts/test-imports.sh

- name: Run All Tests
  run: ./scripts/test-all.sh
```

### GitLab CI

```yaml
verify:
  script:
    - ./scripts/verify-setup.sh
    - ./scripts/test-imports.sh
    - ./scripts/test-all.sh
```

## Troubleshooting

### Python Version Issues

If Python version is < 3.11:

```bash
# Install Python 3.11+
# Ubuntu/Debian
sudo apt-get install python3.11

# macOS
brew install python@3.11
```

### Import Errors

If imports fail:

```bash
# Check PYTHONPATH
export PYTHONPATH="$PWD/libraries/common/src:$PYTHONPATH"

# Verify imports
python3 -c "from common.config import settings; print(settings.APP_NAME)"
```

### Permission Issues

If scripts are not executable:

```bash
chmod +x scripts/*.sh
```

## File Structure

```
Stack4Things_v2.0/
├── scripts/
│   ├── verify-setup.sh          # Setup verification
│   ├── test-all.sh              # Comprehensive tests
│   ├── test-imports.sh          # Import tests
│   └── test-reproducibility.sh  # Reproducibility tests
├── libraries/
│   ├── common/                  # Common library
│   └── sdk/                     # SDK library
└── services/                    # Microservices
```

## Version Control

All dependencies are pinned in `pyproject.toml`:

- Common library: `libraries/common/pyproject.toml`
- SDK library: `libraries/sdk/pyproject.toml`

## Environment Variables

No environment variables required for basic setup. Configuration uses defaults from `common.config.settings`.

## Next Steps

After verification:

1. Review `README.md` for project overview
2. Review `TODO_LIST.md` for implementation status
3. Check `docs/deployment/` for deployment guides
4. Review `docs/adr/` for architecture decisions

## Support

For issues:
1. Run `./scripts/verify-setup.sh` to diagnose
2. Check logs in `scripts/` directory
3. Review documentation in `docs/`

