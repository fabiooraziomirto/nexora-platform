#!/bin/bash
# Setup script for Stack4Things v2.0 development environment

set -e

echo "🚀 Setting up Stack4Things v2.0 Development Environment"

# Check Python version
echo "📋 Checking Python version..."
python_version=$(python3 --version | cut -d' ' -f2 | cut -d'.' -f1,2)
required_version="3.11"

if [ "$(printf '%s\n' "$required_version" "$python_version" | sort -V | head -n1)" != "$required_version" ]; then
    echo "❌ Python 3.11+ is required. Found: $python_version"
    exit 1
fi

echo "✅ Python version: $python_version"

# Check Poetry
echo "📋 Checking Poetry..."
if ! command -v poetry &> /dev/null; then
    echo "📦 Installing Poetry..."
    curl -sSL https://install.python-poetry.org | python3 -
    export PATH="$HOME/.local/bin:$PATH"
else
    echo "✅ Poetry already installed"
fi

# Setup Device Service
echo "📦 Setting up Device Service..."
cd services/device-service
poetry install
cd ../..

# Setup Common Library
echo "📦 Setting up Common Library..."
cd libraries/common
poetry install
cd ../..

# Setup root dependencies
echo "📦 Setting up root dependencies..."
poetry install

# Setup pre-commit hooks
echo "🔧 Setting up pre-commit hooks..."
if command -v pre-commit &> /dev/null; then
    poetry run pre-commit install
    echo "✅ Pre-commit hooks installed"
else
    echo "⚠️  pre-commit not found. Install it with: poetry run pre-commit install"
fi

# Setup git hooks (optional)
echo "🔧 Setting up git hooks..."
if [ -f "scripts/git-hooks-setup.sh" ]; then
    ./scripts/git-hooks-setup.sh
fi

echo "✅ Setup complete!"
echo ""
echo "Next steps:"
echo "1. Copy .env.example to .env and configure:"
echo "   cp services/device-service/.env.example services/device-service/.env"
echo ""
echo "2. Start infrastructure services:"
echo "   docker-compose -f docker-compose.dev.yml up -d"
echo ""
echo "3. Run database migrations:"
echo "   cd services/device-service && poetry run alembic upgrade head"
echo ""
echo "4. Start the service:"
echo "   cd services/device-service && poetry run uvicorn device_service.main:app --reload"
echo ""
echo "5. Run pre-commit checks manually:"
echo "   poetry run pre-commit run --all-files"

