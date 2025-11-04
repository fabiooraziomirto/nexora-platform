#!/bin/bash
# Script to create Python virtual environment with Poetry

set -e

echo "🐍 Setting up Python virtual environment..."

# Check if Poetry is installed
if ! command -v poetry &> /dev/null; then
    echo "📦 Installing Poetry..."
    curl -sSL https://install.python-poetry.org | python3 -
    export PATH="$HOME/.local/bin:$PATH"
fi

# Create virtual environment in project root
echo "📦 Creating virtual environment..."
poetry config virtualenvs.in-project true
poetry env use python3.11

# Install dependencies
echo "📦 Installing dependencies..."
poetry install

# Activate virtual environment info
echo "✅ Virtual environment created!"
echo ""
echo "To activate the virtual environment:"
echo "  poetry shell"
echo ""
echo "Or run commands with:"
echo "  poetry run <command>"

