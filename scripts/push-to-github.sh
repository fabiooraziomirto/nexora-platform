#!/bin/bash
# Push script for Nxr v2.0 to GitHub

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

# Repository configuration
GITHUB_USERNAME="lucadagati"
REPO_NAME="nxr_v2.0"
REPO_URL="https://github.com/${GITHUB_USERNAME}/${REPO_NAME}.git"

echo "🚀 Nxr v2.0 - GitHub Push Script"
echo "=========================================="
echo ""

# Check if git is installed
if ! command -v git &> /dev/null; then
    echo "❌ Git is not installed. Please install git first."
    exit 1
fi

# Check if we're in a git repository
cd "$PROJECT_ROOT"

if [ ! -d ".git" ]; then
    echo "📦 Initializing git repository..."
    git init
    echo "✅ Git repository initialized"
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
        COMMIT_MSG="Update Nxr v2.0 implementation"
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
echo "⚠️  IMPORTANT: GitHub no longer accepts passwords for HTTPS authentication."
echo "   You need to use a Personal Access Token (PAT)."
echo ""
echo "   To create a PAT:"
echo "   1. Go to: https://github.com/settings/tokens"
echo "   2. Click 'Generate new token (classic)'"
echo "   3. Select scopes: repo (all)"
echo "   4. Copy the token"
echo ""

# Ask for credential
read -p "Enter GitHub Personal Access Token (will be hidden): " -s TOKEN
echo ""

if [ -z "$TOKEN" ]; then
    echo "❌ Token is required. Exiting."
    exit 1
fi

# Configure git credential helper (temporary)
echo "🔐 Configuring credentials..."

# Use credential helper for this session
git config credential.helper 'store --file=.git/credentials.tmp'

# Create temporary credentials file
echo "https://${GITHUB_USERNAME}:${TOKEN}@github.com" > .git/credentials.tmp

# Clean up function
cleanup() {
    rm -f .git/credentials.tmp
    git config --unset credential.helper
}

trap cleanup EXIT

echo ""
echo "📤 Pushing to GitHub..."
echo "   Repository: $REPO_URL"
echo "   Branch: $CURRENT_BRANCH"
echo ""

# Push to GitHub
if git push -u origin "$CURRENT_BRANCH" 2>&1; then
    echo ""
    echo "✅ Successfully pushed to GitHub!"
    echo ""
    echo "🌐 Repository URL: https://github.com/${GITHUB_USERNAME}/${REPO_NAME}"
    echo "📋 Branch: $CURRENT_BRANCH"
else
    echo ""
    echo "❌ Push failed. Please check:"
    echo "   1. Token has 'repo' scope"
    echo "   2. Repository exists and you have write access"
    echo "   3. Network connection"
    exit 1
fi

# Cleanup
cleanup

echo ""
echo "✅ Done!"

