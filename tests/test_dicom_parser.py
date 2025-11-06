"""
Unit tests for DICOM parser module.

Tests metadata parsing and tag extraction.
"""

import unittest
import sys
import os

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from core.dicom_parser import DICOMParser


class TestDICOMParser(unittest.TestCase):
    """Test cases for DICOMParser."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.parser = DICOMParser()
    
    def test_parser_initialization(self):
        """Test parser initialization."""
        self.assertIsNotNone(self.parser)
        self.assertIsNone(self.parser.dataset)
    
    def test_get_all_tags_no_dataset(self):
        """Test getting tags with no dataset."""
        tags = self.parser.get_all_tags()
        self.assertEqual(len(tags), 0)
    
    def test_get_tag_value_no_dataset(self):
        """Test getting tag value with no dataset."""
        value = self.parser.get_tag_value((0x0010, 0x0010))
        self.assertIsNone(value)


if __name__ == '__main__':
    unittest.main()

