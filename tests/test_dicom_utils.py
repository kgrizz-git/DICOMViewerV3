"""
Unit tests for DICOM utility functions (utils.dicom_utils).

Tests pure functions: format_distance, pixels_to_mm, mm_to_pixels,
is_patient_tag, get_patient_tag_keywords. Does not require DICOM files.
Runnable with pytest or unittest.
"""

import unittest
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from utils.dicom_utils import (
    format_distance,
    pixels_to_mm,
    mm_to_pixels,
    is_patient_tag,
    get_patient_tag_keywords,
)


class TestFormatDistance(unittest.TestCase):
    """Tests for format_distance."""

    def test_no_pixel_spacing_returns_pixels(self):
        self.assertEqual(format_distance(10.0, None), "10.0 pixels")
        self.assertEqual(format_distance(0.0, None), "0.0 pixels")

    def test_with_pixel_spacing_small_mm(self):
        # 5 pixels * 0.5 mm/pixel = 2.5 mm -> "2.50 mm"
        self.assertEqual(format_distance(5.0, (0.5, 0.5), dimension=0), "2.50 mm")

    def test_with_pixel_spacing_large_mm(self):
        # 20 pixels * 1.0 mm/pixel = 20 mm -> "20.0 mm"
        self.assertEqual(format_distance(20.0, (1.0, 1.0), dimension=0), "20.0 mm")


class TestPixelsToMm(unittest.TestCase):
    """Tests for pixels_to_mm."""

    def test_none_spacing_returns_none(self):
        self.assertIsNone(pixels_to_mm(10.0, None))

    def test_dimension_0_uses_row_spacing(self):
        self.assertEqual(pixels_to_mm(10.0, (0.5, 1.0), dimension=0), 5.0)

    def test_dimension_1_uses_column_spacing(self):
        self.assertEqual(pixels_to_mm(10.0, (0.5, 1.0), dimension=1), 10.0)

    def test_invalid_dimension_returns_none(self):
        self.assertIsNone(pixels_to_mm(10.0, (0.5, 0.5), dimension=2))


class TestMmToPixels(unittest.TestCase):
    """Tests for mm_to_pixels."""

    def test_none_spacing_returns_none(self):
        self.assertIsNone(mm_to_pixels(5.0, None))

    def test_dimension_0_uses_row_spacing(self):
        self.assertEqual(mm_to_pixels(5.0, (0.5, 1.0), dimension=0), 10.0)

    def test_dimension_1_uses_column_spacing(self):
        self.assertEqual(mm_to_pixels(10.0, (0.5, 1.0), dimension=1), 10.0)

    def test_invalid_dimension_returns_none(self):
        self.assertIsNone(mm_to_pixels(5.0, (0.5, 0.5), dimension=2))


class TestIsPatientTag(unittest.TestCase):
    """Tests for is_patient_tag."""

    def test_patient_group_true(self):
        self.assertTrue(is_patient_tag("(0010,0010)"))
        self.assertTrue(is_patient_tag("  (0010,0020)  "))

    def test_non_patient_false(self):
        self.assertFalse(is_patient_tag("(0008,0060)"))
        self.assertFalse(is_patient_tag("(0020,000D)"))

    def test_empty_or_invalid_false(self):
        self.assertFalse(is_patient_tag(""))
        self.assertFalse(is_patient_tag(None))


class TestGetPatientTagKeywords(unittest.TestCase):
    """Tests for get_patient_tag_keywords."""

    def test_returns_list(self):
        keywords = get_patient_tag_keywords()
        self.assertIsInstance(keywords, list)

    def test_contains_expected_keywords(self):
        keywords = get_patient_tag_keywords()
        self.assertIn("PatientName", keywords)
        self.assertIn("PatientID", keywords)
        self.assertIn("PatientBirthDate", keywords)
        self.assertIn("PatientSex", keywords)
        self.assertIn("PatientAge", keywords)
