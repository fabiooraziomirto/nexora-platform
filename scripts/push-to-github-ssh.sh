#!/bin/bash
# Alternative push script using SSH (if SSH keys are configured)

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

# Repository configuration
GITHUB_USERNAME="lucadagati"
REPO_NAME="stack4things_v2.0"
REPO_URL_SSH="git@github.com:${GITHUB_USERNAME}/${REPO_NAME}.git"
REPO_URL_HTTPS="https://github.com/${GITHUB_USERNAME}/${REPO_NAME}.git"

echo "🚀 Stack4Things v2.0 - GitHub Push Script (SSH)"
echo "================================================="
echo ""

# Check if git is installed
if ! command -v git &> /dev/null; then
    echo "❌ Git is not installed. Please install git first."
    exit 1
fi

cd "$PROJECT_ROOT"

# Check if we're in a git repository
if [ ! -d ".git" ]; then
    echo "📦 Initializing git repository..."
    git init
    echo "✅ Git repository initialized"
fi

# Try SSH first, fallback to HTTPS
USE_SSH=false

if ssh -T git@github.com 2>&1 | grep -q "successfully authenticated"; then
    USE_SSH=true
    REPO_URL="$REPO_URL_SSH"
    echo "✅ SSH authentication detected"
else
    REPO_URL="$REPO_URL_HTTPS"
    echo "⚠️  SSH not configured, will use HTTPS"
fi

# Check remote
if git remote get-url origin &>/dev/null; then
    CURRENT_REMOTE=$(git remote get-url origin)
    if [ "$CURRENT_REMOTE" != "$REPO_URL" ]; then
        echo "⚠️  Remote URL mismatch. Updating..."
        git remote set-url origin "$REPO_URL"
    else
        echo "✅ Remote already configured: $REPO_URL"
    fi
else
    echo "📡 Adding remote origin..."
    git remote add origin "$REPO_URL"
    echo "✅ Remote added: $REPO_URL"
fi

# Check if there are changes to commit
if [ -z "$(git status --porcelain)" ]; then
    echo "⚠️  No changes to commit."
    echo "   Repository is up to date."
else
    echo "📝 Staging changes..."
    git add .
    
    echo ""
    echo "Changes to be committed:"
    git status --short
    
    echo ""
    read -p "Enter commit message (or press Enter for default): " COMMIT_MSG
    
    if [ -z "$COMMIT_MSG" ]; then
        COMMIT_MSG="Update Stack4Things v2.0 implementation"
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
echo "📤 Pushing to GitHub..."
echo "   Repository: $REPO_URL"
echo "   Branch: $CURRENT_BRANCH"
echo ""

# Push to GitHub
if [ "$USE_SSH" = true ]; then
    # SSH push (no credentials needed)
    if git push -u origin "$CURRENT_BRANCH" 2>&1; then
        echo ""
        echo "✅ Successfully pushed to GitHub!"
    else
        echo ""
        echo "❌ Push failed. Please check SSH configuration."
        exit 1
    fi
else
    # HTTPS push - need token
    echo "⚠️  HTTPS requires Personal Access Token."
    echo ""
    echo "   To create a PAT:"
    echo "   1. Go to: https://github.com/settings/tokens"
    echo "   2. Click 'Generate new token (classic)'"
    echo "   3. Select scopes: repo (all)"
    echo "   4. Copy the token"
    echo ""
    
    read -p "Enter GitHub Personal Access Token (will be hidden): " -s TOKEN
    echo ""
    
    if [ -z "$TOKEN" ]; then
        echo "❌ Token is required. Exiting."
        exit 1
    fi
    
    # Configure git credential helper (temporary)
    git config credential.helper 'store --file=.git/credentials.tmp'
    echo "https://${GITHUB_USERNAME}:${TOKEN}@github.com" > .git/credentials.tmp
    
    if git push -u origin "$CURRENT_BRANCH" 2>&1; then
        echo ""
        echo "✅ Successfully pushed to GitHub!"
    else
        echo ""
        echo "❌ Push failed. Please check credentials."
        exit 1
    fi
    
    # Cleanup
    rm -f .git/credentials.tmp
    git config --unset credential.helper
fi

echo ""
echo "🌐 Repository URL: https://github.com/${GITHUB_USERNAME}/${REPO_NAME}"
echo "📋 Branch: $CURRENT_BRANCH"
echo ""
echo "✅ Done!"

