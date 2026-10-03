"""Dragging a window edge of the composed curve on the histogram sets window/level."""

from __future__ import annotations

from types import SimpleNamespace

import numpy as np
import pytest

from core.lut_catalog import gamma_lut
from tools.histogram_window_drag import (
    MIN_WIDTH,
    dragged_window,
    edge_near,
    window_edges,
)


def test_dragging_the_high_edge_keeps_the_low_edge() -> None:
    center, width = dragged_window("high", 700.0, 500.0, 200.0)
    assert window_edges(center, width) == (400.0, 700.0)


def test_dragging_the_low_edge_keeps_the_high_edge() -> None:
    center, width = dragged_window("low", 300.0, 500.0, 200.0)
    assert window_edges(center, width) == (300.0, 600.0)


@pytest.mark.parametrize(("edge", "x"), [("low", 900.0), ("high", -50.0)])
def test_an_edge_cannot_cross_the_other(edge, x) -> None:
    _center, width = dragged_window(edge, x, 500.0, 200.0)
    assert width == MIN_WIDTH


def test_edge_near_picks_the_closer_edge_within_tolerance() -> None:
    assert edge_near(103.0, 100.0, 300.0) == "low"
    assert edge_near(296.0, 100.0, 300.0) == "high"
    assert edge_near(200.0, 100.0, 300.0) is None


def _histogram(qapp):
    from tools.histogram_widget import HistogramWidget

    widget = HistogramWidget()
    widget.resize(600, 400)
    widget.set_lut_overlay(gamma_lut(2.0), "MONOCHROME2", False, refresh=False)
    widget.set_pixel_array(np.linspace(0.0, 1000.0, 400).reshape(20, 20))
    widget.set_window_level(500.0, 200.0)
    widget.canvas.draw()
    _ = qapp
    return widget


def _event(widget, x_data: float, button: int | None = 1):
    x_px, y_px = widget.axes.transData.transform((x_data, 1.0))
    return SimpleNamespace(button=button, x=float(x_px), y=float(y_px), inaxes=widget.axes)


@pytest.mark.qt
def test_histogram_emits_the_dragged_window(qapp) -> None:
    widget = _histogram(qapp)
    emitted: list[tuple[float, float]] = []
    widget.window_level_dragged.connect(lambda c, w: emitted.append((c, w)))
    widget._on_press(_event(widget, 600.0))
    widget._on_motion(_event(widget, 800.0))
    widget._on_release(_event(widget, 800.0))
    assert len(emitted) == 1
    center, width = emitted[0]
    low, high = window_edges(center, width)
    assert low == pytest.approx(400.0)
    assert high == pytest.approx(800.0, abs=1.0)
    widget._on_motion(_event(widget, 900.0))
    assert len(emitted) == 1


@pytest.mark.qt
def test_a_press_away_from_the_edges_does_not_drag(qapp) -> None:
    widget = _histogram(qapp)
    emitted: list[tuple[float, float]] = []
    widget.window_level_dragged.connect(lambda c, w: emitted.append((c, w)))
    widget._on_press(_event(widget, 500.0))
    widget._on_motion(_event(widget, 800.0))
    assert emitted == []


@pytest.mark.qt
def test_no_drag_when_the_composed_curve_is_hidden(qapp) -> None:
    widget = _histogram(qapp)
    widget.set_overlay_curves(window=True, lut=True, composed=False)
    widget.canvas.draw()
    widget._on_press(_event(widget, 600.0))
    assert widget._drag_edge is None


@pytest.mark.qt
def test_dialog_forwards_the_drag_to_its_pane(qapp) -> None:
    from gui.dialogs.histogram_dialog import HistogramDialog

    applied: list[tuple[float, float]] = []
    dialog = HistogramDialog(
        None,
        get_window_center=lambda: 500.0,
        get_window_width=lambda: 200.0,
        set_window_level=lambda c, w: applied.append((c, w)),
    )
    dialog.histogram_widget.window_level_dragged.emit(550.0, 300.0)
    assert applied == [(550.0, 300.0)]
    _ = qapp


def test_pane_window_level_focuses_the_pane_then_sets_the_controls() -> None:
    from core.histogram_window_level import apply_pane_window_level

    calls: list[object] = []
    panes = [object(), object()]
    layout = SimpleNamespace(
        get_all_subwindows=lambda: panes,
        set_focused_subwindow=lambda pane: calls.append(("focus", panes.index(pane))),
    )
    controls = SimpleNamespace(set_window_level=lambda c, w: calls.append(("wl", c, w)))
    app = SimpleNamespace(multi_window_layout=layout, window_level_controls=controls)
    apply_pane_window_level(app, 1, 0, 40.0, 400.0)
    assert calls == [("focus", 1), ("wl", 40.0, 400.0)]
    calls.clear()
    apply_pane_window_level(app, 1, 1, 40.0, 400.0)
    assert calls == [("wl", 40.0, 400.0)]
    calls.clear()
    apply_pane_window_level(app, 5, 0, 40.0, 400.0)
    assert calls == []


def test_coordinator_binds_the_setter_to_the_histogram_pane(qapp, monkeypatch) -> None:
    from gui import dialog_coordinator as module

    captured: dict[str, object] = {}

    class _Dialog:
        def __init__(self, _parent, **kwargs):
            captured.update(kwargs)

        def update_histogram(self):
            pass

        def show(self):
            pass

        def raise_(self):
            pass

        def activateWindow(self):
            pass

    monkeypatch.setattr(module, "HistogramDialog", _Dialog)
    coordinator = module.DialogCoordinator.__new__(module.DialogCoordinator)
    coordinator.histogram_dialogs = {}
    coordinator.main_window = None
    coordinator.config_manager = SimpleNamespace(
        get_histogram_window_geometry=lambda: None,
        set_histogram_window_geometry=lambda *_a: None,
    )
    coordinator.get_focused_subwindow_index = lambda: 0
    coordinator.get_histogram_callbacks_for_subwindow = lambda _i: {"get_window_center": lambda: 1.0}
    applied: list[tuple[int, float, float]] = []
    coordinator.histogram_window_level_setter = lambda i, c, w: applied.append((i, c, w))
    coordinator.open_histogram(2)
    setter = captured["set_window_level"]
    assert callable(setter)
    setter(40.0, 400.0)
    assert applied == [(2, 40.0, 400.0)]
    _ = qapp
