"""SR-style instances: organizer synthetic UIDs and metadata duplicate tag keys."""

import os
import sys
import unittest

from pydicom.dataset import Dataset, FileMetaDataset
from pydicom.sequence import Sequence
from pydicom.uid import ExplicitVRLittleEndian

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from core.dicom_organizer import DICOMOrganizer
from core.dicom_parser import DICOMParser


class TestOrganizerSyntheticUids(unittest.TestCase):
    def test_organizes_when_study_and_series_uid_missing(self):
        ds = Dataset()
        ds.SOPClassUID = "1.2.840.10008.5.1.4.1.1.88.11"
        ds.SOPInstanceUID = "1.2.3.4.5.6.7.8.9"
        ds.Modality = "SR"

        organizer = DICOMOrganizer()
        studies = organizer.organize([ds], file_paths=[__file__])

        self.assertEqual(len(studies), 1)
        study_uid = next(iter(studies))
        self.assertTrue(str(study_uid).startswith("2.25."))
        series_map = studies[study_uid]
        self.assertEqual(len(series_map), 1)
        series_key = next(iter(series_map))
        self.assertTrue(str(series_key).startswith("2.25."))
        self.assertEqual(len(series_map[series_key]), 1)
        self.assertEqual(str(ds.StudyInstanceUID), study_uid)
        self.assertIn("2.25.", str(ds.SeriesInstanceUID))

    def test_merge_batch_counts_series_when_uids_were_synthesized(self):
        ds = Dataset()
        ds.SOPClassUID = "1.2.840.10008.5.1.4.1.1.88.11"
        ds.SOPInstanceUID = "1.2.3.4.5.1"
        ds.Modality = "SR"

        organizer = DICOMOrganizer()
        result = organizer.merge_batch([ds], file_paths_input=[__file__], source_dir=os.path.dirname(__file__))

        self.assertEqual(result.added_file_count, 1)
        self.assertEqual(len(result.new_series) + len(result.appended_series), 1)


class TestParserDuplicateTags(unittest.TestCase):
    def test_content_sequence_duplicate_code_value_keys(self):
        ds = Dataset()
        ds.StudyInstanceUID = "1.2.3"
        ds.SeriesInstanceUID = "1.2.4"
        ds.SOPInstanceUID = "1.2.5"
        item1 = Dataset()
        item1.CodeValue = "CODE_A"
        item2 = Dataset()
        item2.CodeValue = "CODE_B"
        ds.ContentSequence = Sequence([item1, item2])

        parser = DICOMParser(ds)
        tags = parser.get_all_tags(include_private=False)

        code_keys = [k for k in tags if k.startswith("(0008, 0100)") or k.startswith("(0008,0100)")]
        self.assertGreaterEqual(len(code_keys), 2, msg=f"keys sample: {list(tags)[:30]}")

        values = {tags[k]["value"] for k in code_keys if isinstance(tags[k].get("value"), str)}
        self.assertIn("CODE_A", values)
        self.assertIn("CODE_B", values)


class TestParserFileMetaTags(unittest.TestCase):
    def test_file_meta_elements_merged_into_tag_map(self):
        ds = Dataset()
        ds.is_implicit_VR = False
        ds.is_little_endian = True
        ds.file_meta = FileMetaDataset()
        ds.file_meta.TransferSyntaxUID = ExplicitVRLittleEndian
        ds.file_meta.MediaStorageSOPClassUID = "1.2.840.10008.5.1.4.1.1.2"
        ds.PatientName = "Test^One"
        parser = DICOMParser(ds)
        tags = parser.get_all_tags(include_private=False)
        keys = list(tags.keys())
        self.assertTrue(
            any("0002" in k and "0010" in k for k in keys),
            msg=f"expected TransferSyntaxUID in keys, got sample: {keys[:25]}",
        )


if __name__ == "__main__":
    unittest.main()
