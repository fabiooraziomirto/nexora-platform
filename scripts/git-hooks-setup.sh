#!/bin/bash
# Git hooks setup script

set -e

echo "🔧 Setting up Git hooks..."

# Create hooks directory if it doesn't exist
mkdir -p .git/hooks
mkdir -p scripts/git-hooks

# Pre-commit hook
cat > scripts/git-hooks/pre-commit << 'EOF'
#!/bin/bash
# Pre-commit hook for Nxr v2.0

set -e

echo "Running pre-commit checks..."

# Check for Python syntax errors
if command -v python3 &> /dev/null; then
    echo "Checking Python syntax..."
    find . -name "*.py" -not -path "./.git/*" -not -path "./venv/*" -not -path "./env/*" | while read file; do
        python3 -m py_compile "$file" || exit 1
    done
fi

# Check for large files
echo "Checking for large files..."
if git rev-parse --verify HEAD >/dev/null 2>&1; then
    against=HEAD
else
    against=4b825dc642cb6eb9a060e54bf8d69288fbee4904
fi

# Check files to be committed
git diff --cached --name-only --diff-filter=ACM | while read file; do
    if [ -f "$file" ]; then
        size=$(stat -f%z "$file" 2>/dev/null || stat -c%s "$file" 2>/dev/null || echo "0")
        if [ "$size" -gt 10485760 ]; then  # 10MB
            echo "Error: File $file is larger than 10MB"
            exit 1
        fi
    fi
done

# Check for secrets (basic check)
echo "Checking for potential secrets..."
git diff --cached --name-only | while read file; do
    if [ -f "$file" ]; then
        if grep -q "password.*=.*['\"].*[A-Za-z0-9]{8,}" "$file" 2>/dev/null; then
            echo "Warning: Potential hardcoded password found in $file"
        fi
        if grep -q "api_key.*=.*['\"].*[A-Za-z0-9]{20,}" "$file" 2>/dev/null; then
            echo "Warning: Potential API key found in $file"
        fi
    fi
done

echo "Pre-commit checks passed!"
EOF

chmod +x scripts/git-hooks/pre-commit

# Install hook
if [ -d ".git" ]; then
    cp scripts/git-hooks/pre-commit .git/hooks/pre-commit
    chmod +x .git/hooks/pre-commit
    echo "✅ Git hooks installed successfully"
else
    echo "⚠️  .git directory not found. Run 'git init' first."
fi

