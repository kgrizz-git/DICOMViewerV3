"""Tests for utils.config.slice_sync_config.SliceSyncConfigMixin."""

from __future__ import annotations

from utils.config.slice_sync_config import SliceSyncConfigMixin


class _Cfg(SliceSyncConfigMixin):
    def __init__(self) -> None:
        self.config: dict = {}
        self.saved = 0

    def save_config(self) -> None:
        self.saved += 1


def test_enabled_default_and_roundtrip() -> None:
    c = _Cfg()
    assert c.get_slice_sync_enabled() is False
    c.set_slice_sync_enabled(True)
    assert c.get_slice_sync_enabled() is True
    assert c.saved == 1


def test_groups_validation_and_cleaning() -> None:
    c = _Cfg()
    assert c.get_slice_sync_groups() == []
    c.config["slice_sync_groups"] = "not a list"
    assert c.get_slice_sync_groups() == []
    c.config["slice_sync_groups"] = [[0, 1], [2], ["x", "y"], [3, 4]]
    # [2] dropped (len<2), ["x","y"] dropped (non-int)
    assert c.get_slice_sync_groups() == [[0, 1], [3, 4]]
    c.set_slice_sync_groups([[0, 1], [2]])
    assert c.config["slice_sync_groups"] == [[0, 1]]


def test_location_line_bool_flags() -> None:
    c = _Cfg()
    for getter, setter in (
        (c.get_slice_location_lines_visible, c.set_slice_location_lines_visible),
        (c.get_slice_location_lines_same_group_only, c.set_slice_location_lines_same_group_only),
        (c.get_slice_location_lines_focused_only, c.set_slice_location_lines_focused_only),
    ):
        assert getter() is False
        setter(True)
        assert getter() is True


def test_line_mode_validation() -> None:
    c = _Cfg()
    assert c.get_slice_location_line_mode() == "middle"
    c.set_slice_location_line_mode("begin_end")
    assert c.get_slice_location_line_mode() == "begin_end"
    c.set_slice_location_line_mode("bogus")  # ignored
    assert c.get_slice_location_line_mode() == "begin_end"
    c.config["slice_location_line_mode"] = "garbage"
    assert c.get_slice_location_line_mode() == "middle"


def test_line_width_clamp() -> None:
    c = _Cfg()
    assert c.get_slice_location_line_width_px() == 1
    c.set_slice_location_line_width_px(100)
    assert c.get_slice_location_line_width_px() == 8
    c.config["slice_location_line_width_px"] = "bad"
    assert c.get_slice_location_line_width_px() == 1


def test_group_strip_height_clamp() -> None:
    c = _Cfg()
    assert c.get_slice_sync_group_strip_height_px() == 5
    c.set_slice_sync_group_strip_height_px(100)
    assert c.get_slice_sync_group_strip_height_px() == 16
    c.config["slice_sync_group_strip_height_px"] = "bad"
    assert c.get_slice_sync_group_strip_height_px() == 5
