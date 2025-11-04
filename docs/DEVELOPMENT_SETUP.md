# Development Environment Setup Guide

## Prerequisites

- Python 3.11+
- Poetry (will be installed automatically if missing)
- Git
- Docker & Docker Compose (for local development)

## Quick Setup

Run the setup script:

```bash
./scripts/setup-dev.sh
```

This will:
1. Check Python version (3.11+)
2. Install Poetry if not present
3. Setup all services and libraries
4. Install pre-commit hooks
5. Setup git hooks

## Manual Setup

### 1. Python Virtual Environment

```bash
# Create virtual environment with Poetry
poetry config virtualenvs.in-project true
poetry env use python3.11

# Install dependencies
poetry install

# Activate virtual environment
poetry shell
```

### 2. Pre-commit Hooks

```bash
# Install pre-commit hooks
poetry run pre-commit install

# Run hooks manually
poetry run pre-commit run --all-files
```

### 3. IDE Configuration

#### VSCode

1. Install recommended extensions (see `.vscode/extensions.json`)
2. Open workspace in VSCode
3. Select Python interpreter: `.venv/bin/python`
4. Settings are automatically loaded from `.vscode/settings.json`

#### PyCharm

See `docs/IDE_SETUP.md` for detailed PyCharm configuration.

## Development Workflow

### Code Formatting

```bash
# Format all Python files
poetry run black .

# Format with Ruff
poetry run ruff format .
```

### Linting

```bash
# Run Ruff linter
poetry run ruff check .

# Fix auto-fixable issues
poetry run ruff check . --fix

# Run MyPy type checker
poetry run mypy .

# Run Bandit security check
poetry run bandit -r . -f json
```

### Testing

```bash
# Run all tests
poetry run pytest

# Run with coverage
poetry run pytest --cov=. --cov-report=html

# Run specific test file
poetry run pytest tests/test_api.py

# Run specific test
poetry run pytest tests/test_api.py::test_create_device
```

### Pre-commit Checks

Before committing, pre-commit hooks will automatically:
- Format code with Black
- Check code with Ruff
- Type check with MyPy
- Check for security issues with Bandit
- Validate YAML/JSON files
- Check for large files
- Check for secrets

## Virtual Environment Management

### Activate Environment

```bash
poetry shell
```

### Deactivate Environment

```bash
exit  # or Ctrl+D
```

### Install New Dependency

```bash
# Production dependency
poetry add package-name

# Development dependency
poetry add --group dev package-name

# Update pyproject.toml and install
poetry add package-name@^1.0.0
```

### Update Dependencies

```bash
# Update all dependencies
poetry update

# Update specific package
poetry update package-name
```

### Remove Dependency

```bash
poetry remove package-name
```

## Environment Variables

Copy example environment files:

```bash
# Device Service
cp services/device-service/.env.example services/device-service/.env

# Edit .env files with your configuration
```

## Running Services Locally

```bash
# Start infrastructure (MySQL, Redis, Kafka)
docker-compose -f docker-compose.dev.yml up -d

# Run database migrations
cd services/device-service
poetry run alembic upgrade head

# Start Device Service
poetry run uvicorn device_service.main:app --reload
```

## Troubleshooting

### Poetry not found

```bash
# Install Poetry
curl -sSL https://install.python-poetry.org | python3 -
export PATH="$HOME/.local/bin:$PATH"
```

### Virtual environment issues

```bash
# Remove existing virtual environment
rm -rf .venv

# Recreate virtual environment
poetry env use python3.11
poetry install
```

### Pre-commit hooks not working

```bash
# Reinstall hooks
poetry run pre-commit install --overwrite

# Run manually
poetry run pre-commit run --all-files
```

### Python version mismatch

```bash
# Check Python version
python3 --version

# Should be 3.11+
# If not, install Python 3.11+ and use:
poetry env use python3.11
```

## IDE-Specific Notes

### VSCode

- Python interpreter is auto-detected from `.venv`
- Format on save is enabled
- Linting runs automatically
- Debugging configurations are in `.vscode/launch.json`

### PyCharm

- Configure Poetry environment: Settings → Project → Python Interpreter
- Enable Black formatter: Settings → Tools → Black
- Configure pytest: Settings → Tools → Python Integrated Tools → Testing

## Additional Tools

### Code Quality

```bash
# Run all quality checks
poetry run ruff check .
poetry run mypy .
poetry run bandit -r .

# Or use pre-commit
poetry run pre-commit run --all-files
```

### Generate Documentation

```bash
# Install sphinx (if needed)
poetry add --group dev sphinx

# Generate docs
cd docs
make html
```

## Next Steps

1. Configure environment variables (`.env` files)
2. Start infrastructure services (`docker-compose up`)
3. Run database migrations
4. Start developing!

