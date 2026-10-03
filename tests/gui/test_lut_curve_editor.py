"""
Curve editor gestures and the shared three-curve overlay.

``test_lut_selector.py`` already covers adding a point, freehand direction,
and undo of gamma/interpolation. This file covers the rest of the Phase 3b
gesture list and the overlay's four MONOCHROME1 x user-invert states.
"""

from __future__ import annotations

import numpy as np
import pytest
from PySide6.QtCore import QEvent, QPointF, Qt
from PySide6.QtGui import QMouseEvent

from core.dicom_window_level import apply_window_level
from core.lut_catalog import colormap_lut, gamma_lut, linear_lut, logarithmic_lut
from core.lut_engine import LookUpTable, apply_lut_to_uint8, gamma_transfer
from gui.dialogs import lut_curve_editor_dialog as editor_module
from gui.dialogs.lut_curve_editor_dialog import LutCurveEditorDialog
from gui.widgets.lut_transfer_function_widget import lut_samples, overlay_paths

_COMBINATIONS = [
    ("MONOCHROME2", False, False),
    ("MONOCHROME2", True, True),
    ("MONOCHROME1", False, True),
    ("MONOCHROME1", True, False),
]


def _mouse(kind: QEvent.Type, point: QPointF, buttons: Qt.MouseButton) -> QMouseEvent:
    return QMouseEvent(
        kind, point, point, Qt.MouseButton.LeftButton, buttons, Qt.KeyboardModifier.NoModifier
    )


def _drag(canvas, start: tuple[float, float], end: tuple[float, float]) -> None:
    first = canvas._from_unit(*start)
    last = canvas._from_unit(*end)
    canvas.mousePressEvent(_mouse(QEvent.Type.MouseButtonPress, first, Qt.MouseButton.LeftButton))
    canvas.mouseMoveEvent(_mouse(QEvent.Type.MouseMove, last, Qt.MouseButton.LeftButton))
    canvas.mouseReleaseEvent(_mouse(QEvent.Type.MouseButtonRelease, last, Qt.MouseButton.NoButton))


def _three_point_dialog() -> LutCurveEditorDialog:
    lut = LookUpTable(
        name="Mine",
        source="custom",
        control_points=((0.0, 0.0), (0.5, 0.25), (1.0, 1.0)),
    )
    dialog = LutCurveEditorDialog(lut)
    dialog._canvas.resize(320, 240)
    return dialog


@pytest.mark.qt
def test_dragging_a_breakpoint_moves_it_in_one_undo_step(qapp) -> None:
    dialog = _three_point_dialog()
    canvas = dialog._canvas
    _drag(canvas, (0.5, 0.25), (0.6, 0.75))
    x, y = canvas.points[1]
    assert x == pytest.approx(0.6, abs=0.01)
    assert y == pytest.approx(0.75, abs=0.01)
    assert dialog.result_lut().name == "Custom"
    dialog._undo_points()
    assert canvas.points[1] == (0.5, 0.25)
    _ = qapp


@pytest.mark.qt
def test_dragging_an_endpoint_keeps_its_x_pinned(qapp) -> None:
    dialog = _three_point_dialog()
    canvas = dialog._canvas
    _drag(canvas, (1.0, 1.0), (0.7, 0.4))
    assert canvas.points[-1][0] == 1.0
    assert canvas.points[-1][1] == pytest.approx(0.4, abs=0.01)
    _ = qapp


@pytest.mark.qt
def test_interior_point_cannot_cross_a_neighbor(qapp) -> None:
    dialog = _three_point_dialog()
    canvas = dialog._canvas
    _drag(canvas, (0.5, 0.25), (0.999, 0.25))
    assert canvas.points[1][0] < canvas.points[2][0]
    _ = qapp


@pytest.mark.qt
def test_delete_removes_an_interior_point_but_never_an_endpoint(qapp) -> None:
    dialog = _three_point_dialog()
    canvas = dialog._canvas
    canvas.selected = 0
    dialog._delete_selected()
    assert len(canvas.points) == 3
    canvas.selected = 1
    dialog._delete_selected()
    assert canvas.points == [(0.0, 0.0), (1.0, 1.0)]
    dialog._undo_points()
    assert len(canvas.points) == 3
    _ = qapp


@pytest.mark.qt
def test_interpolation_switch_changes_the_sampled_curve(qapp) -> None:
    dialog = _three_point_dialog()
    linear = lut_samples(dialog.result_lut())
    dialog._set_interpolation("monotone_cubic")
    smooth = lut_samples(dialog.result_lut())
    assert dialog.result_lut().interpolation == "monotone_cubic"
    assert not np.array_equal(linear, smooth)
    # Both still pass through the control points at their nearest codes.
    assert linear[0] == smooth[0] == 0
    assert linear[255] == smooth[255] == 255
    _ = qapp


@pytest.mark.qt
def test_parameters_button_resamples_the_gamma_curve(qapp, monkeypatch) -> None:
    dialog = LutCurveEditorDialog(gamma_lut(1.0))
    before = lut_samples(dialog.result_lut())
    monkeypatch.setattr(editor_module, "edit_lut_parameters", lambda _lut, _parent: gamma_lut(2.2))
    dialog._edit_parameters()
    result = dialog.result_lut()
    assert result.transfer_fn is gamma_transfer
    assert result.gamma == 2.2
    after = lut_samples(result)
    assert not np.array_equal(before, after)
    assert after[128] < before[128]
    _ = qapp


@pytest.mark.qt
def test_a_loaded_custom_lut_reopens_with_its_name_and_points(qapp) -> None:
    saved = LookUpTable(
        name="Chest",
        source="file",
        control_points=((0.0, 0.0), (0.3, 0.6), (1.0, 1.0)),
        interpolation="catmull_rom",
    )
    dialog = LutCurveEditorDialog(saved)
    assert dialog._canvas.points == [(0.0, 0.0), (0.3, 0.6), (1.0, 1.0)]
    assert dialog._canvas.interpolation == "catmull_rom"
    reopened = dialog.result_lut()
    assert reopened is saved
    assert (reopened.name, reopened.source) == ("Chest", "file")
    _ = qapp


@pytest.mark.parametrize(("photometric", "inverted", "net"), _COMBINATIONS)
def test_overlay_composed_curve_is_lut_of_net_inverted_window(photometric, inverted, net) -> None:
    lut = logarithmic_lut()
    paths = overlay_paths(lut, 500.0, 200.0, photometric, inverted, 0.0, 1000.0)
    assert paths is not None
    assert paths.net_inverted is net
    windowed = apply_window_level(paths.xs.copy(), 500.0, 200.0)
    polarized = 255 - windowed if net else windowed
    expected = apply_lut_to_uint8(polarized.reshape(1, -1).astype(np.uint8), lut).reshape(-1)
    assert np.array_equal(paths.composed, expected.astype(np.float64))
    assert np.array_equal(paths.window, windowed)
    assert paths.collapse is False


@pytest.mark.parametrize(("photometric", "inverted", "net"), _COMBINATIONS)
def test_linear_lut_draws_one_line_only_without_net_inversion(photometric, inverted, net) -> None:
    paths = overlay_paths(linear_lut(), 500.0, 200.0, photometric, inverted, 0.0, 1000.0)
    assert paths is not None
    assert paths.collapse is (not net)
    if net:
        assert np.array_equal(paths.composed, 255.0 - paths.window)
    else:
        assert np.array_equal(paths.composed, paths.window.astype(np.float64))


def test_linear_lut_trace_is_identity_not_the_window_ramp() -> None:
    stored = np.array([0.0, 400.0, 500.0, 600.0, 1000.0])
    ramp = apply_window_level(stored.copy(), 500.0, 200.0)
    # 127.5 truncates to 127. The top code is not asserted here: see the
    # window-top truncation item in TO_DO.md.
    assert ramp.tolist()[:3] == [0, 0, 127]
    paths = overlay_paths(linear_lut(), 500.0, 200.0, "MONOCHROME2", False, 0.0, 1000.0)
    assert paths is not None
    assert paths.lut_trace is not None
    assert np.array_equal(paths.lut_trace, np.arange(256, dtype=np.uint8))
    assert not np.array_equal(paths.lut_trace, paths.window)


def test_color_lut_overlay_draws_a_gradient_not_a_trace() -> None:
    paths = overlay_paths(colormap_lut("hot"), 500.0, 200.0, "MONOCHROME1", True, 0.0, 1000.0)
    assert paths is not None
    assert paths.lut_trace is None
    assert paths.lut_colors is not None
    assert paths.lut_colors.shape == (256, 3)
    assert paths.collapse is False


@pytest.mark.parametrize(("photometric", "inverted", "net"), _COMBINATIONS)
def test_editor_trace_behind_the_curve_matches_the_viewport(photometric, inverted, net) -> None:
    """The editor's display-result trace is the pane's composed curve across the window."""
    lut = logarithmic_lut()
    display = {
        "window_center": 500.0,
        "window_width": 200.0,
        "photometric": photometric,
        "image_inverted": inverted,
    }
    trace = editor_module.composed_trace(lut, display)
    paths = overlay_paths(lut, 500.0, 200.0, photometric, inverted, 400.0, 600.0)
    assert trace is not None
    assert paths is not None
    assert np.array_equal(trace, paths.composed)
    expected_label = "Display result (inverted)" if net else "Display result"
    assert editor_module._composed_label(display) == expected_label


def test_editor_trace_is_absent_without_a_window() -> None:
    assert editor_module.composed_trace(linear_lut(), {}) is None
    assert editor_module.composed_trace(linear_lut(), {"window_center": 1.0, "window_width": 0}) is None


@pytest.mark.qt
def test_editor_paints_with_a_window_context(qapp) -> None:
    display = {"window_center": 40.0, "window_width": 400.0, "photometric": "MONOCHROME1"}
    dialog = LutCurveEditorDialog(gamma_lut(2.0), display=display)
    dialog._canvas.resize(320, 240)
    image = dialog._canvas.grab().toImage()
    assert not image.isNull()
    assert dialog._canvas.display is display
    _ = qapp
