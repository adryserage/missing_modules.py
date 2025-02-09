"""Unit tests for missing_modules.py."""

import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from missing_modules import PackageManager


class TestMissingModules(unittest.TestCase):
    """Test cases for missing_modules.py."""

    def setUp(self):
        """Set up test environment."""
        self.test_dir = tempfile.mkdtemp()
        self.manager = PackageManager(self.test_dir)

    def tearDown(self):
        """Clean up temporary files."""
        # Use shutil.rmtree for recursive directory removal
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_find_python_files(self):
        """Test finding Python files."""
        # Create test Python files
        test_file1 = os.path.join(self.test_dir, "test1.py")
        test_file2 = os.path.join(self.test_dir, "subdir", "test2.py")
        os.makedirs(os.path.dirname(test_file2), exist_ok=True)

        with open(test_file1, "w", encoding="utf-8") as f:
            f.write("import os\n")
        with open(test_file2, "w", encoding="utf-8") as f:
            f.write("import sys\n")

        # Test finding the files
        files = self.manager.find_python_files()
        self.assertEqual(len(files), 2)
        file_paths = [str(f) for f in files]
        self.assertTrue(any(f.endswith("test1.py") for f in file_paths))
        self.assertTrue(any(f.endswith("test2.py") for f in file_paths))

    def test_extract_imported_packages(self):
        """Test extracting imported packages."""
        # Create a test file with various import formats
        test_file = Path(self.test_dir) / "test.py"
        with open(test_file, "w", encoding="utf-8") as f:
            f.write(
                """
import os
import sys as system
from pathlib import Path
from typing import List, Dict
import subprocess, shutil
from concurrent.futures import ThreadPoolExecutor
"""
            )

        # Test extracting imports
        imports = self.manager.extract_imports(test_file)
        self.assertEqual(len(imports), 6)
        self.assertIn("os", imports)
        self.assertIn("sys", imports)
        self.assertIn("pathlib", imports)
        self.assertIn("typing", imports)
        self.assertIn("subprocess", imports)
        self.assertIn("shutil", imports)
        self.assertIn("concurrent.futures", imports)

    def test_stdlib_packages_excluded(self):
        """Test that standard library packages are excluded."""
        # Create a test file with only stdlib imports
        test_file = Path(self.test_dir) / "test.py"
        with open(test_file, "w", encoding="utf-8") as f:
            f.write(
                """
import os
import sys
from datetime import datetime
from pathlib import Path
import unittest
import logging
"""
            )

        # Test extracting imports
        imports = self.manager.extract_imports(test_file)
        self.assertEqual(len(imports), 0)

    def test_package_verification(self):
        """Test package verification functionality."""
        # Test stdlib package
        info = self.manager.verify_package("os")
        self.assertTrue(info.is_stdlib)
        self.assertTrue(info.is_available)
        self.assertIsNone(info.install_name)

        # Test nonexistent package
        info = self.manager.verify_package("nonexistent_package_xyz")
        self.assertFalse(info.is_stdlib)
        self.assertFalse(info.is_available)
        self.assertEqual(info.install_name, "nonexistent_package_xyz")

        # Test package with special mapping
        info = self.manager.verify_package("PIL")
        self.assertFalse(info.is_stdlib)
        self.assertEqual(info.install_name, "Pillow")

    def test_invalid_package_patterns(self):
        """Test detection of invalid package patterns."""
        invalid_names = [
            "%(module)s",
            "{template}",
            "$variable",
            "package with spaces",
            "package/with/slashes",
            "<html>",
            "package\\with\\backslashes",
            "\n",
            "\t",
            " ",
            "",
        ]
        for name in invalid_names:
            self.assertFalse(self.manager.is_valid_package_name(name))

    @patch("subprocess.run")
    def test_package_installation(self, mock_run):
        """Test package installation functionality."""
        # Mock successful installation
        success_result = MagicMock()
        success_result.returncode = 0
        success_result.stdout = "Successfully installed valid-package"
        mock_run.return_value = success_result
        self.assertTrue(self.manager.install_package("valid-package"))

        # Mock failed installation
        mock_run.side_effect = subprocess.CalledProcessError(
            returncode=1,
            cmd=["pip", "install", "invalid-package"],
            output="Could not find a version that satisfies the requirement",
            stderr="Installation failed",
        )
        self.assertFalse(self.manager.install_package("invalid-package"))

    def test_requirements_path(self):
        """Test requirements.txt path generation."""
        # Test default path
        default_path = self.manager.get_requirements_path()
        self.assertEqual(default_path, os.path.join(self.test_dir, "requirements.txt"))

        # Test custom path
        custom_path = "/custom/path/requirements.txt"
        path = self.manager.get_requirements_path(custom_path)
        self.assertEqual(path, os.path.abspath(custom_path))

    def test_operation_results(self):
        """Test operation results counting."""
        results = {
            "package1": True,
            "package2": False,
            "package3": True,
            "package4": False,
            "package5": True,
        }
        success, failed = self.manager.get_operation_results(results)
        self.assertEqual(success, 3)
        self.assertEqual(failed, 2)


if __name__ == "__main__":
    unittest.main()
