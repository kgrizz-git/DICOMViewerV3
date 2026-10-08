"""Tests for HistogramDialog update paths with injected callbacks."""

from __future__ import annotations

import numpy as np
import pytest
from PySide6.QtCore import QCoreApplication, QEvent, Qt
from PySide6.QtWidgets import QWidget

from gui.dialogs.histogram_dialog import HistogramDialog


@pytest.mark.qt
def test_update_with_no_dataset_shows_empty_message(qapp) -> None:
    dlg = HistogramDialog(get_current_dataset=lambda: None)
    dlg.update_histogram()
    assert dlg.info_label.text() == "No image loaded"


@pytest.mark.qt
def test_update_with_pixel_array_callback(qapp) -> None:
    pixels = np.arange(64, dtype=np.float32).reshape(8, 8)

    class _Ds:
        pass

    dlg = HistogramDialog(
        get_current_dataset=lambda: _Ds(),
        get_current_slice_index=lambda: 0,
        get_window_center=lambda: 32.0,
        get_window_width=lambda: 64.0,
        get_use_rescaled=lambda: False,
        get_current_pixel_array=lambda: pixels,
    )
    dlg.update_histogram()
    assert dlg.info_label.text() == "Histogram of current image (Slice 1)"


@pytest.mark.qt
def test_curve_checkboxes_start_checked_and_hide_the_lut(qapp) -> None:
    dlg = HistogramDialog(get_current_dataset=lambda: None)
    assert dlg._window_curve_checkbox.isChecked()
    assert dlg._lut_curve_checkbox.isChecked()
    assert dlg._composed_curve_checkbox.isChecked()
    dlg._lut_curve_checkbox.setChecked(False)
    assert dlg.histogram_widget._show_lut_curve is False
    _ = qapp


@pytest.mark.qt
def test_reject_closes_dialog(qapp) -> None:
    dlg = HistogramDialog(get_current_dataset=lambda: None)
    dlg.reject()
    assert dlg.result() == int(dlg.DialogCode.Rejected)


@pytest.mark.qt
def test_parent_activation_raises_visible_histogram_without_restoring_minimized(
    qapp, monkeypatch
) -> None:
    parent = QWidget()
    dlg = HistogramDialog(parent, get_current_dataset=lambda: None)
    raised: list[bool] = []
    monkeypatch.setattr(dlg, "raise_", lambda: raised.append(True))
    dlg.show()

    assert dlg.windowType() == Qt.WindowType.Dialog
    assert dlg.windowFlags() & Qt.WindowType.WindowMinimizeButtonHint
    assert not (dlg.windowFlags() & Qt.WindowType.WindowStaysOnTopHint)
    QCoreApplication.sendEvent(parent, QEvent(QEvent.Type.WindowActivate))
    assert raised == [True]

    monkeypatch.setattr(dlg, "isMinimized", lambda: True)
    QCoreApplication.sendEvent(parent, QEvent(QEvent.Type.WindowActivate))
    assert raised == [True]
    dlg.close()
    parent.close()


@pytest.mark.qt
def test_parent_activation_raise_skipped_while_blocked_by_modal(
    qapp, monkeypatch
) -> None:
    parent = QWidget()
    dlg = HistogramDialog(parent, get_current_dataset=lambda: None)
    raised: list[bool] = []
    monkeypatch.setattr(dlg, "raise_", lambda: raised.append(True))
    dlg.show()

    QCoreApplication.sendEvent(dlg, QEvent(QEvent.Type.WindowBlocked))
    QCoreApplication.sendEvent(parent, QEvent(QEvent.Type.WindowActivate))
    assert raised == []

    QCoreApplication.sendEvent(dlg, QEvent(QEvent.Type.WindowUnblocked))
    QCoreApplication.sendEvent(parent, QEvent(QEvent.Type.WindowActivate))
    assert raised == [True]
    dlg.close()
    parent.close()


@pytest.mark.qt
def test_parent_activation_raise_skipped_while_hidden(qapp, monkeypatch) -> None:
    parent = QWidget()
    dlg = HistogramDialog(parent, get_current_dataset=lambda: None)
    raised: list[bool] = []
    monkeypatch.setattr(dlg, "raise_", lambda: raised.append(True))
    QCoreApplication.sendEvent(parent, QEvent(QEvent.Type.WindowActivate))
    assert raised == []
    parent.close()


@pytest.mark.qt
def test_histogram_installs_stay_on_top_helper(qapp) -> None:
    dlg = HistogramDialog(get_current_dataset=lambda: None)
    assert dlg._stay_on_top is not None
    assert not (dlg.windowFlags() & Qt.WindowType.WindowStaysOnTopHint)
    dlg.close()
