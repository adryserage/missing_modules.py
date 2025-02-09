# Missing Modules

> Created by [Adryan Serage](https://github.com/adryserage)

[![CodeQL Advanced - Python](https://github.com/Adryan-Serage/missing_modules.py/actions/workflows/codeql.yml/badge.svg)](https://github.com/adryserage/missing_modules.py/actions/workflows/codeql.yml)
[![Pylint](https://github.com/adryserage/missing_modules.py/actions/workflows/pylint.yml/badge.svg)](https://github.com/adryserage/missing_modules.py/actions/workflows/pylint.yml)
[![Black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)
[![isort](https://img.shields.io/badge/%20imports-isort-%231674b1?style=flat&labelColor=ef8336)](https://pycqa.github.io/isort/)

## Overview

A utility script to detect and install missing Python packages in a project. It scans through Python files in a directory, identifies imported packages, checks which ones are missing from the current environment, generates a requirements.txt file, and optionally installs the missing packages using pip.

## Features

- **Smart Package Detection**
  - Handles various import formats (e.g., `import x`, `from x import y`, `import x as y`)
  - Excludes standard library packages automatically
  - Handles special package mappings (e.g., `PIL` → `Pillow`)
  - Filters out invalid package names and common false positives

- **Parallel Processing**
  - Uses ThreadPoolExecutor for parallel package verification
  - Optimized thread pool size to prevent system overload
  - Progress tracking for file scanning and package verification

- **Comprehensive Package Management**
  - Verifies package availability without executing code
  - Installs missing packages using pip
  - Generates requirements.txt file
  - Supports package uninstallation and cache cleaning

- **Robust Error Handling**
  - Graceful handling of file encoding issues
  - Detailed error reporting for package verification failures
  - Proper cleanup of temporary resources

- **Interactive Mode**
  - Menu-driven interface for common operations
  - Progress reporting for long-running operations
  - Detailed logging with configurable verbosity

## Code Quality Tools

### Static Analysis and Formatting

The project uses several tools to maintain code quality:

- **Black** - The uncompromising code formatter
  - Ensures consistent code style
  - Line length set to 100 characters
  - Configured in `pyproject.toml`

- **isort** - Import sorting tool
  - Automatically organizes imports
  - Groups imports by type (stdlib, third-party, local)
  - Configured to work with Black's style

- **pylint** - Python static code analyzer
  - Enforces coding standards
  - Detects potential errors
  - Custom configuration in `.pylintrc`

### Code Quality Configuration

The project includes several configuration files:

- `pyproject.toml`: Configuration for Black and isort
- `.pylintrc`: Pylint configuration with custom rules
- `.github/workflows/pylint.yml`: CI pipeline for code quality checks

### Running Code Quality Tools

```bash
# Format code with Black
black .

# Sort imports with isort
isort .

# Run pylint checks
pylint $(git ls-files '*.py')
```

### Pre-commit Hooks

It's recommended to set up pre-commit hooks to run these tools automatically before each commit:

```bash
# Install pre-commit
pip install pre-commit

# Install the git hook scripts
pre-commit install
```

## Installation

```bash
# Clone the repository
git clone https://github.com/adryserage/missing_modules.py.git

# Navigate to the directory
cd missing_modules.py

# Optional: Create and activate a virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

## Usage

### Command Line Interface

```bash
# Basic usage - scan current directory
python missing_modules.py

# Scan a specific directory
python missing_modules.py -d /path/to/project

# Install missing packages automatically
python missing_modules.py --install

# Generate requirements.txt in a custom location
python missing_modules.py -r /path/to/requirements.txt

# Uninstall all non-standard library packages
python missing_modules.py --uninstall-all

# Clean pip cache
python missing_modules.py --clean-cache

# Enable verbose logging
python missing_modules.py -v

# Combine multiple options
python missing_modules.py --clean-cache --uninstall-all --install
```

### Interactive Mode

The script provides an interactive menu with the following options:

1. Scan directory for Python files
2. Detect missing packages
3. Install missing packages
4. Generate requirements.txt
5. Uninstall all packages
6. Clean package cache
7. Exit

## Package Detection Details

### Import Formats Supported

```python
# Direct imports
import package_name
import package_name as alias

# From imports
from package_name import module
from package_name.submodule import function

# Multiple imports
import os, sys, package_name
```

### Special Package Mappings

Some packages have different import and installation names. The script handles these cases:

- `PIL` → Installs as `Pillow`
- `gi` → Installs as `PyGObject`

### Invalid Package Patterns

The script filters out common false positives and invalid package names:

- Template strings (e.g., `%(module)s`)
- Variable markers (e.g., `${package}`)
- HTML/XML tags
- Paths with slashes or backslashes
- Empty strings and whitespace

## Development

### Running Tests

```bash
# Run all tests
python -m unittest test_missing_modules.py

# Run tests with verbose output
python -m unittest test_missing_modules.py -v
```

### Test Coverage

The test suite covers:

- File scanning and import extraction
- Package verification and installation
- Standard library package exclusion
- Invalid package pattern detection
- Requirements.txt generation
- Error handling scenarios

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add or update tests as needed
5. Submit a pull request

## License

This project is free to use and modify. No warranty is provided.

## Credits

Created and maintained by [Adryan Serage](https://github.com/adryserage).
