"""
Unit tests for the shared base ``DICOMAnonymizer`` (group-0010 patient stripping).

Covers PS3.15-aligned refinements (Phase 3 of the de-identification conformance
plan): sequence-recursive patient stripping and blank-don't-delete for Type-2
date attributes such as PatientBirthDate.
"""

from __future__ import annotations

import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from pydicom.dataset import Dataset
from pydicom.tag import Tag

from utils.dicom_anonymizer import DICOMAnonymizer


def _patient_dataset() -> Dataset:
    ds = Dataset()
    ds.PatientName = "Doe^Jane"
    ds.PatientID = "PID-123"
    ds.PatientBirthDate = "19800101"
    ds.Modality = "CT"
    return ds


class TestBaseAnonymizerPatientTags(unittest.TestCase):
    def test_text_tags_replaced_with_dummy(self) -> None:
        anon = DICOMAnonymizer().anonymize_dataset(_patient_dataset())
        self.assertEqual(anon.PatientName, "ANONYMIZED")
        self.assertEqual(anon.PatientID, "ANONYMIZED")
        # Non-patient tag untouched.
        self.assertEqual(anon.Modality, "CT")

    def test_birthdate_blanked_not_deleted(self) -> None:
        """PatientBirthDate (0010,0030) is Type 2 (PS3.15 action Z) — must stay
        present-but-empty, not be removed."""
        anon = DICOMAnonymizer().anonymize_dataset(_patient_dataset())
        self.assertIn("PatientBirthDate", anon)
        self.assertEqual(anon.PatientBirthDate, "")

    def test_nested_patient_phi_in_sequence_is_anonymized(self) -> None:
        ds = _patient_dataset()
        item = Dataset()
        item.PatientName = "Nested^Person"
        item.PatientID = "NESTED-ID"
        item.PatientBirthDate = "19751212"
        # A non-patient-group sequence that nonetheless contains patient PHI.
        ds.RequestAttributesSequence = [item]

        anon = DICOMAnonymizer().anonymize_dataset(ds)
        out_item = anon.RequestAttributesSequence[0]
        self.assertEqual(out_item.PatientName, "ANONYMIZED")
        self.assertEqual(out_item.PatientID, "ANONYMIZED")
        self.assertEqual(out_item.PatientBirthDate, "")

    def test_deeply_nested_patient_phi_is_anonymized(self) -> None:
        ds = _patient_dataset()
        inner = Dataset()
        inner.PatientName = "Deep^Person"
        middle = Dataset()
        middle.ReferencedImageSequence = [inner]
        ds.RequestAttributesSequence = [middle]

        anon = DICOMAnonymizer().anonymize_dataset(ds)
        out = anon.RequestAttributesSequence[0].ReferencedImageSequence[0]
        self.assertEqual(out.PatientName, "ANONYMIZED")

    def test_other_vr_patient_tag_removed(self) -> None:
        ds = _patient_dataset()
        # PatientWeight is DS (numeric text) — treated as text VR; use a binary-ish
        # patient tag to exercise the "other" removal branch.
        ds.add_new(Tag(0x0010, 0x21C0), "US", 4)  # PregnancyStatus
        anon = DICOMAnonymizer().anonymize_dataset(ds)
        self.assertNotIn(Tag(0x0010, 0x21C0), anon)

    def test_original_not_mutated(self) -> None:
        ds = _patient_dataset()
        DICOMAnonymizer().anonymize_dataset(ds)
        self.assertEqual(ds.PatientName, "Doe^Jane")
        self.assertEqual(ds.PatientBirthDate, "19800101")


if __name__ == "__main__":
    unittest.main()
