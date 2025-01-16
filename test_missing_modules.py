"""Unit tests for missing_modules.py."""

import os
import tempfile
import unittest
from pathlib import Path

from missing_modules import PackageManager

class TestMissingModules(unittest.TestCase):
    """Test cases for missing_modules.py."""

    def setUp(self):
        """Set up test environment."""
        self.test_dir = tempfile.mkdtemp()
        self.manager = PackageManager(self.test_dir)

    def tearDown(self):
        # Clean up temporary files
        for root, _, files in os.walk(self.test_dir):
            for f in files:
                os.remove(os.path.join(root, f))
        os.rmdir(self.test_dir)

    def test_find_python_files(self):
        """Test finding Python files."""
        # Create a test Python file
        test_file = os.path.join(self.test_dir, "test.py")
        with open(test_file, "w", encoding="utf-8") as f:
            f.write("import os\n")

        # Test finding the file
        files = self.manager.find_python_files()
        self.assertEqual(len(files), 1)
        self.assertTrue(str(files[0]).endswith("test.py"))

    def test_extract_imported_packages(self):
        """Test extracting imported packages."""
        # Create a test file with imports
        test_file = Path(self.test_dir) / "test.py"
        with open(test_file, "w", encoding="utf-8") as f:
            f.write("""
import os
import sys
import pandas as pd  # Comment
from numpy import array
from . import local_module
""")

        # Test extracting imports
        imports = self.manager.extract_imports(test_file)
        self.assertEqual(len(imports), 2)  # os, sys are stdlib, local_module is relative
        self.assertIn("pandas", imports)
        self.assertIn("numpy", imports)

    def test_stdlib_packages_excluded(self):
        """Test that standard library packages are excluded."""
        # Create a test file with only stdlib imports
        test_file = Path(self.test_dir) / "test.py"
        with open(test_file, "w", encoding="utf-8") as f:
            f.write("""
import os
import sys
from datetime import datetime
""")

        # Test extracting imports
        imports = self.manager.extract_imports(test_file)
        self.assertEqual(len(imports), 0)  # All should be excluded

    def test_check_missing_packages(self):
        """Test checking for missing packages."""
        # Create a test file with a mix of packages
        test_file = Path(self.test_dir) / "test.py"
        with open(test_file, "w", encoding="utf-8") as f:
            f.write("""
import os  # stdlib
import nonexistent_package  # should be missing
from datetime import datetime  # stdlib
""")

        # Get imports
        imports = self.manager.extract_imports(test_file)
        
        # Verify packages
        for pkg in imports:
            info = self.manager.verify_package(pkg)
            if pkg == "nonexistent_package":
                self.assertFalse(info.is_available)
            else:
                self.assertTrue(info.is_stdlib or info.is_available)

if __name__ == "__main__":
    unittest.main()
