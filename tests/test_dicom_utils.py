"""
Unit tests for DICOM utility functions (utils.dicom_utils).

Tests pure functions: format_distance, pixels_to_mm, mm_to_pixels,
canonical_dicom_tag_string, is_patient_tag, get_patient_tag_keywords.
Does not require DICOM files.
Runnable with pytest or unittest.
"""

import os
import sys
import unittest
from types import SimpleNamespace

import numpy as np
from pydicom.dataset import Dataset
from pydicom.sequence import Sequence

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from utils.dicom_utils import (
    calculate_pixel_spacing_from_fov,
    canonical_dicom_tag_string,
    format_distance,
    get_composite_series_key,
    get_image_orientation,
    get_image_position,
    get_patient_tag_keywords,
    get_pixel_spacing,
    get_slice_location,
    get_slice_thickness,
    is_patient_tag,
    mm_to_pixels,
    pixel_to_patient_coordinates,
    pixels_to_mm,
)


def _functional_group_dataset(
    *,
    pixel_spacing=None,
    slice_thickness=None,
    spacing_between_slices=None,
    image_position=None,
    image_orientation=None,
    shared: bool = True,
) -> Dataset:
    dataset = Dataset()
    item = Dataset()
    if pixel_spacing is not None or slice_thickness is not None or spacing_between_slices is not None:
        pixel_measures = Dataset()
        if pixel_spacing is not None:
            pixel_measures.PixelSpacing = pixel_spacing
        if slice_thickness is not None:
            pixel_measures.SliceThickness = slice_thickness
        if spacing_between_slices is not None:
            pixel_measures.SpacingBetweenSlices = spacing_between_slices
        item.PixelMeasuresSequence = Sequence([pixel_measures])
    if image_position is not None:
        plane_position = Dataset()
        plane_position.ImagePositionPatient = image_position
        item.PlanePositionSequence = Sequence([plane_position])
    if image_orientation is not None:
        plane_orientation = Dataset()
        plane_orientation.ImageOrientationPatient = image_orientation
        item.PlaneOrientationSequence = Sequence([plane_orientation])
    if shared:
        dataset.SharedFunctionalGroupsSequence = Sequence([item])
    else:
        dataset.PerFrameFunctionalGroupsSequence = Sequence([item])
    return dataset


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


class TestCanonicalDicomTagString(unittest.TestCase):
    """Tests for canonical_dicom_tag_string (preset / import compatibility)."""

    def test_pydicom_style_with_space(self):
        self.assertEqual(
            canonical_dicom_tag_string("(0010, 0010)"), "(0010, 0010)"
        )

    def test_no_space_after_comma_matches_tree_keys(self):
        """Editors and older strings often omit the space pydicom uses in str(Tag)."""
        self.assertEqual(
            canonical_dicom_tag_string("(0010,0010)"), "(0010, 0010)"
        )

    def test_concatenated_hex(self):
        self.assertEqual(canonical_dicom_tag_string("00100010"), "(0010, 0010)")

    def test_whitespace_stripped(self):
        self.assertEqual(
            canonical_dicom_tag_string("  (0008,  0005 ) "), "(0008, 0005)"
        )

    def test_non_tag_returns_none(self):
        self.assertIsNone(canonical_dicom_tag_string("PatientName"))
        self.assertIsNone(canonical_dicom_tag_string(""))
        self.assertIsNone(canonical_dicom_tag_string(None))


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


class TestCalculatePixelSpacingFromFov(unittest.TestCase):
    def test_mr_row_phase_encoding_uses_percent_phase_fov(self):
        ds = Dataset()
        ds.Modality = "MR"
        ds.Rows = 80
        ds.Columns = 200
        ds.ReconstructionDiameter = 400
        ds.PercentPhaseFieldOfView = 50
        ds.InPlanePhaseEncodingDirection = "ROW"
        self.assertEqual(calculate_pixel_spacing_from_fov(ds), (2.5, 2.0))

    def test_mr_col_phase_encoding_uses_percent_phase_fov(self):
        ds = Dataset()
        ds.Modality = "MR"
        ds.Rows = 80
        ds.Columns = 200
        ds.ReconstructionDiameter = 400
        ds.PercentPhaseFieldOfView = 50
        ds.InPlanePhaseEncodingDirection = "COL"
        self.assertEqual(calculate_pixel_spacing_from_fov(ds), (5.0, 1.0))


class TestGetPixelSpacing(unittest.TestCase):
    def test_prefers_top_level_pixel_spacing_over_other_sources(self):
        ds = _functional_group_dataset(pixel_spacing=[3.0, 4.0])
        ds.PixelSpacing = [1.0, 2.0]
        ds.ImagerPixelSpacing = [5.0, 6.0]
        self.assertEqual(get_pixel_spacing(ds), (1.0, 2.0))

    def test_uses_functional_group_pixel_spacing_when_top_level_missing(self):
        ds = _functional_group_dataset(pixel_spacing=[1.5, 2.5])
        self.assertEqual(get_pixel_spacing(ds), (1.5, 2.5))

    def test_falls_back_to_imager_pixel_spacing_after_invalid_top_level(self):
        ds = SimpleNamespace(PixelSpacing=["bad", 2.0], ImagerPixelSpacing=[0.7, 0.8])
        self.assertEqual(get_pixel_spacing(ds), (0.7, 0.8))

    def test_falls_back_to_fov_heuristic(self):
        ds = Dataset()
        ds.Rows = 100
        ds.Columns = 200
        ds.ReconstructionDiameter = 400
        self.assertEqual(get_pixel_spacing(ds), (4.0, 2.0))


class TestGetSliceThickness(unittest.TestCase):
    def test_prefers_top_level_slice_thickness(self):
        ds = Dataset()
        ds.SliceThickness = "3.5"
        self.assertEqual(get_slice_thickness(ds), 3.5)

    def test_falls_back_to_functional_group_slice_thickness(self):
        ds = _functional_group_dataset(slice_thickness="2.25")
        self.assertEqual(get_slice_thickness(ds), 2.25)


class TestImageGeometryReaders(unittest.TestCase):
    def test_get_image_position_falls_back_to_functional_group(self):
        ds = _functional_group_dataset(image_position=[1.0, 2.0, 3.0])
        np.testing.assert_array_equal(get_image_position(ds), np.array([1.0, 2.0, 3.0]))

    def test_get_image_orientation_falls_back_to_functional_group(self):
        ds = _functional_group_dataset(image_orientation=[1.0, 0.0, 0.0, 0.0, 1.0, 0.0])
        row, col = get_image_orientation(ds)
        np.testing.assert_array_equal(row, np.array([1.0, 0.0, 0.0]))
        np.testing.assert_array_equal(col, np.array([0.0, 1.0, 0.0]))

    def test_get_slice_location_parses_string_and_invalid_returns_none(self):
        ds = Dataset()
        ds.SliceLocation = " 12.75 "
        self.assertEqual(get_slice_location(ds), 12.75)
        self.assertIsNone(get_slice_location(SimpleNamespace(SliceLocation="not-a-float")))


class TestPixelToPatientCoordinates(unittest.TestCase):
    def test_axial_orientation_uses_spacing_and_slice_thickness(self):
        ds = Dataset()
        ds.ImagePositionPatient = [10.0, 20.0, 30.0]
        ds.ImageOrientationPatient = [1.0, 0.0, 0.0, 0.0, 1.0, 0.0]
        ds.PixelSpacing = [2.0, 3.0]
        ds.SliceThickness = 1.5
        coords = pixel_to_patient_coordinates(ds, pixel_x=4, pixel_y=5, slice_index=2)
        self.assertEqual(coords, (22.0, 30.0, 33.0))

    def test_oblique_orientation_uses_cross_product_for_slice_normal(self):
        ds = Dataset()
        ds.ImagePositionPatient = [1.0, 2.0, 3.0]
        ds.ImageOrientationPatient = [0.0, 1.0, 0.0, 0.0, 0.0, 1.0]
        ds.PixelSpacing = [2.0, 4.0]
        ds.SpacingBetweenSlices = 5.0
        coords = pixel_to_patient_coordinates(ds, pixel_x=2, pixel_y=3, slice_index=1)
        self.assertEqual(coords, (6.0, 10.0, 9.0))

    def test_returns_none_when_required_geometry_is_missing(self):
        self.assertIsNone(pixel_to_patient_coordinates(Dataset(), pixel_x=1, pixel_y=1))


class TestGetCompositeSeriesKey(unittest.TestCase):
    def test_includes_trimmed_series_number_when_present(self):
        ds = Dataset()
        ds.SeriesInstanceUID = "1.2.3"
        ds.SeriesNumber = " 7 "
        self.assertEqual(get_composite_series_key(ds), "1.2.3_7")

    def test_returns_series_uid_when_series_number_missing_or_empty(self):
        ds = Dataset()
        ds.SeriesInstanceUID = "1.2.3"
        self.assertEqual(get_composite_series_key(ds), "1.2.3")
        ds.SeriesNumber = "   "
        self.assertEqual(get_composite_series_key(ds), "1.2.3")
