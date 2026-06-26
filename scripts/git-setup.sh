#!/bin/bash
# Git setup and initial push script

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

echo "🔧 Nxr v2.0 - Git Setup"
echo "================================="
echo ""

cd "$PROJECT_ROOT"

# Check if git is installed
if ! command -v git &> /dev/null; then
    echo "❌ Git is not installed. Please install git first."
    exit 1
fi

# Initialize git if needed
if [ ! -d ".git" ]; then
    echo "📦 Initializing git repository..."
    git init
    echo "✅ Git repository initialized"
fi

# Configure git user (if not configured)
if [ -z "$(git config user.name)" ]; then
    echo ""
    echo "Git user configuration not found."
    read -p "Enter your name for git commits: " GIT_NAME
    git config user.name "$GIT_NAME"
fi

if [ -z "$(git config user.email)" ]; then
    echo ""
    read -p "Enter your email for git commits: " GIT_EMAIL
    git config user.email "$GIT_EMAIL"
fi

echo ""
echo "Git configuration:"
echo "  Name: $(git config user.name)"
echo "  Email: $(git config user.email)"
echo ""

# Check .gitignore
if [ ! -f ".gitignore" ]; then
    echo "⚠️  .gitignore not found. Creating default..."
    cat > .gitignore << 'EOF'
# Python
__pycache__/
*.py[cod]
*$py.class
*.so
.Python
env/
venv/
ENV/
.venv

# IDE
.vscode/
.idea/
*.swp
*.swo
*~

# OS
.DS_Store
Thumbs.db

# Environment
.env
.env.local

# Build
dist/
build/
*.egg-info/

# Logs
*.log

# Temporary files
*.tmp
.git/credentials.tmp
EOF
    echo "✅ .gitignore created"
fi

# Check if there are uncommitted changes
if [ -n "$(git status --porcelain)" ]; then
    echo "📝 Staging all changes..."
    git add .
    
    echo ""
    echo "Changes to be committed:"
    git status --short
    
    echo ""
    read -p "Enter commit message (or press Enter for default): " COMMIT_MSG
    
    if [ -z "$COMMIT_MSG" ]; then
        COMMIT_MSG="Initial commit: Nxr v2.0 implementation"
    fi
    
    echo "💾 Committing changes..."
    git commit -m "$COMMIT_MSG"
    echo "✅ Changes committed"
fi

# Check current branch
CURRENT_BRANCH=$(git branch --show-current 2>/dev/null || echo "main")

if [ -z "$CURRENT_BRANCH" ]; then
    echo "🌿 Creating main branch..."
    git checkout -b main
    CURRENT_BRANCH="main"
fi

echo ""
echo "✅ Git setup complete!"
echo ""
echo "Current branch: $CURRENT_BRANCH"
echo ""
echo "Next steps:"
echo "  1. Run: ./scripts/push-to-github.sh"
echo "     (or: ./scripts/push-to-github-ssh.sh if SSH is configured)"
echo ""
echo "Note: GitHub requires Personal Access Token (not password)"
echo "      Create one at: https://github.com/settings/tokens"

