"""
Unit tests for utils.deid_provenance (PS3.15 / CID 7050 method codes).
"""

from __future__ import annotations

import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from pydicom.dataset import Dataset

from utils.deid_provenance import (
    apply_deidentification_provenance,
    build_method_codes,
)


class TestBuildMethodCodes(unittest.TestCase):
    def _values(self, **kwargs) -> set:
        return {c[0] for c in build_method_codes(**kwargs)}

    def test_basic_profile_always_present(self) -> None:
        self.assertIn("113100", self._values(date_mode="remove"))

    def test_date_modes(self) -> None:
        self.assertIn("113107", self._values(date_mode="shift"))
        self.assertIn("113106", self._values(date_mode="keep"))
        remove = self._values(date_mode="remove")
        self.assertNotIn("113106", remove)
        self.assertNotIn("113107", remove)

    def test_retain_flags_add_codes(self) -> None:
        vals = self._values(
            date_mode="shift",
            retain_device_identity=True,
            retain_institution_identity=True,
            retain_uids=True,
        )
        self.assertIn("113109", vals)
        self.assertIn("113112", vals)
        self.assertIn("113110", vals)

    def test_no_retain_flags_minimal(self) -> None:
        vals = self._values(date_mode="remove")
        self.assertEqual(vals, {"113100"})


class TestApplyProvenance(unittest.TestCase):
    def test_writes_identity_method_and_sequence(self) -> None:
        ds = Dataset()
        apply_deidentification_provenance(
            ds, method_text="Test method", date_mode="shift"
        )
        self.assertEqual(ds.PatientIdentityRemoved, "YES")
        self.assertEqual(ds.DeidentificationMethod, "Test method")
        items = ds.DeidentificationMethodCodeSequence
        self.assertTrue(any(i.CodeValue == "113100" for i in items))
        for i in items:
            self.assertEqual(i.CodingSchemeDesignator, "DCM")
            self.assertTrue(i.CodeMeaning)


if __name__ == "__main__":
    unittest.main()
