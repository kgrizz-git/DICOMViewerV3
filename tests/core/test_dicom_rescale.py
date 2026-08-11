"""
Unit tests for core.dicom_rescale (rescale parameters and type inference).
"""

import unittest

from pydicom.dataset import Dataset
from pydicom.sequence import Sequence

from core.dicom_rescale import (
    _get_pixel_value_transformation_item,
    _normalize_explicit_rescale_type,
    get_rescale_parameters,
    infer_rescale_type,
)


class TestNormalizeExplicitRescaleType(unittest.TestCase):
    """Tests for _normalize_explicit_rescale_type."""

    def test_none_returns_none(self):
        assert _normalize_explicit_rescale_type(None) is None

    def test_empty_returns_none(self):
        assert _normalize_explicit_rescale_type("") is None

    def test_whitespace_returns_none(self):
        assert _normalize_explicit_rescale_type("   ") is None

    def test_unspecified_returns_none(self):
        assert _normalize_explicit_rescale_type("UNSPECIFIED") is None

    def test_lowercase_unspecified_returns_none(self):
        assert _normalize_explicit_rescale_type("unspecified") is None

    def test_us_returns_none(self):
        assert _normalize_explicit_rescale_type("us") is None

    def test_hu_returns_hu(self):
        assert _normalize_explicit_rescale_type("HU") == "HU"


class TestGetPixelValueTransformationItem(unittest.TestCase):
    """Tests for _get_pixel_value_transformation_item."""

    def test_no_sequence_returns_none(self):
        assert _get_pixel_value_transformation_item(Dataset()) is None

    def test_shared_functional_groups(self):
        ds = Dataset()
        pvt = Dataset()
        pvt.RescaleSlope = 1.5
        shared = Dataset()
        shared.PixelValueTransformationSequence = Sequence([pvt])
        ds.SharedFunctionalGroupsSequence = Sequence([shared])
        assert _get_pixel_value_transformation_item(ds) == pvt

    def test_per_frame_functional_groups(self):
        ds = Dataset()
        pvt = Dataset()
        pvt.RescaleSlope = 2.0
        per_frame = Dataset()
        per_frame.PixelValueTransformationSequence = Sequence([pvt])
        ds.PerFrameFunctionalGroupsSequence = Sequence([per_frame])
        assert _get_pixel_value_transformation_item(ds) == pvt


class TestInferRescaleType(unittest.TestCase):
    """Tests for infer_rescale_type."""

    def test_ct_with_nonstandard_intercept_returns_hu(self):
        ds = Dataset()
        ds.Modality = "CT"
        self.assertEqual(
            infer_rescale_type(ds, 1.0, 0.0, None),
            "HU",
        )

    def test_display_none_rescale_type_falls_back_to_ct_hu(self):
        ds = Dataset()
        ds.Modality = "CT"
        self.assertEqual(
            infer_rescale_type(ds, 1.0, 0.0, "US"),
            "HU",
        )

    def test_unspecified_rescale_type_is_hidden_for_non_ct(self):
        ds = Dataset()
        ds.Modality = "MR"
        self.assertIsNone(
            infer_rescale_type(ds, 1.0, 0.0, "UNSPECIFIED"),
        )

    def test_meaningful_rescale_type_is_preserved(self):
        ds = Dataset()
        ds.Modality = "PT"
        self.assertEqual(
            infer_rescale_type(ds, 1.0, 0.0, "BQML"),
            "BQML",
        )

    def test_ct_no_slope_returns_none(self):
        ds = Dataset()
        ds.Modality = "CT"
        assert infer_rescale_type(ds, None, 0.0, "US") is None

    def test_non_ct_returns_none(self):
        ds = Dataset()
        ds.Modality = "MR"
        assert infer_rescale_type(ds, 1.0, 0.0, "US") is None

    def test_empty_rescale_type_non_ct_returns_none(self):
        ds = Dataset()
        ds.Modality = "MR"
        assert infer_rescale_type(ds, 1.0, 0.0, "") is None

    def test_empty_rescale_type_ct_infers_hu(self):
        ds = Dataset()
        ds.Modality = "CT"
        assert infer_rescale_type(ds, 1.0, 0.0, "") == "HU"

    def test_ct_with_both_slope_and_intercept(self):
        ds = Dataset()
        ds.Modality = "CT"
        assert infer_rescale_type(ds, 1.0, -1024.0, None) == "HU"

    def test_ct_missing_intercept_returns_none(self):
        ds = Dataset()
        ds.Modality = "CT"
        assert infer_rescale_type(ds, 1.0, None, None) is None

    def test_explicit_type_wins_over_modality(self):
        ds = Dataset()
        ds.Modality = "MR"
        assert infer_rescale_type(ds, 1.0, 0.0, "HU") == "HU"


class TestGetRescaleParameters(unittest.TestCase):
    """Tests for get_rescale_parameters."""

    def test_top_level_scalar_values(self):
        ds = Dataset()
        ds.RescaleSlope = 1.5
        ds.RescaleIntercept = -100.0
        ds.RescaleType = "HU"
        self.assertEqual(get_rescale_parameters(ds), (1.5, -100.0, "HU"))

    def test_top_level_list_values(self):
        ds = Dataset()
        ds.RescaleSlope = [1.5]
        ds.RescaleIntercept = [-100.0]
        ds.RescaleType = ["HU"]
        self.assertEqual(get_rescale_parameters(ds), (1.5, -100.0, "HU"))

    def test_missing_returns_none_tuple(self):
        ds = Dataset()
        assert get_rescale_parameters(ds) == (None, None, None)

    def test_shared_functional_groups_fallback(self):
        ds = Dataset()
        pvt_item = Dataset()
        pvt_item.RescaleSlope = 2.0
        pvt_item.RescaleIntercept = 10.0
        pvt_item.RescaleType = "US"
        shared_item = Dataset()
        shared_item.PixelValueTransformationSequence = [pvt_item]
        ds.SharedFunctionalGroupsSequence = [shared_item]
        self.assertEqual(get_rescale_parameters(ds), (2.0, 10.0, "US"))

    def test_per_frame_functional_groups_fallback(self):
        ds = Dataset()
        pvt_item = Dataset()
        pvt_item.RescaleSlope = [2.5]
        pvt_item.RescaleIntercept = [5.0]
        pvt_item.RescaleType = ["OD"]
        per_frame_item = Dataset()
        per_frame_item.PixelValueTransformationSequence = [pvt_item]
        ds.PerFrameFunctionalGroupsSequence = [per_frame_item]
        self.assertEqual(get_rescale_parameters(ds), (2.5, 5.0, "OD"))

    def test_empty_rescale_type_becomes_none(self):
        ds = Dataset()
        ds.RescaleSlope = 1.0
        ds.RescaleIntercept = 0.0
        ds.RescaleType = "   "
        self.assertEqual(get_rescale_parameters(ds), (1.0, 0.0, None))

    def test_exception_returns_nones(self):
        class ExplodingDataset:
            @property
            def RescaleSlope(self):
                raise RuntimeError("unreadable tag")

        self.assertEqual(get_rescale_parameters(ExplodingDataset()), (None, None, None))


if __name__ == "__main__":
    unittest.main()
