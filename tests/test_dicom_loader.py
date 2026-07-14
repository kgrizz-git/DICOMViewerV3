"""
Unit tests for DICOM loader module.

Tests file loading, directory loading, and error handling.
"""

import os

# Add src to path
import sys
import unittest

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

    def test_load_structured_report_fixture_is_not_failed(self):
        """SR fixtures should load as SR datasets without being treated as pixel failures."""
        fixture_path = os.path.join(
            os.path.dirname(__file__),
            "fixtures",
            "dicom_rdsr",
            "synthetic_ct_dose_xray_rdsr.dcm",
        )

        result = self.loader.load_file(fixture_path)

        self.assertIsNotNone(result)
        self.assertEqual(getattr(result, "Modality", None), "SR")
        self.assertEqual(getattr(result, "_no_pixel_reason", None), "structured_report")
        self.assertEqual(len(self.loader.failed_files), 0)


if __name__ == '__main__':
    unittest.main()

