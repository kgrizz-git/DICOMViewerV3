"""
Tests for PathsConfigMixin.

Verifies last_path, last_export_path, recent_files (add/remove/dedupe/cap),
and normalize_path via a lightweight ConfigManager with a temp config file.
"""
import pytest
from pathlib import Path
from utils.config_manager import ConfigManager


def _cm(tmp_path: Path) -> ConfigManager:
    cm = ConfigManager()
    cm.config_path = tmp_path / "cfg.json"
    cm.config = cm.default_config.copy()
    return cm


class TestLastPath:
    def test_default_is_empty(self, tmp_path):
        assert _cm(tmp_path).get_last_path() == ""

    def test_set_and_get(self, tmp_path):
        cm = _cm(tmp_path)
        cm.set_last_path("/some/path")
        assert cm.get_last_path() == "/some/path"

    def test_set_persists(self, tmp_path):
        cm = _cm(tmp_path)
        cm.set_last_path("/some/path")
        cm2 = ConfigManager()
        cm2.config_path = cm.config_path
        cm2.config = cm2._load_config()
        assert cm2.get_last_path() == "/some/path"


class TestLastExportPath:
    def test_default_is_empty(self, tmp_path):
        assert _cm(tmp_path).get_last_export_path() == ""

    def test_set_and_get(self, tmp_path):
        cm = _cm(tmp_path)
        cm.set_last_export_path("/exports")
        assert cm.get_last_export_path() == "/exports"


class TestRecentFiles:
    def test_default_is_empty(self, tmp_path):
        assert _cm(tmp_path).get_recent_files() == []

    def test_add_file_appears_first(self, tmp_path):
        cm = _cm(tmp_path)
        cm.add_recent_file("/a/b.dcm")
        assert cm.get_recent_files()[0].endswith("b.dcm")

    def test_add_deduplicates_and_moves_to_top(self, tmp_path):
        cm = _cm(tmp_path)
        cm.add_recent_file("/a.dcm")
        cm.add_recent_file("/b.dcm")
        cm.add_recent_file("/a.dcm")
        files = cm.get_recent_files()
        # /a.dcm should now be first and appear only once
        assert sum(f.endswith("a.dcm") for f in files) == 1
        assert files[0].endswith("a.dcm")

    def test_capped_at_20(self, tmp_path):
        cm = _cm(tmp_path)
        for i in range(25):
            cm.add_recent_file(f"/file{i}.dcm")
        assert len(cm.get_recent_files()) == 20

    def test_remove_file(self, tmp_path):
        cm = _cm(tmp_path)
        cm.add_recent_file("/keep.dcm")
        cm.add_recent_file("/remove.dcm")
        # remove_recent_file uses the exact stored path, so grab it
        stored = cm.get_recent_files()[0]  # most recently added
        cm.remove_recent_file(stored)
        assert stored not in cm.get_recent_files()

    def test_add_invalid_path_is_ignored(self, tmp_path):
        cm = _cm(tmp_path)
        cm.add_recent_file("")
        cm.add_recent_file(None)  # type: ignore
        assert cm.get_recent_files() == []


class TestNormalizePath:
    def test_empty_returns_none(self):
        assert ConfigManager.normalize_path("") is None

    def test_none_returns_none(self):
        assert ConfigManager.normalize_path(None) is None  # type: ignore

    def test_whitespace_only_returns_none(self):
        assert ConfigManager.normalize_path("   ") is None

    def test_valid_path_returned(self, tmp_path):
        result = ConfigManager.normalize_path(str(tmp_path))
        assert result is not None
        assert isinstance(result, str)
