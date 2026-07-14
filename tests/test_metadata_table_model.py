"""Tests for ``gui.metadata_table_model`` pure helpers."""

from __future__ import annotations

import unittest

from gui.metadata_table_model import (
    METADATA_VALUE_DISPLAY_MAX_LEN,
    filter_metadata_tags_by_search,
    format_metadata_value_for_tree,
    get_metadata_tag_children,
    group_metadata_tags_sorted,
)


def _mode_b_deid_sequence_tags() -> dict[str, dict[str, object]]:
    """Mode B rows for a De-identification Method Code Sequence with 3 items,
    mirroring the plan's worked example (``(0012,0064)`` with a matching item 3).
    """
    seq_key = "(0012, 0064)"
    return {
        "(0012, 0062)": {
            "name": "PatientIdentityRemoved",
            "VR": "CS",
            "value": "YES",
            "depth": 0,
            "parent_key": None,
            "item_index": None,
            "row_kind": "element",
        },
        seq_key: {
            "name": "De-identification Method Code Sequence",
            "VR": "SQ",
            "value": "3 item(s)",
            "depth": 0,
            "parent_key": None,
            "item_index": None,
            "row_kind": "sequence",
        },
        f"{seq_key}[0]": {
            "name": "Item 1",
            "VR": "",
            "value": "",
            "depth": 1,
            "parent_key": seq_key,
            "item_index": 0,
            "row_kind": "item",
        },
        f"{seq_key}[0].(0008, 0104)": {
            "name": "Code Meaning",
            "VR": "LO",
            "value": "Basic Application Confidentiality Profile",
            "depth": 2,
            "parent_key": f"{seq_key}[0]",
            "item_index": None,
            "row_kind": "element",
        },
        f"{seq_key}[1]": {
            "name": "Item 2",
            "VR": "",
            "value": "",
            "depth": 1,
            "parent_key": seq_key,
            "item_index": 1,
            "row_kind": "item",
        },
        f"{seq_key}[1].(0008, 0104)": {
            "name": "Code Meaning",
            "VR": "LO",
            "value": "Retain Longitudinal Temporal Information Full Dates Option",
            "depth": 2,
            "parent_key": f"{seq_key}[1]",
            "item_index": None,
            "row_kind": "element",
        },
        f"{seq_key}[2]": {
            "name": "Item 3",
            "VR": "",
            "value": "",
            "depth": 1,
            "parent_key": seq_key,
            "item_index": 2,
            "row_kind": "item",
        },
        f"{seq_key}[2].(0008, 0104)": {
            "name": "Code Meaning",
            "VR": "LO",
            "value": "Retain Device Identity Option",
            "depth": 2,
            "parent_key": f"{seq_key}[2]",
            "item_index": None,
            "row_kind": "element",
        },
        # A second, unrelated sequence whose child shares the same tag/keyword —
        # this is the ambiguity Mode B path keys resolve; it must NOT be pulled in
        # by a search that matches only the deid sequence's item 3.
        "(0018, 9346)": {
            "name": "CTDIPhantomTypeCodeSequence",
            "VR": "SQ",
            "value": "1 item(s)",
            "depth": 0,
            "parent_key": None,
            "item_index": None,
            "row_kind": "sequence",
        },
        "(0018, 9346)[0]": {
            "name": "Item 1",
            "VR": "",
            "value": "",
            "depth": 1,
            "parent_key": "(0018, 9346)",
            "item_index": 0,
            "row_kind": "item",
        },
        "(0018, 9346)[0].(0008, 0104)": {
            "name": "Code Meaning",
            "VR": "LO",
            "value": "IEC Body Dosimetry Phantom",
            "depth": 2,
            "parent_key": "(0018, 9346)[0]",
            "item_index": None,
            "row_kind": "element",
        },
    }


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

    # --- Phase 2: nested-row aware helpers -----------------------------------

    def test_group_sorted_excludes_nested_rows(self) -> None:
        """Mode B: only depth-0 rows get a group bucket; nested rows are excluded
        (they hang off their sequence/item parent instead)."""
        tags = _mode_b_deid_sequence_tags()
        grouped = group_metadata_tags_sorted(tags)
        group_keys = [g for g, _ in grouped]
        self.assertEqual(group_keys, ["(0012", "(0018"])

        group_0012 = dict(grouped[0][1])
        # Only the two depth-0 rows in group 0012: the scalar and the SQ parent.
        self.assertEqual(set(group_0012.keys()), {"(0012, 0062)", "(0012, 0064)"})

        group_0018 = dict(grouped[1][1])
        self.assertEqual(set(group_0018.keys()), {"(0018, 9346)"})

    def test_group_sorted_mode_a_dict_unaffected(self) -> None:
        """Mode A rows (no depth field) are all treated as depth 0 — behavior must
        match the pre-nesting output exactly."""
        tags = {
            "(0010,0010)": {"name": "A", "VR": "PN", "value": "x"},
            "(0008,0016)": {"name": "B", "VR": "UI", "value": "y"},
        }
        grouped = group_metadata_tags_sorted(tags)
        self.assertEqual([g for g, _ in grouped], ["(0008", "(0010"])

    def test_get_metadata_tag_children_ordered_by_item_index(self) -> None:
        tags = _mode_b_deid_sequence_tags()
        children = get_metadata_tag_children(tags, "(0012, 0064)")
        self.assertEqual(
            [key for key, _ in children],
            ["(0012, 0064)[0]", "(0012, 0064)[1]", "(0012, 0064)[2]"],
        )

    def test_get_metadata_tag_children_mode_a_dict_no_keyerror(self) -> None:
        """Mode A rows have no ``parent_key`` field; must not KeyError, and nothing
        has a parent so the result is empty."""
        tags = {"(0010,0010)": {"name": "A", "VR": "PN", "value": "x"}}
        self.assertEqual(get_metadata_tag_children(tags, "(0010,0010)"), [])

    def test_filter_retains_ancestor_chain_of_nested_match(self) -> None:
        """Searching text that only matches a nested leaf must retain the leaf's
        SQ parent and Item node too, and must NOT pull in the unrelated sequence."""
        tags = _mode_b_deid_sequence_tags()
        out = filter_metadata_tags_by_search(tags, "Retain Device Identity")

        self.assertIn("(0012, 0064)", out)
        self.assertIn("(0012, 0064)[2]", out)
        self.assertIn("(0012, 0064)[2].(0008, 0104)", out)

        # Sibling items and the unrelated CTDI phantom sequence are not retained.
        self.assertNotIn("(0012, 0064)[0]", out)
        self.assertNotIn("(0012, 0064)[0].(0008, 0104)", out)
        self.assertNotIn("(0018, 9346)", out)
        self.assertNotIn("(0018, 9346)[0]", out)
        self.assertNotIn("(0018, 9346)[0].(0008, 0104)", out)

    def test_filter_mode_a_dict_no_keyerror(self) -> None:
        """Mode A rows tolerate the ancestor-walk logic without KeyError."""
        tags = {
            "(0010,0010)": {"name": "PatientName", "VR": "PN", "value": "Smith"},
            "(0010,0020)": {"name": "PatientID", "VR": "LO", "value": "123"},
        }
        out = filter_metadata_tags_by_search(tags, "smith")
        self.assertEqual(list(out.keys()), ["(0010,0010)"])


if __name__ == "__main__":
    unittest.main()
