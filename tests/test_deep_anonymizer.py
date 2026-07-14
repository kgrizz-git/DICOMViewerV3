"""
Unit tests for DeepDICOMAnonymizer and deep anonymizer profile.

Covers profile tag stripping, batch UID remapping, date shifting, private tag
removal, PS3.15 de-identification tags, and pydicom round-trip.
"""

from __future__ import annotations

import io
import os
import sys
import unittest
from datetime import datetime, timedelta

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import pydicom
from pydicom.dataset import Dataset, FileMetaDataset
from pydicom.sequence import Sequence as DicomSequence
from pydicom.tag import Tag
from pydicom.uid import ExplicitVRLittleEndian, generate_uid

from utils.deep_anonymizer import (
    DATE_ANCHOR,
    DATE_JITTER_MAX_DAYS,
    DeepAnonymizerOptions,
    DeepDICOMAnonymizer,
)
from utils.deep_anonymizer_profile import (
    DEEP_ANONYMIZER_PROFILE,
    INSTITUTION_SITE_TAGS,
    OPERATOR_PHYSICIAN_TAGS,
    STATION_DEVICE_TAGS,
    UID_TAGS,
)


def _synthetic_dataset(
    *,
    study_uid: str | None = None,
    series_uid: str | None = None,
    sop_uid: str | None = None,
    with_private: bool = False,
) -> Dataset:
    """Build a minimal synthetic dataset with identifying metadata."""
    ds = Dataset()
    ds.file_meta = FileMetaDataset()
    ds.file_meta.TransferSyntaxUID = ExplicitVRLittleEndian
    ds.is_little_endian = True
    ds.is_implicit_VR = False

    ds.PatientName = "Test^Patient"
    ds.PatientID = "PID123"
    ds.PatientBirthDate = "19800101"
    ds.StudyInstanceUID = study_uid or generate_uid()
    ds.SeriesInstanceUID = series_uid or generate_uid()
    ds.SOPInstanceUID = sop_uid or generate_uid()
    ds.SOPClassUID = "1.2.840.10008.5.1.4.1.1.2"
    ds.Modality = "CT"
    ds.StudyDate = "20240115"
    ds.SeriesDate = "20240115"
    ds.InstitutionName = "Test Hospital"
    ds.InstitutionAddress = "123 Main St"
    ds.StationName = "CT-ROOM-1"
    ds.Manufacturer = "ACME Scanner Co"
    ds.ManufacturerModelName = "Model X"
    ds.DeviceSerialNumber = "SN-9999"
    ds.OperatorsName = "Operator^One"
    ds.ReferringPhysicianName = "Ref^Doc"
    ds.StudyDescription = "Head CT"
    ds.SeriesDescription = "Axial"
    ds.ImageComments = "Patient visible on scout"
    ds.Rows = 2
    ds.Columns = 2
    ds.BitsAllocated = 16
    ds.BitsStored = 16
    ds.HighBit = 15
    ds.PixelRepresentation = 0
    ds.SamplesPerPixel = 1
    ds.PhotometricInterpretation = "MONOCHROME2"
    ds.PixelData = b"\x00\x01" * 4

    if with_private:
        ds.add_new(Tag(0x0011, 0x0010), "LO", "PRIVATE_CREATOR")
        ds.add_new(Tag(0x0011, 0x1001), "LO", "secret-value")

    return ds


class TestDeepAnonymizerProfile(unittest.TestCase):
    """Profile constant covers expected tag categories."""

    def test_profile_includes_institution_device_operator_uid_entries(self) -> None:
        profile_tags = {entry[0] for entry in DEEP_ANONYMIZER_PROFILE}
        for tag in INSTITUTION_SITE_TAGS + STATION_DEVICE_TAGS + OPERATOR_PHYSICIAN_TAGS:
            self.assertIn(tag, profile_tags)
        for tag in UID_TAGS:
            self.assertIn(tag, profile_tags)


class TestDeepDICOMAnonymizer(unittest.TestCase):
    """Deep anonymizer behavior on synthetic datasets."""

    def test_strips_identifying_tags_and_sets_ps315_tags(self) -> None:
        ds = _synthetic_dataset()
        options = DeepAnonymizerOptions()
        anon = DeepDICOMAnonymizer(options).anonymize_dataset(ds)

        self.assertEqual(anon.PatientName, "ANONYMIZED")
        self.assertEqual(anon.PatientID, "ANONYMIZED")
        # PatientBirthDate is Type 2 (PS3.15 action Z) → blanked, not deleted.
        self.assertIn("PatientBirthDate", anon)
        self.assertEqual(anon.PatientBirthDate, "")
        self.assertNotIn("InstitutionName", anon)
        self.assertNotIn("StationName", anon)
        self.assertNotIn("OperatorsName", anon)
        self.assertNotIn("ImageComments", anon)
        self.assertEqual(anon.PatientIdentityRemoved, "YES")
        self.assertIn("Deep anonymization", anon.DeidentificationMethod)

    def test_retain_device_identity_keeps_device_tags(self) -> None:
        """Retain Device Identity Option (§E.3.8) keeps device identity — including
        the serial number — and declares 113109."""
        ds = _synthetic_dataset()
        options = DeepAnonymizerOptions(retain_device_identity=True)
        anon = DeepDICOMAnonymizer(options).anonymize_dataset(ds)

        self.assertEqual(anon.Manufacturer, "ACME Scanner Co")
        self.assertEqual(anon.ManufacturerModelName, "Model X")
        self.assertEqual(anon.DeviceSerialNumber, "SN-9999")
        self.assertEqual(anon.StationName, "CT-ROOM-1")
        codes = {item.CodeValue for item in anon.DeidentificationMethodCodeSequence}
        self.assertIn("113109", codes)

    def test_strip_device_default_removes_and_no_retain_code(self) -> None:
        ds = _synthetic_dataset()
        anon = DeepDICOMAnonymizer(DeepAnonymizerOptions()).anonymize_dataset(ds)
        self.assertNotIn("DeviceSerialNumber", anon)
        self.assertNotIn("StationName", anon)
        codes = {item.CodeValue for item in anon.DeidentificationMethodCodeSequence}
        self.assertNotIn("113109", codes)

    def test_curated_physician_contact_tags_removed(self) -> None:
        ds = _synthetic_dataset()
        ds.add_new(Tag(0x0008, 0x0092), "ST", "1 Clinic Way")  # ReferringPhysicianAddress
        ds.add_new(Tag(0x0008, 0x0094), "SH", "555-1234")  # ReferringPhysicianTelephone
        ds.add_new(Tag(0x0008, 0x1048), "PN", "Record^Doc")  # PhysiciansOfRecord
        anon = DeepDICOMAnonymizer(DeepAnonymizerOptions()).anonymize_dataset(ds)
        self.assertNotIn(Tag(0x0008, 0x0092), anon)
        self.assertNotIn(Tag(0x0008, 0x0094), anon)
        self.assertNotIn(Tag(0x0008, 0x1048), anon)

    def test_identifying_tags_removed_from_nested_sequence_items(self) -> None:
        """Nested sequence items must not retain identifiers in de-identified output."""
        ds = _synthetic_dataset()
        nested = Dataset()
        nested.InstitutionName = "Nested Hospital"
        nested.StationName = "NESTED-CT-ROOM"
        nested.OperatorsName = "Nested^Operator"
        nested.ImageComments = "Free text with patient address"
        nested.AccessionNumber = "NESTED-ACC-123"
        ds.RequestAttributesSequence = [nested]

        anon = DeepDICOMAnonymizer(DeepAnonymizerOptions()).anonymize_dataset(ds)
        nested_anon = anon.RequestAttributesSequence[0]

        self.assertNotIn("InstitutionName", nested_anon)
        self.assertNotIn("StationName", nested_anon)
        self.assertNotIn("OperatorsName", nested_anon)
        self.assertNotIn("ImageComments", nested_anon)
        self.assertIn("AccessionNumber", nested_anon)
        self.assertEqual(nested_anon.AccessionNumber, "")

    def test_strips_sr_content_sequence_text_and_person_names(self) -> None:
        """SR narrative values can contain PHI and must be scrubbed recursively."""
        ds = _synthetic_dataset()
        ds.Modality = "SR"

        root_item = Dataset()
        root_item.ValueType = "TEXT"
        root_item.TextValue = "Patient John Doe reported a prior surgery."
        root_item.PersonName = "Reading^Physician"

        nested_item = Dataset()
        nested_item.ValueType = "PNAME"
        nested_item.PersonName = "Consulting^Doctor"
        root_item.ContentSequence = DicomSequence([nested_item])
        ds.ContentSequence = DicomSequence([root_item])

        anon = DeepDICOMAnonymizer(
            DeepAnonymizerOptions(date_shift=False, uid_remap=False)
        ).anonymize_dataset(ds)

        anon_root = anon.ContentSequence[0]
        self.assertNotIn(Tag(0x0040, 0xA160), anon_root)  # TextValue
        self.assertNotIn(Tag(0x0040, 0xA123), anon_root)  # PersonName
        self.assertNotIn(Tag(0x0040, 0xA123), anon_root.ContentSequence[0])

    def test_retain_institution_identity_keeps_and_declares(self) -> None:
        ds = _synthetic_dataset()
        anon = DeepDICOMAnonymizer(
            DeepAnonymizerOptions(retain_institution_identity=True)
        ).anonymize_dataset(ds)
        self.assertEqual(anon.InstitutionName, "Test Hospital")
        codes = {item.CodeValue for item in anon.DeidentificationMethodCodeSequence}
        self.assertIn("113112", codes)

    def test_retain_uids_skips_remap_and_declares_113110(self) -> None:
        study = generate_uid()
        ds = _synthetic_dataset(study_uid=study)
        anon = DeepDICOMAnonymizer(
            DeepAnonymizerOptions(retain_uids=True)
        ).anonymize_batch([ds])[0]
        # UID retained (not re-minted) ...
        self.assertEqual(str(anon.StudyInstanceUID), study)
        # ... and declared.
        codes = {item.CodeValue for item in anon.DeidentificationMethodCodeSequence}
        self.assertIn("113110", codes)

    def test_method_codes_basic_profile_and_date_mode(self) -> None:
        ds = _synthetic_dataset()
        # Default = shift → 113107, no 113106/113110/113109/113112.
        anon = DeepDICOMAnonymizer(DeepAnonymizerOptions()).anonymize_dataset(ds)
        codes = {item.CodeValue for item in anon.DeidentificationMethodCodeSequence}
        self.assertIn("113100", codes)
        self.assertIn("113107", codes)
        self.assertNotIn("113106", codes)
        # Coding scheme designator is DCM.
        for item in anon.DeidentificationMethodCodeSequence:
            self.assertEqual(item.CodingSchemeDesignator, "DCM")

    def test_method_codes_keep_dates_uses_113106(self) -> None:
        ds = _synthetic_dataset()
        anon = DeepDICOMAnonymizer(
            DeepAnonymizerOptions(date_shift=False, date_remove=False)
        ).anonymize_dataset(ds)
        codes = {item.CodeValue for item in anon.DeidentificationMethodCodeSequence}
        self.assertIn("113106", codes)
        self.assertNotIn("113107", codes)

    def test_method_codes_remove_dates_no_temporal_code(self) -> None:
        ds = _synthetic_dataset()
        anon = DeepDICOMAnonymizer(
            DeepAnonymizerOptions(date_remove=True)
        ).anonymize_dataset(ds)
        codes = {item.CodeValue for item in anon.DeidentificationMethodCodeSequence}
        self.assertNotIn("113106", codes)
        self.assertNotIn("113107", codes)

    def test_uid_remap_consistent_in_batch(self) -> None:
        study = generate_uid()
        series_a = generate_uid()
        series_b = generate_uid()
        ds1 = _synthetic_dataset(study_uid=study, series_uid=series_a)
        ds2 = _synthetic_dataset(study_uid=study, series_uid=series_b)

        options = DeepAnonymizerOptions(date_shift=False)
        results = DeepDICOMAnonymizer(options).anonymize_batch([ds1, ds2])

        self.assertEqual(results[0].StudyInstanceUID, results[1].StudyInstanceUID)
        self.assertNotEqual(results[0].StudyInstanceUID, study)
        self.assertNotEqual(results[0].SeriesInstanceUID, series_a)
        self.assertNotEqual(results[1].SeriesInstanceUID, series_b)
        self.assertNotEqual(results[0].SeriesInstanceUID, results[1].SeriesInstanceUID)

    def test_uid_remap_preserves_sop_class_and_standard_uids(self) -> None:
        """Regression: deep anonymize must NOT regenerate SOPClassUID / TransferSyntaxUID
        (DICOM-standard UIDs under 1.2.840.10008). It previously clobbered them, which
        breaks SOP-class dispatch and pylinac loading."""
        sop = generate_uid()
        series = generate_uid()
        study = generate_uid()
        ds = _synthetic_dataset(study_uid=study, series_uid=series, sop_uid=sop)
        orig_class = str(ds.SOPClassUID)
        orig_ts = str(ds.file_meta.TransferSyntaxUID)

        result = DeepDICOMAnonymizer(DeepAnonymizerOptions(date_shift=False)).anonymize_batch([ds])[0]

        # Standard UIDs preserved
        self.assertEqual(str(result.SOPClassUID), orig_class)
        self.assertEqual(str(result.file_meta.TransferSyntaxUID), orig_ts)
        # Instance identifiers still remapped (anonymization still works)
        self.assertNotEqual(str(result.SOPInstanceUID), sop)
        self.assertNotEqual(str(result.SeriesInstanceUID), series)
        self.assertNotEqual(str(result.StudyInstanceUID), study)

    def test_identifiers_blanked_not_deleted(self) -> None:
        """AccessionNumber/StudyID (PS3.15 action Z) are blanked, kept present."""
        ds = _synthetic_dataset()
        ds.AccessionNumber = "ACC123456"
        ds.StudyID = "STU-99"
        ds.RequestedProcedureID = "RP-7"

        result = DeepDICOMAnonymizer(DeepAnonymizerOptions()).anonymize_batch([ds])[0]

        self.assertIn("AccessionNumber", result)
        self.assertEqual(result.AccessionNumber, "")
        self.assertEqual(result.StudyID, "")
        self.assertEqual(result.RequestedProcedureID, "")

    def test_identifiers_blanked_even_when_strip_flags_off(self) -> None:
        """Identifier removal is part of the base profile — not gated by strip flags."""
        ds = _synthetic_dataset()
        ds.AccessionNumber = "ACC123456"
        options = DeepAnonymizerOptions(
            retain_institution_identity=True,
            retain_device_identity=True,
            strip_operators=False,
            strip_free_text=False,
            strip_private=False,
            uid_remap=False,
            date_shift=False,
        )
        result = DeepDICOMAnonymizer(options).anonymize_batch([ds])[0]
        self.assertEqual(result.AccessionNumber, "")

    def test_file_meta_sop_instance_uid_synced_after_remap(self) -> None:
        """PS3.15 E.1.1: File Meta MediaStorageSOPInstanceUID must follow the remap
        (else the original instance UID leaks + PS3.10 mismatch with 0008,0018)."""
        sop = generate_uid()
        ds = _synthetic_dataset(sop_uid=sop)
        ds.file_meta.MediaStorageSOPInstanceUID = sop
        ds.file_meta.MediaStorageSOPClassUID = ds.SOPClassUID

        result = DeepDICOMAnonymizer(DeepAnonymizerOptions()).anonymize_batch([ds])[0]

        self.assertNotEqual(str(result.file_meta.MediaStorageSOPInstanceUID), sop)
        self.assertEqual(
            str(result.file_meta.MediaStorageSOPInstanceUID),
            str(result.SOPInstanceUID),
        )
        # Standard class UID preserved and consistent.
        self.assertEqual(
            str(result.file_meta.MediaStorageSOPClassUID), str(result.SOPClassUID)
        )

    def test_file_meta_identifying_tags_removed(self) -> None:
        ds = _synthetic_dataset()
        ds.file_meta.SourceApplicationEntityTitle = "SITE_PACS_AE"
        result = DeepDICOMAnonymizer(DeepAnonymizerOptions()).anonymize_batch([ds])[0]
        self.assertNotIn(Tag(0x0002, 0x0016), result.file_meta)
        self.assertEqual(result.file_meta.ImplementationVersionName, "DICOMViewerV3")

    def test_file_meta_preamble_zeroed(self) -> None:
        ds = _synthetic_dataset()
        ds.preamble = b"\xAA" * 128
        result = DeepDICOMAnonymizer(DeepAnonymizerOptions()).anonymize_batch([ds])[0]
        self.assertEqual(result.preamble, b"\x00" * 128)

    def test_uid_remap_referential_integrity(self) -> None:
        """Referenced *instance* UIDs are remapped consistently with the instance they
        point to, while referenced *class* UIDs (standard) are preserved."""
        sop = generate_uid()
        ds = _synthetic_dataset(sop_uid=sop)
        ref_item = Dataset()
        ref_item.ReferencedSOPClassUID = "1.2.840.10008.5.1.4.1.1.2"  # standard
        ref_item.ReferencedSOPInstanceUID = sop  # points at this instance
        ds.ReferencedImageSequence = [ref_item]

        result = DeepDICOMAnonymizer(DeepAnonymizerOptions(date_shift=False)).anonymize_batch([ds])[0]
        out_ref = result.ReferencedImageSequence[0]

        # Referenced class UID preserved; referenced instance UID follows the remap
        self.assertEqual(str(out_ref.ReferencedSOPClassUID), "1.2.840.10008.5.1.4.1.1.2")
        self.assertNotEqual(str(out_ref.ReferencedSOPInstanceUID), sop)
        self.assertEqual(str(out_ref.ReferencedSOPInstanceUID), str(result.SOPInstanceUID))

    def test_date_shift_applies_when_uid_remap_enabled(self) -> None:
        """Regression: date shift must apply even when uid_remap=True (the default).

        Bug was: _apply_uid_remap ran before the StudyInstanceUID lookup into
        _study_date_offsets, so the lookup always returned 0 and no shift occurred.
        """
        study = generate_uid()
        ds = _synthetic_dataset(study_uid=study)
        ds.StudyDate = "20240115"

        options = DeepAnonymizerOptions()  # uid_remap=True, date_shift=True by default
        result = DeepDICOMAnonymizer(options).anonymize_batch([ds])[0]

        self.assertNotEqual(result.StudyDate, "20240115")
        # Must land near the fake 1900 anchor, not a recent-looking date.
        self.assertIn(result.StudyDate[:3], ("188", "189", "190"))

    def _assert_in_anchor_window(self, date_str: str) -> None:
        """Earliest batch date lands within [anchor - jitter_max, anchor]."""
        shifted = datetime.strptime(date_str, "%Y%m%d")
        earliest_possible = DATE_ANCHOR - timedelta(days=DATE_JITTER_MAX_DAYS)
        self.assertGreaterEqual(shifted, earliest_possible)
        self.assertLessEqual(shifted, DATE_ANCHOR)

    def test_date_shift_lands_earliest_near_1900(self) -> None:
        """The earliest StudyDate in the batch maps into the fake 1900 anchor window."""
        study = generate_uid()
        ds = _synthetic_dataset(study_uid=study)
        ds.StudyDate = "20240115"
        ds.SeriesDate = "20240115"

        options = DeepAnonymizerOptions(uid_remap=False)
        result = DeepDICOMAnonymizer(options).anonymize_batch([ds])[0]

        self._assert_in_anchor_window(result.StudyDate)
        # StudyDate and SeriesDate share the single batch offset.
        self.assertEqual(result.StudyDate, result.SeriesDate)

    def test_date_shift_preserves_relative_order_within_study(self) -> None:
        study = generate_uid()
        ds_early = _synthetic_dataset(study_uid=study)
        ds_early.StudyDate = "20240101"
        ds_late = _synthetic_dataset(study_uid=study)
        ds_late.StudyDate = "20240110"

        options = DeepAnonymizerOptions(
            uid_remap=False,
            retain_institution_identity=True,
            retain_device_identity=True,
            strip_operators=False,
            strip_free_text=False,
            strip_private=False,
        )
        results = DeepDICOMAnonymizer(options).anonymize_batch([ds_early, ds_late])

        d0 = datetime.strptime(results[0].StudyDate, "%Y%m%d")
        d1 = datetime.strptime(results[1].StudyDate, "%Y%m%d")
        # Earliest lands in the anchor window; the 9-day gap is preserved.
        self._assert_in_anchor_window(results[0].StudyDate)
        self.assertEqual((d1 - d0).days, 9)

    def test_date_shift_preserves_relative_timing_across_studies(self) -> None:
        """A single batch-wide offset preserves gaps between *different* studies,
        anchoring the earliest study near 1900."""
        study_a = generate_uid()
        study_b = generate_uid()
        ds_a = _synthetic_dataset(study_uid=study_a)
        ds_a.StudyDate = "20240110"  # later study, listed first
        ds_b = _synthetic_dataset(study_uid=study_b)
        ds_b.StudyDate = "20240101"  # earliest in the batch

        options = DeepAnonymizerOptions(uid_remap=False)
        results = DeepDICOMAnonymizer(options).anonymize_batch([ds_a, ds_b])

        d_a = datetime.strptime(results[0].StudyDate, "%Y%m%d")
        d_b = datetime.strptime(results[1].StudyDate, "%Y%m%d")
        # Earliest (study B) anchored near 1900; study A keeps its +9 day gap.
        self._assert_in_anchor_window(results[1].StudyDate)
        self.assertEqual((d_a - d_b).days, 9)

    def test_date_shift_jitter_varies_across_batches(self) -> None:
        """Jitter is random per batch, so the same input rarely maps to a fixed date.

        Guards the structural-leak fix: the anchor must not be a constant 1900-01-01."""
        seen = set()
        for _ in range(25):
            ds = _synthetic_dataset()
            ds.StudyDate = "20240115"
            result = DeepDICOMAnonymizer(
                DeepAnonymizerOptions(uid_remap=False)
            ).anonymize_batch([ds])[0]
            seen.add(result.StudyDate)
        # With a ~10-year jitter window, 25 draws should yield several distinct anchors.
        self.assertGreater(len(seen), 1)

    def test_date_remove_blanks_dates_but_keeps_elements(self) -> None:
        """Remove-dates blanks DA/DT values (PS3.15 'Z') without deleting the tags,
        so Type-2 attributes stay present-but-empty and the file stays conformant."""
        ds = _synthetic_dataset()
        ds.StudyDate = "20240115"
        ds.SeriesDate = "20240115"
        ds.PatientBirthDate = "19800101"
        ds.AcquisitionDateTime = "20240115120000"

        options = DeepAnonymizerOptions(date_remove=True, uid_remap=False)
        anon = DeepDICOMAnonymizer(options).anonymize_batch([ds])[0]

        # Elements remain present (not deleted) but hold zero-length values.
        self.assertIn("StudyDate", anon)
        self.assertEqual(anon.StudyDate, "")
        self.assertEqual(anon.SeriesDate, "")
        self.assertEqual(anon.AcquisitionDateTime, "")

    def test_date_remove_takes_precedence_over_shift(self) -> None:
        ds = _synthetic_dataset()
        ds.StudyDate = "20240115"

        options = DeepAnonymizerOptions(date_remove=True, date_shift=True, uid_remap=False)
        anon = DeepDICOMAnonymizer(options).anonymize_batch([ds])[0]

        self.assertEqual(anon.StudyDate, "")

    def test_date_remove_keeps_file_loadable(self) -> None:
        """Blanked dates round-trip through pydicom without error."""
        ds = _synthetic_dataset()
        ds.StudyDate = "20240115"
        anon = DeepDICOMAnonymizer(
            DeepAnonymizerOptions(date_remove=True)
        ).anonymize_dataset(ds)

        buffer = io.BytesIO()
        anon.save_as(buffer, write_like_original=False)
        buffer.seek(0)
        reloaded = pydicom.dcmread(buffer)
        self.assertEqual(reloaded.StudyDate, "")

    def test_strip_private_removes_odd_group_tags(self) -> None:
        ds = _synthetic_dataset(with_private=True)
        options = DeepAnonymizerOptions(
            uid_remap=False,
            date_shift=False,
            retain_institution_identity=True,
            retain_device_identity=True,
            strip_operators=False,
            strip_free_text=False,
        )
        anon = DeepDICOMAnonymizer(options).anonymize_dataset(ds)
        for elem in anon:
            self.assertEqual(elem.tag.group % 2, 0, f"Private tag remained: {elem.tag}")

    def test_pydicom_round_trip(self) -> None:
        ds = _synthetic_dataset(with_private=True)
        anon = DeepDICOMAnonymizer(DeepAnonymizerOptions()).anonymize_dataset(ds)

        buffer = io.BytesIO()
        anon.save_as(buffer, write_like_original=False)
        buffer.seek(0)
        reloaded = pydicom.dcmread(buffer)

        self.assertEqual(reloaded.PatientIdentityRemoved, "YES")
        self.assertEqual(reloaded.PatientName, "ANONYMIZED")
        self.assertIn("PixelData", reloaded)


if __name__ == "__main__":
    unittest.main()
