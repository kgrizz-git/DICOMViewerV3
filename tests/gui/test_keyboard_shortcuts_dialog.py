"""Tests for KeyboardShortcutsDialog: title, size, and shortcut sections."""

from __future__ import annotations

import pytest
from PySide6.QtWidgets import QDialogButtonBox, QGroupBox, QLabel

from gui.dialogs.keyboard_shortcuts_dialog import _SECTIONS, KeyboardShortcutsDialog


@pytest.mark.qt
def test_dialog_title_and_fixed_size(qapp) -> None:
    dlg = KeyboardShortcutsDialog()
    assert dlg.windowTitle() == "Keyboard Shortcuts"
    assert dlg.width() == 580
    assert dlg.height() == 600


@pytest.mark.qt
def test_dialog_builds_one_group_per_section(qapp) -> None:
    dlg = KeyboardShortcutsDialog()
    groups = dlg.findChildren(QGroupBox)
    titles = [g.title() for g in groups]
    expected = [section_title for section_title, _ in _SECTIONS]
    assert titles == expected


@pytest.mark.qt
def test_dialog_shows_known_shortcut_labels(qapp) -> None:
    dlg = KeyboardShortcutsDialog()
    labels = [lab.text() for lab in dlg.findChildren(QLabel)]
    assert "Open File(s)…" in labels
    assert "Ctrl+O" in labels
    assert "Pan / Scroll" in labels
    assert "P" in labels


@pytest.mark.qt
def test_close_button_accepts_dialog(qapp) -> None:
    dlg = KeyboardShortcutsDialog()
    boxes = dlg.findChildren(QDialogButtonBox)
    assert len(boxes) == 1
    boxes[0].rejected.emit()
    assert dlg.result() == int(dlg.DialogCode.Accepted)
