> Created by [Adryan Serage](https://github.com/adryserage)

[![CodeQL Advanced - Python](https://github.com/Adryan-Serage/missing_modules.py/actions/workflows/codeql.yml/badge.svg)](https://github.com/Adryan-Serage/missing_modules.py/actions/workflows/codeql.yml)
[![Pylint](https://github.com/adryserage/missing_modules.py/actions/workflows/pylint.yml/badge.svg)](https://github.com/adryserage/missing_modules.py/actions/workflows/pylint.yml)

## Context
A utility script to detect and install missing Python packages in a project.

This module scans through Python files in a directory, identifies imported packages,
checks which ones are missing from the current environment, generates a requirements.txt file,
and optionally installs the missing packages using pip.

## Overview
This Python script automates the management of Python dependencies for a project by:
1. Recursively scanning all Python files in the project directory.
2. Extracting all imported packages.
3. Checking for missing packages that are not installed in the current environment.
4. Generating a `requirements.txt` file with all detected packages.
5. Installing any missing packages using `pip`.

## Features
- **Recursive File Scanning**: Automatically identifies all Python files in the specified project directory.
- **Dependency Detection**: Extracts imported packages from the identified Python files.
- **Requirements File Generation**: Creates or updates a `requirements.txt` file listing all detected dependencies.
- **Package Installation**: Installs any missing dependencies using `pip`.

## Prerequisites
- Python 3.x installed on your system.
- `pip` installed for package management.

## How to Use
1. **Run the Script**:
   - Save the script in the root directory of your project.
   - Execute the script:
     ```bash
     python script_name.py
     ```
Available options:

- Scan a specific directory
`python missing_modules.py -d /path/to/project`

-  Install missing packages automatically
`python missing_modules.py --install`

-  Uninstall all non-standard library packages
`python missing_modules.py --uninstall-all`

-  Clean pip cache
`python missing_modules.py --clean-cache`

-  Specify custom requirements.txt location
`python missing_modules.py -r /path/to/requirements.txt`

# Enable verbose logging
python missing_modules.py -v
2. **Output**:
   - The script performs the following steps:
     - Lists all Python files in the directory and subdirectories.
     - Extracts a list of all imported packages.
     - Writes the packages into a `requirements.txt` file.
     - Checks for missing packages and installs them if necessary.

## Example Workflow
- **Step 1**: You run the script in your project directory.
  - Example: Your project contains `app.py` and `utils/helpers.py`.
- **Step 2**: The script scans all `.py` files and detects imports such as `numpy`, `pandas`, etc.
- **Step 3**: It checks if these packages are installed in your environment.
- **Step 4**: If any package is missing, it installs them using `pip`.
- **Step 5**: A `requirements.txt` file is generated, containing:
  ```
  numpy
  pandas
  ```

## Generated Files
- `requirements.txt`: A text file listing all detected dependencies, suitable for use with `pip install -r requirements.txt`.

## Error Handling
- Skips files with encoding issues and notifies the user.
- Handles `ImportError` for missing packages and attempts to install them.

## Notes
- The script may detect packages that are not explicitly needed if they are dynamically imported or unused in the project.
- Use the generated `requirements.txt` file as a starting point and manually refine it as necessary.

## License
This script is free to use and modify. No warranty is provided.

