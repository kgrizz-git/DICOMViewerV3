"""Tests for ``utils.undo_redo_tag_commands`` and re-export from ``undo_redo``."""

from __future__ import annotations

import unittest

from pydicom import Dataset
from pydicom.tag import Tag

from utils.undo_redo import TagEditCommand as TagEditCommandReexport
from utils.undo_redo_tag_commands import TagEditCommand


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


if __name__ == "__main__":
    unittest.main()
