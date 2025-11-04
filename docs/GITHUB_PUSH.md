# GitHub Push Guide

## Repository Information

- **Username**: lucadagati
- **Repository**: stack4things_v2.0
- **URL**: https://github.com/lucadagati/stack4things_v2.0.git

## Important Note

⚠️ **GitHub no longer accepts passwords for HTTPS authentication.**

You need to use a **Personal Access Token (PAT)** instead of a password.

### Creating a Personal Access Token

1. Go to: https://github.com/settings/tokens
2. Click **"Generate new token (classic)"**
3. Give it a name: `Stack4Things v2.0`
4. Select expiration (or no expiration)
5. Select scopes:
   - ✅ **repo** (all) - Full control of private repositories
6. Click **"Generate token"**
7. **Copy the token immediately** (you won't see it again!)

## Usage

### Option 1: HTTPS with Personal Access Token (Recommended)

```bash
./scripts/push-to-github.sh
```

This script will:
- Initialize git repository if needed
- Configure remote origin
- Stage all changes
- Ask for commit message
- Ask for Personal Access Token
- Push to GitHub

### Option 2: SSH (If SSH keys are configured)

```bash
./scripts/push-to-github-ssh.sh
```

This script will:
- Try SSH first (if configured)
- Fallback to HTTPS if SSH is not available
- No password/token needed if SSH works

### Option 3: Initial Git Setup

If this is the first time setting up git:

```bash
./scripts/git-setup.sh
```

This script will:
- Initialize git repository
- Configure git user name and email
- Create .gitignore
- Make initial commit
- Then you can push with: `./scripts/push-to-github.sh`

## Manual Push

If you prefer manual steps:

```bash
# Initialize git (if not done)
git init

# Configure git user (if not configured)
git config user.name "Your Name"
git config user.email "your.email@example.com"

# Add remote
git remote add origin https://github.com/lucadagati/stack4things_v2.0.git

# Stage changes
git add .

# Commit
git commit -m "Initial commit: Stack4Things v2.0"

# Push (will ask for username and token)
git push -u origin main
```

When prompted:
- **Username**: `lucadagati`
- **Password**: Enter your **Personal Access Token** (not password!)

## First Push

If this is the first push to an empty repository:

```bash
# Make sure you're on main branch
git checkout -b main

# Push with upstream
git push -u origin main
```

## Troubleshooting

### Authentication Failed

If you get authentication errors:

1. Make sure you're using a Personal Access Token (not password)
2. Check token has `repo` scope
3. Verify token hasn't expired

### Repository Not Found

If you get "repository not found":

1. Make sure repository exists at: https://github.com/lucadagati/stack4things_v2.0
2. Check you have write access
3. Verify repository URL is correct

### Remote Already Exists

If remote already exists with different URL:

```bash
git remote set-url origin https://github.com/lucadagati/stack4things_v2.0.git
```

## Security Notes

- **Never commit tokens or passwords** to git
- The script uses temporary credential storage (cleaned up after push)
- Consider using SSH keys for better security
- Rotate tokens regularly

## SSH Setup (Optional)

For better security, set up SSH keys:

```bash
# Generate SSH key (if not exists)
ssh-keygen -t ed25519 -C "your.email@example.com"

# Add to ssh-agent
eval "$(ssh-agent -s)"
ssh-add ~/.ssh/id_ed25519

# Add public key to GitHub
cat ~/.ssh/id_ed25519.pub
# Copy output and add at: https://github.com/settings/keys

# Then use SSH URL
git remote set-url origin git@github.com:lucadagati/stack4things_v2.0.git
```

## Repository Status

Check repository status:

```bash
# Check remote
git remote -v

# Check status
git status

# Check branches
git branch -a

# View commits
git log --oneline
```

## Next Steps After Push

1. Verify repository at: https://github.com/lucadagati/stack4things_v2.0
2. Set up branch protection (if needed)
3. Configure GitHub Actions (if needed)
4. Add collaborators (if needed)

