"""Tests for HistogramDialog update paths with injected callbacks."""

from __future__ import annotations

import numpy as np
import pytest

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
    assert dlg.info_label.text() != "No image loaded"


@pytest.mark.qt
def test_reject_closes_dialog(qapp) -> None:
    dlg = HistogramDialog(get_current_dataset=lambda: None)
    dlg.reject()
    assert dlg.result() == int(dlg.DialogCode.Rejected)
