#!/bin/bash
# Install dependencies for testing

set -e

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

echo "📦 Installing Dependencies for Testing"
echo "======================================"
echo ""

# Check if pip is available
if ! command -v pip3 &> /dev/null; then
    echo "❌ pip3 not found. Please install pip first."
    exit 1
fi

# Install common library dependencies
echo "Installing common library dependencies..."
cd "$PROJECT_ROOT/libraries/common"
if [ -f "pyproject.toml" ]; then
    if command -v poetry &> /dev/null; then
        echo "Using Poetry..."
        poetry install --no-interaction || pip3 install -q pydantic pydantic-settings sqlalchemy aiomysql pymysql redis aiokafka structlog prometheus-client fastapi || true
    else
        echo "Using pip..."
        pip3 install -q pydantic pydantic-settings sqlalchemy aiomysql pymysql redis aiokafka structlog prometheus-client fastapi || true
    fi
fi

# Install SDK library dependencies
echo "Installing SDK library dependencies..."
cd "$PROJECT_ROOT/libraries/sdk"
if [ -f "pyproject.toml" ]; then
    if command -v poetry &> /dev/null; then
        echo "Using Poetry..."
        poetry install --no-interaction || pip3 install -q httpx grpcio grpcio-tools protobuf pydantic pydantic-settings || true
    else
        echo "Using pip..."
        pip3 install -q httpx grpcio grpcio-tools protobuf pydantic pydantic-settings || true
    fi
fi

echo ""
echo "✅ Dependencies installed!"
echo ""
echo "Next steps:"
echo "  ./scripts/test-imports.sh"
echo "  ./scripts/test-all.sh"

