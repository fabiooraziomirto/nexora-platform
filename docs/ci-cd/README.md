# CI/CD Pipeline Documentation

## Overview

Stack4Things v2.0 uses CI/CD pipelines for automated testing, building, and deployment.

## Pipeline Stages

### 1. Linting Stage

Runs code quality checks:

- **Black**: Code formatting check
- **Ruff**: Python linting
- **MyPy**: Type checking
- **Pre-commit**: All pre-commit hooks

**Trigger**: On every push and pull request

### 2. Testing Stage

Runs test suites:

- **Device Service Tests**: Unit and integration tests
- **Common Library Tests**: Library tests
- **Coverage Reports**: Code coverage analysis

**Services**: MySQL, Redis containers

**Trigger**: On every push and pull request

### 3. Build Stage

Builds Docker images:

- **Device Service**: Docker image build and push
- **Common Library**: Docker image build and push

**Trigger**: On push to main/develop branches

### 4. Security Scanning Stage

Security vulnerability scanning:

- **Bandit**: Python security linter
- **Safety**: Dependency vulnerability checker
- **Snyk**: Comprehensive security scanning
- **Trivy**: Container image scanning

**Trigger**: On every push and pull request

### 5. Deploy Stage

Deploys to environments:

- **Staging**: Deploy from develop branch
- **Production**: Deploy from main branch

**Trigger**: Manual approval required

## GitLab CI

Configuration file: `.gitlab-ci.yml`

### Variables

Set in GitLab CI/CD Settings:

- `CI_REGISTRY`: Docker registry URL
- `CI_REGISTRY_USER`: Registry username
- `CI_REGISTRY_PASSWORD`: Registry password
- `KUBECONFIG`: Kubernetes config (base64 encoded)

### Cache

- Poetry cache: `.cache/poetry/`
- Pip cache: `.cache/pip/`
- Virtual environment: `.venv/`

### Artifacts

- Coverage reports: Available for 1 week
- Security reports: Available for 1 week
- Docker images: Pushed to registry

## GitHub Actions

Configuration file: `.github/workflows/ci.yml`

### Secrets

Configure in GitHub Settings → Secrets:

- `SNYK_TOKEN`: Snyk API token
- `KUBECONFIG`: Kubernetes config (base64 encoded)

### Features

- **Matrix builds**: Build multiple services in parallel
- **Caching**: Poetry and pip cache
- **Codecov**: Coverage reporting
- **SARIF**: Security scan results

## Dependabot

Configuration file: `.github/dependabot.yml`

### Updates

- **Python dependencies**: Weekly
- **Docker images**: Weekly
- **GitHub Actions**: Weekly

### Pull Requests

- Automatic PR creation
- Labels: `dependencies`, `python`, etc.
- Reviewers: `stack4things-team`

## Security Scanning

### Bandit

```bash
poetry run bandit -r . -f json -o bandit-report.json
```

### Safety

```bash
poetry export -f requirements.txt --without-hashes -o requirements.txt
safety check --file requirements.txt
```

### Snyk

```bash
snyk test --severity-threshold=high
```

### Trivy

```bash
trivy fs --format sarif --output trivy-results.sarif .
```

## Local Testing

### Run Linting Locally

```bash
poetry run black --check .
poetry run ruff check .
poetry run mypy .
```

### Run Tests Locally

```bash
# With services
docker-compose -f docker-compose.dev.yml up -d
poetry run pytest

# Without services (unit tests only)
poetry run pytest -m "not integration"
```

### Run Security Scans Locally

```bash
poetry run bandit -r .
poetry run safety check
```

## Deployment

### Staging

```bash
# GitLab CI
# Manual trigger from develop branch

# GitHub Actions
# Manual trigger from develop branch
```

### Production

```bash
# GitLab CI
# Manual trigger from main branch

# GitHub Actions
# Automatic on push to main (if configured)
```

## Troubleshooting

### Pipeline Fails

1. Check logs in CI/CD dashboard
2. Run commands locally to reproduce
3. Check environment variables
4. Verify secrets are set correctly

### Build Fails

1. Check Dockerfile syntax
2. Verify dependencies are correct
3. Check Docker registry permissions
4. Review build logs

### Tests Fail

1. Check test database connection
2. Verify service dependencies
3. Check environment variables
4. Review test logs

### Security Scan Fails

1. Review security report
2. Fix vulnerabilities
3. Update dependencies
4. Review false positives

## Best Practices

1. **Keep pipelines fast**: Use caching and parallel execution
2. **Fail fast**: Run quick checks first
3. **Clear errors**: Provide helpful error messages
4. **Security first**: Always run security scans
5. **Document changes**: Update pipeline docs when changing CI/CD

