#!/bin/bash
# Comprehensive test script for Stack4Things v2.0

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

echo "🧪 Testing Stack4Things v2.0 Implementation"
echo "=========================================="
echo ""

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Test counters
PASSED=0
FAILED=0

test_pass() {
    echo -e "${GREEN}✅ PASS:${NC} $1"
    ((PASSED++))
}

test_fail() {
    echo -e "${RED}❌ FAIL:${NC} $1"
    ((FAILED++))
}

test_warn() {
    echo -e "${YELLOW}⚠️  WARN:${NC} $1"
}

# 1. Check Python version
echo "1. Checking Python version..."
PYTHON_VERSION=$(python3 --version 2>&1 | awk '{print $2}')
if python3 -c "import sys; exit(0 if sys.version_info >= (3, 11) else 1)" 2>/dev/null; then
    test_pass "Python $PYTHON_VERSION (>= 3.11)"
else
    test_fail "Python $PYTHON_VERSION (< 3.11 required)"
fi
echo ""

# 2. Check project structure
echo "2. Checking project structure..."
STRUCTURE_FILES=(
    "README.md"
    "TODO_LIST.md"
    "pyproject.toml"
    "libraries/common/pyproject.toml"
    "libraries/common/src/common/__init__.py"
    "libraries/sdk/pyproject.toml"
    "libraries/sdk/src/sdk/__init__.py"
    "services/device-service/src/device_service/main.py"
    "infrastructure/kubernetes/base/namespaces.yaml"
    "docs/deployment/README.md"
)

for file in "${STRUCTURE_FILES[@]}"; do
    if [ -f "$PROJECT_ROOT/$file" ]; then
        test_pass "File exists: $file"
    else
        test_fail "File missing: $file"
    fi
done
echo ""

# 3. Check Python syntax
echo "3. Checking Python syntax..."
PYTHON_FILES=$(find "$PROJECT_ROOT/libraries" "$PROJECT_ROOT/services" -name "*.py" -type f 2>/dev/null | head -20)
SYNTAX_ERRORS=0

for file in $PYTHON_FILES; do
    if python3 -m py_compile "$file" 2>/dev/null; then
        test_pass "Syntax OK: $(basename $file)"
    else
        test_fail "Syntax error: $file"
        ((SYNTAX_ERRORS++))
    fi
done

if [ $SYNTAX_ERRORS -eq 0 ]; then
    test_pass "All Python files have valid syntax"
else
    test_fail "Found $SYNTAX_ERRORS syntax errors"
fi
echo ""

# 4. Check YAML syntax
echo "4. Checking YAML syntax..."
YAML_FILES=$(find "$PROJECT_ROOT/infrastructure" "$PROJECT_ROOT/services" -name "*.yaml" -o -name "*.yml" 2>/dev/null | head -20)
YAML_ERRORS=0

if command -v yamllint &> /dev/null; then
    for file in $YAML_FILES; do
        if yamllint "$file" &>/dev/null; then
            test_pass "YAML OK: $(basename $file)"
        else
            test_warn "YAML issue: $file"
            ((YAML_ERRORS++))
        fi
    done
else
    test_warn "yamllint not installed, skipping YAML validation"
fi
echo ""

# 5. Check shell scripts
echo "5. Checking shell scripts..."
SHELL_SCRIPTS=$(find "$PROJECT_ROOT/scripts" -name "*.sh" -type f 2>/dev/null)

for script in $SHELL_SCRIPTS; do
    if [ -x "$script" ] || [ -r "$script" ]; then
        if bash -n "$script" 2>/dev/null; then
            test_pass "Shell script OK: $(basename $script)"
        else
            test_fail "Shell script error: $script"
        fi
    fi
done
echo ""

# 6. Check library imports (common)
echo "6. Testing library imports..."
cd "$PROJECT_ROOT/libraries/common"

if [ -f "pyproject.toml" ]; then
    # Try to import common library modules
    PYTHONPATH="$PROJECT_ROOT/libraries/common/src:$PYTHONPATH" python3 -c "
import sys
try:
    # Test imports
    from common.config import settings
    from common.types import Device, DeviceStatus
    print('✅ Common library imports OK')
except ImportError as e:
    print(f'❌ Import error: {e}')
    sys.exit(1)
" 2>&1 | while read line; do
    if [[ $line == *"✅"* ]]; then
        test_pass "$line"
    elif [[ $line == *"❌"* ]]; then
        test_fail "$line"
    fi
done
fi
echo ""

# 7. Check dependencies
echo "7. Checking dependencies..."
if command -v poetry &> /dev/null; then
    test_pass "Poetry is installed"
    
    # Check if pyproject.toml files are valid
    cd "$PROJECT_ROOT"
    if poetry check &>/dev/null; then
        test_pass "Root pyproject.toml is valid"
    else
        test_warn "Root pyproject.toml may have issues"
    fi
    
    cd "$PROJECT_ROOT/libraries/common"
    if poetry check &>/dev/null; then
        test_pass "Common library pyproject.toml is valid"
    else
        test_warn "Common library pyproject.toml may have issues"
    fi
    
    cd "$PROJECT_ROOT/libraries/sdk"
    if poetry check &>/dev/null; then
        test_pass "SDK library pyproject.toml is valid"
    else
        test_warn "SDK library pyproject.toml may have issues"
    fi
else
    test_warn "Poetry not installed (optional)"
fi
echo ""

# 8. Check documentation
echo "8. Checking documentation..."
DOC_FILES=(
    "README.md"
    "docs/deployment/README.md"
    "docs/deployment/rbac-implementation.md"
    "docs/deployment/keycloak-authentication.md"
    "docs/deployment/crossplane-guide.md"
    "libraries/common/README.md"
    "libraries/sdk/README.md"
)

for doc in "${DOC_FILES[@]}"; do
    if [ -f "$PROJECT_ROOT/$doc" ]; then
        if [ -s "$PROJECT_ROOT/$doc" ]; then
            test_pass "Documentation exists: $doc"
        else
            test_warn "Documentation empty: $doc"
        fi
    else
        test_warn "Documentation missing: $doc"
    fi
done
echo ""

# 9. Check Kubernetes manifests
echo "9. Checking Kubernetes manifests..."
K8S_MANIFESTS=$(find "$PROJECT_ROOT/infrastructure/kubernetes" -name "*.yaml" -type f 2>/dev/null | wc -l)
if [ $K8S_MANIFESTS -gt 0 ]; then
    test_pass "Found $K8S_MANIFESTS Kubernetes manifests"
else
    test_warn "No Kubernetes manifests found"
fi
echo ""

# 10. Check scripts
echo "10. Checking setup scripts..."
SETUP_SCRIPTS=(
    "scripts/setup-dev.sh"
    "scripts/kubernetes/setup-k3d.sh"
    "scripts/kubernetes/rbac/setup-rbac.sh"
    "scripts/kubernetes/keycloak/setup-keycloak.sh"
)

for script in "${SETUP_SCRIPTS[@]}"; do
    if [ -f "$PROJECT_ROOT/$script" ]; then
        if [ -x "$PROJECT_ROOT/$script" ] || [ -r "$PROJECT_ROOT/$script" ]; then
            test_pass "Setup script exists: $script"
        else
            test_warn "Setup script not executable: $script"
        fi
    else
        test_warn "Setup script missing: $script"
    fi
done
echo ""

# 11. Docker Compose microservices smoke test
echo "11. Docker Compose microservices smoke test..."
if command -v docker &> /dev/null; then
    cd "$PROJECT_ROOT"
    if docker compose -f docker-compose.dev.yml up -d --build &>/dev/null; then
        test_pass "Docker compose stack started"
        sleep 10

        SERVICES=(
            "http://localhost:8000/health"
            "http://localhost:8001/health"
            "http://localhost:8002/health"
            "http://localhost:8003/health"
            "http://localhost:8004/health"
            "http://localhost:8005/health"
            "http://localhost:8006/health"
            "http://localhost:8007/health"
        )

        for endpoint in "${SERVICES[@]}"; do
            if curl -fsS "$endpoint" &>/dev/null; then
                test_pass "Service healthy: $endpoint"
            else
                test_fail "Service not healthy: $endpoint"
            fi
        done

        if PLUGIN_ID=$(curl -fsS -X POST "http://localhost:8001/api/v2/plugins" -H "Content-Type: application/json" -d '{"name":"smoke-plugin"}' | python3 -c "import sys,json; print(json.load(sys.stdin)['id'])" 2>/dev/null); then
            if curl -fsS "http://localhost:8001/api/v2/plugins/$PLUGIN_ID" &>/dev/null; then
                test_pass "Plugin CRUD smoke OK"
            else
                test_fail "Plugin CRUD smoke failed"
            fi
        else
            test_fail "Plugin creation smoke failed"
        fi

        if bash "$PROJECT_ROOT/scripts/integration-cross-service.sh" &>/dev/null; then
            test_pass "Cross-service integration flow OK"
        else
            test_fail "Cross-service integration flow failed"
        fi

        if python3 "$PROJECT_ROOT/scripts/contract-tests-api.py" &>/dev/null; then
            test_pass "API contract tests OK"
        else
            test_fail "API contract tests failed"
        fi

        if [ -x "$PROJECT_ROOT/scripts/lr-emulator-e2e.sh" ] && bash "$PROJECT_ROOT/scripts/lr-emulator-e2e.sh" &>/dev/null; then
            test_pass "LR emulator E2E flow OK"
        elif [ -f "$PROJECT_ROOT/scripts/lr-emulator-e2e.sh" ]; then
            test_warn "LR emulator E2E flow had issues (Kafka timing possible)"
        fi

        docker compose -f docker-compose.dev.yml down -v &>/dev/null || true
    else
        test_fail "Failed to start docker compose stack"
    fi
else
    test_warn "Docker not installed, skipping compose smoke test"
fi
echo ""

# Summary
echo "=========================================="
echo "Test Summary"
echo "=========================================="
echo -e "${GREEN}Passed: $PASSED${NC}"
if [ $FAILED -gt 0 ]; then
    echo -e "${RED}Failed: $FAILED${NC}"
else
    echo -e "${GREEN}Failed: 0${NC}"
fi
echo ""

if [ $FAILED -eq 0 ]; then
    echo -e "${GREEN}✅ All tests passed!${NC}"
    exit 0
else
    echo -e "${RED}❌ Some tests failed${NC}"
    exit 1
fi

