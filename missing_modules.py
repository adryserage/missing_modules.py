"""A utility script to detect and install missing Python packages in a project.

This module scans through Python files in a directory, identifies imported packages,
checks which ones are missing from the current environment, generates a requirements.txt file,
and optionally installs the missing packages using pip.
"""

import os
import sys
import subprocess


def find_python_files(root_dir):
    """Recursively find all Python files starting from the given directory."""
    py_files = []
    for root, _, files in os.walk(root_dir):
        py_files.extend([os.path.join(root, f)
                        for f in files if f.endswith(".py")])
    return py_files


def extract_imported_packages(py_files):
    """Extract a list of imported packages from Python files."""
    imported_packages = set()
    for file in py_files:
        try:
            with open(file, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    # Skip empty lines and comments
                    if not line or line.startswith("#"):
                        continue
                    # Detect `import` and `from ... import ...` statements
                    if line.startswith("import ") or line.startswith("from "):
                        if line.startswith("import "):
                            # Handle multiple imports on one line (e.g., import os, sys)
                            packages = [p.strip().split(".")[0] for p in line[7:].split(",")]
                        else:
                            # Handle from ... import ... statements
                            package = line.split()[1].split(".")[0]
                            packages = [package]

                        # Add non-empty package names
                        imported_packages.update(p for p in packages if p and not p.startswith("."))
        except UnicodeDecodeError:
            print(f"Skipping file with encoding issue: {file}")
    return imported_packages


def check_missing_packages(imported_packages):
    """Check which imported packages are missing."""
    missing_packages = []
    for package in imported_packages:
        try:
            __import__(package)
        except ImportError:
            missing_packages.append(package)
    return missing_packages


def write_requirements(imported_packages):
    """Write all imported packages to requirements.txt."""
    with open("requirements.txt", "w", encoding="utf-8") as req_file:
        req_file.write("\n".join(sorted(imported_packages)))
    print("All detected packages written to 'requirements.txt'.")


def install_packages(missing_packages):
    """Install missing packages using pip."""
    for package in missing_packages:
        print(f"Installing {package}...")
        subprocess.check_call(
            [sys.executable, "-m", "pip", "install", package])
    print("All missing packages installed.")


if __name__ == "__main__":
    # Root directory for your project
    root_directory = os.path.dirname(os.path.abspath(__file__))

    # Step 1: Find all Python files
    python_files = find_python_files(root_directory)

    # Step 2: Extract imported packages
    imported = extract_imported_packages(python_files)

    # Step 3: Check for missing packages
    missing = check_missing_packages(imported)

    # Step 4: Write all detected packages to requirements.txt
    write_requirements(imported)

    # Step 5: Install missing packages
    if missing:
        print(f"Missing packages detected: {missing}")
        install_packages(missing)
    else:
        print("No missing packages detected. All packages are installed.")
