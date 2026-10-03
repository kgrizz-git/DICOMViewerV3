"""
QImage stride consistency for color-LUT output.

Every Qt consumer of an RGB LUT result builds a ``QImage`` from a packed byte
buffer. A mismatched ``bytesPerLine`` skews each row by the difference, which
is invisible on widths whose RGB rows happen to be 4-byte aligned. Widths 63,
65 and 101 are not, so a hardcoded or padded stride shows up here.

The histogram and menu strip (``LutTransferFunctionWidget``) and the toolbar
swatch are covered too. The MPR thumbnail always builds a ``THUMBNAIL_SIZE`` square, so it is tested
with its real 68-pixel buffer. ``3 * 68 = 204`` is aligned: that case checks
buffer/stride agreement, not the unaligned path.
"""

from __future__ import annotations

from typing import Any, ClassVar

import numpy as np
import pytest
from PIL import Image
from PySide6.QtGui import QImage

from core.lut_catalog import colormap_lut
from core.lut_display import apply_user_invert_and_lut
from core.lut_engine import apply_lut_to_uint8

_ODD_WIDTHS = (63, 65, 101)


class _QImageSpy:
    """Stands in for ``QImage`` in one module and records each buffer constructor."""

    Format = QImage.Format
    calls: ClassVar[list[tuple[Any, ...]]] = []

    def __new__(cls, *args: Any) -> QImage:  # type: ignore[misc]
        cls.calls.append(args)
        return QImage(*args)


def _spy(monkeypatch: pytest.MonkeyPatch, module: str) -> type[_QImageSpy]:
    _QImageSpy.calls = []
    monkeypatch.setattr(f"{module}.QImage", _QImageSpy)
    return _QImageSpy


def _rgb_pixels(image: QImage) -> np.ndarray:
    """Copy a QImage into a packed ``(H, W, 3)`` array, dropping any row padding."""
    rgb = image.convertToFormat(QImage.Format.Format_RGB888)
    rows = np.frombuffer(rgb.constBits(), dtype=np.uint8).reshape(rgb.height(), rgb.bytesPerLine())
    return rows[:, : rgb.width() * 3].reshape(rgb.height(), rgb.width(), 3).copy()


def _ramp(height: int, width: int) -> np.ndarray:
    """uint8 codes that differ along both axes, so a row skew changes pixels."""
    rows = np.arange(height, dtype=np.int64).reshape(-1, 1) * 7
    cols = np.arange(width, dtype=np.int64).reshape(1, -1) * 3
    return ((rows + cols) % 256).astype(np.uint8)


def _buffer_strides(calls: list[tuple[Any, ...]]) -> list[tuple[int, int]]:
    """``(len(buffer) // height, bytesPerLine)`` for each buffer-backed RGB888 call."""
    found = []
    for args in calls:
        if len(args) == 5 and args[4] == QImage.Format.Format_RGB888:
            data, _width, height, bytes_per_line, _fmt = args
            found.append((len(bytes(data)) // height, bytes_per_line))
    return found


@pytest.mark.qt
@pytest.mark.parametrize("width", _ODD_WIDTHS)
def test_viewer_color_lut_has_no_row_skew(qapp, monkeypatch, width: int) -> None:
    from gui.image_viewer import ImageViewer

    spy = _spy(monkeypatch, "gui.image_viewer_view")
    expected = apply_lut_to_uint8(_ramp(9, width), colormap_lut("hot"))
    viewer = ImageViewer()
    viewer.set_image(Image.fromarray(expected, mode="RGB"), apply_inversion=False)
    assert viewer.image_item is not None
    shown = _rgb_pixels(viewer.image_item.pixmap().toImage())
    assert np.array_equal(shown, expected)
    strides = _buffer_strides(spy.calls)
    assert strides, "set_image did not build an RGB888 QImage from a buffer"
    for packed, passed in strides:
        assert passed == packed
    _ = qapp


@pytest.mark.qt
def test_thumbnail_color_lut_stride_matches_its_68px_buffer(qapp, monkeypatch) -> None:
    from gui.mpr_thumbnail_widget import MprThumbnailWidget

    size = MprThumbnailWidget.THUMBNAIL_SIZE
    assert size == 68
    spy = _spy(monkeypatch, "gui.mpr_thumbnail_widget")
    codes = _ramp(size, size)
    lut = colormap_lut("viridis")
    widget = MprThumbnailWidget(0)
    # Center 127.5 / width 255 maps code c to c exactly, so the expected
    # pixels are the LUT of the input codes with no resampling (68 fits).
    widget.update_preview(codes.astype(np.float32), 127.5, 255.0, "MONOCHROME2", lut=lut)
    assert widget._preview_pixmap is not None
    expected = apply_user_invert_and_lut(codes, image_inverted=False, lut=lut)
    assert np.array_equal(_rgb_pixels(widget._preview_pixmap.toImage()), expected)
    assert _buffer_strides(spy.calls) == [(3 * size, 3 * size)]
    _ = qapp


@pytest.mark.qt
def test_lut_swatch_icon_stride_matches_its_buffer(qapp, monkeypatch) -> None:
    from gui import lut_actions

    spy = _spy(monkeypatch, "gui.lut_actions")
    icon = lut_actions.swatch_icon(colormap_lut("hot"))
    assert not icon.isNull()
    strides = _buffer_strides(spy.calls)
    assert strides
    for packed, passed in strides:
        assert passed == packed
    _ = qapp


@pytest.mark.qt
def test_transfer_widget_strip_stride_matches_its_buffer(qapp, monkeypatch) -> None:
    from gui.widgets.lut_transfer_function_widget import LutTransferFunctionWidget

    spy = _spy(monkeypatch, "gui.widgets.lut_transfer_function_widget")
    widget = LutTransferFunctionWidget()
    widget.resize(200, 80)
    widget.set_lut(colormap_lut("hot"), window_center=40.0, window_width=400.0)
    assert not widget.grab().isNull()
    strides = _buffer_strides(spy.calls)
    assert strides == [(3 * 256, 3 * 256)]
    _ = qapp
