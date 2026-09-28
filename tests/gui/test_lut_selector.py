"""LUT parameter slider, curve editor, and histogram overlay."""

from __future__ import annotations

import numpy as np
import pytest
from PySide6.QtCore import QEvent, QPointF, Qt
from PySide6.QtGui import QMouseEvent

from core.lut_catalog import gamma_lut, inverse_lut, linear_lut, logarithmic_lut
from core.lut_engine import gamma_transfer
from core.lut_series_state import set_series_lut
from gui.dialog_coordinator import _focused_export_lut
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
def test_editor_ok_keeps_a_builtin_curve(qapp) -> None:
    dialog = LutCurveEditorDialog(logarithmic_lut())
    result = dialog.result_lut()
    assert result.name == "Logarithmic"
    assert result.transfer_fn is logarithmic_lut().transfer_fn


@pytest.mark.qt
def test_editor_undo_restores_gamma_and_interpolation(qapp) -> None:
    dialog = LutCurveEditorDialog(gamma_lut(2.2))
    dialog._canvas.points[1] = (dialog._canvas.points[1][0], 0.2)
    dialog._on_points_changed()
    assert dialog.result_lut().name == "Custom"
    dialog._undo_points()
    restored = dialog.result_lut()
    assert restored.transfer_fn is gamma_transfer
    assert restored.gamma == 2.2
    dialog._set_interpolation("monotone_cubic")
    assert dialog._canvas.interpolation == "monotone_cubic"
    dialog._undo_points()
    assert dialog.result_lut().gamma == 2.2
    assert dialog._canvas.interpolation == "linear"


@pytest.mark.qt
def test_export_lut_comes_from_the_app_pane(qapp) -> None:
    viewer = type("Viewer", (), {"image_inverted": True})()
    view = type(
        "View",
        (),
        {"series_defaults": {}, "current_series_identifier": "series", "image_viewer": viewer},
    )()
    set_series_lut(view, inverse_lut(), "series")
    app = type("App", (), {"subwindow_managers": {2: {"view_state_manager": view}}})()
    window = type("Window", (), {})()
    coordinator = type("Coordinator", (), {"main_window": window, "tag_export_union_host": app})()
    inverted, lut = _focused_export_lut(coordinator, 2)
    assert inverted is True
    assert lut.name == "Inverse"
    _ = qapp


def _mouse(kind: QEvent.Type, point: QPointF, buttons: Qt.MouseButton) -> QMouseEvent:
    return QMouseEvent(
        kind,
        point,
        point,
        Qt.MouseButton.LeftButton,
        buttons,
        Qt.KeyboardModifier.NoModifier,
    )


@pytest.mark.qt
def test_adding_a_point_undoes_in_one_step(qapp) -> None:
    dialog = LutCurveEditorDialog(logarithmic_lut())
    canvas = dialog._canvas
    canvas.resize(320, 240)
    before = list(canvas.points)
    point = QPointF(32, 120)
    canvas.mousePressEvent(_mouse(QEvent.Type.MouseButtonPress, point, Qt.MouseButton.LeftButton))
    canvas.mouseReleaseEvent(_mouse(QEvent.Type.MouseButtonRelease, point, Qt.MouseButton.NoButton))
    assert len(canvas.points) == len(before) + 1
    dialog._undo_points()
    assert canvas.points == before
    assert dialog.result_lut().name == "Logarithmic"
    _ = qapp


@pytest.mark.qt
def test_histogram_overlay_draws_a_transfer_axis(qapp) -> None:
    widget = HistogramWidget()
    widget.set_lut_overlay(inverse_lut(), "MONOCHROME2", True, refresh=False)
    widget.set_pixel_array(np.arange(64, dtype=np.float32).reshape(8, 8))
    widget.set_window_level(32.0, 64.0)
    assert widget._transfer_axis is not None
    assert widget._lut_input_axis is not None
    assert widget._lut_input_axis.get_xlim() == (0.0, 255.0)

    linear = HistogramWidget()
    linear.set_lut_overlay(linear_lut(), "MONOCHROME2", False, refresh=False)
    linear.set_pixel_array(np.arange(64, dtype=np.float32).reshape(8, 8))
    linear.set_window_level(32.0, 64.0)
    assert len(linear._transfer_axis.get_lines()) == 1
    lut_line = linear._lut_input_axis.get_lines()[0]
    assert lut_line.get_xdata()[0] == 0
    assert lut_line.get_xdata()[-1] == 255


@pytest.mark.qt
def test_histogram_curve_toggles_hide_each_overlay(qapp) -> None:
    widget = HistogramWidget()
    widget.set_lut_overlay(inverse_lut(), "MONOCHROME2", False, refresh=False)
    widget.set_pixel_array(np.arange(64, dtype=np.float32).reshape(8, 8))
    widget.set_window_level(32.0, 64.0)
    widget.set_overlay_curves(window=False, lut=False, composed=True)
    assert widget._lut_input_axis is None
    assert len(widget._transfer_axis.get_lines()) == 1
    widget.set_overlay_curves(window=False, lut=True, composed=False)
    assert widget._lut_input_axis is not None
    assert widget._transfer_axis.get_lines() == []
    widget.set_overlay_curves(window=False, lut=False, composed=False)
    assert widget._transfer_axis is None
    assert widget._lut_input_axis is None
    _ = qapp
