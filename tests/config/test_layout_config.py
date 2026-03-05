"""
Tests for LayoutConfigMixin.

Covers multi_window_layout and view_slot_order get/set/validation.
"""
from pathlib import Path
from utils.config_manager import ConfigManager


def _cm(tmp_path: Path) -> ConfigManager:
    cm = ConfigManager()
    cm.config_path = tmp_path / "cfg.json"
    cm.config = cm.default_config.copy()
    return cm


class TestMultiWindowLayout:
    def test_default(self, tmp_path):
        assert _cm(tmp_path).get_multi_window_layout() == "1x1"

    def test_set_valid_modes(self, tmp_path):
        cm = _cm(tmp_path)
        for mode in ["1x2", "2x1", "2x2", "1x1"]:
            cm.set_multi_window_layout(mode)
            assert cm.get_multi_window_layout() == mode

    def test_invalid_ignored(self, tmp_path):
        cm = _cm(tmp_path)
        cm.set_multi_window_layout("3x3")
        assert cm.get_multi_window_layout() == "1x1"


class TestViewSlotOrder:
    def test_default(self, tmp_path):
        assert _cm(tmp_path).get_view_slot_order() == [0, 1, 2, 3]

    def test_set_valid_permutation(self, tmp_path):
        cm = _cm(tmp_path)
        cm.set_view_slot_order([3, 2, 1, 0])
        assert cm.get_view_slot_order() == [3, 2, 1, 0]

    def test_wrong_length_ignored(self, tmp_path):
        cm = _cm(tmp_path)
        cm.set_view_slot_order([0, 1, 2])
        assert cm.get_view_slot_order() == [0, 1, 2, 3]

    def test_not_permutation_ignored(self, tmp_path):
        cm = _cm(tmp_path)
        cm.set_view_slot_order([0, 0, 1, 2])
        assert cm.get_view_slot_order() == [0, 1, 2, 3]

    def test_returns_copy(self, tmp_path):
        cm = _cm(tmp_path)
        order = cm.get_view_slot_order()
        order.append(99)
        assert cm.get_view_slot_order() == [0, 1, 2, 3]
