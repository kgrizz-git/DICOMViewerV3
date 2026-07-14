"""
Characterization tests for CustomizationsConfigMixin.import_customizations.

These pin the exact validation semantics of the importer so it can be refactored
without behaviour drift. Key invariants captured here:

  - Out-of-range values are *rejected* (the setter is never called), not clamped.
  - ``slice_sync_group_strip_height_px`` has a type check but no range check.
  - Only OSError / JSONDecodeError are caught; other errors propagate.
"""

from __future__ import annotations

import json
from typing import Any

import pytest

from utils.config.customizations_config import CustomizationsConfigMixin


class RecordingConfig(CustomizationsConfigMixin):
    """Config host that records every ``set_*`` call instead of applying it."""

    def __init__(self) -> None:
        self.config: dict[str, Any] = {}
        self.calls: list[tuple[str, tuple[Any, ...]]] = []

    def __getattr__(self, name: str):
        if name.startswith(("set_", "get_")):
            def _record(*args: Any, **kwargs: Any) -> None:
                self.calls.append((name, args))
            return _record
        raise AttributeError(name)

    def save_config(self) -> None:
        pass

    def called(self, setter: str) -> list[tuple[Any, ...]]:
        return [args for name, args in self.calls if name == setter]

    def was_called(self, setter: str) -> bool:
        return any(name == setter for name, _ in self.calls)


def _import(tmp_path, data: Any) -> tuple[RecordingConfig, bool]:
    path = tmp_path / "custom.json"
    path.write_text(json.dumps(data), encoding="utf-8")
    cfg = RecordingConfig()
    ok = cfg.import_customizations(str(path))
    return cfg, ok


# --- happy path ------------------------------------------------------------

def test_full_valid_import_applies_every_setter(tmp_path):
    cfg, ok = _import(tmp_path, {
        "overlay": {
            "mode": "detailed",
            "visibility_state": 2,
            "custom_fields": ["PatientName"],
            "tags": {"CT": {"top_left": ["PatientID"]}},
            "tags_detailed_extra": {"CT": {"top_right": ["StudyDate"]}},
            "font_size": 14,
            "font_color": {"r": 1, "g": 2, "b": 3},
            "slice_sync_group_strip_height_px": 24,
        },
        "annotation": {
            "roi": {
                "font_size": 8,
                "font_color": {"r": 10, "g": 20, "b": 30},
                "line_thickness": 3,
                "line_color": {"r": 40, "g": 50, "b": 60},
                "default_visible_statistics": ["mean", "std"],
                "show_per_channel_statistics": True,
            },
            "measurement": {
                "font_size": 9,
                "font_color": {"r": 70, "g": 80, "b": 90},
                "line_thickness": 4,
                "line_color": {"r": 100, "g": 110, "b": 120},
            },
            "text_annotation": {
                "font_size": 11,
                "color": {"r": 130, "g": 140, "b": 150},
            },
            "arrow_annotation": {
                "color": {"r": 160, "g": 170, "b": 180},
                "size": 12,
            },
        },
        "metadata_panel": {"column_widths": [10, 20, 30, 40]},
        "theme": "dark",
    })

    assert ok is True
    assert cfg.called("set_overlay_mode") == [("detailed",)]
    assert cfg.called("set_overlay_visibility_state") == [(2,)]
    assert cfg.called("set_overlay_custom_fields") == [(["PatientName"],)]
    assert cfg.called("set_overlay_tags") == [("CT", {"top_left": ["PatientID"]})]
    assert cfg.called("set_overlay_tags_detailed_extra") == [
        ("CT", {"top_right": ["StudyDate"]})
    ]
    assert cfg.called("set_overlay_font_size") == [(14,)]
    assert cfg.called("set_overlay_font_color") == [(1, 2, 3)]
    assert cfg.called("set_slice_sync_group_strip_height_px") == [(24,)]

    assert cfg.called("set_roi_font_size") == [(8,)]
    assert cfg.called("set_roi_font_color") == [(10, 20, 30)]
    assert cfg.called("set_roi_line_thickness") == [(3,)]
    assert cfg.called("set_roi_line_color") == [(40, 50, 60)]
    assert cfg.called("set_roi_default_visible_statistics") == [(["mean", "std"],)]
    assert cfg.called("set_roi_show_per_channel_statistics") == [(True,)]

    assert cfg.called("set_measurement_font_size") == [(9,)]
    assert cfg.called("set_measurement_font_color") == [(70, 80, 90)]
    assert cfg.called("set_measurement_line_thickness") == [(4,)]
    assert cfg.called("set_measurement_line_color") == [(100, 110, 120)]

    assert cfg.called("set_text_annotation_font_size") == [(11,)]
    assert cfg.called("set_text_annotation_color") == [(130, 140, 150)]

    assert cfg.called("set_arrow_annotation_color") == [(160, 170, 180)]
    assert cfg.called("set_arrow_annotation_size") == [(12,)]

    assert cfg.called("set_metadata_panel_column_widths") == [([10, 20, 30, 40],)]
    assert cfg.called("set_theme") == [("dark",)]


def test_empty_object_imports_successfully_and_sets_nothing(tmp_path):
    cfg, ok = _import(tmp_path, {})
    assert ok is True
    assert cfg.calls == []


# --- colour defaults and rejection -----------------------------------------

@pytest.mark.parametrize(
    ("section", "field", "setter", "expected_default"),
    [
        ("overlay", "font_color", "set_overlay_font_color", (255, 255, 0)),
    ],
)
def test_partial_color_uses_per_field_defaults(
    tmp_path, section, field, setter, expected_default
):
    cfg, ok = _import(tmp_path, {section: {field: {}}})
    assert ok is True
    assert cfg.called(setter) == [expected_default]


def test_roi_and_measurement_colors_have_distinct_defaults(tmp_path):
    cfg, ok = _import(tmp_path, {
        "annotation": {
            "roi": {"font_color": {}, "line_color": {}},
            "measurement": {"font_color": {}, "line_color": {}},
            "text_annotation": {"color": {}},
            "arrow_annotation": {"color": {}},
        }
    })
    assert ok is True
    assert cfg.called("set_roi_font_color") == [(255, 255, 0)]
    assert cfg.called("set_roi_line_color") == [(255, 0, 0)]
    assert cfg.called("set_measurement_font_color") == [(0, 255, 0)]
    assert cfg.called("set_measurement_line_color") == [(0, 255, 0)]
    assert cfg.called("set_text_annotation_color") == [(255, 255, 0)]
    assert cfg.called("set_arrow_annotation_color") == [(255, 255, 0)]


@pytest.mark.parametrize("bad", [{"r": 256, "g": 0, "b": 0}, {"r": -1, "g": 0, "b": 0}])
def test_out_of_range_color_is_rejected_not_clamped(tmp_path, bad):
    cfg, ok = _import(tmp_path, {"overlay": {"font_color": bad}})
    assert ok is True
    assert not cfg.was_called("set_overlay_font_color")


def test_non_dict_color_is_ignored(tmp_path):
    cfg, ok = _import(tmp_path, {"overlay": {"font_color": [255, 0, 0]}})
    assert ok is True
    assert not cfg.was_called("set_overlay_font_color")


# --- int fields -------------------------------------------------------------

@pytest.mark.parametrize("bad", [0, -5, "12", 12.5, None])
def test_non_positive_or_wrong_type_font_size_rejected(tmp_path, bad):
    cfg, ok = _import(tmp_path, {"overlay": {"font_size": bad}})
    assert ok is True
    assert not cfg.was_called("set_overlay_font_size")


@pytest.mark.parametrize(("size", "applied"), [(3, False), (4, True), (30, True), (31, False)])
def test_arrow_size_bounds_are_inclusive_4_to_30(tmp_path, size, applied):
    cfg, ok = _import(tmp_path, {"annotation": {"arrow_annotation": {"size": size}}})
    assert ok is True
    assert cfg.was_called("set_arrow_annotation_size") is applied


def test_strip_height_has_no_range_check(tmp_path):
    """Type-checked only: a negative value is accepted today."""
    cfg, ok = _import(tmp_path, {"overlay": {"slice_sync_group_strip_height_px": -99}})
    assert ok is True
    assert cfg.called("set_slice_sync_group_strip_height_px") == [(-99,)]


def test_strip_height_rejects_non_int(tmp_path):
    cfg, ok = _import(tmp_path, {"overlay": {"slice_sync_group_strip_height_px": "24"}})
    assert ok is True
    assert not cfg.was_called("set_slice_sync_group_strip_height_px")


# --- allow-lists ------------------------------------------------------------

@pytest.mark.parametrize(("mode", "applied"), [
    ("minimal", True), ("detailed", True), ("hidden", True), ("bogus", False),
])
def test_overlay_mode_allowlist(tmp_path, mode, applied):
    cfg, ok = _import(tmp_path, {"overlay": {"mode": mode}})
    assert ok is True
    assert cfg.was_called("set_overlay_mode") is applied


@pytest.mark.parametrize(("state", "applied"), [(0, True), (1, True), (2, True), (3, False)])
def test_overlay_visibility_state_allowlist(tmp_path, state, applied):
    cfg, ok = _import(tmp_path, {"overlay": {"visibility_state": state}})
    assert ok is True
    assert cfg.was_called("set_overlay_visibility_state") is applied


@pytest.mark.parametrize(("theme", "applied"), [
    ("light", True), ("dark", True), ("solarized", False),
])
def test_theme_allowlist(tmp_path, theme, applied):
    cfg, ok = _import(tmp_path, {"theme": theme})
    assert ok is True
    assert cfg.was_called("set_theme") is applied


@pytest.mark.parametrize("widths", [
    [1, 2, 3],            # too few
    [1, 2, 3, 4, 5],      # too many
    [1, 2, 3, 0],         # non-positive
    [1, 2, 3, "4"],       # wrong element type
    "1,2,3,4",            # not a list
])
def test_column_widths_must_be_four_positive_ints(tmp_path, widths):
    cfg, ok = _import(tmp_path, {"metadata_panel": {"column_widths": widths}})
    assert ok is True
    assert not cfg.was_called("set_metadata_panel_column_widths")


def test_overlay_tags_skips_non_dict_entries(tmp_path):
    cfg, ok = _import(tmp_path, {
        "overlay": {"tags": {"CT": {"top_left": ["A"]}, "MR": "not-a-dict"}}
    })
    assert ok is True
    assert cfg.called("set_overlay_tags") == [("CT", {"top_left": ["A"]})]


# --- top-level guards -------------------------------------------------------

def test_non_dict_json_returns_false(tmp_path):
    cfg, ok = _import(tmp_path, [1, 2, 3])
    assert ok is False
    assert cfg.calls == []


def test_missing_file_returns_false(tmp_path):
    cfg = RecordingConfig()
    assert cfg.import_customizations(str(tmp_path / "nope.json")) is False


def test_malformed_json_returns_false(tmp_path):
    path = tmp_path / "bad.json"
    path.write_text("{not json", encoding="utf-8")
    cfg = RecordingConfig()
    assert cfg.import_customizations(str(path)) is False


def test_non_dict_section_is_ignored(tmp_path):
    cfg, ok = _import(tmp_path, {"overlay": "nope", "annotation": 5, "metadata_panel": []})
    assert ok is True
    assert cfg.calls == []


def test_non_numeric_color_component_propagates_type_error(tmp_path):
    """Documents current behaviour: TypeError is not caught by the OSError/JSON handler."""
    path = tmp_path / "custom.json"
    path.write_text(json.dumps({"overlay": {"font_color": {"r": "x"}}}), encoding="utf-8")
    cfg = RecordingConfig()
    with pytest.raises(TypeError):
        cfg.import_customizations(str(path))
