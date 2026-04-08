"""Tests for ``gui.metadata_table_model`` pure helpers."""

from __future__ import annotations

import unittest

from gui.metadata_table_model import (
    METADATA_VALUE_DISPLAY_MAX_LEN,
    filter_metadata_tags_by_search,
    format_metadata_value_for_tree,
    group_metadata_tags_sorted,
)


class TestMetadataTableModelHelpers(unittest.TestCase):
    def test_filter_by_name_substring(self) -> None:
        tags = {
            "(0010,0010)": {"name": "PatientName", "VR": "PN", "value": "Smith"},
            "(0010,0020)": {"name": "PatientID", "VR": "LO", "value": "123"},
        }
        out = filter_metadata_tags_by_search(tags, "patientid")
        self.assertEqual(list(out.keys()), ["(0010,0020)"])

    def test_filter_empty_returns_same(self) -> None:
        tags = {"(0008,0020)": {"name": "StudyDate", "VR": "DA", "value": "20200101"}}
        self.assertIs(filter_metadata_tags_by_search(tags, ""), tags)

    def test_group_sorted_by_group_prefix(self) -> None:
        tags = {
            "(0010,0010)": {"name": "A", "VR": "PN", "value": "x"},
            "(0008,0016)": {"name": "B", "VR": "UI", "value": "y"},
        }
        grouped = group_metadata_tags_sorted(tags)
        self.assertEqual([g for g, _ in grouped], ["(0008", "(0010"])

    def test_format_truncates_long_value(self) -> None:
        long_s = "x" * (METADATA_VALUE_DISPLAY_MAX_LEN + 10)
        s = format_metadata_value_for_tree(long_s)
        self.assertEqual(len(s), METADATA_VALUE_DISPLAY_MAX_LEN)
        self.assertTrue(s.endswith("..."))

    def test_format_list_join(self) -> None:
        self.assertEqual(format_metadata_value_for_tree([1, 2]), "1, 2")


if __name__ == "__main__":
    unittest.main()
