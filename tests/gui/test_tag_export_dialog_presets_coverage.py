"""Focused synthetic tests for gui.dialogs.tag_export_dialog_presets – untested branches."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest
from pydicom.dataset import Dataset
from PySide6.QtCore import Qt

from gui.dialogs.tag_export_dialog import TagExportDialog
from gui.dialogs.tag_export_dialog_presets import (
    _ITEM_NO_PRESET,
    _TITLE_NO_CONFIG_MANAGER,
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


def _first_exportable_leaves(dialog: TagExportDialog, limit: int = 3):
    leaves = list(dialog._iter_visible_exportable_leaves())
    assert len(leaves) >= limit
    return leaves[:limit]


# ---------------------------------------------------------------------------
# _on_preset_selected
# ---------------------------------------------------------------------------

@pytest.mark.qt
class TestOnPresetSelected:
    def test_empty_name_noop(self, qapp, tmp_path):
        cm = _cm(tmp_path)
        dlg = TagExportDialog(_studies(), config_manager=cm)
        dlg._on_preset_selected("")
        # Should not crash; no preset loaded

    def test_no_preset_sentinel_noop(self, qapp, tmp_path):
        cm = _cm(tmp_path)
        dlg = TagExportDialog(_studies(), config_manager=cm)
        dlg._on_preset_selected(_ITEM_NO_PRESET)
        # Should not crash

    def test_no_config_manager_noop(self, qapp, tmp_path):
        dlg = TagExportDialog(_studies(), config_manager=None)
        dlg._on_preset_selected("SomePreset")
        # Should return early


# ---------------------------------------------------------------------------
# _save_current_preset
# ---------------------------------------------------------------------------

@pytest.mark.qt
class TestSaveCurrentPreset:
    def test_no_config_manager_shows_warning(self, qapp, tmp_path):
        dlg = TagExportDialog(_studies(), config_manager=None)
        with patch("gui.dialogs.tag_export_dialog_presets.QMessageBox.warning") as mock_warn:
            dlg._save_current_preset()
            mock_warn.assert_called_once()
            assert _TITLE_NO_CONFIG_MANAGER in str(mock_warn.call_args)

    def test_no_preset_combo_noop(self, qapp, tmp_path):
        cm = _cm(tmp_path)
        dlg = TagExportDialog(_studies(), config_manager=cm)
        dlg.preset_combo = None
        dlg._save_current_preset()  # should not crash

    def test_no_preset_selected_delegates_to_save_preset(self, qapp, tmp_path):
        cm = _cm(tmp_path)
        dlg = TagExportDialog(_studies(), config_manager=cm)
        called = {"save_as": False}
        def _fake():
            called["save_as"] = True

        dlg._save_preset = _fake
        dlg._save_current_preset()
        assert called["save_as"] is True

    def test_no_selected_tags_shows_warning(self, qapp, tmp_path):
        cm = _cm(tmp_path)
        dlg = TagExportDialog(_studies(), config_manager=cm)
        leaves = _first_exportable_leaves(dlg, 1)
        tag = leaves[0].data(0, Qt.ItemDataRole.UserRole)
        cm.save_tag_export_preset("TestPreset", [tag])
        dlg._load_presets_list()
        idx = dlg.preset_combo.findText("TestPreset")
        dlg.preset_combo.setCurrentIndex(idx)
        dlg._toggle_all_tags(False)
        dlg._update_selected_tags()
        with patch("gui.dialogs.tag_export_dialog_presets.QMessageBox.warning") as mock_warn:
            dlg._save_current_preset()
            assert any("No Tags Selected" in str(c) for c in mock_warn.call_args_list)


# ---------------------------------------------------------------------------
# _save_preset
# ---------------------------------------------------------------------------

@pytest.mark.qt
class TestSavePreset:
    def test_no_config_manager_shows_warning(self, qapp, tmp_path):
        dlg = TagExportDialog(_studies(), config_manager=None)
        with patch("gui.dialogs.tag_export_dialog_presets.QMessageBox.warning") as mock_warn:
            dlg._save_preset()
            mock_warn.assert_called_once()

    def test_no_selected_tags_shows_warning(self, qapp, tmp_path):
        cm = _cm(tmp_path)
        dlg = TagExportDialog(_studies(), config_manager=cm)
        dlg._toggle_all_tags(False)
        dlg._update_selected_tags()
        with patch("gui.dialogs.tag_export_dialog_presets.QMessageBox.warning") as mock_warn:
            dlg._save_preset()
            assert any("No Tags Selected" in str(c) for c in mock_warn.call_args_list)

    def test_user_cancels_input_dialog(self, qapp, tmp_path, monkeypatch):
        cm = _cm(tmp_path)
        dlg = TagExportDialog(_studies(), config_manager=cm)
        leaves = _first_exportable_leaves(dlg, 1)
        leaves[0].setCheckState(0, Qt.CheckState.Checked)
        dlg._update_selected_tags()
        monkeypatch.setattr(
            "PySide6.QtWidgets.QInputDialog.getText",
            lambda *a, **k: ("", False),
        )
        dlg._save_preset()
        # No crash, no preset saved

    def test_user_confirms_save(self, qapp, tmp_path, monkeypatch):
        cm = _cm(tmp_path)
        dlg = TagExportDialog(_studies(), config_manager=cm)
        leaves = _first_exportable_leaves(dlg, 1)
        leaves[0].setCheckState(0, Qt.CheckState.Checked)
        dlg._update_selected_tags()
        monkeypatch.setattr(
            "PySide6.QtWidgets.QInputDialog.getText",
            lambda *a, **k: ("MyPreset", True),
        )
        monkeypatch.setattr(
            "PySide6.QtWidgets.QMessageBox.information",
            lambda *a, **k: None,
        )
        dlg._save_preset()
        assert "MyPreset" in cm.get_tag_export_presets()

    def test_save_as_duplicate_confirms_overwrite(self, qapp, tmp_path, monkeypatch):
        cm = _cm(tmp_path)
        dlg = TagExportDialog(_studies(), config_manager=cm)
        leaves = _first_exportable_leaves(dlg, 2)
        tag_a = leaves[0].data(0, Qt.ItemDataRole.UserRole)
        cm.save_tag_export_preset("Existing", [tag_a])
        dlg._load_presets_list()
        dlg._toggle_all_tags(False)
        leaves[1].setCheckState(0, Qt.CheckState.Checked)
        dlg._update_selected_tags()
        monkeypatch.setattr(
            "PySide6.QtWidgets.QInputDialog.getText",
            lambda *a, **k: ("Existing", True),
        )
        monkeypatch.setattr(
            "PySide6.QtWidgets.QMessageBox.information",
            lambda *a, **k: None,
        )
        # User says No to overwrite (QMessageBox.StandardButton.No = 0x00000400)
        monkeypatch.setattr(
            "PySide6.QtWidgets.QMessageBox.question",
            lambda *a, **k: 0x00000400,
        )
        dlg._save_preset()
        saved = cm.get_tag_export_presets()["Existing"]
        assert saved == [tag_a]  # original preserved

    def test_save_as_duplicate_confirms_yes_overwrite(self, qapp, tmp_path, monkeypatch):
        cm = _cm(tmp_path)
        dlg = TagExportDialog(_studies(), config_manager=cm)
        leaves = _first_exportable_leaves(dlg, 2)
        tag_a = leaves[0].data(0, Qt.ItemDataRole.UserRole)
        tag_b = leaves[1].data(0, Qt.ItemDataRole.UserRole)
        cm.save_tag_export_preset("Existing", [tag_a])
        dlg._load_presets_list()
        dlg._toggle_all_tags(False)
        leaves[1].setCheckState(0, Qt.CheckState.Checked)
        dlg._update_selected_tags()
        monkeypatch.setattr(
            "PySide6.QtWidgets.QInputDialog.getText",
            lambda *a, **k: ("Existing", True),
        )
        monkeypatch.setattr(
            "PySide6.QtWidgets.QMessageBox.information",
            lambda *a, **k: None,
        )
        # User says Yes (QMessageBox.StandardButton.Yes = 0x00004000)
        monkeypatch.setattr(
            "PySide6.QtWidgets.QMessageBox.question",
            lambda *a, **k: 0x00004000,
        )
        dlg._save_preset()
        saved = cm.get_tag_export_presets()["Existing"]
        assert saved == [tag_b]


# ---------------------------------------------------------------------------
# _load_preset
# ---------------------------------------------------------------------------

@pytest.mark.qt
class TestLoadPreset:
    def test_no_config_manager_shows_warning(self, qapp, tmp_path):
        dlg = TagExportDialog(_studies(), config_manager=None)
        with patch("gui.dialogs.tag_export_dialog_presets.QMessageBox.warning") as mock_warn:
            dlg._load_preset()
            mock_warn.assert_called_once()

    def test_no_preset_combo_noop(self, qapp, tmp_path):
        cm = _cm(tmp_path)
        dlg = TagExportDialog(_studies(), config_manager=cm)
        dlg.preset_combo = None
        dlg._load_preset()

    def test_no_preset_selected_shows_warning(self, qapp, tmp_path):
        cm = _cm(tmp_path)
        dlg = TagExportDialog(_studies(), config_manager=cm)
        with patch("gui.dialogs.tag_export_dialog_presets.QMessageBox.warning") as mock_warn:
            dlg._load_preset()
            assert any("No Preset Selected" in str(c) for c in mock_warn.call_args_list)


# ---------------------------------------------------------------------------
# _load_preset_by_name
# ---------------------------------------------------------------------------

@pytest.mark.qt
class TestLoadPresetByName:
    def test_no_config_manager_noop(self, qapp, tmp_path):
        dlg = TagExportDialog(_studies(), config_manager=None)
        dlg._load_preset_by_name("foo")  # should not crash

    def test_preset_not_found_shows_warning(self, qapp, tmp_path):
        cm = _cm(tmp_path)
        dlg = TagExportDialog(_studies(), config_manager=cm)
        with patch("gui.dialogs.tag_export_dialog_presets.QMessageBox.warning") as mock_warn:
            dlg._load_preset_by_name("nonexistent", show_feedback=True)
            assert any("not found" in str(c).lower() for c in mock_warn.call_args_list)

    def test_show_feedback_true_shows_information(self, qapp, tmp_path, monkeypatch):
        cm = _cm(tmp_path)
        dlg = TagExportDialog(_studies(), config_manager=cm)
        leaves = _first_exportable_leaves(dlg, 1)
        tag = leaves[0].data(0, Qt.ItemDataRole.UserRole)
        cm.save_tag_export_preset("Feedback", [tag])
        monkeypatch.setattr(
            "PySide6.QtWidgets.QMessageBox.information",
            lambda *a, **k: None,
        )
        dlg._load_preset_by_name("Feedback", show_feedback=True)
        assert tag in dlg.selected_tags

    def test_load_with_sequences_on(self, qapp, tmp_path, monkeypatch):
        cm = _cm(tmp_path)
        dlg = TagExportDialog(_studies(), config_manager=cm)
        dlg.include_sequences_checkbox.setChecked(True)
        leaves = _first_exportable_leaves(dlg, 1)
        tag = leaves[0].data(0, Qt.ItemDataRole.UserRole)
        cm.save_tag_export_preset("SeqPreset", [tag])
        monkeypatch.setattr(
            "PySide6.QtWidgets.QMessageBox.information",
            lambda *a, **k: None,
        )
        dlg._load_preset_by_name("SeqPreset", show_feedback=False)
        assert tag in dlg.selected_tags


# ---------------------------------------------------------------------------
# _delete_preset
# ---------------------------------------------------------------------------

@pytest.mark.qt
class TestDeletePreset:
    def test_no_config_manager_shows_warning(self, qapp, tmp_path):
        dlg = TagExportDialog(_studies(), config_manager=None)
        with patch("gui.dialogs.tag_export_dialog_presets.QMessageBox.warning") as mock_warn:
            dlg._delete_preset()
            mock_warn.assert_called_once()

    def test_no_preset_combo_noop(self, qapp, tmp_path):
        cm = _cm(tmp_path)
        dlg = TagExportDialog(_studies(), config_manager=cm)
        dlg.preset_combo = None
        dlg._delete_preset()

    def test_no_preset_selected_shows_warning(self, qapp, tmp_path):
        cm = _cm(tmp_path)
        dlg = TagExportDialog(_studies(), config_manager=cm)
        with patch("gui.dialogs.tag_export_dialog_presets.QMessageBox.warning") as mock_warn:
            dlg._delete_preset()
            assert any("No Preset Selected" in str(c) for c in mock_warn.call_args_list)

    def test_user_declines_delete(self, qapp, tmp_path, monkeypatch):
        cm = _cm(tmp_path)
        dlg = TagExportDialog(_studies(), config_manager=cm)
        cm.save_tag_export_preset("ToDelete", ["tag1"])
        dlg._load_presets_list()
        idx = dlg.preset_combo.findText("ToDelete")
        dlg.preset_combo.setCurrentIndex(idx)
        # No = 0x00000400
        monkeypatch.setattr(
            "PySide6.QtWidgets.QMessageBox.question",
            lambda *a, **k: 0x00000400,
        )
        dlg._delete_preset()
        assert "ToDelete" in cm.get_tag_export_presets()

    def test_user_confirms_delete(self, qapp, tmp_path, monkeypatch):
        cm = _cm(tmp_path)
        dlg = TagExportDialog(_studies(), config_manager=cm)
        cm.save_tag_export_preset("ToDelete", ["tag1"])
        dlg._load_presets_list()
        idx = dlg.preset_combo.findText("ToDelete")
        dlg.preset_combo.setCurrentIndex(idx)
        # Yes = 0x00004000
        monkeypatch.setattr(
            "PySide6.QtWidgets.QMessageBox.question",
            lambda *a, **k: 0x00004000,
        )
        monkeypatch.setattr(
            "PySide6.QtWidgets.QMessageBox.information",
            lambda *a, **k: None,
        )
        dlg._delete_preset()
        assert "ToDelete" not in cm.get_tag_export_presets()


# ---------------------------------------------------------------------------
# _export_presets
# ---------------------------------------------------------------------------

@pytest.mark.qt
class TestExportPresets:
    def test_no_config_manager_shows_warning(self, qapp, tmp_path):
        dlg = TagExportDialog(_studies(), config_manager=None)
        with patch("gui.dialogs.tag_export_dialog_presets.QMessageBox.warning") as mock_warn:
            dlg._export_presets()
            mock_warn.assert_called_once()

    def test_no_presets_shows_info(self, qapp, tmp_path):
        cm = _cm(tmp_path)
        dlg = TagExportDialog(_studies(), config_manager=cm)
        with patch("gui.dialogs.tag_export_dialog_presets.QMessageBox.information") as mock_info:
            dlg._export_presets()
            mock_info.assert_called_once()

    def test_user_cancels_file_dialog(self, qapp, tmp_path, monkeypatch):
        cm = _cm(tmp_path)
        dlg = TagExportDialog(_studies(), config_manager=cm)
        cm.save_tag_export_preset("Exp1", ["tag1"])
        monkeypatch.setattr(
            "PySide6.QtWidgets.QFileDialog.getSaveFileName",
            lambda *a, **k: ("", ""),
        )
        dlg._export_presets()  # no crash

    def test_export_success(self, qapp, tmp_path, monkeypatch):
        cm = _cm(tmp_path)
        cm.config_path = tmp_path / "cfg.json"
        cm.save_config()
        dlg = TagExportDialog(_studies(), config_manager=cm)
        cm.save_tag_export_preset("Exp1", ["tag1"])
        out_file = str(tmp_path / "export.json")
        monkeypatch.setattr(
            "PySide6.QtWidgets.QFileDialog.getSaveFileName",
            lambda *a, **k: (out_file, "JSON"),
        )
        monkeypatch.setattr(
            "PySide6.QtWidgets.QMessageBox.information",
            lambda *a, **k: None,
        )
        dlg._export_presets()
        assert Path(out_file).exists()

    def test_export_failure_shows_warning(self, qapp, tmp_path, monkeypatch):
        cm = _cm(tmp_path)
        dlg = TagExportDialog(_studies(), config_manager=cm)
        cm.save_tag_export_preset("Exp1", ["tag1"])
        monkeypatch.setattr(
            "PySide6.QtWidgets.QFileDialog.getSaveFileName",
            lambda *a, **k: ("/nonexistent/dir/file.json", "JSON"),
        )
        monkeypatch.setattr(
            "PySide6.QtWidgets.QMessageBox.warning",
            lambda *a, **k: None,
        )
        dlg._export_presets()

    def test_export_appends_json_extension(self, qapp, tmp_path, monkeypatch):
        cm = _cm(tmp_path)
        cm.config_path = tmp_path / "cfg.json"
        cm.save_config()
        dlg = TagExportDialog(_studies(), config_manager=cm)
        cm.save_tag_export_preset("Exp1", ["tag1"])
        out_file = str(tmp_path / "export")
        monkeypatch.setattr(
            "PySide6.QtWidgets.QFileDialog.getSaveFileName",
            lambda *a, **k: (out_file, "JSON"),
        )
        monkeypatch.setattr(
            "PySide6.QtWidgets.QMessageBox.information",
            lambda *a, **k: None,
        )
        dlg._export_presets()
        assert Path(out_file + ".json").exists()


# ---------------------------------------------------------------------------
# _import_presets
# ---------------------------------------------------------------------------

@pytest.mark.qt
class TestImportPresets:
    def test_no_config_manager_shows_warning(self, qapp, tmp_path):
        dlg = TagExportDialog(_studies(), config_manager=None)
        with patch("gui.dialogs.tag_export_dialog_presets.QMessageBox.warning") as mock_warn:
            dlg._import_presets()
            mock_warn.assert_called_once()

    def test_user_cancels_file_dialog(self, qapp, tmp_path, monkeypatch):
        cm = _cm(tmp_path)
        dlg = TagExportDialog(_studies(), config_manager=cm)
        monkeypatch.setattr(
            "PySide6.QtWidgets.QFileDialog.getOpenFileName",
            lambda *a, **k: ("", ""),
        )
        dlg._import_presets()  # no crash

    def test_import_failure_returns_none(self, qapp, tmp_path, monkeypatch):
        cm = _cm(tmp_path)
        dlg = TagExportDialog(_studies(), config_manager=cm)
        monkeypatch.setattr(
            "PySide6.QtWidgets.QFileDialog.getOpenFileName",
            lambda *a, **k: ("/bad/path.json", "JSON"),
        )
        monkeypatch.setattr(
            "PySide6.QtWidgets.QMessageBox.critical",
            lambda *a, **k: None,
        )
        dlg._import_presets()

    def test_import_success(self, qapp, tmp_path, monkeypatch):
        cm = _cm(tmp_path)
        cm.config_path = tmp_path / "cfg.json"
        cm.save_config()
        cm.save_tag_export_preset("Imported", ["tag1"])
        import json
        export_file = tmp_path / "import.json"
        export_data = {"version": "1.0", "presets": cm.get_tag_export_presets()}
        export_file.write_text(json.dumps(export_data))
        cm2 = _cm(tmp_path)
        cm2.config_path = tmp_path / "cfg2.json"
        cm2.config = cm2.default_config.copy()
        dlg = TagExportDialog(_studies(), config_manager=cm2)
        monkeypatch.setattr(
            "PySide6.QtWidgets.QFileDialog.getOpenFileName",
            lambda *a, **k: (str(export_file), "JSON"),
        )
        monkeypatch.setattr(
            "PySide6.QtWidgets.QMessageBox.information",
            lambda *a, **k: None,
        )
        dlg._import_presets()
        assert "Imported" in cm2.get_tag_export_presets()

    def test_import_empty_file(self, qapp, tmp_path, monkeypatch):
        cm = _cm(tmp_path)
        dlg = TagExportDialog(_studies(), config_manager=cm)
        empty_file = tmp_path / "empty.json"
        empty_file.write_text("{}")
        monkeypatch.setattr(
            "PySide6.QtWidgets.QFileDialog.getOpenFileName",
            lambda *a, **k: (str(empty_file), "JSON"),
        )
        monkeypatch.setattr(
            "PySide6.QtWidgets.QMessageBox.critical",
            lambda *a, **k: None,
        )
        dlg._import_presets()
