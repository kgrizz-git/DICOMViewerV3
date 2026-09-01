"""
Unit tests for the shared base ``DICOMAnonymizer`` (group-0010 patient stripping).

Covers PS3.15-aligned refinements: sequence-recursive patient stripping and
blank-don't-delete for common Type-2 Patient Module attributes.
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
    ds.PatientSex = "F"
    ds.PatientAge = "044Y"
    ds.IssuerOfPatientID = "Example Hospital"
    ds.Modality = "CT"
    return ds


class TestBaseAnonymizerPatientTags(unittest.TestCase):
    def test_type_two_patient_tags_are_blanked_not_replaced_with_dummy(self) -> None:
        anon = DICOMAnonymizer().anonymize_dataset(_patient_dataset())
        for keyword in (
            "PatientName",
            "PatientID",
            "PatientBirthDate",
            "PatientSex",
        ):
            with self.subTest(keyword=keyword):
                self.assertIn(keyword, anon)
                self.assertEqual(getattr(anon, keyword), "")
        # Non-patient tag untouched.
        self.assertEqual(anon.Modality, "CT")

    def test_patient_age_is_removed(self) -> None:
        anon = DICOMAnonymizer().anonymize_dataset(_patient_dataset())
        self.assertNotIn("PatientAge", anon)

    def test_birthdate_blanked_not_deleted(self) -> None:
        """PatientBirthDate (0010,0030) is Type 2 (PS3.15 action Z) — must stay
        present-but-empty, not be removed."""
        anon = DICOMAnonymizer().anonymize_dataset(_patient_dataset())
        self.assertIn("PatientBirthDate", anon)
        self.assertEqual(anon.PatientBirthDate, "")

    def test_issuer_of_patient_id_and_other_patient_text_are_removed(self) -> None:
        ds = _patient_dataset()
        ds.PatientAddress = "1 Example Street"

        anon = DICOMAnonymizer().anonymize_dataset(ds)

        # PS3.15 Table E.1-1 action X: IssuerOfPatientID must be removed, not
        # replaced with a dummy. A generic text group-0010 tag follows the same
        # conservative remove path.
        self.assertNotIn("IssuerOfPatientID", anon)
        self.assertNotIn("PatientAddress", anon)

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
        self.assertEqual(out_item.PatientName, "")
        self.assertEqual(out_item.PatientID, "")
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
        self.assertEqual(out.PatientName, "")

    def test_other_vr_patient_tag_removed(self) -> None:
        ds = _patient_dataset()
        # PatientWeight is a numeric-text DS. It must be removed rather than
        # replaced by a text dummy that violates its VR.
        ds.PatientWeight = "75"
        ds.add_new(Tag(0x0010, 0x21C0), "US", 4)  # PregnancyStatus
        anon = DICOMAnonymizer().anonymize_dataset(ds)
        self.assertNotIn("PatientWeight", anon)
        self.assertNotIn(Tag(0x0010, 0x21C0), anon)

    def test_original_not_mutated(self) -> None:
        ds = _patient_dataset()
        DICOMAnonymizer().anonymize_dataset(ds)
        self.assertEqual(ds.PatientName, "Doe^Jane")
        self.assertEqual(ds.PatientBirthDate, "19800101")


if __name__ == "__main__":
    unittest.main()
