"""
Unit tests for DICOM loader module.

Tests file loading, directory loading, and error handling.
"""

import unittest
import os
import tempfile
from pathlib import Path

# Add src to path
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from core.dicom_loader import DICOMLoader


class TestDICOMLoader(unittest.TestCase):
    """Test cases for DICOMLoader."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.loader = DICOMLoader()
    
    def test_loader_initialization(self):
        """Test loader initialization."""
        self.assertIsNotNone(self.loader)
        self.assertEqual(len(self.loader.loaded_files), 0)
        self.assertEqual(len(self.loader.failed_files), 0)
    
    def test_load_nonexistent_file(self):
        """Test loading a non-existent file."""
        result = self.loader.load_file("/nonexistent/file.dcm")
        self.assertIsNone(result)
        self.assertEqual(len(self.loader.failed_files), 1)
    
    def test_clear(self):
        """Test clearing loaded files."""
        self.loader.clear()
        self.assertEqual(len(self.loader.loaded_files), 0)
        self.assertEqual(len(self.loader.failed_files), 0)


if __name__ == '__main__':
    unittest.main()

