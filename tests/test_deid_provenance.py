"""Unit tests for scoped metadata-transformation records."""

from __future__ import annotations

import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from pydicom.dataset import Dataset

from utils.deid_provenance import apply_deidentification_provenance


class TestApplyProvenance(unittest.TestCase):
    def test_writes_method_and_removes_profile_assertions(self) -> None:
        ds = Dataset()
        ds.PatientIdentityRemoved = "YES"
        ds.DeidentificationMethodCodeSequence = []
        nested = Dataset()
        nested.PatientIdentityRemoved = "YES"
        nested.DeidentificationMethodCodeSequence = []
        ds.RequestAttributesSequence = [nested]
        apply_deidentification_provenance(ds, method_text="Test method")
        self.assertEqual(ds.DeidentificationMethod, "Test method")
        self.assertNotIn("PatientIdentityRemoved", ds)
        self.assertNotIn("DeidentificationMethodCodeSequence", ds)
        self.assertNotIn("PatientIdentityRemoved", ds.RequestAttributesSequence[0])
        self.assertNotIn(
            "DeidentificationMethodCodeSequence", ds.RequestAttributesSequence[0]
        )


if __name__ == "__main__":
    unittest.main()
