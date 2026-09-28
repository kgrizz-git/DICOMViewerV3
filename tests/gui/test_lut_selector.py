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
    assert widget.figure.subplotpars.right > 0.95
    assert widget.figure.subplotpars.top > 0.95
    _ = qapp


@pytest.mark.qt
def test_histogram_overlay_labels_stay_inside_and_follow_theme(qapp) -> None:
    import matplotlib.colors as mcolors
    from PySide6.QtGui import QColor, QPalette

    widget = HistogramWidget()
    palette = widget.palette()
    palette.setColor(QPalette.ColorRole.Window, QColor(26, 26, 26))
    widget.setPalette(palette)
    widget.figure.set_dpi(100)
    widget.figure.set_size_inches(5.2, 3.4)
    widget.set_lut_overlay(inverse_lut(), "MONOCHROME2", False, refresh=False)
    widget.set_pixel_array(np.arange(64, dtype=np.float32).reshape(8, 8))
    widget.set_window_level(32.0, 64.0)
    assert widget.figure.subplotpars.right <= 0.90
    assert widget.figure.subplotpars.top <= 0.85
    widget.canvas.draw()
    renderer = widget.canvas.get_renderer()
    figure_box = widget.figure.bbox
    artists = [
        widget._transfer_axis.yaxis.label,
        widget._lut_input_axis.xaxis.label,
        *widget._transfer_axis.get_yticklabels(),
        *widget._lut_input_axis.get_xticklabels(),
    ]
    for artist in artists:
        box = artist.get_window_extent(renderer)
        assert box.x0 >= -1
        assert box.y0 >= -1
        assert box.x1 <= figure_box.width + 1
        assert box.y1 <= figure_box.height + 1
    output_color = mcolors.to_hex(widget._transfer_axis.yaxis.label.get_color())
    assert output_color.lower() == "#cccccc"
    hist_legend = widget.axes.get_legend().get_window_extent(renderer)
    lut_legend = widget._lut_input_axis.get_legend().get_window_extent(renderer)
    assert not hist_legend.overlaps(lut_legend)
    widget.update_font_sizes_for_size(200, 200)
    assert widget._transfer_axis.yaxis.get_label().get_fontsize() == 7
    _ = qapp


@pytest.mark.qt
def test_window_only_linear_overlay_is_the_dashed_ramp(qapp) -> None:
    widget = HistogramWidget()
    widget.set_lut_overlay(linear_lut(), "MONOCHROME2", False, refresh=False)
    widget.set_pixel_array(np.arange(64, dtype=np.float32).reshape(8, 8))
    widget.set_window_level(32.0, 64.0)
    widget.set_overlay_curves(window=True, lut=False, composed=False)
    line = widget._transfer_axis.get_lines()[0]
    assert line.get_linestyle() == "--"
    assert line.get_label() == "W/L ramp"
    _ = qapp


def _stroke(canvas, units: list[tuple[float, float]]) -> None:
    first = canvas._from_unit(*units[0])
    canvas.mousePressEvent(_mouse(QEvent.Type.MouseButtonPress, first, Qt.MouseButton.LeftButton))
    for unit in units[1:]:
        point = canvas._from_unit(*unit)
        canvas.mouseMoveEvent(_mouse(QEvent.Type.MouseMove, point, Qt.MouseButton.LeftButton))
    last = canvas._from_unit(*units[-1])
    canvas.mouseReleaseEvent(_mouse(QEvent.Type.MouseButtonRelease, last, Qt.MouseButton.NoButton))


@pytest.mark.qt
def test_reverse_freehand_matches_forward_and_a_click_keeps_the_curve(qapp) -> None:
    dialog = LutCurveEditorDialog(linear_lut())
    canvas = dialog._canvas
    canvas.resize(320, 240)
    canvas.freehand = True
    forward = [(index / 20, (index / 20) ** 2) for index in range(21)]
    _stroke(canvas, forward)
    forward_points = list(canvas.points)
    assert len(dialog._undo) == 2
    dialog._undo_points()
    _stroke(canvas, list(reversed(forward)))
    assert canvas.points == forward_points
    undo_steps = len(dialog._undo)
    kept = list(canvas.points)
    _stroke(canvas, [(0.2, 0.2)])
    assert canvas.points == kept
    assert len(dialog._undo) == undo_steps
    _ = qapp


@pytest.mark.qt
def test_reopening_lut_menu_drops_old_submenus(qapp) -> None:
    from PySide6.QtCore import QEvent
    from PySide6.QtGui import QActionGroup
    from PySide6.QtWidgets import QMenu, QWidget

    from gui.lut_actions import populate_lut_menu

    menu = QMenu()
    populate_lut_menu(menu, QWidget())
    populate_lut_menu(menu, QWidget())
    qapp.sendPostedEvents(None, QEvent.Type.DeferredDelete)
    assert len(menu.findChildren(QMenu)) == 2
    assert len(menu.findChildren(QActionGroup)) == 1


@pytest.mark.qt
def test_hidden_lut_button_opens_the_menu(qapp) -> None:
    from PySide6.QtWidgets import QToolBar, QWidget

    from gui.lut_actions import attach_toolbar_lut_button, show_lut_toolbar_menu

    host = QWidget()
    toolbar = QToolBar(host)
    button = attach_toolbar_lut_button(toolbar, host)
    host.lut_toolbar_button = button
    assert not button.isVisible()
    show_lut_toolbar_menu(host)
    menu = button.menu()
    assert menu is not None and menu.isVisible()
    menu.close()
    _ = qapp
