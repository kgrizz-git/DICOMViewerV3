"""LUT parameter slider, curve editor, and histogram overlay."""

from __future__ import annotations

import numpy as np
import pytest

from core.lut_catalog import gamma_lut, inverse_lut
from core.lut_engine import gamma_transfer
from gui.dialogs.lut_curve_editor_dialog import LutCurveEditorDialog
from gui.dialogs.lut_parameter_dialog import LutParameterDialog
from tools.histogram_widget import HistogramWidget


@pytest.mark.qt
def test_parameter_slider_sets_gamma(qapp) -> None:
    dialog = LutParameterDialog(gamma_lut(1.0))
    dialog._slider.setValue(22)
    result = dialog.result_lut()
    assert result.transfer_fn is gamma_transfer
    assert result.gamma == 2.2


@pytest.mark.qt
def test_editor_keeps_gamma_until_the_curve_is_edited(qapp) -> None:
    dialog = LutCurveEditorDialog(gamma_lut(2.2))
    result = dialog.result_lut()
    assert result.transfer_fn is gamma_transfer
    assert result.gamma == 2.2


@pytest.mark.qt
def test_histogram_overlay_draws_a_transfer_axis(qapp) -> None:
    widget = HistogramWidget()
    widget.set_lut_overlay(inverse_lut(), "MONOCHROME2", True, refresh=False)
    widget.set_pixel_array(np.arange(64, dtype=np.float32).reshape(8, 8))
    widget.set_window_level(32.0, 64.0)
    assert widget._transfer_axis is not None
