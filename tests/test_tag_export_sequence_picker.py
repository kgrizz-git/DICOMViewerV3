"""
Phase 5 (sequence tag viewer plan) — selectable sequence leaves in the export
picker.

Phase 4 exported an SQ parent as a single summary cell and dropped every
nested (``depth > 0``) row from the union. For a *code* sequence the summary
carries real content; for every other sequence it is ``"1 item(s)"`` — data-
shaped but empty. Phase 5 lets the user pick individual nested leaves as their
own export columns instead of widening the summary. These tests cover:

- a selected nested leaf exports the instance's real value, not "N item(s)";
- ``SourceImageSequence[0].ReferencedSOPInstanceUID`` differing per instance is
  bucketed varying (the case that exposed the Phase 4 gap);
- recursive checkbox propagation (check down, tri-state up, any depth);
- the picker builds a 24k-leaf tree without hanging, and the large-sequence
  warning fires only for sequences over the threshold;
- instances with unequal item counts export without a spurious column/crash.
"""

from __future__ import annotations

import csv
import os
import tempfile
import time

from pydicom.dataset import Dataset
from pydicom.sequence import Sequence
from pydicom.tag import Tag
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QMessageBox

from core.tag_export_analysis_service import analyze_tag_variations
from core.tag_export_union import union_tags_across_datasets
from core.tag_export_writer import write_csv_files
from gui.dialogs.tag_export_dialog import (
    LARGE_SEQUENCE_LEAF_THRESHOLD,
    TagExportDialog,
)


def _seq_tag() -> str:
    return str(Tag("SourceImageSequence"))


def _ref_uid_tag() -> str:
    return str(Tag("ReferencedSOPInstanceUID"))


def _nested_leaf_key(item_index: int = 0) -> str:
    return f"{_seq_tag()}[{item_index}].{_ref_uid_tag()}"


def _instance_with_source_image(sop_uid: str) -> Dataset:
    ref = Dataset()
    ref.ReferencedSOPClassUID = "1.2.840.10008.5.1.4.1.1.2"
    ref.ReferencedSOPInstanceUID = sop_uid
    ds = Dataset()
    ds.PatientName = "Same^Patient"
    ds.SourceImageSequence = Sequence([ref])
    return ds


class TestNestedLeafExportsRealValue:
    def test_selected_nested_leaf_exports_real_value_not_item_count(self) -> None:
        ds = _instance_with_source_image("1.2.3.4.5")
        studies = {"study1": {"series1": [ds]}}
        selected_series = {"study1": {"series1": [0]}}
        leaf_key = _nested_leaf_key(0)
        selected_tags = [leaf_key]
        variation = {"series1": {"varying_tags": [], "constant_tags": selected_tags}}

        with tempfile.TemporaryDirectory() as tmp:
            out_path = os.path.join(tmp, "out.csv")
            write_csv_files(
                out_path,
                variation,
                studies,
                selected_series,
                selected_tags,
                include_private=False,
                include_missing_selected_tags=True,
                include_sequences=True,
            )
            with open(out_path, newline="", encoding="utf-8") as f:
                rows = list(csv.reader(f))

        data_rows = [r for r in rows if len(r) >= 4 and r[0] == "All"]
        assert len(data_rows) == 1
        assert data_rows[0][1] == leaf_key
        # The real nested value, not a "N item(s)" / "1 item(s)" summary.
        assert data_rows[0][3] == "1.2.3.4.5"
        assert "item(s)" not in data_rows[0][3]

    def test_sq_parent_still_selectable_independently_for_summary_cell(self) -> None:
        """Selecting the SQ parent alongside its own leaf still yields the
        parent's summary cell — the two are independent export columns."""
        ds = _instance_with_source_image("1.2.3.4.5")
        studies = {"study1": {"series1": [ds]}}
        selected_series = {"study1": {"series1": [0]}}
        seq_tag = _seq_tag()
        leaf_key = _nested_leaf_key(0)
        selected_tags = [seq_tag, leaf_key]
        variation = {"series1": {"varying_tags": [], "constant_tags": selected_tags}}

        with tempfile.TemporaryDirectory() as tmp:
            out_path = os.path.join(tmp, "out.csv")
            write_csv_files(
                out_path,
                variation,
                studies,
                selected_series,
                selected_tags,
                include_private=False,
                include_missing_selected_tags=True,
                include_sequences=True,
            )
            with open(out_path, newline="", encoding="utf-8") as f:
                rows = list(csv.reader(f))

        data_rows = {r[1]: r[3] for r in rows if len(r) >= 4 and r[0] == "All"}
        assert data_rows[seq_tag] == "1 item(s)"
        assert data_rows[leaf_key] == "1.2.3.4.5"


class TestVariationAnalysisSeesNestedLeaves:
    """The exact case that exposed the Phase 4 gap: a nested leaf value that
    differs per instance must be bucketed varying, not silently constant."""

    def test_source_image_sequence_leaf_differing_per_instance_is_varying(self) -> None:
        datasets = [
            _instance_with_source_image("1.1"),
            _instance_with_source_image("1.2"),
            _instance_with_source_image("1.3"),
        ]
        studies = {"STUDY": {"SERIES": datasets}}
        selected_series = {"STUDY": {"SERIES": [0, 1, 2]}}
        leaf_key = _nested_leaf_key(0)
        selected_tags = [str(Tag("PatientName")), leaf_key]

        result = analyze_tag_variations(
            studies,
            selected_series,
            selected_tags,
            include_private=True,
            include_sequences=True,
        )
        analysis = result["SERIES"]
        assert leaf_key in analysis["varying_tags"]
        assert leaf_key not in analysis["constant_tags"]
        assert str(Tag("PatientName")) in analysis["constant_tags"]


class TestRecursiveCheckboxPropagation:
    def _dialog_with_two_item_sequence(self) -> tuple[TagExportDialog, str, list[str]]:
        item1 = Dataset()
        item1.CodeValue = "113100"
        item1.CodingSchemeDesignator = "DCM"
        item1.CodeMeaning = "Basic Application Confidentiality Profile"
        item2 = Dataset()
        item2.CodeValue = "113107"
        item2.CodingSchemeDesignator = "DCM"
        item2.CodeMeaning = "Retain Longitudinal Temporal Information Modified Dates Option"
        ds = Dataset()
        ds.DeidentificationMethodCodeSequence = Sequence([item1, item2])
        studies = {"study1": {"series1": [ds]}}
        dialog = TagExportDialog(studies=studies, config_manager=None)
        dialog.include_sequences_checkbox.setChecked(True)

        seq_tag = str(Tag("DeidentificationMethodCodeSequence"))
        code_meaning = str(Tag("CodeMeaning"))
        leaf_keys = [
            f"{seq_tag}[0].{code_meaning}",
            f"{seq_tag}[1].{code_meaning}",
        ]
        return dialog, seq_tag, leaf_keys

    def _find_item(self, dialog: TagExportDialog, tag_str: str):
        root = dialog.tags_tree.invisibleRootItem()
        for item in dialog._iter_all_tag_items(root):
            if item.data(0, Qt.ItemDataRole.UserRole) == tag_str:
                return item
        return None

    def test_checking_sequence_checks_all_leaves(self, qapp) -> None:
        dialog, seq_tag, leaf_keys = self._dialog_with_two_item_sequence()
        seq_item = self._find_item(dialog, seq_tag)
        assert seq_item is not None

        seq_item.setCheckState(0, Qt.CheckState.Checked)
        dialog._on_tag_selection_changed(seq_item, 0)

        for leaf_key in leaf_keys:
            leaf_item = self._find_item(dialog, leaf_key)
            assert leaf_item is not None
            assert leaf_item.checkState(0) == Qt.CheckState.Checked

        dialog._update_selected_tags()
        for leaf_key in leaf_keys:
            assert leaf_key in dialog.selected_tags

        dialog.deleteLater()

    def test_checking_some_but_not_all_leaves_leaves_ancestors_partial(self, qapp) -> None:
        dialog, seq_tag, leaf_keys = self._dialog_with_two_item_sequence()
        first_leaf = self._find_item(dialog, leaf_keys[0])
        assert first_leaf is not None

        first_leaf.setCheckState(0, Qt.CheckState.Checked)
        dialog._on_tag_selection_changed(first_leaf, 0)

        seq_item = self._find_item(dialog, seq_tag)
        assert seq_item is not None
        assert seq_item.checkState(0) == Qt.CheckState.PartiallyChecked

        # The group header ancestor is partial too (any depth, not just one level).
        group_item = seq_item.parent()
        while group_item.parent() is not None:
            group_item = group_item.parent()
        assert group_item.checkState(0) == Qt.CheckState.PartiallyChecked

        # The second leaf and the item node above it remain unchecked.
        second_leaf = self._find_item(dialog, leaf_keys[1])
        assert second_leaf is not None
        assert second_leaf.checkState(0) == Qt.CheckState.Unchecked

        dialog.deleteLater()

    def test_unchecking_a_leaf_after_checking_sequence_leaves_ancestor_partial(self, qapp) -> None:
        dialog, seq_tag, leaf_keys = self._dialog_with_two_item_sequence()
        seq_item = self._find_item(dialog, seq_tag)
        assert seq_item is not None
        seq_item.setCheckState(0, Qt.CheckState.Checked)
        dialog._on_tag_selection_changed(seq_item, 0)

        first_leaf = self._find_item(dialog, leaf_keys[0])
        assert first_leaf is not None
        first_leaf.setCheckState(0, Qt.CheckState.Unchecked)
        dialog._on_tag_selection_changed(first_leaf, 0)

        assert seq_item.checkState(0) == Qt.CheckState.PartiallyChecked
        second_leaf = self._find_item(dialog, leaf_keys[1])
        assert second_leaf is not None
        assert second_leaf.checkState(0) == Qt.CheckState.Checked

        dialog.deleteLater()


class TestLargeSequenceWarningAndPerf:
    @staticmethod
    def _synthetic_enhanced_multiframe_dataset(n_frames: int = 2000) -> Dataset:
        frames = []
        for frame_index in range(n_frames):
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
        return ds

    def test_picker_populates_24k_leaf_tree_without_hanging(self, qapp) -> None:
        ds = self._synthetic_enhanced_multiframe_dataset(2000)
        merged = union_tags_across_datasets(
            [ds], include_private=True, supplement_standard_tags=False, include_sequences=True
        )
        assert len(merged) > 20000

        dialog = TagExportDialog(studies={}, config_manager=None)
        start = time.perf_counter()
        dialog._render_tag_tree(merged)
        elapsed_ms = (time.perf_counter() - start) * 1000
        print(
            f"\n[perf] tag_export_dialog picker population: {elapsed_ms:.1f} ms "
            f"for {len(merged)} rows"
        )

        assert dialog.tags_tree.topLevelItemCount() > 0
        # Plan's budget: this must not be the ~19s O(n^2) per-parent rescan.
        # Allow headroom above 1s so CI runner jitter does not flake near the edge.
        assert elapsed_ms < 2000

        dialog.deleteLater()

    def test_large_sequence_shows_count_and_warns_on_expand(self, qapp, monkeypatch) -> None:
        ds = self._synthetic_enhanced_multiframe_dataset(2000)
        merged = union_tags_across_datasets(
            [ds], include_private=True, supplement_standard_tags=False, include_sequences=True
        )

        dialog = TagExportDialog(studies={}, config_manager=None)
        dialog._render_tag_tree(merged)

        seq_tag = str(Tag("PerFrameFunctionalGroupsSequence"))
        root = dialog.tags_tree.invisibleRootItem()
        seq_item = None
        for item in dialog._iter_all_tag_items(root):
            if item.data(0, Qt.ItemDataRole.UserRole) == seq_tag:
                seq_item = item
                break
        assert seq_item is not None

        # Collapsed by default, and the leaf count is stamped on the node.
        assert seq_item.isExpanded() is False
        leaf_count = seq_item.data(0, Qt.ItemDataRole.UserRole + 1)
        assert isinstance(leaf_count, int)
        assert leaf_count > LARGE_SEQUENCE_LEAF_THRESHOLD
        assert f"{leaf_count:,}" in seq_item.text(1)

        warnings: list[tuple[str, str]] = []
        monkeypatch.setattr(
            QMessageBox,
            "warning",
            lambda parent, title, text, *a, **kw: warnings.append((title, text)),
        )
        dialog._on_tag_tree_item_expanded(seq_item)
        assert len(warnings) == 1
        assert str(leaf_count) in warnings[0][1] or f"{leaf_count:,}" in warnings[0][1]

        dialog.deleteLater()

    def test_small_sequence_does_not_warn_on_expand(self, qapp, monkeypatch) -> None:
        item1 = Dataset()
        item1.CodeValue = "113100"
        item1.CodingSchemeDesignator = "DCM"
        item1.CodeMeaning = "Basic Application Confidentiality Profile"
        ds = Dataset()
        ds.DeidentificationMethodCodeSequence = Sequence([item1])
        merged = union_tags_across_datasets(
            [ds], include_private=True, supplement_standard_tags=False, include_sequences=True
        )

        dialog = TagExportDialog(studies={}, config_manager=None)
        dialog._render_tag_tree(merged)

        seq_tag = str(Tag("DeidentificationMethodCodeSequence"))
        root = dialog.tags_tree.invisibleRootItem()
        seq_item = None
        for item in dialog._iter_all_tag_items(root):
            if item.data(0, Qt.ItemDataRole.UserRole) == seq_tag:
                seq_item = item
                break
        assert seq_item is not None
        assert seq_item.data(0, Qt.ItemDataRole.UserRole + 1) is None

        warnings: list[tuple[str, str]] = []
        monkeypatch.setattr(
            QMessageBox,
            "warning",
            lambda parent, title, text, *a, **kw: warnings.append((title, text)),
        )
        dialog._on_tag_tree_item_expanded(seq_item)
        assert len(warnings) == 0

        dialog.deleteLater()


class TestUnequalItemCountsExportSafely:
    """Instances with fewer sequence items legitimately lack some path keys
    (e.g. ``[3]`` on a 2-item instance) — the existing missing-tag row, not a
    crash or a bogus blank-vs-present conflation."""

    @staticmethod
    def _instance_with_n_source_images(n: int) -> Dataset:
        refs = []
        for i in range(n):
            ref = Dataset()
            ref.ReferencedSOPClassUID = "1.2.840.10008.5.1.4.1.1.2"
            ref.ReferencedSOPInstanceUID = f"1.{i}"
            refs.append(ref)
        ds = Dataset()
        ds.SourceImageSequence = Sequence(refs)
        return ds

    def test_export_with_unequal_item_counts_has_no_crash_and_no_spurious_column(self) -> None:
        two_item_instance = self._instance_with_n_source_images(2)
        three_item_instance = self._instance_with_n_source_images(3)
        studies = {"study1": {"series1": [two_item_instance, three_item_instance]}}
        selected_series = {"study1": {"series1": [0, 1]}}

        # Index [2] exists only on the second (3-item) instance.
        leaf_key_present_on_both = _nested_leaf_key(0)
        leaf_key_present_on_one = _nested_leaf_key(2)
        selected_tags = [leaf_key_present_on_both, leaf_key_present_on_one]
        variation = {
            "series1": {"varying_tags": [], "constant_tags": selected_tags},
        }

        with tempfile.TemporaryDirectory() as tmp:
            out_path = os.path.join(tmp, "out.csv")
            # No exception raised despite the second instance lacking [2] on
            # the first row and the first instance lacking [2] entirely.
            write_csv_files(
                out_path,
                variation,
                studies,
                selected_series,
                selected_tags,
                include_private=False,
                include_missing_selected_tags=True,
                include_sequences=True,
            )
            with open(out_path, newline="", encoding="utf-8") as f:
                rows = list(csv.reader(f))

        data_rows = [r for r in rows if len(r) >= 4 and r[0] == "All"]
        # Exactly the two selected tags produce rows — no extra/spurious column.
        assert len(data_rows) == 2
        by_tag = {r[1]: r[3] for r in data_rows}
        assert by_tag[leaf_key_present_on_both] == "1.0"
        # [2] absent on the (first) instance used for the "constant" export —
        # missing-tag row, blank value, not a crash.
        assert by_tag[leaf_key_present_on_one] == ""

    def test_missing_index_on_varying_export_yields_blank_row_per_instance(self) -> None:
        two_item_instance = self._instance_with_n_source_images(2)
        three_item_instance = self._instance_with_n_source_images(3)
        studies = {"study1": {"series1": [two_item_instance, three_item_instance]}}
        selected_series = {"study1": {"series1": [0, 1]}}

        leaf_key_present_on_one = _nested_leaf_key(2)
        selected_tags = [leaf_key_present_on_one]
        variation = {
            "series1": {"varying_tags": selected_tags, "constant_tags": []},
        }

        with tempfile.TemporaryDirectory() as tmp:
            out_path = os.path.join(tmp, "out.csv")
            write_csv_files(
                out_path,
                variation,
                studies,
                selected_series,
                selected_tags,
                include_private=False,
                include_missing_selected_tags=True,
                include_sequences=True,
            )
            with open(out_path, newline="", encoding="utf-8") as f:
                rows = list(csv.reader(f))

        # "Instance " with the trailing space excludes the literal "Instance" header
        # row; the per-series banner starts with "Series".
        data_rows = [r for r in rows if len(r) >= 4 and r[0].startswith("Instance ")]
        # One row per selected instance: blank for the 2-item instance, real
        # value for the 3-item instance — no crash, no missing row.
        assert len(data_rows) == 2
        values = {r[0]: r[3] for r in data_rows}
        assert values["Instance 1"] == ""
        assert values["Instance 2"] == "1.2"
