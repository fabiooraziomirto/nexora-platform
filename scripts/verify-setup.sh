#!/bin/bash
# Setup verification script for Stack4Things v2.0

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

echo "🔍 Verifying Stack4Things v2.0 Setup"
echo "====================================="
echo ""

# Check if we're in the right directory
if [ ! -f "$PROJECT_ROOT/README.md" ]; then
    echo "❌ Error: Not in Stack4Things_v2.0 directory"
    exit 1
fi

echo "✅ Project root: $PROJECT_ROOT"
echo ""

# Check required tools
echo "Checking required tools..."
REQUIRED_TOOLS=("python3" "bash")
OPTIONAL_TOOLS=("poetry" "docker" "kubectl" "yamllint")

for tool in "${REQUIRED_TOOLS[@]}"; do
    if command -v "$tool" &> /dev/null; then
        VERSION=$($tool --version 2>&1 | head -1)
        echo "✅ $tool: $VERSION"
    else
        echo "❌ $tool: NOT FOUND (required)"
        exit 1
    fi
done

for tool in "${OPTIONAL_TOOLS[@]}"; do
    if command -v "$tool" &> /dev/null; then
        VERSION=$($tool --version 2>&1 | head -1)
        echo "✅ $tool: $VERSION"
    else
        echo "⚠️  $tool: NOT FOUND (optional)"
    fi
done
echo ""

# Check Python version
echo "Checking Python version..."
PYTHON_VERSION=$(python3 --version 2>&1 | awk '{print $2}')
if python3 -c "import sys; exit(0 if sys.version_info >= (3, 11) else 1)" 2>/dev/null; then
    echo "✅ Python $PYTHON_VERSION (>= 3.11)"
else
    echo "❌ Python $PYTHON_VERSION (< 3.11 required)"
    exit 1
fi
echo ""

# Check directory structure
echo "Checking directory structure..."
REQUIRED_DIRS=(
    "libraries/common"
    "libraries/sdk"
    "services/device-service"
    "infrastructure/kubernetes"
    "scripts/kubernetes"
    "docs/deployment"
)

for dir in "${REQUIRED_DIRS[@]}"; do
    if [ -d "$PROJECT_ROOT/$dir" ]; then
        echo "✅ Directory exists: $dir"
    else
        echo "❌ Directory missing: $dir"
        exit 1
    fi
done
echo ""

# Check critical files
echo "Checking critical files..."
CRITICAL_FILES=(
    "README.md"
    "TODO_LIST.md"
    "pyproject.toml"
    "libraries/common/pyproject.toml"
    "libraries/common/src/common/__init__.py"
    "libraries/sdk/pyproject.toml"
    "libraries/sdk/src/sdk/__init__.py"
)

for file in "${CRITICAL_FILES[@]}"; do
    if [ -f "$PROJECT_ROOT/$file" ]; then
        echo "✅ File exists: $file"
    else
        echo "❌ File missing: $file"
        exit 1
    fi
done
echo ""

# Check Python syntax
echo "Checking Python syntax..."
PYTHON_FILES=$(find "$PROJECT_ROOT/libraries" "$PROJECT_ROOT/services" -name "*.py" -type f 2>/dev/null | head -10)
ERRORS=0

for file in $PYTHON_FILES; do
    if python3 -m py_compile "$file" 2>/dev/null; then
        echo "✅ Syntax OK: $(basename $file)"
    else
        echo "❌ Syntax error: $file"
        ((ERRORS++))
    fi
done

if [ $ERRORS -gt 0 ]; then
    echo "❌ Found $ERRORS syntax errors"
    exit 1
fi
echo ""

echo "✅ Setup verification complete!"
echo ""
echo "Next steps:"
echo "  1. Run: ./scripts/test-all.sh"
echo "  2. Run: ./scripts/setup-dev.sh"
echo "  3. Run: poetry install (in libraries/common and libraries/sdk)"

