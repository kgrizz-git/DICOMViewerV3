"""Configured-accent coverage for edited metadata-panel rows.

Kept in a sibling module so ``tests/test_metadata_panel.py`` stays under the
750-line grandfather cap.
"""

from __future__ import annotations

import pydicom
from pydicom.dataset import Dataset
from pydicom.sequence import Sequence
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import QTreeWidgetItem

from gui.accent_presets import DEFAULT_ACCENT_ID, get_preset
from gui.metadata_panel import MetadataPanel


def _dataset_with_patient_name() -> Dataset:
    """Minimal dataset with an edited-row candidate at PatientName."""
    ds = Dataset()
    ds.PatientName = "Test^Patient"
    ds.PatientID = "12345"
    item = Dataset()
    item.CodeValue = "113100"
    item.CodingSchemeDesignator = "DCM"
    item.CodeMeaning = "Basic Application Confidentiality Profile"
    ds.DeidentificationMethodCodeSequence = Sequence([item])
    return ds


def _find_item_by_tag_str(item: QTreeWidgetItem, tag_str: str) -> QTreeWidgetItem | None:
    for i in range(item.childCount()):
        child = item.child(i)
        if child.data(0, Qt.ItemDataRole.UserRole) == tag_str:
            return child
        found = _find_item_by_tag_str(child, tag_str)
        if found is not None:
            return found
    return None


def _find_in_tree(panel: MetadataPanel, tag_str: str) -> QTreeWidgetItem | None:
    root = panel.tree_widget.invisibleRootItem()
    for i in range(root.childCount()):
        found = _find_item_by_tag_str(root.child(i), tag_str)
        if found is not None:
            return found
    return None


class _FakeHistoryManager:
    def is_tag_edited(self, _dataset: Dataset, tag: str) -> bool:
        return tag == str(pydicom.tag.Tag("PatientName"))


class _FakeAccentConfig:
    """Config stand-in that only supplies a non-default accent id."""

    def __init__(self, accent_id: str) -> None:
        self._accent_id = accent_id

    def get_accent(self) -> str:
        return self._accent_id


def test_edited_tag_uses_configured_accent_soft_highlight(qapp) -> None:
    """Edited PatientName background follows a non-default accent_soft token."""
    configured_accent = "garnet"
    assert configured_accent != DEFAULT_ACCENT_ID

    panel = MetadataPanel()
    panel.set_dataset(_dataset_with_patient_name())
    panel.history_manager = _FakeHistoryManager()
    panel.config_manager = _FakeAccentConfig(configured_accent)
    panel._populate_tags("")

    patient_name = _find_in_tree(panel, str(pydicom.tag.Tag("PatientName")))
    assert patient_name is not None
    assert patient_name.background(0).color() == QColor(
        get_preset(configured_accent).accent_soft
    )
    assert patient_name.foreground(0).color() == QColor(0, 0, 0)
