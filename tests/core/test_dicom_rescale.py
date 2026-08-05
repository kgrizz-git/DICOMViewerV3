"""
Unit tests for core.dicom_rescale (rescale parameters and type inference).
"""

import os
import sys
import unittest

from pydicom.dataset import Dataset

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "src"))

from core.dicom_rescale import infer_rescale_type


class TestInferRescaleType(unittest.TestCase):
    """Tests for infer_rescale_type."""

    def test_ct_with_nonstandard_intercept_returns_hu(self):
        ds = Dataset()
        ds.Modality = "CT"
        self.assertEqual(
            infer_rescale_type(ds, 1.0, 0.0, None),
            "HU",
        )

    def test_rescale_type_tag_wins(self):
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


class TestGetRescaleParameters(unittest.TestCase):
    """Tests for get_rescale_parameters."""

    def test_top_level_scalar_values(self):
        from core.dicom_rescale import get_rescale_parameters

        ds = Dataset()
        ds.RescaleSlope = 1.5
        ds.RescaleIntercept = -100.0
        ds.RescaleType = "HU"
        self.assertEqual(get_rescale_parameters(ds), (1.5, -100.0, "HU"))

    def test_top_level_list_values(self):
        from core.dicom_rescale import get_rescale_parameters

        ds = Dataset()
        ds.RescaleSlope = [1.5]
        ds.RescaleIntercept = [-100.0]
        ds.RescaleType = ["HU"]
        self.assertEqual(get_rescale_parameters(ds), (1.5, -100.0, "HU"))

    def test_shared_functional_groups_fallback(self):
        from core.dicom_rescale import get_rescale_parameters

        ds = Dataset()
        # Create Enhanced multi-frame functional groups
        pvt_item = Dataset()
        pvt_item.RescaleSlope = 2.0
        pvt_item.RescaleIntercept = 10.0
        pvt_item.RescaleType = "US"

        pvt_seq = [pvt_item]

        shared_item = Dataset()
        shared_item.PixelValueTransformationSequence = pvt_seq

        ds.SharedFunctionalGroupsSequence = [shared_item]

        self.assertEqual(get_rescale_parameters(ds), (2.0, 10.0, "US"))

    def test_per_frame_functional_groups_fallback(self):
        from core.dicom_rescale import get_rescale_parameters

        ds = Dataset()
        # Create Enhanced multi-frame functional groups in PerFrame
        pvt_item = Dataset()
        pvt_item.RescaleSlope = [2.5]
        pvt_item.RescaleIntercept = [5.0]
        pvt_item.RescaleType = ["OD"]

        pvt_seq = [pvt_item]

        per_frame_item = Dataset()
        per_frame_item.PixelValueTransformationSequence = pvt_seq

        ds.PerFrameFunctionalGroupsSequence = [per_frame_item]

        self.assertEqual(get_rescale_parameters(ds), (2.5, 5.0, "OD"))

    def test_empty_rescale_type_becomes_none(self):
        from core.dicom_rescale import get_rescale_parameters

        ds = Dataset()
        ds.RescaleSlope = 1.0
        ds.RescaleIntercept = 0.0
        ds.RescaleType = "   "
        self.assertEqual(get_rescale_parameters(ds), (1.0, 0.0, None))

    def test_exception_returns_nones(self):
        from core.dicom_rescale import get_rescale_parameters

        class ExplodingDataset:
            @property
            def RescaleSlope(self):
                raise RuntimeError("unreadable tag")

        self.assertEqual(get_rescale_parameters(ExplodingDataset()), (None, None, None))


if __name__ == "__main__":
    unittest.main()
