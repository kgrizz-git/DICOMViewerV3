"""Tests for WLPresetManagerDialog table and OK emission."""

from __future__ import annotations

import pytest
from PySide6.QtWidgets import QMessageBox

from gui.dialogs.wl_preset_manager_dialog import WLPresetManagerDialog


def _preset(name: str = "Chest", modality: str = "CT", center: float = 40.0,
            width: float = 400.0, is_rescaled: bool = True) -> dict:
    return {
        "name": name,
        "modality": modality,
        "center": center,
        "width": width,
        "is_rescaled": is_rescaled,
    }


@pytest.mark.qt
def test_table_populated_from_user_presets(qapp) -> None:
    dlg = WLPresetManagerDialog([_preset(), _preset("Bone", "CT", 300.0, 1500.0, False)])
    assert dlg._table.rowCount() == 2
    assert dlg._table.item(0, 0).text() == "Chest"
    assert dlg._table.item(1, 4).text() == "No (raw pixels)"
    assert dlg.get_presets()[0]["name"] == "Chest"


@pytest.mark.qt
def test_ok_emits_presets_saved(qapp) -> None:
    dlg = WLPresetManagerDialog([_preset()])
    saved: list[list] = []
    dlg.presets_saved.connect(saved.append)
    dlg._on_ok()
    assert len(saved) == 1
    assert saved[0][0]["width"] == 400.0
    assert dlg.result() == int(dlg.DialogCode.Accepted)


@pytest.mark.qt
def test_ok_rejects_zero_width(qapp, monkeypatch) -> None:
    warned: list[str] = []

    def _warn(parent, title, text):
        warned.append(title)
        return QMessageBox.StandardButton.Ok

    monkeypatch.setattr(QMessageBox, "warning", _warn)
    dlg = WLPresetManagerDialog([_preset(width=0.0)])
    dlg._on_ok()
    assert warned == ["Validation"]
    assert dlg.result() != int(dlg.DialogCode.Accepted)


@pytest.mark.qt
def test_delete_selected_row(qapp, monkeypatch) -> None:
    monkeypatch.setattr(
        QMessageBox,
        "question",
        lambda *a, **k: QMessageBox.StandardButton.Yes,
    )
    dlg = WLPresetManagerDialog([_preset("A"), _preset("B")])
    dlg._table.selectRow(0)
    dlg._on_delete()
    assert [p["name"] for p in dlg.get_presets()] == ["B"]
