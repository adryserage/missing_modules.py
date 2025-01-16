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
        # Core Python standard library
        'os', 'sys', 'subprocess', 'logging', 'pathlib', 'typing',
        'datetime', 'time', 'json', 're', 'math', 'random', 'collections',
        'ssl', 'StringIO', 'io', 'unittest', 'tempfile', 'configparser',
        'xml', 'html', 'http', 'urllib', 'socket', 'email', 'calendar',
        'argparse', 'asyncio', 'concurrent', 'contextlib', 'csv', 'curses',
        'dbm', 'decimal', 'difflib', 'distutils', 'enum', 'fileinput',
        'fnmatch', 'fractions', 'ftplib', 'functools', 'glob', 'hashlib',
        'heapq', 'hmac', 'imaplib', 'imp', 'inspect', 'itertools', 'keyword',
        'linecache', 'locale', 'mimetypes', 'numbers', 'operator', 'optparse',
        'pickle', 'pkgutil', 'platform', 'pprint', 'pwd', 'queue', 'Queue',
        'shlex', 'shutil', 'signal', 'smtplib', 'statistics', 'string',
        'struct', 'symbol', 'sysconfig', 'telnetlib', 'textwrap',
        'threading', 'token', 'tokenize', 'traceback', 'types', 'uuid',
        'warnings', 'weakref', 'zipfile', 'zlib', 'urllib2', 'urlparse',
        'grp', '_typeshed', 'PIL', 'this', '_pyi_rth_utils', 'pyimod01_archive', 'yourapplication', 'otherfile',
        'environment', 'successful', 'limited_api1', 'pkg1', 'it', 'an',
        'ASCII', 'android'
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

    def find_python_files(self) -> List[Path]:
        """Find all Python files recursively."""
        logger.info("Scanning for Python files in %s", self.root_dir)
        
        python_files = []
        total_dirs = 0
        processed_dirs = 0
        
        # First count total directories for progress tracking
        for _, dirs, _ in os.walk(self.root_dir):
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
        """Verify package availability and status."""
        info = PackageInfo(import_name=package_name)

        # Check if it's a stdlib package
        if package_name in self.STDLIB_PACKAGES:
            info.is_stdlib = True
            return info

        # Try importing the package
        try:
            __import__(package_name)
            info.is_available = True
            return info
        except ImportError:
            pass

        # Check if package exists on PyPI
        install_name = self.get_install_name(package_name)
        info.install_name = install_name

        try:
            result = subprocess.run(
                ["pip", "index", "versions", install_name],
                capture_output=True,
                text=True
            )
            info.is_available = result.returncode == 0 and "versions:" in result.stdout
        except Exception as e:
            info.error_message = str(e)

        return info

    def install_package(self, package_info: PackageInfo) -> PackageInfo:
        """Install a single package."""
        if not package_info.is_available or not package_info.install_name:
            return package_info

        try:
            logger.info("Installing %s as %s...", 
                       package_info.import_name, package_info.install_name)
            subprocess.check_call(
                ["pip", "install", package_info.install_name],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE
            )
            package_info.install_status = True
        except subprocess.CalledProcessError as e:
            package_info.install_status = False
            package_info.error_message = str(e)
            logger.error("Failed to install %s: %s", package_info.install_name, e)

        return package_info

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
        logger.info("Searching for availability of %d packages...", len(all_imports))
        
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
                executor.submit(self.install_package, info): info
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
                    logger.error("Error installing %s: %s", info.import_name, e)
                    
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

    def generate_requirements(self) -> None:
        """Generate requirements.txt file."""
        requirements = [
            info.install_name
            for info in self.packages.values()
            if info.is_available and not info.is_stdlib and info.install_name
        ]

        if requirements:
            with open("requirements.txt", "w", encoding="utf-8") as f:
                f.write("\n".join(sorted(requirements)))
            logger.info("Generated requirements.txt")
        else:
            logger.info("No requirements to write")


def main():
    """Main entry point for the script."""
    try:
        # Get the project root directory
        root_dir = os.path.dirname(os.path.abspath(__file__))

        # Create and run package manager
        manager = PackageManager(root_dir)
        success = manager.process_packages()

        # Generate requirements.txt
        manager.generate_requirements()

        if not success:
            logger.warning("Some packages could not be installed - check the logs for details")
            sys.exit(1)

    except Exception as e:
        logger.error("An error occurred: %s", e)
        sys.exit(1)


if __name__ == "__main__":
    main()
