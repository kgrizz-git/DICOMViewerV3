"""
Characterization tests for ROI statistics overlay helpers (Sonar S3776 slice).

Covers text formatting and font/style resolution extracted from
``ROIManager.create_statistics_overlay``.
"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock

from PySide6.QtCore import QRectF

from tools.roi_statistics_overlay import (
    channel_labels_from_statistics,
    format_area_overlay_line,
    format_roi_statistics_overlay_lines,
    resolve_roi_overlay_font_style,
    statistics_overlay_scene_pos,
    sync_statistics_overlay_scene_visibility,
)


def test_resolve_roi_overlay_font_style_defaults_and_overrides() -> None:
    size, color, family, variant = resolve_roi_overlay_font_style(None, None, None)
    assert size == 6
    assert color == (255, 255, 0)
    assert family == "IBM Plex Sans"
    assert variant == "Bold"

    cfg = MagicMock()
    cfg.get_roi_font_size.return_value = 9
    cfg.get_roi_font_color.return_value = (1, 2, 3)
    cfg.get_roi_font_family.return_value = "IBM Plex Mono"
    cfg.get_roi_font_variant.return_value = "Regular"
    size, color, family, variant = resolve_roi_overlay_font_style(cfg, None, None)
    assert (size, color, family, variant) == (9, (1, 2, 3), "IBM Plex Mono", "Regular")

    size, color, _, _ = resolve_roi_overlay_font_style(cfg, 4, (9, 9, 9))
    assert size == 4
    assert color == (9, 9, 9)


def test_format_area_and_channel_labels() -> None:
    assert format_area_overlay_line({"area_mm2": 250.0}) == "Area: 2.50 cm²"
    assert format_area_overlay_line({"area_mm2": 50.0}) == "Area: 50.00 mm²"
    assert format_area_overlay_line({"area_pixels": 12.5}) == "Area: 12.5 px"
    assert channel_labels_from_statistics({}, 2) == ("Ch0", "Ch1")
    assert channel_labels_from_statistics({"channel_labels": ["R", "G"]}, 2) == ("R", "G")


def test_format_roi_statistics_overlay_lines_scalar_and_multichannel() -> None:
    visible = {"mean", "std", "min", "max", "count", "area"}
    stats = {
        "mean": 10.5,
        "std": 1.25,
        "min": 0.0,
        "max": 20.0,
        "count": 42,
        "area_mm2": 12.0,
        "multichannel_count": 2,
        "channel_labels": ("R", "G"),
        "mean_ch0": 1.0,
        "mean_ch1": 2.0,
        "std_ch0": 0.1,
        "std_ch1": 0.2,
        "min_ch0": 0.0,
        "min_ch1": 1.0,
        "max_ch0": 3.0,
        "max_ch1": 4.0,
    }
    lines = format_roi_statistics_overlay_lines(visible, stats, rescale_type="HU")
    assert lines[0] == "Mean: 10.50 HU"
    assert lines[1] == "Std Dev: 1.25 HU"
    assert any(line.startswith("Ch mean:") and "R μ=1.00 HU" in line for line in lines)
    assert any(line.startswith("Ch std:") and "G σ=0.20 HU" in line for line in lines)
    assert "Pixels: 42" in lines
    assert "Area: 12.00 mm²" in lines

    assert format_roi_statistics_overlay_lines(set(), stats) == []


def test_statistics_overlay_scene_pos_without_view() -> None:
    roi = SimpleNamespace(
        get_bounds=lambda: QRectF(10, 20, 30, 40),
        statistics_overlay_offset=(5.0, 7.0),
    )
    scene = MagicMock()
    scene.views.return_value = []
    x, y = statistics_overlay_scene_pos(roi, scene)
    assert x == 45.0  # right (40) + offset_x (5)
    assert y == 27.0  # top (20) + offset_y (7)


def test_sync_statistics_overlay_scene_visibility() -> None:
    text_item = MagicMock()
    text_item.scene.return_value = None
    roi = SimpleNamespace(statistics_overlay_visible=True)
    scene = MagicMock()
    sync_statistics_overlay_scene_visibility(text_item, roi, scene)
    scene.addItem.assert_called_once_with(text_item)
    text_item.show.assert_called_once()

    roi.statistics_overlay_visible = False
    sync_statistics_overlay_scene_visibility(text_item, roi, scene)
    text_item.hide.assert_called_once()
