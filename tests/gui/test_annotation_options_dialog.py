"""Regression tests for AnnotationOptionsDialog color loading.

Confirms ROI and measurement display colors follow the configured line color
even when the stored font color differs (the former identical if/else arms
that always preferred line color).
"""

from __future__ import annotations

from pathlib import Path

import pytest

from gui.dialogs.annotation_options_dialog import AnnotationOptionsDialog
from utils.config_manager import ConfigManager


def _cm(tmp_path: Path) -> ConfigManager:
    cm = ConfigManager()
    cm.config_path = tmp_path / "cfg.json"
    cm.config = cm.default_config.copy()
    return cm


@pytest.mark.qt
def test_load_settings_prefers_roi_line_color_when_font_differs(
    qapp, tmp_path: Path
) -> None:
    cm = _cm(tmp_path)
    cm.set_roi_line_color(10, 20, 30)
    cm.set_roi_font_color(200, 100, 50)
    dlg = AnnotationOptionsDialog(cm)
    assert dlg.roi_color == (10, 20, 30)


@pytest.mark.qt
def test_load_settings_prefers_measurement_line_color_when_font_differs(
    qapp, tmp_path: Path
) -> None:
    cm = _cm(tmp_path)
    cm.set_measurement_line_color(1, 2, 3)
    cm.set_measurement_font_color(9, 8, 7)
    dlg = AnnotationOptionsDialog(cm)
    assert dlg.measurement_color == (1, 2, 3)


@pytest.mark.qt
def test_load_settings_uses_line_color_when_font_matches(
    qapp, tmp_path: Path
) -> None:
    cm = _cm(tmp_path)
    cm.set_roi_line_color(40, 50, 60)
    cm.set_roi_font_color(40, 50, 60)
    cm.set_measurement_line_color(70, 80, 90)
    cm.set_measurement_font_color(70, 80, 90)
    dlg = AnnotationOptionsDialog(cm)
    assert dlg.roi_color == (40, 50, 60)
    assert dlg.measurement_color == (70, 80, 90)
