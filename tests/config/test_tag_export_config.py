"""
Tests for TagExportConfigMixin.

Covers save/get/delete presets and file export/import (including conflict handling).
"""
import json
import pytest
from pathlib import Path
from utils.config_manager import ConfigManager


def _cm(tmp_path: Path) -> ConfigManager:
    cm = ConfigManager()
    cm.config_path = tmp_path / "cfg.json"
    cm.config = cm.default_config.copy()
    return cm


class TestGetSaveDeletePresets:
    def test_default_empty(self, tmp_path):
        assert _cm(tmp_path).get_tag_export_presets() == {}

    def test_save_and_retrieve(self, tmp_path):
        cm = _cm(tmp_path)
        cm.save_tag_export_preset("MyPreset", ["(0010,0010)", "(0010,0020)"])
        presets = cm.get_tag_export_presets()
        assert "MyPreset" in presets
        assert presets["MyPreset"] == ["(0010,0010)", "(0010,0020)"]

    def test_overwrite_existing(self, tmp_path):
        cm = _cm(tmp_path)
        cm.save_tag_export_preset("P", ["TagA"])
        cm.save_tag_export_preset("P", ["TagB"])
        assert cm.get_tag_export_presets()["P"] == ["TagB"]

    def test_delete_preset(self, tmp_path):
        cm = _cm(tmp_path)
        cm.save_tag_export_preset("ToDelete", ["TagX"])
        cm.delete_tag_export_preset("ToDelete")
        assert "ToDelete" not in cm.get_tag_export_presets()

    def test_delete_nonexistent_is_safe(self, tmp_path):
        cm = _cm(tmp_path)
        cm.delete_tag_export_preset("ghost")  # should not raise


class TestExportImportPresets:
    def test_export_creates_valid_json(self, tmp_path):
        cm = _cm(tmp_path)
        cm.save_tag_export_preset("P1", ["T1", "T2"])
        out_file = tmp_path / "presets.json"
        assert cm.export_tag_export_presets(str(out_file)) is True
        data = json.loads(out_file.read_text())
        assert data["presets"]["P1"] == ["T1", "T2"]

    def test_import_adds_new_presets(self, tmp_path):
        cm = _cm(tmp_path)
        src = tmp_path / "import.json"
        src.write_text(json.dumps({"version": "1.0", "presets": {"NewP": ["T3"]}}))
        result = cm.import_tag_export_presets(str(src))
        assert result["imported"] == 1
        assert result["skipped_conflicts"] == 0
        assert cm.get_tag_export_presets()["NewP"] == ["T3"]

    def test_import_skips_conflicts(self, tmp_path):
        cm = _cm(tmp_path)
        cm.save_tag_export_preset("Existing", ["old"])
        src = tmp_path / "import.json"
        src.write_text(json.dumps({"version": "1.0", "presets": {"Existing": ["new"], "Fresh": ["X"]}}))
        result = cm.import_tag_export_presets(str(src))
        assert result["skipped_conflicts"] == 1
        assert result["imported"] == 1
        assert cm.get_tag_export_presets()["Existing"] == ["old"]

    def test_import_bad_file_returns_none(self, tmp_path):
        cm = _cm(tmp_path)
        bad = tmp_path / "bad.json"
        bad.write_text("not json {{{")
        assert cm.import_tag_export_presets(str(bad)) is None

    def test_import_missing_presets_key_returns_none(self, tmp_path):
        cm = _cm(tmp_path)
        bad = tmp_path / "bad.json"
        bad.write_text(json.dumps({"version": "1.0"}))
        assert cm.import_tag_export_presets(str(bad)) is None
