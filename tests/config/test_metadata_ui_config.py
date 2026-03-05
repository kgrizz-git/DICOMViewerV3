"""
Tests for MetadataUIConfigMixin.

Covers metadata panel column widths and column order.
"""
from pathlib import Path
from utils.config_manager import ConfigManager


def _cm(tmp_path: Path) -> ConfigManager:
    cm = ConfigManager()
    cm.config_path = tmp_path / "cfg.json"
    cm.config = cm.default_config.copy()
    return cm


class TestMetadataPanelColumnWidths:
    def test_default(self, tmp_path):
        assert _cm(tmp_path).get_metadata_panel_column_widths() == [100, 200, 50, 200]

    def test_set_and_get(self, tmp_path):
        cm = _cm(tmp_path)
        cm.set_metadata_panel_column_widths([80, 150, 40, 180])
        assert cm.get_metadata_panel_column_widths() == [80, 150, 40, 180]


class TestMetadataPanelColumnOrder:
    def test_default(self, tmp_path):
        assert _cm(tmp_path).get_metadata_panel_column_order() == [0, 1, 2, 3]

    def test_set_and_get(self, tmp_path):
        cm = _cm(tmp_path)
        cm.set_metadata_panel_column_order([1, 0, 2, 3])
        assert cm.get_metadata_panel_column_order() == [1, 0, 2, 3]
