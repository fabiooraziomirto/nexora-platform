#!/bin/bash
# Quick import test for libraries

set -e

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

echo "🧪 Testing Library Imports"
echo "=========================="
echo ""

# Test common library
echo "Testing common library..."
cd "$PROJECT_ROOT/libraries/common"

PYTHONPATH="$PROJECT_ROOT/libraries/common/src:$PYTHONPATH" python3 << 'EOF'
try:
    # Test basic imports
    from common.config import settings
    print("✅ Settings imported")
    
    from common.database import Base, get_db_session
    print("✅ Database utilities imported")
    
    from common.events import EventBus, EventBusType
    print("✅ Event bus imported")
    
    from common.cache import Cache, get_cache
    print("✅ Cache imported")
    
    from common.logging import setup_logging, get_logger
    print("✅ Logging imported")
    
    from common.errors import NotFoundError, ValidationError
    print("✅ Error handling imported")
    
    from common.health import HealthChecker, HealthStatus
    print("✅ Health checks imported")
    
    from common.metrics import Metrics, get_metrics
    print("✅ Metrics imported")
    
    print("\n✅ All common library imports successful!")
except ImportError as e:
    print(f"❌ Import error: {e}")
    import traceback
    traceback.print_exc()
    exit(1)
EOF

if [ $? -eq 0 ]; then
    echo "✅ Common library imports: PASS"
else
    echo "❌ Common library imports: FAIL"
    exit 1
fi
echo ""

# Test SDK library
echo "Testing SDK library..."
cd "$PROJECT_ROOT/libraries/sdk"

# Check if dependencies are installed
if ! python3 -c "import httpx" 2>/dev/null; then
    echo "⚠️  Dependencies not installed. Installing..."
    if command -v pip3 &> /dev/null; then
        pip3 install -q httpx pydantic pydantic-settings grpcio protobuf || true
    else
        echo "❌ pip3 not found. Please install dependencies first."
        echo "   cd libraries/sdk && poetry install"
        exit 1
    fi
fi

PYTHONPATH="$PROJECT_ROOT/libraries/sdk/src:$PYTHONPATH" python3 << 'EOF'
try:
    # Test basic imports
    from sdk import NxrClient
    print("✅ NxrClient imported")
    
    from sdk import NxrGRPCClient
    print("✅ NxrGRPCClient imported")
    
    from sdk import Device, DeviceStatus, DeviceCreate
    print("✅ Device types imported")
    
    from sdk import Fleet, FleetCreate
    print("✅ Fleet types imported")
    
    from sdk import Network, NetworkCreate
    print("✅ Network types imported")
    
    from sdk import Execution, ExecutionStatus, ExecutionCreate
    print("✅ Execution types imported")
    
    from sdk import PaginatedResponse
    print("✅ PaginatedResponse imported")
    
    print("\n✅ All SDK library imports successful!")
except ImportError as e:
    print(f"❌ Import error: {e}")
    import traceback
    traceback.print_exc()
    exit(1)
EOF

if [ $? -eq 0 ]; then
    echo "✅ SDK library imports: PASS"
else
    echo "❌ SDK library imports: FAIL"
    exit 1
fi
echo ""

echo "✅ All library imports successful!"

