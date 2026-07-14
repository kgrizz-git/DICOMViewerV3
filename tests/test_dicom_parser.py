"""
Unit tests for DICOM parser module.

Tests metadata parsing and tag extraction.
"""

import glob
import os
import sys
import time
import unittest

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

import pydicom
from pydicom.dataset import Dataset
from pydicom.sequence import Sequence

from core.dicom_parser import DICOMParser
from core.tag_export_union import union_tags_across_datasets

FIXTURES_DIR = os.path.join(os.path.dirname(__file__), "fixtures")

RDSR_FIXTURES_DIR = os.path.join(FIXTURES_DIR, "dicom_rdsr")


class TestDICOMParser(unittest.TestCase):
    """Test cases for DICOMParser."""

    def setUp(self):
        """Set up test fixtures."""
        self.parser = DICOMParser()

    def test_parser_initialization(self):
        """Test parser initialization."""
        self.assertIsNotNone(self.parser)
        self.assertIsNone(self.parser.dataset)

    def test_get_all_tags_no_dataset(self):
        """Test getting tags with no dataset."""
        tags = self.parser.get_all_tags()
        self.assertEqual(len(tags), 0)

    def test_get_tag_value_no_dataset(self):
        """Test getting tag value with no dataset."""
        value = self.parser.get_tag_value((0x0010, 0x0010))
        self.assertIsNone(value)

    def test_get_all_tags_nested_element_is_path_keyed_under_its_sequence(self):
        """A nested element is reachable only under its sequence's path, never at root.

        It used to be emitted flat at root level, keyed by its own tag number, which is
        what made a functional group's KVP indistinguishable from a real top-level KVP.
        """
        ds = Dataset()
        ds.PatientName = "Test"
        sq = Sequence([Dataset()])
        sq[0].KVP = "120"
        ds.SharedFunctionalGroupsSequence = sq

        parser = DICOMParser(ds)
        seq_key = str(pydicom.tag.Tag("SharedFunctionalGroupsSequence"))
        kvp_key = str(pydicom.tag.Tag("KVP"))
        nested_kvp_key = f"{seq_key}[0].{kvp_key}"

        tags = parser.get_all_tags(include_private=False, include_sequences=True)
        self.assertNotIn(kvp_key, tags, "nested KVP must not masquerade as a root tag")
        self.assertEqual(tags[nested_kvp_key]["value"], "120")
        self.assertEqual(tags[nested_kvp_key]["depth"], 2)

        # Contents off: the sequence is a childless summary row, and its KVP is gone.
        tags_off = parser.get_all_tags(include_private=False)
        self.assertIn(seq_key, tags_off)
        self.assertNotIn(nested_kvp_key, tags_off)
        self.assertNotIn(kvp_key, tags_off)

    def test_get_all_tags_duplicate_nested_tags_get_distinct_path_keys(self):
        """The same tag in two sequence items must not collide — both survive.

        The occurrence-suffix scheme ((gggg,eeee)#2) that used to disambiguate these is
        gone; a path key encodes the owning item, so neither value shadows the other.
        """
        ds = Dataset()
        sq = Sequence([Dataset(), Dataset()])
        sq[0].KVP = "120"
        sq[1].KVP = "130"
        ds.SharedFunctionalGroupsSequence = sq

        parser = DICOMParser(ds)
        tags = parser.get_all_tags(include_private=False, include_sequences=True)

        seq_key = str(pydicom.tag.Tag("SharedFunctionalGroupsSequence"))
        kvp_key = str(pydicom.tag.Tag("KVP"))
        self.assertEqual(tags[f"{seq_key}[0].{kvp_key}"]["value"], "120")
        self.assertEqual(tags[f"{seq_key}[1].{kvp_key}"]["value"], "130")
        self.assertNotIn(f"{kvp_key}#2", tags, "occurrence suffixes must be extinct")

    def test_get_all_tags_exports_deidentification_method_code_sequence(self):
        """PS3.15 provenance code sequence appears as a compact exportable row."""
        ds = Dataset()
        item_basic = Dataset()
        item_basic.CodeValue = "113100"
        item_basic.CodingSchemeDesignator = "DCM"
        item_basic.CodeMeaning = "Basic Application Confidentiality Profile"
        item_dates = Dataset()
        item_dates.CodeValue = "113107"
        item_dates.CodingSchemeDesignator = "DCM"
        item_dates.CodeMeaning = "Retain Longitudinal Temporal Information Modified Dates Option"
        ds.DeidentificationMethodCodeSequence = Sequence([item_basic, item_dates])

        parser = DICOMParser(ds)
        code_sequence_key = str(pydicom.tag.Tag("DeidentificationMethodCodeSequence"))

        # The SQ parent is emitted whether or not its contents are — it used to be
        # dropped outright when sequences were off, which is why a de-identified file
        # could show no (0012,0064) anywhere in the UI.
        for include_sequences in (False, True):
            tags = parser.get_all_tags(
                include_private=False, include_sequences=include_sequences
            )
            self.assertIn(code_sequence_key, tags)
            self.assertEqual(tags[code_sequence_key]["row_kind"], "sequence")

        # Its value is the compact CID 7050 summary in both cases.
        tags = parser.get_all_tags(include_private=False, include_sequences=True)
        self.assertIn(code_sequence_key, tags)
        self.assertEqual(tags[code_sequence_key]["VR"], "SQ")
        value = tags[code_sequence_key]["value"]
        self.assertIn(
            "113100 DCM: Basic Application Confidentiality Profile",
            value,
        )
        self.assertIn(
            "113107 DCM: Retain Longitudinal Temporal Information Modified Dates Option",
            value,
        )

    def test_get_all_tags_sequences_off_yields_childless_summary_row(self):
        """Sequences off hides a sequence's *contents*, not the sequence itself."""
        ds = Dataset()
        item = Dataset()
        item.KVP = "120"
        ds.SharedFunctionalGroupsSequence = Sequence([item])

        parser = DICOMParser(ds)
        tags = parser.get_all_tags(include_private=False)

        shared_fg_key = str(pydicom.tag.Tag("SharedFunctionalGroupsSequence"))
        self.assertIn(shared_fg_key, tags)
        self.assertEqual(tags[shared_fg_key]["value"], "1 item(s)")
        self.assertEqual(tags[shared_fg_key]["row_kind"], "sequence")
        self.assertEqual(tags[shared_fg_key]["depth"], 0)

        # No item nodes, no leaves — nothing hangs off it.
        self.assertEqual(
            [k for k in tags if k.startswith(f"{shared_fg_key}[")],
            [],
        )

    def test_get_all_tags_supplement_standard_tags(self):
        """Catalog can add standard tags missing from the dataset (empty value)."""
        ds = Dataset()
        parser = DICOMParser(ds)
        tags = parser.get_all_tags(
            include_private=False,
            supplement_standard_tags=True,
        )
        patient_name_key = str(pydicom.tag.Tag("PatientName"))
        self.assertIn(patient_name_key, tags)
        self.assertEqual(tags[patient_name_key]["value"], "")

    def test_no_row_anywhere_uses_an_occurrence_suffix_key(self):
        """Guards the deletion of the occurrence-keying scheme on real files.

        ``(gggg,eeee)#2`` keys existed only to disambiguate duplicate tag numbers pulled
        out of sequences and flattened to root. Path keys make them unreachable; an SR
        with a deep ContentSequence is the shape that used to generate them by the dozen.
        """
        fixture_files = sorted(glob.glob(os.path.join(RDSR_FIXTURES_DIR, "*.dcm")))
        self.assertTrue(fixture_files, "expected at least one .dcm fixture")

        for dcm_path in fixture_files:
            name = os.path.splitext(os.path.basename(dcm_path))[0]
            with self.subTest(fixture=name):
                parser = DICOMParser(pydicom.dcmread(dcm_path))
                for include_sequences in (False, True):
                    tags = parser.get_all_tags(
                        include_private=True, include_sequences=include_sequences
                    )
                    self.assertEqual([k for k in tags if "#" in k], [])
                    # And every row can state where it lives.
                    for row in tags.values():
                        self.assertIn("depth", row)
                        self.assertIn("row_kind", row)

    def test_get_all_tags_disambiguates_nested_code_meaning(self):
        """Worked example: the same nested tag under two different sequences resolves to
        distinct, correctly-parented path keys instead of colliding on an occurrence suffix."""
        ds = Dataset()

        deid_item_1 = Dataset()
        deid_item_1.CodeValue = "113100"
        deid_item_1.CodingSchemeDesignator = "DCM"
        deid_item_1.CodeMeaning = "Basic Application Confidentiality Profile"
        deid_item_2 = Dataset()
        deid_item_2.CodeValue = "113107"
        deid_item_2.CodingSchemeDesignator = "DCM"
        deid_item_2.CodeMeaning = "Retain Longitudinal Temporal Information Modified Dates Option"
        ds.DeidentificationMethodCodeSequence = Sequence([deid_item_1, deid_item_2])

        phantom_item = Dataset()
        phantom_item.CodeValue = "113691"
        phantom_item.CodingSchemeDesignator = "DCM"
        phantom_item.CodeMeaning = "IEC Body Dosimetry Phantom"
        ds.CTDIPhantomTypeCodeSequence = Sequence([phantom_item])

        parser = DICOMParser(ds)
        tags = parser.get_all_tags(include_private=False, include_sequences=True)

        deid_key = str(pydicom.tag.Tag("DeidentificationMethodCodeSequence"))
        phantom_key = str(pydicom.tag.Tag("CTDIPhantomTypeCodeSequence"))
        code_meaning_tag = str(pydicom.tag.Tag("CodeMeaning"))

        self.assertIn(deid_key, tags)
        self.assertEqual(tags[deid_key]["row_kind"], "sequence")
        self.assertEqual(tags[deid_key]["depth"], 0)

        deid_item1_key = f"{deid_key}[0]"
        deid_item2_key = f"{deid_key}[1]"
        phantom_item_key = f"{phantom_key}[0]"
        self.assertEqual(tags[deid_item1_key]["row_kind"], "item")
        self.assertEqual(tags[deid_item1_key]["parent_key"], deid_key)
        self.assertEqual(tags[deid_item1_key]["item_index"], 0)
        self.assertEqual(tags[deid_item1_key]["name"], "Item 1")

        deid_leaf1 = f"{deid_item1_key}.{code_meaning_tag}"
        deid_leaf2 = f"{deid_item2_key}.{code_meaning_tag}"
        phantom_leaf = f"{phantom_item_key}.{code_meaning_tag}"

        self.assertEqual(
            tags[deid_leaf1]["value"], "Basic Application Confidentiality Profile"
        )
        self.assertEqual(
            tags[deid_leaf2]["value"],
            "Retain Longitudinal Temporal Information Modified Dates Option",
        )
        # The CTDI phantom's Code Meaning must resolve under its own sequence, not the
        # de-identification one — this is the ambiguity Mode B's path keys fix.
        self.assertEqual(tags[phantom_leaf]["value"], "IEC Body Dosimetry Phantom")
        self.assertEqual(tags[phantom_leaf]["parent_key"], phantom_item_key)
        self.assertEqual(tags[deid_leaf1]["depth"], 2)

    def test_get_all_tags_mode_b_recursion_cap_emits_truncation_row(self):
        """A pathologically deep sequence nest is capped, not blown through the stack."""
        leaf = Dataset()
        leaf.PatientName = "Deep"
        current = leaf
        # Build 20 levels of Sequence-of-one-item-containing-a-sequence.
        for _ in range(20):
            wrapper = Dataset()
            wrapper.ReferencedImageSequence = Sequence([current])
            current = wrapper

        parser = DICOMParser(current)
        tags = parser.get_all_tags(include_private=False, include_sequences=True)

        truncated_rows = [row for row in tags.values() if row.get("row_kind") == "element"
                           and row.get("name") == "<truncated: max depth reached>"]
        self.assertTrue(truncated_rows, "expected a truncation row on a 20-deep nest")

    def test_get_all_tags_mode_b_perf_gate(self):
        """Mode B stays well under the 250ms budget on the largest available fixture."""
        fixture_files = sorted(glob.glob(os.path.join(RDSR_FIXTURES_DIR, "*.dcm")))
        self.assertTrue(fixture_files)
        largest = max(fixture_files, key=os.path.getsize)
        ds = pydicom.dcmread(largest)
        parser = DICOMParser(ds)

        start = time.perf_counter()
        parser.get_all_tags(include_private=True, include_sequences=True)
        elapsed_ms = (time.perf_counter() - start) * 1000
        self.assertLess(elapsed_ms, 250)

    def test_get_all_tags_mode_b_perf_gate_enhanced_multiframe(self):
        """Parsing enhanced per-frame functional groups stays linear in row count.

        The RDSR fixtures are small (~170 rows); this is the shape that actually
        produces tens of thousands of rows, and it is what decides whether the tag
        tree can be populated eagerly or must be built lazily on expand.

        The budget catches a super-linear regression, not a slow machine: a dev laptop
        parses this in ~85ms and a shared CI runner in ~500ms, so anything under a
        second is within the noise of where it runs.
        """
        frames = []
        for frame_index in range(2000):
            plane_position = Dataset()
            plane_position.ImagePositionPatient = [0.0, 0.0, float(frame_index)]
            pixel_measures = Dataset()
            pixel_measures.PixelSpacing = [0.5, 0.5]
            pixel_measures.SliceThickness = "1.0"
            frame_content = Dataset()
            frame_content.InStackPositionNumber = frame_index + 1
            frame_content.StackID = "1"

            frame = Dataset()
            frame.PlanePositionSequence = Sequence([plane_position])
            frame.PixelMeasuresSequence = Sequence([pixel_measures])
            frame.FrameContentSequence = Sequence([frame_content])
            frames.append(frame)

        ds = Dataset()
        ds.PerFrameFunctionalGroupsSequence = Sequence(frames)
        parser = DICOMParser(ds)

        start = time.perf_counter()
        tags = parser.get_all_tags(include_private=True, include_sequences=True)
        elapsed_ms = (time.perf_counter() - start) * 1000

        # Guard the guard: if this stops producing a big tree, the budget means nothing.
        self.assertGreater(len(tags), 20000)
        self.assertLess(elapsed_ms, 2000)

    def test_union_tags_across_datasets_merges_keys(self):
        """Export dialog union: tags present only on different instances all appear."""
        ds_a = Dataset()
        ds_a.PatientName = "A"
        ds_b = Dataset()
        ds_b.KVP = "120"

        merged = union_tags_across_datasets(
            [ds_a, ds_b],
            include_private=False,
            supplement_standard_tags=False,
        )
        pn = str(pydicom.tag.Tag("PatientName"))
        kvp = str(pydicom.tag.Tag("KVP"))
        self.assertIn(pn, merged)
        self.assertIn(kvp, merged)
        self.assertEqual(merged[pn]["value"], "A")
        self.assertEqual(merged[kvp]["value"], "120")


if __name__ == '__main__':
    unittest.main()
