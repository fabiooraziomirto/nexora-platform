#!/bin/bash
# Reproducibility test script

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

echo "🔄 Testing Reproducibility"
echo "=========================="
echo ""

# Check if all required files are present
echo "1. Checking required files..."
REQUIRED_FILES=(
    "README.md"
    "pyproject.toml"
    "libraries/common/pyproject.toml"
    "libraries/sdk/pyproject.toml"
    "scripts/setup-dev.sh"
    "scripts/verify-setup.sh"
    "scripts/test-all.sh"
    "scripts/test-imports.sh"
)

MISSING_FILES=0
for file in "${REQUIRED_FILES[@]}"; do
    if [ ! -f "$PROJECT_ROOT/$file" ]; then
        echo "❌ Missing: $file"
        ((MISSING_FILES++))
    fi
done

if [ $MISSING_FILES -eq 0 ]; then
    echo "✅ All required files present"
else
    echo "❌ Missing $MISSING_FILES required files"
    exit 1
fi
echo ""

# Check if scripts are executable
echo "2. Checking script permissions..."
SCRIPTS=(
    "scripts/setup-dev.sh"
    "scripts/verify-setup.sh"
    "scripts/test-all.sh"
    "scripts/test-imports.sh"
)

for script in "${SCRIPTS[@]}"; do
    if [ -x "$PROJECT_ROOT/$script" ]; then
        echo "✅ Executable: $script"
    else
        echo "⚠️  Not executable: $script (making executable...)"
        chmod +x "$PROJECT_ROOT/$script"
    fi
done
echo ""

# Check Poetry lock files
echo "3. Checking Poetry configuration..."
if command -v poetry &> /dev/null; then
    cd "$PROJECT_ROOT/libraries/common"
    if [ -f "pyproject.toml" ]; then
        echo "✅ Common library pyproject.toml exists"
        poetry check 2>/dev/null && echo "✅ Common library pyproject.toml is valid" || echo "⚠️  Common library pyproject.toml validation failed"
    fi
    
    cd "$PROJECT_ROOT/libraries/sdk"
    if [ -f "pyproject.toml" ]; then
        echo "✅ SDK library pyproject.toml exists"
        poetry check 2>/dev/null && echo "✅ SDK library pyproject.toml is valid" || echo "⚠️  SDK library pyproject.toml validation failed"
    fi
else
    echo "⚠️  Poetry not installed (optional for reproducibility)"
fi
echo ""

# Test import reproducibility
echo "4. Testing import reproducibility..."
if [ -f "$PROJECT_ROOT/scripts/test-imports.sh" ]; then
    bash "$PROJECT_ROOT/scripts/test-imports.sh"
    if [ $? -eq 0 ]; then
        echo "✅ Imports are reproducible"
    else
        echo "❌ Import reproducibility test failed"
        exit 1
    fi
else
    echo "⚠️  test-imports.sh not found"
fi
echo ""

echo "✅ Reproducibility check complete!"
echo ""
echo "To reproduce this setup:"
echo "  1. Clone the repository"
echo "  2. Run: ./scripts/verify-setup.sh"
echo "  3. Run: ./scripts/setup-dev.sh"
echo "  4. Run: ./scripts/test-all.sh"

