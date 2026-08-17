"""Focused TagExportDialog toggle/filter/preset list slice + UX improvements."""

from __future__ import annotations

from pathlib import Path
from unittest import mock

import pytest
from pydicom.dataset import Dataset
from pydicom.sequence import Sequence
from pydicom.tag import Tag
from PySide6.QtCore import Qt

from gui.dialogs import tag_export_dialog as _tag_export_dialog_mod
from gui.dialogs.tag_export_dialog import _ITEM_NO_PRESET, TagExportDialog
from utils.config_manager import ConfigManager


def _cm(tmp_path: Path) -> ConfigManager:
    cm = ConfigManager()
    cm.config_path = tmp_path / "cfg.json"
    cm.config = cm.default_config.copy()
    return cm


def _studies() -> dict:
    ds = Dataset()
    ds.SOPInstanceUID = "1.2.840.10008.10.20.0.1"
    ds.PatientID = "SYNTH01"
    ds.Modality = "CT"
    ds.SeriesDescription = "Axial"
    return {"1.2.840.10008.10.20.0.10": {"1.2.840.10008.10.20.0.20": [ds]}}


def _find_tag_item(dialog: TagExportDialog, tag_str: str):
    root = dialog.tags_tree.invisibleRootItem()
    for item in dialog._iter_all_tag_items(root):
        if item.data(0, Qt.ItemDataRole.UserRole) == tag_str:
            return item
    return None


def _first_exportable_leaves(dialog: TagExportDialog, limit: int = 3):
    leaves = list(dialog._iter_visible_exportable_leaves())
    assert len(leaves) >= limit
    return leaves[:limit]


def _visible_group_headers(dialog: TagExportDialog) -> list:
    """Visible top-level group headers (no tag string in UserRole)."""
    root = dialog.tags_tree.invisibleRootItem()
    out = []
    for i in range(root.childCount()):
        item = root.child(i)
        assert item.data(0, Qt.ItemDataRole.UserRole) is None
        if not item.isHidden():
            out.append(item)
    return out


@pytest.mark.qt
def test_construct_populates_series_and_tags(qapp, tmp_path) -> None:
    dlg = TagExportDialog(_studies(), config_manager=_cm(tmp_path))
    assert dlg.series_tree.topLevelItemCount() >= 1
    assert dlg.tags_tree.topLevelItemCount() >= 1
    dlg.reject()
    assert dlg.result() == int(dlg.DialogCode.Rejected)


@pytest.mark.qt
def test_tags_tree_has_qss_targetable_object_name(qapp, tmp_path) -> None:
    dlg = TagExportDialog(_studies(), config_manager=_cm(tmp_path))
    assert dlg.tags_tree.objectName() == "tag_export_tags_tree"
    dlg.close()


@pytest.mark.qt
def test_toggle_all_series_and_tags(qapp, tmp_path) -> None:
    dlg = TagExportDialog(_studies(), config_manager=_cm(tmp_path))
    dlg._toggle_all_series(True)
    study = dlg.series_tree.topLevelItem(0)
    assert study.child(0).checkState(0) == Qt.CheckState.Checked
    dlg._toggle_all_series(False)
    assert study.child(0).checkState(0) == Qt.CheckState.Unchecked

    dlg._toggle_all_tags(True)
    # Visible exportable leaves should be checked after toggle-all.
    leaves = list(dlg._iter_visible_exportable_leaves())
    assert leaves
    assert all(leaf.checkState(0) == Qt.CheckState.Checked for leaf in leaves)
    assert len(dlg.selected_tags) >= 1
    dlg.close()


@pytest.mark.qt
def test_filter_tags_hides_non_matches(qapp, tmp_path) -> None:
    dlg = TagExportDialog(_studies(), config_manager=_cm(tmp_path))
    before = dlg.tags_tree.topLevelItemCount()
    assert before >= 1
    dlg._filter_tags("Patient ID")
    visible_texts: list[str] = []
    for i in range(dlg.tags_tree.topLevelItemCount()):
        item = dlg.tags_tree.topLevelItem(i)
        if item.isHidden():
            continue
        visible_texts.append(f"{item.text(0)} {item.text(1)}")
        for j in range(item.childCount()):
            child = item.child(j)
            if not child.isHidden():
                visible_texts.append(f"{child.text(0)} {child.text(1)}")
    assert any("Patient ID" in text for text in visible_texts)
    # Unrelated groups (e.g. pixel data) should be hidden by the filter.
    assert any(item.isHidden() for i in range(dlg.tags_tree.topLevelItemCount())
               for item in [dlg.tags_tree.topLevelItem(i)])
    dlg._filter_tags("")
    assert dlg.tags_tree.topLevelItemCount() == before
    dlg.close()


@pytest.mark.qt
def test_load_presets_list_runs(qapp, tmp_path) -> None:
    cm = _cm(tmp_path)
    dlg = TagExportDialog(_studies(), config_manager=cm)
    dlg._load_presets_list()
    assert dlg.preset_combo is not None
    assert dlg.preset_combo.count() >= 1
    assert dlg.preset_combo.currentText() == _ITEM_NO_PRESET
    dlg.close()


@pytest.mark.qt
def test_top_select_all_checkbox_reflects_state(qapp, tmp_path) -> None:
    dlg = TagExportDialog(_studies(), config_manager=_cm(tmp_path))
    leaves = _first_exportable_leaves(dlg, 3)
    leaves[0].setCheckState(0, Qt.CheckState.Checked)
    dlg._on_tag_selection_changed(leaves[0], 0)
    assert dlg.select_all_tags_checkbox.checkState() == Qt.CheckState.PartiallyChecked

    dlg._toggle_all_tags(True)
    assert dlg.select_all_tags_checkbox.checkState() == Qt.CheckState.Checked

    dlg._toggle_all_tags(False)
    assert dlg.select_all_tags_checkbox.checkState() == Qt.CheckState.Unchecked
    dlg.close()


@pytest.mark.qt
def test_top_select_all_checkbox_toggles(qapp, tmp_path) -> None:
    dlg = TagExportDialog(_studies(), config_manager=_cm(tmp_path))
    dlg.select_all_tags_checkbox.setCheckState(Qt.CheckState.Checked)
    dlg._on_select_all_tag_checkbox(Qt.CheckState.Checked)
    leaves = list(dlg._iter_visible_exportable_leaves())
    assert leaves
    assert all(leaf.checkState(0) == Qt.CheckState.Checked for leaf in leaves)

    dlg.select_all_tags_checkbox.setCheckState(Qt.CheckState.Unchecked)
    dlg._on_select_all_tag_checkbox(Qt.CheckState.Unchecked)
    assert all(leaf.checkState(0) == Qt.CheckState.Unchecked for leaf in leaves)
    dlg.close()


@pytest.mark.qt
def test_top_select_all_click_after_partial_is_not_noop(qapp, tmp_path) -> None:
    """
    Qt enables tristate when PartiallyChecked is set; without a fix, the next
    user click from Unchecked lands on Partial and was previously ignored.
    """
    dlg = TagExportDialog(_studies(), config_manager=_cm(tmp_path))
    leaves = _first_exportable_leaves(dlg, 2)
    leaves[0].setCheckState(0, Qt.CheckState.Checked)
    dlg._on_tag_selection_changed(leaves[0], 0)
    assert dlg.select_all_tags_checkbox.checkState() == Qt.CheckState.PartiallyChecked

    dlg._toggle_all_tags(False)
    assert dlg.select_all_tags_checkbox.checkState() == Qt.CheckState.Unchecked
    assert dlg.select_all_tags_checkbox.isTristate() is False

    # Emulate the Qt click state machine (nextCheckState), then the signal handler.
    dlg.select_all_tags_checkbox.nextCheckState()
    dlg._on_select_all_tag_checkbox(dlg.select_all_tags_checkbox.checkState())
    visible = list(dlg._iter_visible_exportable_leaves())
    assert visible
    assert all(leaf.checkState(0) == Qt.CheckState.Checked for leaf in visible)
    assert dlg.select_all_tags_checkbox.checkState() == Qt.CheckState.Checked
    dlg.close()


@pytest.mark.qt
def test_top_select_all_respects_filter(qapp, tmp_path) -> None:
    dlg = TagExportDialog(_studies(), config_manager=_cm(tmp_path))
    all_leaves_before = list(dlg._iter_visible_exportable_leaves())
    assert len(all_leaves_before) >= 2

    dlg._filter_tags("Patient ID")
    visible = list(dlg._iter_visible_exportable_leaves())
    assert visible
    assert len(visible) < len(all_leaves_before)

    dlg._toggle_all_tags(True)
    for leaf in visible:
        assert leaf.checkState(0) == Qt.CheckState.Checked

    dlg._filter_tags("")
    assert dlg.select_all_tags_checkbox.checkState() == Qt.CheckState.PartiallyChecked
    dlg.close()


@pytest.mark.qt
def test_studies_collapsed_at_load(qapp, tmp_path) -> None:
    dlg = TagExportDialog(_studies(), config_manager=_cm(tmp_path))
    for i in range(dlg.series_tree.topLevelItemCount()):
        study = dlg.series_tree.topLevelItem(i)
        assert study.isExpanded() is False
        for j in range(study.childCount()):
            assert study.child(j).isExpanded() is False
    dlg.close()


@pytest.mark.qt
def test_preset_save_includes_hidden_checked_tags(qapp, tmp_path) -> None:
    cm = _cm(tmp_path)
    dlg = TagExportDialog(_studies(), config_manager=cm)
    leaves = _first_exportable_leaves(dlg, 2)
    tag_a = leaves[0].data(0, Qt.ItemDataRole.UserRole)
    tag_b = leaves[1].data(0, Qt.ItemDataRole.UserRole)
    leaves[0].setCheckState(0, Qt.CheckState.Checked)
    leaves[1].setCheckState(0, Qt.CheckState.Checked)
    dlg._update_selected_tags()

    dlg._filter_tags("Patient ID")
    # At least one of the checked tags may be hidden now; save must keep both.
    cm.save_tag_export_preset("keep-hidden", list(dlg.selected_tags))
    saved = cm.get_tag_export_presets()["keep-hidden"]
    assert tag_a in saved
    assert tag_b in saved

    dlg._filter_tags("")
    dlg._toggle_all_tags(False)
    dlg._load_preset_by_name("keep-hidden", show_feedback=False)
    assert tag_a in dlg.selected_tags
    assert tag_b in dlg.selected_tags
    dlg.close()


@pytest.mark.qt
def test_tag_count_label_updates(qapp, tmp_path) -> None:
    dlg = TagExportDialog(_studies(), config_manager=_cm(tmp_path))
    assert dlg.tag_count_label.text() == "No tags selected"

    leaves = _first_exportable_leaves(dlg, 2)
    leaves[0].setCheckState(0, Qt.CheckState.Checked)
    dlg._on_tag_selection_changed(leaves[0], 0)
    assert dlg.tag_count_label.text() == "1 tag selected"

    leaves[0].setCheckState(0, Qt.CheckState.Unchecked)
    dlg._on_tag_selection_changed(leaves[0], 0)
    assert dlg.tag_count_label.text() == "No tags selected"

    leaves[0].setCheckState(0, Qt.CheckState.Checked)
    leaves[1].setCheckState(0, Qt.CheckState.Checked)
    dlg._update_selected_tags()
    assert dlg.tag_count_label.text() == "2 tags selected"
    dlg.close()


@pytest.mark.qt
def test_save_current_preset_overwrites(qapp, tmp_path, monkeypatch) -> None:
    cm = _cm(tmp_path)
    dlg = TagExportDialog(_studies(), config_manager=cm)
    leaves = _first_exportable_leaves(dlg, 4)
    tag_a = leaves[0].data(0, Qt.ItemDataRole.UserRole)
    tag_b = leaves[1].data(0, Qt.ItemDataRole.UserRole)
    tag_c = leaves[2].data(0, Qt.ItemDataRole.UserRole)
    tag_d = leaves[3].data(0, Qt.ItemDataRole.UserRole)

    cm.save_tag_export_preset("X", [tag_a, tag_b])
    dlg._load_presets_list()
    assert dlg.preset_combo is not None
    idx = dlg.preset_combo.findText("X")
    assert idx >= 0
    dlg.preset_combo.setCurrentIndex(idx)

    dlg._toggle_all_tags(False)
    leaves[2].setCheckState(0, Qt.CheckState.Checked)
    leaves[3].setCheckState(0, Qt.CheckState.Checked)
    dlg._update_selected_tags()

    monkeypatch.setattr(
        "PySide6.QtWidgets.QMessageBox.information",
        lambda *a, **k: None,
    )
    dlg._save_current_preset()
    saved = cm.get_tag_export_presets()["X"]
    assert set(saved) == {tag_c, tag_d}
    dlg.close()


@pytest.mark.qt
def test_save_current_preset_no_selection_falls_back(qapp, tmp_path, monkeypatch) -> None:
    cm = _cm(tmp_path)
    dlg = TagExportDialog(_studies(), config_manager=cm)
    assert dlg.preset_combo is not None
    assert dlg.preset_combo.currentText() == _ITEM_NO_PRESET

    called = {"save_as": False}

    def _fake_save_preset() -> None:
        called["save_as"] = True

    monkeypatch.setattr(dlg, "_save_preset", _fake_save_preset)
    dlg._save_current_preset()
    assert called["save_as"] is True
    dlg.close()


@pytest.mark.qt
def test_auto_load_preset_on_text_activated(qapp, tmp_path, monkeypatch) -> None:
    cm = _cm(tmp_path)
    dlg = TagExportDialog(_studies(), config_manager=cm)
    leaves = _first_exportable_leaves(dlg, 1)
    tag = leaves[0].data(0, Qt.ItemDataRole.UserRole)
    cm.save_tag_export_preset("AutoLoad", [tag])
    dlg._load_presets_list()
    assert dlg.preset_combo is not None

    dlg._toggle_all_tags(False)
    before = list(dlg.selected_tags)

    # Index-only activated must NOT auto-load.
    idx = dlg.preset_combo.findText("AutoLoad")
    assert idx >= 0
    dlg.preset_combo.activated.emit(idx)
    assert dlg.selected_tags == before

    monkeypatch.setattr(
        "PySide6.QtWidgets.QMessageBox.information",
        lambda *a, **k: None,
    )
    dlg.preset_combo.textActivated.emit("AutoLoad")
    assert tag in dlg.selected_tags
    dlg.close()


@pytest.mark.qt
def test_programmatic_combo_change_no_auto_load(qapp, tmp_path) -> None:
    cm = _cm(tmp_path)
    dlg = TagExportDialog(_studies(), config_manager=cm)
    leaves = _first_exportable_leaves(dlg, 1)
    tag = leaves[0].data(0, Qt.ItemDataRole.UserRole)
    cm.save_tag_export_preset("Prog", [tag])
    dlg._load_presets_list()
    assert dlg.preset_combo is not None

    dlg._toggle_all_tags(False)
    before = list(dlg.selected_tags)
    idx = dlg.preset_combo.findText("Prog")
    assert idx >= 0
    dlg.preset_combo.setCurrentIndex(idx)
    assert dlg.selected_tags == before
    dlg.close()


@pytest.mark.qt
def test_checkbox_count_reset_after_rebuild(qapp, tmp_path) -> None:
    dlg = TagExportDialog(_studies(), config_manager=_cm(tmp_path))
    dlg._toggle_all_tags(True)
    assert dlg.select_all_tags_checkbox.checkState() == Qt.CheckState.Checked
    assert "tags selected" in dlg.tag_count_label.text() or dlg.tag_count_label.text() == "1 tag selected"

    dlg.private_tags_checkbox.setChecked(False)
    # Rebuild clears checks; checkbox/count must not stay stale as Checked/old count.
    assert dlg.select_all_tags_checkbox.checkState() == Qt.CheckState.Unchecked
    assert dlg.tag_count_label.text() == "No tags selected"
    dlg.close()


@pytest.mark.qt
def test_menu_export_tags_in_file_menu(qapp) -> None:
    from pathlib import Path as _Path

    menu_src = (
        _Path(__file__).resolve().parents[2]
        / "src"
        / "gui"
        / "main_window_menu_builder.py"
    ).read_text(encoding="utf-8")
    # Action definition after Save MPR (File export group) and before Tools.
    file_anchor = menu_src.index('QAction("Save MPR as DICOM')
    tools_anchor = menu_src.index("# --- Tools menu ---")
    export_def = menu_src.index('QAction("Export DICOM &Tags..."')
    assert file_anchor < export_def < tools_anchor


@pytest.mark.qt
def test_filter_preserves_independently_checked_sequence_parents(qapp, tmp_path) -> None:
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
    ds.PatientID = "SYNTH01"
    studies = {"study1": {"series1": [ds]}}

    cm = _cm(tmp_path)
    dlg = TagExportDialog(studies, config_manager=cm)
    dlg.include_sequences_checkbox.setChecked(True)

    seq_tag = str(Tag("DeidentificationMethodCodeSequence"))
    code_meaning = str(Tag("CodeMeaning"))
    leaf_key = f"{seq_tag}[0].{code_meaning}"

    seq_item = _find_tag_item(dlg, seq_tag)
    leaf_item = _find_tag_item(dlg, leaf_key)
    assert seq_item is not None
    assert leaf_item is not None

    # Independently check the sequence parent (summary column) without cascading
    # via _on_tag_selection_changed (which would force descendants).
    dlg.tags_tree.blockSignals(True)
    seq_item.setCheckState(0, Qt.CheckState.Checked)
    leaf_item.setCheckState(0, Qt.CheckState.Checked)
    dlg.tags_tree.blockSignals(False)
    dlg._update_selected_tags()
    assert seq_tag in dlg.selected_tags
    assert leaf_key in dlg.selected_tags

    dlg._filter_tags("CodeMeaning")
    assert seq_item.checkState(0) == Qt.CheckState.Checked
    dlg._update_selected_tags()
    assert seq_tag in dlg.selected_tags

    cm.save_tag_export_preset("seq-parent", list(dlg.selected_tags))
    reloaded = cm.get_tag_export_presets()["seq-parent"]
    assert seq_tag in reloaded

    # Reload must preserve the explicitly checked sequence parent (summary column)
    # rather than demoting it via _update_ancestors_check_state.
    dlg._load_preset_by_name("seq-parent", show_feedback=False)
    assert seq_item.checkState(0) == Qt.CheckState.Checked
    assert seq_tag in dlg.selected_tags
    dlg.close()


# --- Task A2: group-header tri-state after Select All / filter -----------------


@pytest.mark.qt
def test_toggle_all_checks_visible_group_headers(qapp, tmp_path) -> None:
    dlg = TagExportDialog(_studies(), config_manager=_cm(tmp_path))
    dlg._toggle_all_tags(True)
    headers = _visible_group_headers(dlg)
    assert headers
    for header in headers:
        assert header.checkState(0) == Qt.CheckState.Checked
    dlg.close()


@pytest.mark.qt
def test_deselect_all_unchecks_visible_group_headers(qapp, tmp_path) -> None:
    dlg = TagExportDialog(_studies(), config_manager=_cm(tmp_path))
    dlg._toggle_all_tags(True)
    dlg._toggle_all_tags(False)
    for header in _visible_group_headers(dlg):
        assert header.checkState(0) == Qt.CheckState.Unchecked
    dlg.close()


@pytest.mark.qt
def test_group_header_partial_after_single_leaf_unchecked(qapp, tmp_path) -> None:
    dlg = TagExportDialog(_studies(), config_manager=_cm(tmp_path))
    dlg._toggle_all_tags(True)
    headers = _visible_group_headers(dlg)
    assert headers
    target_group = None
    target_leaf = None
    for header in headers:
        visible_children = [
            header.child(i) for i in range(header.childCount())
            if not header.child(i).isHidden()
        ]
        if len(visible_children) >= 2:
            target_group = header
            target_leaf = visible_children[0]
            break
    assert target_group is not None
    target_leaf.setCheckState(0, Qt.CheckState.Unchecked)
    dlg._on_tag_selection_changed(target_leaf, 0)
    assert target_group.checkState(0) == Qt.CheckState.PartiallyChecked
    for header in headers:
        if header is target_group:
            continue
        assert header.checkState(0) == Qt.CheckState.Checked
    dlg.close()


@pytest.mark.qt
def test_group_header_stays_checked_after_leaf_click_when_leaves_all_checked(
    qapp, tmp_path
) -> None:
    """Leaf-click ancestor walk must use the same leaf aggregate as Select All."""
    dlg = TagExportDialog(_studies(), config_manager=_cm(tmp_path))
    dlg._toggle_all_tags(True)
    headers = _visible_group_headers(dlg)
    assert headers
    leaf = _first_exportable_leaves(dlg, 1)[0]
    dlg._on_tag_selection_changed(leaf, 0)
    for header in headers:
        assert header.checkState(0) == Qt.CheckState.Checked
    dlg.close()


@pytest.mark.qt
def test_select_all_checkbox_updates_visible_group_headers(qapp, tmp_path) -> None:
    dlg = TagExportDialog(_studies(), config_manager=_cm(tmp_path))
    dlg._on_select_all_tag_checkbox(Qt.CheckState.Checked)
    for header in _visible_group_headers(dlg):
        assert header.checkState(0) == Qt.CheckState.Checked
    dlg.close()


@pytest.mark.qt
def test_toggle_all_preserves_independent_sequence_parent_checks(qapp, tmp_path) -> None:
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
    ds.PatientID = "SYNTH01"
    studies = {"study1": {"series1": [ds]}}

    dlg = TagExportDialog(studies, config_manager=_cm(tmp_path))
    dlg.include_sequences_checkbox.setChecked(True)
    seq_tag = str(Tag("DeidentificationMethodCodeSequence"))
    seq_item = _find_tag_item(dlg, seq_tag)
    assert seq_item is not None

    dlg.tags_tree.blockSignals(True)
    seq_item.setCheckState(0, Qt.CheckState.Checked)
    dlg.tags_tree.blockSignals(False)

    dlg._toggle_all_tags(True)
    assert seq_item.checkState(0) == Qt.CheckState.Checked
    dlg._toggle_all_tags(False)
    assert seq_item.checkState(0) == Qt.CheckState.Checked
    dlg.close()


# --- Task A3: filter-walk _is_filtering guard --------------------------------


def _sequence_dialog(tmp_path: Path) -> TagExportDialog:
    """Dialog whose tree carries one sequence parent with >0 leaf descendants."""
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
    ds.PatientID = "SYNTH01"
    return TagExportDialog(
        {"study1": {"series1": [ds]}}, config_manager=_cm(tmp_path)
    )


@pytest.mark.qt
def test_filtering_does_not_warn_on_large_sequence_expand(
    qapp, tmp_path, monkeypatch
) -> None:
    monkeypatch.setattr(
        _tag_export_dialog_mod, "LARGE_SEQUENCE_LEAF_THRESHOLD", 0
    )
    dlg = _sequence_dialog(tmp_path)
    dlg.include_sequences_checkbox.setChecked(True)
    seq_tag = str(Tag("DeidentificationMethodCodeSequence"))
    seq_item = _find_tag_item(dlg, seq_tag)
    assert seq_item is not None
    # Threshold was patched to 0, so the build flags this node for the warning.
    assert isinstance(seq_item.data(0, Qt.ItemDataRole.UserRole + 1), int)

    warning = mock.Mock()
    monkeypatch.setattr(_tag_export_dialog_mod.QMessageBox, "warning", warning)

    # "Code Value" matches leaves nested under the sequence, so the walk
    # programmatically expands the sequence parent (emitting itemExpanded).
    dlg._filter_tags("Code Value")
    assert seq_item.isExpanded()
    warning.assert_not_called()
    dlg.close()


@pytest.mark.qt
def test_item_expanded_warns_outside_filtering(qapp, tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(
        _tag_export_dialog_mod, "LARGE_SEQUENCE_LEAF_THRESHOLD", 0
    )
    dlg = _sequence_dialog(tmp_path)
    dlg.include_sequences_checkbox.setChecked(True)
    seq_tag = str(Tag("DeidentificationMethodCodeSequence"))
    seq_item = _find_tag_item(dlg, seq_tag)
    assert seq_item is not None

    warning = mock.Mock()
    monkeypatch.setattr(_tag_export_dialog_mod.QMessageBox, "warning", warning)

    assert dlg._is_filtering is False
    dlg._on_tag_tree_item_expanded(seq_item)
    assert warning.called
    dlg.close()


@pytest.mark.qt
def test_filter_tags_leaves_tree_signals_unblocked(qapp, tmp_path) -> None:
    dlg = TagExportDialog(_studies(), config_manager=_cm(tmp_path))
    dlg._filter_tags("Patient")
    assert dlg.tags_tree.signalsBlocked() is False
    dlg.close()


@pytest.mark.qt
def test_is_filtering_cleared_after_filter(qapp, tmp_path) -> None:
    dlg = TagExportDialog(_studies(), config_manager=_cm(tmp_path))
    assert dlg._is_filtering is False
    dlg._filter_tags("Patient ID")
    assert dlg._is_filtering is False
    dlg.close()


@pytest.mark.qt
def test_is_filtering_cleared_when_filter_walk_raises(
    qapp, tmp_path, monkeypatch
) -> None:
    dlg = TagExportDialog(_studies(), config_manager=_cm(tmp_path))

    def _boom(*_args, **_kwargs):
        raise RuntimeError("boom")

    monkeypatch.setattr(dlg, "_apply_tag_filter_recursive", _boom)
    with pytest.raises(RuntimeError):
        dlg._filter_tags("Patient")
    assert dlg._is_filtering is False
    assert dlg.tags_tree.signalsBlocked() is False
    dlg.close()


# --- Task A5: remaining Select All / filter / objectName coherence ------------


@pytest.mark.qt
def test_filter_then_select_all_updates_visible_group_headers(qapp, tmp_path) -> None:
    """After a filter, Select All still checks every remaining visible group header."""
    dlg = TagExportDialog(_studies(), config_manager=_cm(tmp_path))
    dlg._filter_tags("Patient ID")
    visible = _visible_group_headers(dlg)
    assert visible
    dlg._toggle_all_tags(True)
    for header in visible:
        assert header.checkState(0) == Qt.CheckState.Checked
    dlg.close()


@pytest.mark.qt
def test_filter_matching_only_group_label_unchecks_header(qapp, tmp_path) -> None:
    """A filter that matches only a group label unchecks that header.

    Exportable leaves under the header are hidden, so the aggregate is None
    and the header must not keep a stale Checked state from Select All.
    """
    dlg = TagExportDialog(_studies(), config_manager=_cm(tmp_path))
    dlg._toggle_all_tags(True)
    headers = _visible_group_headers(dlg)
    assert headers
    header = headers[0]
    assert header.checkState(0) == Qt.CheckState.Checked
    label = header.text(0)
    assert label.startswith("Group ")

    dlg._filter_tags(label)
    visible = _visible_group_headers(dlg)
    assert header in visible
    assert list(dlg._iter_visible_exportable_leaves(start_item=header)) == []
    assert header.checkState(0) == Qt.CheckState.Unchecked
    dlg.close()
