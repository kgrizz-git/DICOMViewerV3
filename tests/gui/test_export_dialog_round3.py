"""Round-three behavioral coverage for the ExportDialog Qt seams."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import pytest
from pydicom.dataset import Dataset
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFileDialog, QMessageBox

from gui.dialogs.export_dialog import ExportDialog
from utils.config_manager import ConfigManager
from utils.deep_anonymizer import DeepAnonymizerOptions


def _config(tmp_path: Path) -> ConfigManager:
    config = ConfigManager(config_dir=tmp_path)
    config.config = config.default_config.copy()
    return config


def _dataset(uid: str, series_number: int, instance: int) -> Dataset:
    dataset = Dataset()
    dataset.SOPInstanceUID = uid
    dataset.StudyDescription = "Synthetic Study"
    dataset.StudyDate = "20260101"
    dataset.SeriesNumber = series_number
    dataset.SeriesDescription = f"Synthetic Series {series_number}"
    dataset.Modality = "CT"
    dataset.InstanceNumber = instance
    return dataset


def _studies() -> dict[str, dict[str, list[Dataset]]]:
    return {
        "1.2.3.1": {
            "1.2.3.1.1": [_dataset("1.2.3.1.1.1", 2, 1), _dataset("1.2.3.1.1.2", 2, 2)],
            "1.2.3.1.2": [_dataset("1.2.3.1.2.1", 1, 1)],
        },
        "1.2.3.2": {
            "1.2.3.2.1": [_dataset("1.2.3.2.1.1", 1, 1)],
        },
    }


def _dialog(tmp_path: Path) -> ExportDialog:
    return ExportDialog(_studies(), config_manager=_config(tmp_path))


@pytest.mark.qt
def test_tree_selection_propagates_and_tracks_partial_parent(qapp, tmp_path) -> None:
    dlg = _dialog(tmp_path)
    study = dlg.tree_widget.topLevelItem(0)
    series = study.child(1)
    first_slice = series.child(0)

    series.setCheckState(0, Qt.CheckState.Checked)
    dlg._on_item_changed(series, 0)
    first_slice.setCheckState(0, Qt.CheckState.Unchecked)
    series.child(1).setCheckState(0, Qt.CheckState.Checked)
    dlg._update_parent_state(series)
    dlg._update_selection()

    assert series.checkState(0) == Qt.CheckState.PartiallyChecked
    assert study.checkState(0) == Qt.CheckState.PartiallyChecked
    assert len(dlg.selected_items) == 1
    assert dlg.count_label.text() == "Selected: 1 items"

    study.setCheckState(0, Qt.CheckState.Checked)
    dlg._on_item_changed(study, 0)
    assert all(
        series_item.checkState(0) == Qt.CheckState.Checked
        for series_item in (study.child(0), study.child(1))
    )
    assert len(dlg.selected_items) == 3
    dlg.close()


@pytest.mark.qt
def test_format_resolution_and_anonymize_availability(qapp, tmp_path) -> None:
    dlg = _dialog(tmp_path)
    assert dlg.window_level_group.isEnabled()
    assert dlg.resolution_group.isEnabled()
    assert not dlg.anonymize_checkbox.isEnabled()

    dlg.resolution_combo.setCurrentIndex(3)
    assert dlg.export_scale == 4.0
    dlg.dicom_radio.setChecked(True)
    dlg._on_format_changed()
    assert not dlg.window_level_group.isEnabled()
    assert not dlg.resolution_group.isEnabled()
    assert dlg.anonymize_checkbox.isEnabled()
    assert not dlg.anonymize_options_button.isEnabled()

    dlg.anonymize_checkbox.setChecked(True)
    assert dlg.anonymize_enabled is True
    assert dlg.anonymize_options_button.isEnabled()
    dlg.png_radio.setChecked(True)
    dlg._on_format_changed()
    assert dlg.anonymize_enabled is False
    assert not dlg.anonymize_checkbox.isEnabled()
    assert dlg.overlay_checkbox.isChecked() is False
    dlg.close()


@pytest.mark.qt
def test_deep_anonymize_options_flow_updates_options_and_request(qapp, tmp_path, monkeypatch) -> None:
    options = DeepAnonymizerOptions.maximal_strip()

    class _OptionsDialog:
        def __init__(self, current, parent=None) -> None:
            assert current == DeepAnonymizerOptions.standard_share()

        def exec(self) -> int:
            return 1

        def get_options(self) -> DeepAnonymizerOptions:
            return options

    manager = MagicMock()
    manager.export_selected.return_value = (1, [])
    export_api = MagicMock(return_value=manager)
    export_api.get_export_paths_for_selection.return_value = []
    export_api.build_deep_anonymized_selection.return_value = {"synthetic": "copy"}
    monkeypatch.setattr("gui.dialogs.export_dialog.ExportManager", export_api)
    monkeypatch.setattr("gui.dialogs.export_dialog.AnonymizationOptionsDialog", _OptionsDialog)
    monkeypatch.setattr(QMessageBox, "information", lambda *a, **k: QMessageBox.StandardButton.Ok)

    dlg = _dialog(tmp_path)
    dlg._open_anonymize_options()
    assert dlg.anonymizer_options == options
    study = dlg.tree_widget.topLevelItem(0)
    study.setCheckState(0, Qt.CheckState.Checked)
    dlg._on_item_changed(study, 0)
    dlg.dicom_radio.setChecked(True)
    dlg._on_format_changed()
    dlg.anonymize_checkbox.setChecked(True)
    dlg.output_path = str(tmp_path)
    dlg._on_export()

    request = manager.export_selected.call_args.args[0]
    assert request.deep_anonymize is True
    assert request.deep_anonymizer_options == options
    assert request.deep_anonymized_items == {"synthetic": "copy"}
    export_api.build_deep_anonymized_selection.assert_called_once()
    dlg.close()


@pytest.mark.qt
def test_browse_output_uses_fake_file_dialog_and_persists_path(qapp, tmp_path, monkeypatch) -> None:
    selected = tmp_path / "chosen-output"
    selected.mkdir()

    class _DirectoryDialog:
        FileMode = QFileDialog.FileMode

        def __init__(self, *args, **kwargs) -> None:
            self.directory = None

        def setFileMode(self, mode) -> None:
            assert mode == QFileDialog.FileMode.Directory

        def setWindowTitle(self, title: str) -> None:
            assert title == "Select Output Directory"

        def setDirectory(self, directory: str) -> None:
            self.directory = directory

        def exec(self) -> int:
            return 1

        def selectedFiles(self) -> list[str]:
            return [str(selected)]

    monkeypatch.setattr("gui.dialogs.export_dialog.QFileDialog", _DirectoryDialog)
    config = _config(tmp_path)
    dlg = ExportDialog(_studies(), config_manager=config)
    dlg._browse_output()
    assert dlg.output_path == str(selected)
    assert dlg.path_edit.text() == str(selected)
    assert config.get_last_export_path() == str(selected)
    dlg.close()


@pytest.mark.qt
def test_export_handoff_success_and_error(qapp, tmp_path, monkeypatch) -> None:
    messages: list[tuple[str, str]] = []
    monkeypatch.setattr(
        QMessageBox,
        "information",
        lambda _parent, title, text: messages.append((title, text)),
    )
    monkeypatch.setattr(
        QMessageBox,
        "critical",
        lambda _parent, title, text: messages.append((title, text)),
    )

    manager = MagicMock()
    manager.export_selected.return_value = (2, [("synthetic.png", 4.0, 2.0)])
    export_api = MagicMock(return_value=manager)
    export_api.get_export_paths_for_selection.return_value = []
    monkeypatch.setattr("gui.dialogs.export_dialog.ExportManager", export_api)

    dlg = _dialog(tmp_path)
    study = dlg.tree_widget.topLevelItem(0)
    study.setCheckState(0, Qt.CheckState.Checked)
    dlg._on_item_changed(study, 0)
    dlg.output_path = str(tmp_path)
    dlg._on_export()
    assert dlg.result() == int(dlg.DialogCode.Accepted)
    assert messages[0][0] == "Export Complete"
    assert "lower magnification" in messages[0][1]

    failing_manager = MagicMock()
    failing_manager.export_selected.side_effect = RuntimeError("synthetic export failure")
    failing_api = MagicMock(return_value=failing_manager)
    failing_api.get_export_paths_for_selection.return_value = []
    monkeypatch.setattr("gui.dialogs.export_dialog.ExportManager", failing_api)
    dlg = _dialog(tmp_path)
    dlg.selected_items = {("1.2.3.1", "1.2.3.1.1", 0): _studies()["1.2.3.1"]["1.2.3.1.1"][0]}
    dlg.output_path = str(tmp_path)
    dlg._on_export()
    assert messages[-1][0] == "Export Failed"
    assert "synthetic export failure" in messages[-1][1]
    dlg.close()
