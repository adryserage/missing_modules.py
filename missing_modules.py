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

import os
import sys
import logging
import subprocess
import argparse
from typing import List, Set, Dict, Optional
from pathlib import Path
from dataclasses import dataclass
from concurrent.futures import ThreadPoolExecutor, as_completed

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
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
        'abc', 'argparse', 'array', 'ast', 'asyncio', 'atexit', 'base64',
        'binascii', 'builtins', 'bz2', 'calendar', 'cgi', 'chunk', 'cmd',
        'code', 'codecs', 'collections', 'colorsys', 'configparser', 'contextlib',
        'copy', 'copyreg', 'csv', 'datetime', 'decimal', 'difflib', 'dis',
        'email', 'encodings', 'enum', 'errno', 'faulthandler', 'fcntl', 'filecmp',
        'fileinput', 'fnmatch', 'fractions', 'ftplib', 'functools', 'gc',
        'getopt', 'getpass', 'gettext', 'glob', 'graphlib', 'gzip', 'hashlib',
        'heapq', 'hmac', 'html', 'http', 'imaplib', 'imghdr', 'importlib',
        'inspect', 'io', 'ipaddress', 'itertools', 'json', 'keyword', 'linecache',
        'locale', 'logging', 'lzma', 'mailbox', 'marshal', 'math', 'mimetypes',
        'mmap', 'modulefinder', 'multiprocessing', 'netrc', 'numbers', 'operator',
        'optparse', 'os', 'pathlib', 'pdb', 'pickle', 'pickletools', 'pipes',
        'pkgutil', 'platform', 'plistlib', 'poplib', 'pprint', 'profile',
        'pstats', 'pty', 'pwd', 'py_compile', 'pyclbr', 'pydoc', 'queue',
        'quopri', 'random', 're', 'readline', 'reprlib', 'resource', 'rlcompleter',
        'runpy', 'sched', 'secrets', 'select', 'selectors', 'shelve', 'shlex',
        'shutil', 'signal', 'site', 'smtpd', 'smtplib', 'sndhdr', 'socket',
        'socketserver', 'sqlite3', 'ssl', 'stat', 'statistics', 'string',
        'stringprep', 'struct', 'subprocess', 'sys', 'sysconfig', 'tabnanny',
        'tarfile', 'tempfile', 'termios', 'textwrap', 'threading', 'time',
        'timeit', 'token', 'tokenize', 'trace', 'traceback', 'tracemalloc',
        'types', 'typing', 'unicodedata', 'unittest', 'urllib', 'uuid', 'venv',
        'warnings', 'wave', 'weakref', 'webbrowser', 'winreg', 'winsound',
        'wsgiref', 'xml', 'xmlrpc', 'zipapp', 'zipfile', 'zipimport', 'zlib'
    }

    # Package name mappings for pip installation
    PACKAGE_MAPPINGS = {
        'PIL': 'Pillow',  # PIL should be installed as Pillow
        'gi': 'PyGObject',  # gi module comes from PyGObject
    }

    # Invalid package name patterns
    INVALID_PATTERNS = {
        '%(module)s',  # Template strings
        'lowest',      # Common false positives
        '%',          # Template markers
        '$',          # Variable markers
        '{',          # Format strings
        '}',
        '<',          # HTML/XML tags
        '>',
        '\\',         # Path separators
        '/',
        '"',          # Quotes
        "'",
        ' ',          # Spaces
        '\t',         # Tabs
        '\n',         # Newlines
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
            logger.info(f"Installing package: {package_name}")
            process = subprocess.run(
                [sys.executable, "-m", "pip", "install", package_name],
                capture_output=True,
                text=True,
                check=True
            )
            logger.debug(f"Installation output: {process.stdout}")
            return True
        except subprocess.CalledProcessError as e:
            logger.error(f"Failed to install {package_name}: {e.stderr}")
            return False

    def find_python_files(self) -> List[Path]:
        """Find all Python files recursively."""
        logger.info("Scanning for Python files in %s", self.root_dir)

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

            if processed_dirs % 100 == 0 or processed_dirs == total_dirs:  # Log every 100 directories
                logger.info("Scanning progress: %.1f%% (%d/%d directories)",
                            progress, processed_dirs, total_dirs)

            python_files.extend([
                Path(os.path.join(root, f))
                for f in files if f.endswith(".py")
            ])

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

        if not (name[0].isalpha() or name[0] == '_'):
            return False

        if name.startswith('_'):
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
                                name = parts[1].split(".")[0].split("#")[
                                    0].strip()
                                if name and self.is_valid_package_name(name):
                                    imports.add(name)
        except Exception as e:
            logger.error("Error processing %s: %s", file_path, e)

        return imports

    def verify_package(self, package_name: str) -> PackageInfo:
        """Verify if a package is available and get its installation status."""
        info = PackageInfo(import_name=package_name)

        # Check if it's a standard library package
        if package_name.lower() in (p.lower() for p in self.STDLIB_PACKAGES):
            info.is_stdlib = True
            info.is_available = True
            return info

        # Get installation name from mapping if available
        info.install_name = self.PACKAGE_MAPPINGS.get(package_name, package_name)

        try:
            # Try importing the module without executing it
            import importlib.util
            spec = importlib.util.find_spec(package_name)
            info.is_available = spec is not None
        except (ImportError, AttributeError, ValueError):
            info.is_available = False
        except Exception as e:
            logger.error(f"Error verifying {package_name}: {e}")
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
                logger.info("Progress: %.1f%% (%d/%d files analyzed)",
                            progress, i, total_files)

        logger.info("Found %d unique imported packages", len(all_imports))
        logger.info("Searching for availability of %d packages...",
                    len(all_imports))

        # Verify packages in parallel using a smaller thread pool
        completed = 0
        total_packages = len(all_imports)
        logger.info("Starting package verification...")

        missing_packages = []
        # Use a smaller number of workers to avoid overwhelming the system
        with ThreadPoolExecutor(max_workers=min(32, os.cpu_count() or 1)) as executor:
            future_to_package = {
                executor.submit(self.verify_package, pkg): pkg
                for pkg in all_imports
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
                        logger.info("Verification progress: %.1f%% (%d/%d packages)",
                                    progress, completed, total_packages)
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
        logger.info(f"Installation complete: {success} succeeded, {failed} failed")
        return results

    def process_packages(self) -> bool:
        """Process all packages: verify and install if needed."""
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
                logger.info("Progress: %.1f%% (%d/%d files analyzed)",
                            progress, i, total_files)

        logger.info("Found %d unique imported packages", len(all_imports))
        logger.info("Searching for availability of %d packages...",
                    len(all_imports))

        # Verify packages in parallel
        completed = 0
        total_packages = len(all_imports)
        logger.info("Starting package verification...")

        with ThreadPoolExecutor() as executor:
            future_to_package = {
                executor.submit(self.verify_package, pkg): pkg
                for pkg in all_imports
            }

            for future in as_completed(future_to_package):
                package = future_to_package[future]
                try:
                    info = future.result()
                    self.packages[package] = info
                    completed += 1
                    if completed % 10 == 0 or completed == total_packages:  # Log every 10 packages
                        progress = (completed / total_packages) * 100
                        logger.info("Verification progress: %.1f%% (%d/%d packages)",
                                    progress, completed, total_packages)
                except Exception as e:
                    logger.error("Error verifying %s: %s", package, e)

        logger.info("Filtering packages that need installation...")
        # Filter packages that need installation
        to_install = [
            info for info in self.packages.values()
            if info.is_available and not info.is_stdlib and info.install_name
        ]

        if not to_install:
            logger.info("No packages need to be installed")
            return True

        logger.info("Installing %d packages...", len(to_install))

        # Install packages in parallel
        completed = 0
        total_installs = len(to_install)

        with ThreadPoolExecutor() as executor:
            future_to_info = {
                executor.submit(self.install_package, info.install_name): info
                for info in to_install
            }

            for future in as_completed(future_to_info):
                info = future_to_info[future]
                try:
                    updated_info = future.result()
                    self.packages[info.import_name] = updated_info
                    completed += 1
                    progress = (completed / total_installs) * 100
                    logger.info("Installation progress: %.1f%% (%d/%d packages)",
                                progress, completed, total_installs)
                except Exception as e:
                    logger.error("Error installing %s: %s",
                                 info.import_name, e)

        # Generate summary
        successful = [
            info.import_name for info in self.packages.values()
            if info.install_status is True
        ]
        failed = [
            info.import_name for info in self.packages.values()
            if info.install_status is False
        ]
        skipped = [
            info.import_name for info in self.packages.values()
            if info.is_stdlib or not info.is_available
        ]

        if successful:
            logger.info("Successfully installed: %s", successful)
        if failed:
            logger.warning("Failed to install: %s", failed)
        if skipped:
            logger.info("Skipped (stdlib or unavailable): %s", skipped)

        return not bool(failed)

    def uninstall_all_packages(self) -> Dict[str, bool]:
        """Uninstall all non-standard library packages from the environment.

        Returns:
            Dict[str, bool]: A dictionary mapping package names to uninstallation success status
        """
        logger.info(
            "Starting uninstallation of all non-standard library packages...")
        results = {}
        
        try:
            # Get list of installed packages
            process = subprocess.run(
                [sys.executable, "-m", "pip", "freeze"],
                capture_output=True,
                text=True,
                check=True
            )
            installed_packages = process.stdout.strip().split('\n')

            for package in installed_packages:
                if not package:  # Skip empty lines
                    continue

                package_name = package.split('==')[0]
                if package_name.lower() in (p.lower() for p in self.STDLIB_PACKAGES):
                    continue  # Skip standard library packages

                try:
                    logger.info(f"Uninstalling package: {package_name}")
                    subprocess.run(
                        [sys.executable, "-m", "pip",
                            "uninstall", "-y", package_name],
                        capture_output=True,
                        check=True
                    )
                    results[package_name] = True
                except subprocess.CalledProcessError as e:
                    logger.error(f"Failed to uninstall {package_name}: {e}")
                    results[package_name] = False

        except subprocess.CalledProcessError as e:
            logger.error(f"Failed to get list of installed packages: {e}")

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
                [sys.executable, "-m", "pip", "cache", "purge"],
                capture_output=True,
                check=True
            )
            logger.info("Successfully cleaned pip cache")
            return True
        except subprocess.CalledProcessError as e:
            logger.error(f"Failed to clean pip cache: {e}")
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
            logger.info(f"Generated requirements file: {requirements_file}")
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


def interactive_mode(package_manager: 'PackageManager'):
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
                confirm = input("\nThis will uninstall all non-standard packages. Continue? (y/N): ")
                if confirm.lower() == 'y':
                    results = package_manager.uninstall_all_packages()
                    success, failed = package_manager.get_operation_results(results)
                    print(f"\nUninstallation complete: {success} succeeded, {failed} failed")
                
            elif choice == 4:  # Clean Cache
                if package_manager.clean_package_cache():
                    print("\nSuccessfully cleaned pip cache")
                else:
                    print("\nFailed to clean pip cache")
                
            elif choice == 5:  # Generate Requirements
                req_file = input("\nEnter requirements file path (or press Enter for default): ").strip()
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
        "--directory", "-d",
        default=".",
        help="Root directory to scan for Python files (default: current directory)"
    )
    parser.add_argument(
        "--requirements", "-r",
        help="Path to requirements.txt file (default: requirements.txt in root directory)"
    )
    parser.add_argument(
        "--install", "-i",
        action="store_true",
        help="Install missing packages automatically"
    )
    parser.add_argument(
        "--uninstall-all", "-u",
        action="store_true",
        help="Uninstall all non-standard library packages"
    )
    parser.add_argument(
        "--clean-cache", "-c",
        action="store_true",
        help="Clean pip cache"
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Enable verbose logging"
    )
    parser.add_argument(
        "--option", "-o",
        action="store_true",
        help="Run in interactive menu mode"
    )

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
                    results = package_manager.install_missing_packages()
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
