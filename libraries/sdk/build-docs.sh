# Build script for SDK documentation

#!/bin/bash
set -e

echo "📚 Building SDK documentation..."

# Build Sphinx docs
if [ -d "docs" ]; then
    echo "Building Sphinx documentation..."
    cd docs
    sphinx-build -b html . _build/html
    cd ..
fi

# Build MkDocs docs
if [ -f "mkdocs.yml" ]; then
    echo "Building MkDocs documentation..."
    mkdocs build
fi

echo "✅ Documentation built successfully!"

