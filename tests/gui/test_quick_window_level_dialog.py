"""Tests for QuickWindowLevelDialog apply callback and defaults."""

from __future__ import annotations

import pytest

from gui.dialogs.quick_window_level_dialog import QuickWindowLevelDialog


@pytest.mark.qt
def test_initial_values_and_unit_labels(qapp) -> None:
    dlg = QuickWindowLevelDialog(
        initial_center=40.0,
        initial_width=400.0,
        unit="HU",
    )
    assert dlg._center_spinbox.value() == 40.0
    assert dlg._width_spinbox.value() == 400.0
    assert "HU" in dlg._center_label.text()
    assert "HU" in dlg._width_label.text()


@pytest.mark.qt
def test_accept_invokes_apply_callback(qapp) -> None:
    applied: list[tuple[float, float]] = []
    dlg = QuickWindowLevelDialog(
        initial_center=10.0,
        initial_width=100.0,
        apply_callback=lambda c, w: applied.append((c, w)),
    )
    dlg._center_spinbox.setValue(25.5)
    dlg._width_spinbox.setValue(250.0)
    dlg._on_accept()
    assert applied == [(25.5, 250.0)]
    assert dlg.result() == int(dlg.DialogCode.Accepted)


@pytest.mark.qt
def test_accept_clamps_nonpositive_width_to_one(qapp) -> None:
    applied: list[tuple[float, float]] = []
    dlg = QuickWindowLevelDialog(
        width_range=(0.0, 10000.0),
        apply_callback=lambda c, w: applied.append((c, w)),
    )
    dlg._width_spinbox.setValue(0.0)
    dlg._on_accept()
    assert applied[0][1] == 1.0
