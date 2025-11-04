# PyCharm/IntelliJ IDEA Configuration Guide

## Setup PyCharm

### 1. Python Interpreter

1. **File** → **Settings** → **Project** → **Python Interpreter**
2. Click **Add Interpreter** → **Add Local Interpreter**
3. Select **Poetry Environment**
4. Choose the `pyproject.toml` in the root directory
5. Click **OK**

### 2. Code Style

1. **File** → **Settings** → **Editor** → **Code Style** → **Python**
2. Set **Hard wrap at**: `100`
3. Set **Tab size**: `4`
4. Set **Indent**: `4`
5. Enable **Wrapping and Braces** → **Keep when reformatting** → **Line breaks**

### 3. Formatter

1. **File** → **Settings** → **Tools** → **Black**
2. Enable **Black**
3. Set **Black executable**: `<poetry-env>/bin/black`
4. Set **Command line options**: `--line-length=100`

### 4. Linters

#### Ruff

1. **File** → **Settings** → **Tools** → **External Tools**
2. Click **+** to add new tool:
   - **Name**: `Ruff`
   - **Program**: `<poetry-env>/bin/ruff`
   - **Arguments**: `check $FilePath$`
   - **Working directory**: `$ProjectFileDir$`

#### MyPy

1. **File** → **Settings** → **Tools** → **External Tools**
2. Click **+** to add new tool:
   - **Name**: `MyPy`
   - **Program**: `<poetry-env>/bin/mypy`
   - **Arguments**: `$FilePath$`
   - **Working directory**: `$ProjectFileDir$`

### 5. Testing

1. **File** → **Settings** → **Tools** → **Python Integrated Tools**
2. **Testing** → **Default test runner**: `pytest`
3. **Test runner**: `pytest`
4. **Working directory**: `$ProjectFileDir$`

### 6. File Templates

1. **File** → **Settings** → **Editor** → **File and Code Templates**
2. Create Python test template:
   ```python
   import pytest
   
   def test_${NAME}():
       """Test ${NAME}."""
       assert True
   ```

### 7. Run Configurations

#### FastAPI Application

1. **Run** → **Edit Configurations**
2. Click **+** → **Python**
3. **Name**: `Device Service`
4. **Script path**: `<project-root>/services/device-service/src/device_service/main.py`
5. **Parameters**: `-m uvicorn device_service.main:app --reload --host 0.0.0.0 --port 8000`
6. **Working directory**: `<project-root>/services/device-service`
7. **Environment variables**: Load from `.env` file

#### Pytest

1. **Run** → **Edit Configurations**
2. Click **+** → **Python tests** → **pytest**
3. **Name**: `All Tests`
4. **Target**: `Custom`
5. **Additional arguments**: `--cov=. --cov-report=html --cov-report=term-missing`
6. **Working directory**: `<project-root>`

### 8. Pre-commit Hook

1. **File** → **Settings** → **Tools** → **External Tools**
2. Click **+** to add new tool:
   - **Name**: `Pre-commit`
   - **Program**: `<poetry-env>/bin/pre-commit`
   - **Arguments**: `run --all-files`
   - **Working directory**: `$ProjectFileDir$`

### 9. Git Integration

1. **File** → **Settings** → **Version Control** → **Git**
2. Enable **Commit dialog** → **Reformat code**
3. Enable **Commit dialog** → **Run code cleanup**
4. Enable **Commit dialog** → **Optimize imports**

### 10. Markdown Support

1. **File** → **Settings** → **Languages & Frameworks** → **Markdown**
2. Enable **Markdown support**
3. Install **Markdown Navigator** plugin (optional)

## Recommended Plugins

- **Black** - Code formatter
- **Ruff** - Fast Python linter
- **MyPy** - Type checker
- **Poetry** - Dependency management
- **Docker** - Docker support
- **Kubernetes** - K8s support
- **YAML** - YAML support
- **GitToolBox** - Git integration
- **Markdown Navigator** - Markdown support

## Code Style Configuration

Create `.idea/codeStyles/codeStyleConfig.xml`:

```xml
<component name="ProjectCodeStyleConfiguration">
  <code_scheme name="Project" version="173">
    <option name="RIGHT_MARGIN" value="100" />
    <Python>
      <option name="USE_CONTINUATION_INDENT_FOR_ARGUMENTS" value="true" />
    </Python>
  </code_scheme>
</component>
```

## Inspection Settings

1. **File** → **Settings** → **Editor** → **Inspections**
2. Enable:
   - **Python** → **Code quality** → **Unresolved references**
   - **Python** → **Code quality** → **Unused import**
   - **Python** → **Code quality** → **Unused variable**
   - **Python** → **Type checker** → **Type checker**

## Live Templates

Create useful shortcuts:

1. **File** → **Settings** → **Editor** → **Live Templates**
2. Add Python templates:
   - `test` → Create test function
   - `async` → Create async function
   - `doc` → Create docstring

