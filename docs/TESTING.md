# Testing Guide

This guide explains how to test Stack4Things v2.0 implementation.

## Test Scripts

### 1. Verify Setup (`scripts/verify-setup.sh`)

Verifies that the environment is correctly configured:

```bash
./scripts/verify-setup.sh
```

**Checks:**
- Python version (>= 3.11)
- Required tools
- Directory structure
- Critical files
- Python syntax

### 2. Test Imports (`scripts/test-imports.sh`)

Tests that all libraries can be imported:

```bash
./scripts/test-imports.sh
```

**Tests:**
- Common library imports
- SDK library imports
- Type definitions

### 3. Comprehensive Tests (`scripts/test-all.sh`)

Runs all tests:

```bash
./scripts/test-all.sh
```

**Tests:**
- Python version
- Project structure
- Python syntax
- YAML syntax
- Shell scripts
- Library imports
- Dependencies
- Documentation
- Kubernetes manifests

### 4. Reproducibility Tests (`scripts/test-reproducibility.sh`)

Tests reproducibility:

```bash
./scripts/test-reproducibility.sh
```

**Checks:**
- Required files
- Script permissions
- Poetry configuration
- Import reproducibility

## Manual Testing

### Test Common Library

```bash
cd libraries/common
PYTHONPATH=src python3 -c "
from common.config import settings
from common.database import Base
from common.events import EventBus
from common.cache import Cache
from common.logging import setup_logging
from common.errors import NotFoundError
from common.health import HealthChecker
from common.metrics import Metrics
print('✅ All imports successful')
"
```

### Test SDK Library

```bash
cd libraries/sdk
PYTHONPATH=src python3 -c "
from sdk import Stack4ThingsClient
from sdk import Device, DeviceStatus
from sdk import Fleet
from sdk import Network
from sdk import Execution
print('✅ All imports successful')
"
```

## Python Syntax Check

```bash
# Check all Python files
find libraries services -name "*.py" -exec python3 -m py_compile {} \;
```

## YAML Validation

```bash
# If yamllint is installed
find infrastructure services -name "*.yaml" -exec yamllint {} \;
```

## Shell Script Validation

```bash
# Check all shell scripts
find scripts -name "*.sh" -exec bash -n {} \;
```

## Expected Results

### verify-setup.sh

```
✅ Project root: /path/to/Stack4Things_v2.0
✅ python3: Python 3.11+
✅ bash: GNU bash
✅ Python 3.11+ (>= 3.11)
✅ All directories exist
✅ All critical files exist
✅ All Python files have valid syntax
✅ Setup verification complete!
```

### test-imports.sh

```
✅ Settings imported
✅ Database utilities imported
✅ Event bus imported
✅ Cache imported
✅ Logging imported
✅ Error handling imported
✅ Health checks imported
✅ Metrics imported
✅ All common library imports successful!
✅ All SDK library imports successful!
```

### test-all.sh

```
✅ Passed: 50+
✅ Failed: 0
✅ All tests passed!
```

## CI/CD Integration

### GitHub Actions

```yaml
name: Tests

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - uses: actions/setup-python@v4
        with:
          python-version: '3.11'
      - name: Verify Setup
        run: ./scripts/verify-setup.sh
      - name: Test Imports
        run: ./scripts/test-imports.sh
      - name: Run All Tests
        run: ./scripts/test-all.sh
```

### GitLab CI

```yaml
test:
  image: python:3.11
  script:
    - ./scripts/verify-setup.sh
    - ./scripts/test-imports.sh
    - ./scripts/test-all.sh
```

## Troubleshooting

### Import Errors

```bash
# Set PYTHONPATH
export PYTHONPATH="$PWD/libraries/common/src:$PYTHONPATH"
export PYTHONPATH="$PWD/libraries/sdk/src:$PYTHONPATH"

# Test import
python3 -c "from common.config import settings"
```

### Syntax Errors

```bash
# Check specific file
python3 -m py_compile path/to/file.py

# Check all files
find . -name "*.py" -exec python3 -m py_compile {} \;
```

### Permission Errors

```bash
# Make scripts executable
chmod +x scripts/*.sh
```

## Test Coverage

Current test coverage:

- ✅ Project structure
- ✅ Python syntax
- ✅ Library imports
- ✅ YAML syntax (optional)
- ✅ Shell scripts
- ✅ Dependencies
- ✅ Documentation

**Note:** Unit tests for individual functions will be added as services are implemented.

## Next Steps

After passing all tests:

1. Review implementation status in `TODO_LIST.md`
2. Check deployment guides in `docs/deployment/`
3. Review architecture decisions in `docs/adr/`
4. Proceed with service implementation

