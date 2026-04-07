"""
Unit tests for DICOM parser module.

Tests metadata parsing and tag extraction.
"""

import unittest
import sys
import os

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

import pydicom
from pydicom.dataset import Dataset
from pydicom.sequence import Sequence

from core.dicom_parser import DICOMParser
from core.tag_export_catalog import union_tags_across_datasets


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

    def test_get_all_tags_nested_kvp_in_shared_functional_groups(self):
        """Nested elements (functional groups) appear in the flat tag map."""
        ds = Dataset()
        ds.PatientName = "Test"
        sq = Sequence([Dataset()])
        sq[0].KVP = "120"
        ds.SharedFunctionalGroupsSequence = sq

        parser = DICOMParser(ds)
        tags = parser.get_all_tags(include_private=False)
        kvp_key = str(pydicom.tag.Tag("KVP"))
        self.assertIn(kvp_key, tags)
        self.assertEqual(tags[kvp_key]["value"], "120")

    def test_get_all_tags_duplicate_nested_first_wins(self):
        """When the same tag appears in multiple items, the first occurrence wins."""
        ds = Dataset()
        sq = Sequence([Dataset(), Dataset()])
        sq[0].KVP = "120"
        sq[1].KVP = "130"
        ds.SharedFunctionalGroupsSequence = sq

        parser = DICOMParser(ds)
        tags = parser.get_all_tags(include_private=False)
        kvp_key = str(pydicom.tag.Tag("KVP"))
        self.assertEqual(tags[kvp_key]["value"], "120")

    def test_get_all_tags_supplement_standard_tags(self):
        """Catalog can add standard tags missing from the dataset (empty value)."""
        ds = Dataset()
        parser = DICOMParser(ds)
        tags = parser.get_all_tags(
            include_private=False,
            supplement_standard_tags=True,
        )
        patient_name_key = str(pydicom.tag.Tag("PatientName"))
        self.assertIn(patient_name_key, tags)
        self.assertEqual(tags[patient_name_key]["value"], "")

    def test_union_tags_across_datasets_merges_keys(self):
        """Export dialog union: tags present only on different instances all appear."""
        ds_a = Dataset()
        ds_a.PatientName = "A"
        ds_b = Dataset()
        ds_b.KVP = "120"

        merged = union_tags_across_datasets(
            [ds_a, ds_b],
            include_private=False,
            supplement_standard_tags=False,
        )
        pn = str(pydicom.tag.Tag("PatientName"))
        kvp = str(pydicom.tag.Tag("KVP"))
        self.assertIn(pn, merged)
        self.assertIn(kvp, merged)
        self.assertEqual(merged[pn]["value"], "A")
        self.assertEqual(merged[kvp]["value"], "120")


if __name__ == '__main__':
    unittest.main()

