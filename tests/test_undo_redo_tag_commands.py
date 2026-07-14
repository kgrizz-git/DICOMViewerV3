"""Tests for ``utils.undo_redo_tag_commands`` and re-export from ``undo_redo``."""

from __future__ import annotations

import unittest

from pydicom import Dataset
from pydicom.sequence import Sequence
from pydicom.tag import Tag

from utils.undo_redo import TagEditCommand as TagEditCommandReexport
from utils.undo_redo import UndoRedoManager
from utils.undo_redo_tag_commands import TagEditCommand

DEID_SEQ = Tag(0x0012, 0x0064)
CODE_MEANING = Tag(0x0008, 0x0104)


def _dataset_with_two_nested_meanings(first="First", second="Second"):
    ds = Dataset()
    first_item = Dataset()
    first_item.add_new(CODE_MEANING, "LO", first)
    second_item = Dataset()
    second_item.add_new(CODE_MEANING, "LO", second)
    ds.add_new(DEID_SEQ, "SQ", Sequence([first_item, second_item]))
    return ds


class TestUndoRedoTagCommands(unittest.TestCase):
    def test_reexport_same_class(self) -> None:
        self.assertIs(TagEditCommand, TagEditCommandReexport)

    def test_execute_undo_value_change(self) -> None:
        ds = Dataset()
        ds.PatientID = "OLD"
        tag = Tag(0x0010, 0x0020)
        cmd = TagEditCommand(ds, tag, "OLD", "NEW", vr="LO")
        cmd.execute()
        self.assertEqual(ds.PatientID, "NEW")
        cmd.undo()
        self.assertEqual(ds.PatientID, "OLD")

    def test_delete_tag_undo_restores(self) -> None:
        ds = Dataset()
        ds.PatientID = "X"
        tag = Tag(0x0010, 0x0020)
        cmd = TagEditCommand(ds, tag, "X", None, vr="LO")
        cmd.execute()
        self.assertNotIn(tag, ds)
        cmd.undo()
        self.assertEqual(ds.PatientID, "X")

    def test_execute_undo_nested_value_change(self) -> None:
        ds = _dataset_with_two_nested_meanings()
        cmd = TagEditCommand(
            ds,
            CODE_MEANING,
            "display value should not be used",
            "Changed",
            vr="LO",
            path_key="(0012, 0064)[0].(0008, 0104)",
        )

        cmd.execute()
        self.assertEqual(ds[DEID_SEQ].value[0][CODE_MEANING].value, "Changed")
        cmd.undo()
        self.assertEqual(ds[DEID_SEQ].value[0][CODE_MEANING].value, "First")

    def test_same_tag_under_different_items_undo_independently(self) -> None:
        ds = _dataset_with_two_nested_meanings()
        first = TagEditCommand(
            ds,
            CODE_MEANING,
            "First",
            "Changed first",
            vr="LO",
            path_key="(0012, 0064)[0].(0008, 0104)",
        )
        second = TagEditCommand(
            ds,
            CODE_MEANING,
            "Second",
            "Changed second",
            vr="LO",
            path_key="(0012, 0064)[1].(0008, 0104)",
        )

        first.execute()
        second.execute()
        first.undo()

        self.assertEqual(ds[DEID_SEQ].value[0][CODE_MEANING].value, "First")
        self.assertEqual(ds[DEID_SEQ].value[1][CODE_MEANING].value, "Changed second")

    def test_nested_frame_wrapper_updates_and_undoes_both_graphs(self) -> None:
        original = _dataset_with_two_nested_meanings(first="Original old")
        wrapper = _dataset_with_two_nested_meanings(first="Wrapper old")
        wrapper._original_dataset = original
        cmd = TagEditCommand(
            wrapper,
            CODE_MEANING,
            "display value should not be used",
            "Changed",
            vr="LO",
            path_key="(0012, 0064)[0].(0008, 0104)",
        )

        cmd.execute()
        self.assertEqual(original[DEID_SEQ].value[0][CODE_MEANING].value, "Changed")
        self.assertEqual(wrapper[DEID_SEQ].value[0][CODE_MEANING].value, "Changed")

        cmd.undo()
        self.assertEqual(original[DEID_SEQ].value[0][CODE_MEANING].value, "Original old")
        self.assertEqual(wrapper[DEID_SEQ].value[0][CODE_MEANING].value, "Wrapper old")

    def test_unresolvable_nested_path_does_not_enter_undo_stack(self) -> None:
        ds = _dataset_with_two_nested_meanings()
        manager = UndoRedoManager()
        cmd = TagEditCommand(
            ds,
            CODE_MEANING,
            "First",
            "Changed",
            vr="LO",
            path_key="(0012, 0064)[4].(0008, 0104)",
        )

        with self.assertRaises(ValueError):
            manager.execute_command(cmd)

        self.assertEqual(manager.undo_stack, [])
        self.assertEqual(ds[DEID_SEQ].value[0][CODE_MEANING].value, "First")

    def test_root_undo_restores_raw_original_value_not_display_string(self) -> None:
        ds = Dataset()
        private_tag = Tag(0x7777, 0x0010)
        ds.add_new(private_tag, "UN", b"\x01\x02")
        cmd = TagEditCommand(
            ds,
            private_tag,
            "b'\\x01\\x02'",
            b"\x03\x04",
            vr="UN",
        )

        cmd.execute()
        self.assertEqual(ds[private_tag].value, b"\x03\x04")
        cmd.undo()
        self.assertEqual(ds[private_tag].value, b"\x01\x02")


if __name__ == "__main__":
    unittest.main()
