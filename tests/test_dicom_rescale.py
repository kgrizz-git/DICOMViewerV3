"""
Unit tests for core.dicom_rescale (rescale parameters and type inference).
"""

import os
import sys
import unittest

from pydicom.dataset import Dataset

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

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
            "US",
        )


if __name__ == "__main__":
    unittest.main()
