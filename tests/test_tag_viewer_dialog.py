"""
Targeted tests for DICOM tag viewer dialog readability.
"""

from __future__ import annotations

import time

import pydicom
from pydicom.dataset import Dataset
from pydicom.sequence import Sequence
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import QDialog, QTreeWidgetItem

from gui.dialogs.tag_viewer_dialog import TagViewerDialog


class _FakeHistoryManager:
    def is_tag_edited(self, _dataset: Dataset, tag: str) -> bool:
        return tag == "(0010,0010)"


class _FakeParser:
    def __init__(self, tags: dict[str, dict[str, str]]) -> None:
        self._tags = tags

    def get_all_tags(
        self,
        include_private: bool,
        privacy_mode: bool,
        include_sequences: bool = False,
    ) -> dict[str, dict[str, str]]:
        return self._tags


def test_edited_tag_uses_readable_accent_tinted_highlight(qapp) -> None:
    dialog = TagViewerDialog()
    dialog.dataset = Dataset()
    dialog.dataset.PatientName = "Edited^Patient"
    dialog.history_manager = _FakeHistoryManager()
    tags = {
        "(0010,0010)": {
            "name": "PatientName",
            "VR": "PN",
            "value": "Edited^Patient",
        }
    }
    dialog.parser = _FakeParser(tags)  # type: ignore[assignment]

    dialog._populate_tags("")

    group = dialog.tree_widget.topLevelItem(0)
    item = group.child(0)
    assert item.background(0).color() != QColor(80, 50, 120)
    assert item.foreground(0).color() == QColor(0, 0, 0)


def _find_item_by_tag_str(root_item: QTreeWidgetItem, tag_str: str) -> QTreeWidgetItem | None:
    for i in range(root_item.childCount()):
        child = root_item.child(i)
        if child.data(0, Qt.ItemDataRole.UserRole) == tag_str:
            return child
        found = _find_item_by_tag_str(child, tag_str)
        if found is not None:
            return found
    return None


def _find_item_in_tree(tree_widget, tag_str: str) -> QTreeWidgetItem | None:
    for i in range(tree_widget.topLevelItemCount()):
        group_item = tree_widget.topLevelItem(i)
        if group_item.data(0, Qt.ItemDataRole.UserRole) == tag_str:
            return group_item
        found = _find_item_by_tag_str(group_item, tag_str)
        if found is not None:
            return found
    return None


def _dataset_with_nested_only_code_meaning() -> Dataset:
    """A dataset where ``(0008,0104)`` Code Meaning exists ONLY inside
    ``DeidentificationMethodCodeSequence`` — no root-level Code Meaning at all."""
    ds = Dataset()
    ds.PatientName = "Test^Patient"
    item = Dataset()
    item.CodeValue = "113100"
    item.CodingSchemeDesignator = "DCM"
    item.CodeMeaning = "Basic Application Confidentiality Profile"
    ds.DeidentificationMethodCodeSequence = Sequence([item])
    return ds


def test_nested_only_tag_row_is_editable_without_becoming_root_level(qapp) -> None:
    """Nested scalar rows become editable while remaining path-addressed."""
    dialog = TagViewerDialog()
    ds = _dataset_with_nested_only_code_meaning()
    code_meaning_tag = pydicom.tag.Tag("CodeMeaning")
    assert code_meaning_tag not in ds  # nested-only, confirmed before the edit attempt

    dialog.set_dataset(ds)
    dialog._populate_tags("")

    seq_tag_str = str(pydicom.tag.Tag("DeidentificationMethodCodeSequence"))
    code_meaning_str = str(code_meaning_tag)
    nested_key = f"{seq_tag_str}[0].{code_meaning_str}"

    item = _find_item_in_tree(dialog.tree_widget, nested_key)
    assert item is not None, "nested Code Meaning row should be present in Mode B"

    assert dialog._is_editable_item(item) is True
    assert code_meaning_tag not in ds


def test_nested_leaf_edit_uses_path_key_and_does_not_create_root_tag(qapp, monkeypatch) -> None:
    dialog = TagViewerDialog()
    ds = _dataset_with_nested_only_code_meaning()
    dialog.set_dataset(ds)

    class _AcceptingDialog:
        def __init__(self, *args, **kwargs) -> None:
            pass

        def exec(self):
            return QDialog.DialogCode.Accepted

        def get_value(self):
            return "Changed nested meaning"

    class _ExecutingUndoManager:
        def __init__(self) -> None:
            self.command = None

        def execute_command(self, command) -> None:
            self.command = command
            command.execute()

    undo_manager = _ExecutingUndoManager()
    dialog.undo_redo_manager = undo_manager
    monkeypatch.setattr("gui.dialogs.tag_viewer_dialog.TagEditDialog", _AcceptingDialog)

    seq_tag_str = str(pydicom.tag.Tag("DeidentificationMethodCodeSequence"))
    code_meaning_tag = pydicom.tag.Tag("CodeMeaning")
    nested_key = f"{seq_tag_str}[0].{code_meaning_tag!s}"
    item = _find_item_in_tree(dialog.tree_widget, nested_key)
    assert item is not None
    assert code_meaning_tag not in ds

    dialog._edit_tag_item(item)

    assert undo_manager.command is not None
    assert undo_manager.command.path_key == nested_key
    assert code_meaning_tag not in ds
    assert ds.DeidentificationMethodCodeSequence[0].CodeMeaning == "Changed nested meaning"


def test_sequence_parent_and_item_node_reject_edits(qapp) -> None:
    dialog = TagViewerDialog()
    ds = _dataset_with_nested_only_code_meaning()
    dialog.set_dataset(ds)
    dialog._populate_tags("")

    seq_tag_str = str(pydicom.tag.Tag("DeidentificationMethodCodeSequence"))
    item_node_key = f"{seq_tag_str}[0]"

    seq_item = _find_item_in_tree(dialog.tree_widget, seq_tag_str)
    item_node = _find_item_in_tree(dialog.tree_widget, item_node_key)

    assert seq_item is not None
    assert item_node is not None
    assert dialog._is_editable_item(seq_item) is False
    assert dialog._is_editable_item(item_node) is False

    # Group headers are also read-only (no tag_data at all).
    group_item = dialog.tree_widget.topLevelItem(0)
    assert dialog._is_editable_item(group_item) is False


def test_nested_patient_tag_is_blocked_by_privacy(qapp) -> None:
    dialog = TagViewerDialog()
    dialog.privacy_mode = True

    assert dialog._is_edit_blocked_by_privacy("(0012, 0064)[0].(0010, 0010)") is True


def test_root_level_scalar_tag_still_editable(qapp) -> None:
    """Sanity check for the gating logic itself: a genuine root-level scalar row
    must still pass ``_is_editable_item`` (Phase 2 removes nested editing only)."""
    dialog = TagViewerDialog()
    ds = _dataset_with_nested_only_code_meaning()
    dialog.set_dataset(ds)
    dialog._populate_tags("")

    patient_name_str = str(pydicom.tag.Tag("PatientName"))
    item = _find_item_in_tree(dialog.tree_widget, patient_name_str)
    assert item is not None
    assert dialog._is_editable_item(item) is True


def test_widget_population_perf_gate_enhanced_multiframe(qapp) -> None:
    """Perf gate (plan §"Row cap / eager vs lazy"): the parser is fast (24k rows in
    85ms), but constructing 24k QTreeWidgetItems is a separate cost the parser
    perf gate does not cover. Build the tree once for a synthetic 2000-frame
    enhanced dataset and time ONLY the widget-population step (tags are already
    cached by the priming ``set_dataset`` call, isolating Qt construction cost).

    This guards the child-indexing in ``_populate_tags``: resolving each parent's
    children by rescanning the tag dict is O(n²) and put this at ~19s. Eager
    population is only viable because the index makes it O(n).
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

    dialog = TagViewerDialog()
    dialog.set_dataset(ds)  # primes the parser cache (Mode B, ~24k rows)
    assert dialog._cached_tags is not None
    assert len(dialog._cached_tags) > 20000

    start = time.perf_counter()
    dialog._populate_tags("")
    elapsed_ms = (time.perf_counter() - start) * 1000

    print(
        f"\n[perf] tag_viewer_dialog widget population: {elapsed_ms:.1f} ms "
        f"for {len(dialog._cached_tags)} rows"
    )

    assert dialog.tree_widget.topLevelItemCount() > 0
    # What this gate is for is the O(n²) rescan, which put this step at ~19s. The budget
    # is set to catch that class of regression on any machine rather than to pin the
    # wall-clock of a fast one: a shared CI runner takes ~1s here where a dev laptop
    # takes ~250ms, so a 1s budget fails on load alone.
    assert elapsed_ms < 5000


def test_sequences_off_hides_contents_without_orphaning_them_into_other_groups(qapp) -> None:
    """Unchecking "Show Sequences" must hide sequence *contents*, not fall back to a
    flat Mode A parse.

    Mode A re-keys a sequence's leaves by occurrence and drops the SQ parent, so the
    nested Code Meaning resurfaced as a root-level row bucketed under "Group 0008" —
    detached from the de-identification sequence it actually belongs to. That is the
    ambiguity the sequence work exists to remove; it must not reappear when the box is
    unchecked.
    """
    dialog = TagViewerDialog()
    ds = _dataset_with_nested_only_code_meaning()
    dialog.set_dataset(ds)

    seq_tag_str = str(pydicom.tag.Tag("DeidentificationMethodCodeSequence"))
    code_meaning_str = str(pydicom.tag.Tag("CodeMeaning"))
    nested_key = f"{seq_tag_str}[0].{code_meaning_str}"

    dialog.show_sequences = False
    dialog._populate_tags("")

    # The SQ parent survives as a childless summary row. (A *code* sequence summarizes
    # as its code rather than "N item(s)" — that summary is the whole point of the
    # special-casing, so assert it verbatim.)
    seq_item = _find_item_in_tree(dialog.tree_widget, seq_tag_str)
    assert seq_item is not None, "SQ parent must stay visible when contents are hidden"
    assert seq_item.childCount() == 0
    assert seq_item.text(2) == "SQ"
    assert seq_item.text(3) == "113100 DCM: Basic Application Confidentiality Profile"

    # ...and nothing from inside it appears anywhere in the tree, under any key.
    assert _find_item_in_tree(dialog.tree_widget, nested_key) is None
    assert _find_item_in_tree(dialog.tree_widget, code_meaning_str) is None
    for i in range(dialog.tree_widget.topLevelItemCount()):
        assert dialog.tree_widget.topLevelItem(i).text(0) != "Group (0008"

    # Re-checking restores the full hierarchy from the same cached Mode B parse.
    dialog.show_sequences = True
    dialog._populate_tags("")
    assert _find_item_in_tree(dialog.tree_widget, nested_key) is not None


def test_sequences_off_search_cannot_resurrect_hidden_nested_rows(qapp) -> None:
    """A hidden nested row must not be reachable via search, nor drag its ancestors
    back into the tree as a match.

    Uses a plain (non-code) sequence deliberately: a code sequence's parent row
    summarizes as its code, so a search for the leaf's text would match the *parent*
    on its own merits and prove nothing about the leaf being hidden.
    """
    ds = Dataset()
    ds.PatientName = "Test^Patient"
    item = Dataset()
    item.ReferencedSOPInstanceUID = "1.2.826.0.1.3680043.8.498.99999"
    ds.SourceImageSequence = Sequence([item])

    dialog = TagViewerDialog()
    dialog.set_dataset(ds)
    dialog.show_sequences = False

    # The UID lives only on the nested leaf; the parent summarizes as "1 item(s)".
    dialog._populate_tags("1.2.826.0.1.3680043.8.498.99999")

    assert dialog.tree_widget.topLevelItemCount() == 0

    # With sequences on, the same search does reach it (through its ancestor chain).
    dialog.show_sequences = True
    dialog._populate_tags("1.2.826.0.1.3680043.8.498.99999")
    seq_tag_str = str(pydicom.tag.Tag("SourceImageSequence"))
    uid_key = f"{seq_tag_str}[0].{pydicom.tag.Tag('ReferencedSOPInstanceUID')}"
    assert _find_item_in_tree(dialog.tree_widget, uid_key) is not None
