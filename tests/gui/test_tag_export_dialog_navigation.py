"""Phase C6: tag export dialog expand/collapse navigation parity."""

from __future__ import annotations

from pathlib import Path
from unittest import mock

import pytest
from pydicom.dataset import Dataset
from pydicom.sequence import Sequence
from pydicom.tag import Tag
from PySide6.QtCore import QPoint, Qt
from PySide6.QtGui import QAction, QShortcut
from PySide6.QtWidgets import QLabel

from gui.dialogs import tag_export_dialog as _tag_export_dialog_mod
from gui.dialogs.tag_export_dialog import TagExportDialog
from gui.dialogs.tag_export_dialog_navigation import (
    _COLLAPSE_ALL_SHORTCUT,
    _EXPAND_ALL_SHORTCUT,
)
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


def _sequence_dialog(tmp_path: Path) -> TagExportDialog:
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


def _first_group_with_children(dlg: TagExportDialog):
    root = dlg.tags_tree.invisibleRootItem()
    for i in range(root.childCount()):
        item = root.child(i)
        if item.childCount() > 0:
            return item
    return None


@pytest.mark.qt
def test_expand_all_and_collapse_all_buttons_exist(qapp, tmp_path) -> None:
    dlg = TagExportDialog(_studies(), config_manager=_cm(tmp_path))
    assert dlg.expand_all_button.text() == "Expand All"
    assert dlg.collapse_all_button.text() == "Collapse All"
    dlg.close()


@pytest.mark.qt
def test_privacy_notice_is_visible(qapp, tmp_path) -> None:
    dlg = TagExportDialog(_studies(), config_manager=_cm(tmp_path))
    notice = dlg.findChild(QLabel, "tagExportPrivacyNotice")
    assert notice is not None
    assert "Private tags" in notice.text()
    dlg.close()


@pytest.mark.qt
def test_expand_all_expands_groups(qapp, tmp_path) -> None:
    dlg = TagExportDialog(_studies(), config_manager=_cm(tmp_path))
    group = _first_group_with_children(dlg)
    assert group is not None
    group.setExpanded(False)
    dlg._on_expand_all_clicked()
    assert group.isExpanded()
    dlg.close()


@pytest.mark.qt
def test_collapse_all_collapses_groups(qapp, tmp_path) -> None:
    dlg = TagExportDialog(_studies(), config_manager=_cm(tmp_path))
    group = _first_group_with_children(dlg)
    assert group is not None
    dlg._on_expand_all_clicked()
    assert group.isExpanded()
    dlg._on_collapse_all_clicked()
    assert not group.isExpanded()
    dlg.close()


@pytest.mark.qt
def test_expand_all_shortcuts_deliver_commands(qapp, tmp_path) -> None:
    dlg = TagExportDialog(_studies(), config_manager=_cm(tmp_path))
    group = _first_group_with_children(dlg)
    assert group is not None
    expand = collapse = None
    for child in dlg.findChildren(QShortcut):
        if child.key() == _EXPAND_ALL_SHORTCUT:
            expand = child
        elif child.key() == _COLLAPSE_ALL_SHORTCUT:
            collapse = child
    assert expand is not None
    assert collapse is not None
    group.setExpanded(False)
    expand.activated.emit()
    assert group.isExpanded()
    collapse.activated.emit()
    assert not group.isExpanded()
    dlg.close()


@pytest.mark.qt
def test_context_menu_offers_expand_for_collapsed_parent(
    qapp, tmp_path, monkeypatch
) -> None:
    """Context menu lists Expand for a collapsed parent without blocking on QMenu.exec."""
    dlg = TagExportDialog(_studies(), config_manager=_cm(tmp_path))
    group = _first_group_with_children(dlg)
    assert group is not None
    group.setExpanded(False)
    rect = dlg.tags_tree.visualItemRect(group)
    pos = QPoint(rect.center().x(), rect.center().y())

    captured_labels: list[str] = []

    class _FakeContextMenu:
        def __init__(self, parent=None):
            self._parent = parent
            self._actions = []

        def addAction(self, label):
            captured_labels.append(label)
            action = QAction(label, self._parent)
            self._actions.append(action)
            return action

        def exec(self, _pos=None):
            return None

    monkeypatch.setattr(
        "gui.dialogs.tag_export_dialog_navigation.QMenu",
        _FakeContextMenu,
    )
    dlg._show_tags_context_menu(pos)
    assert captured_labels == ["Expand"]
    dlg.close()


@pytest.mark.qt
def test_expand_all_does_not_warn_on_large_sequence(
    qapp, tmp_path, monkeypatch
) -> None:
    monkeypatch.setattr(
        _tag_export_dialog_mod, "LARGE_SEQUENCE_LEAF_THRESHOLD", 0
    )
    dlg = _sequence_dialog(tmp_path)
    dlg.include_sequences_checkbox.setChecked(True)
    seq_tag = str(Tag("DeidentificationMethodCodeSequence"))
    seq_item = None
    root = dlg.tags_tree.invisibleRootItem()
    for item in dlg._iter_all_tag_items(root):
        if item.data(0, Qt.ItemDataRole.UserRole) == seq_tag:
            seq_item = item
            break
    assert seq_item is not None

    warning = mock.Mock()
    monkeypatch.setattr(_tag_export_dialog_mod.QMessageBox, "warning", warning)
    dlg._on_expand_all_clicked()
    warning.assert_not_called()
    assert seq_item.isExpanded()
    dlg.close()


@pytest.mark.qt
def test_filter_clear_visible_when_filter_hides_all(qapp, tmp_path) -> None:
    dlg = TagExportDialog(_studies(), config_manager=_cm(tmp_path))
    dlg.tag_search.setText("zzzzno-match-zzzz")
    assert not dlg.tag_filter_clear_button.isHidden()
    dlg.tag_filter_clear_button.click()
    assert dlg.tag_search.text() == ""
    assert dlg.tag_filter_clear_button.isHidden()
    dlg.close()


@pytest.mark.qt
def test_filter_clear_visible_when_only_group_headers_match(qapp, tmp_path) -> None:
    dlg = TagExportDialog(_studies(), config_manager=_cm(tmp_path))
    dlg.tag_search.setText("Group 00")
    assert not dlg.tag_filter_clear_button.isHidden()
    dlg.close()
