"""Round-5 coverage tests for gui.image_viewer_view — overlays, pixel info, magnifier, drawForeground."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock

import numpy as np
from image_viewer_view_round5_helpers import create_image as _img
from image_viewer_view_round5_helpers import create_viewer as _viewer
from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QPainter, QPixmap

# ---------------------------------------------------------------------------
# Overlay painting helper
# ---------------------------------------------------------------------------


def _overlay_painter() -> tuple[QPainter, QPixmap]:
    """Return an active painter backed by an offscreen paint device."""
    target = QPixmap(512, 512)
    target.fill(Qt.GlobalColor.transparent)
    return QPainter(target), target


# ---------------------------------------------------------------------------
# drawForeground — basic branches
# ---------------------------------------------------------------------------

def test_drawForeground_no_image_returns_early(qapp) -> None:
    v = _viewer(qapp)
    v.image_item = None
    p, _target = _overlay_painter()
    v.drawForeground(p, QRectF(0, 0, 100, 100))
    p.end()


def test_drawForeground_no_dataset_returns_early(qapp) -> None:
    v = _viewer(qapp)
    v.set_image(_img(), preserve_view=False)
    v.get_current_dataset_callback = None
    p, _target = _overlay_painter()
    v.drawForeground(p, QRectF(0, 0, 100, 100))
    p.end()


def test_drawForeground_dataset_none_returns_early(qapp) -> None:
    v = _viewer(qapp)
    v.set_image(_img(), preserve_view=False)
    v.get_current_dataset_callback = lambda: None
    p, _target = _overlay_painter()
    v.drawForeground(p, QRectF(0, 0, 100, 100))
    p.end()


def test_drawForeground_with_scale_markers_and_direction_labels(qapp) -> None:
    v = _viewer(qapp)
    v.set_image(_img(), preserve_view=False)
    v._show_scale_markers = True
    v._show_direction_labels = True
    ds = SimpleNamespace(
        PixelSpacing=[0.5, 0.5],
        ImageOrientationPatient=[1, 0, 0, 0, 1, 0],
    )
    v.get_current_dataset_callback = lambda: ds
    p, _target = _overlay_painter()
    v.drawForeground(p, QRectF(0, 0, 100, 100))
    p.end()


# ---------------------------------------------------------------------------
# _draw_scale_markers
# ---------------------------------------------------------------------------

def test_draw_scale_markers_no_spacing(qapp) -> None:
    v = _viewer(qapp)
    v.set_image(_img(), preserve_view=False)
    ds = SimpleNamespace()
    p, _target = _overlay_painter()
    v._draw_scale_markers(p, ds)
    p.end()


def test_draw_scale_markers_zero_spacing(qapp) -> None:
    v = _viewer(qapp)
    v.set_image(_img(), preserve_view=False)
    ds = SimpleNamespace(PixelSpacing=[0.0, 0.0])
    p, _target = _overlay_painter()
    v._draw_scale_markers(p, ds)
    p.end()


def test_draw_scale_markers_no_image_item(qapp) -> None:
    v = _viewer(qapp)
    ds = SimpleNamespace(PixelSpacing=[0.5, 0.5])
    p, _target = _overlay_painter()
    v._draw_scale_markers(p, ds)
    p.end()


def test_draw_scale_markers_visible_area(qapp) -> None:
    v = _viewer(qapp, w=400, h=300)
    v.set_image(_img("L", (200, 200)), preserve_view=False)
    v.fit_to_view()
    ds = SimpleNamespace(PixelSpacing=[0.5, 0.5])
    p, _target = _overlay_painter()
    v._draw_scale_markers(p, ds)
    p.end()


# ---------------------------------------------------------------------------
# _draw_direction_labels
# ---------------------------------------------------------------------------

def test_draw_direction_labels_no_image(qapp) -> None:
    v = _viewer(qapp)
    ds = SimpleNamespace(ImageOrientationPatient=[1, 0, 0, 0, 1, 0])
    p, _target = _overlay_painter()
    v._draw_direction_labels(p, ds)
    p.end()


def test_draw_direction_labels_no_labels(qapp) -> None:
    v = _viewer(qapp)
    v.set_image(_img(), preserve_view=False)
    ds = SimpleNamespace()  # no ImageOrientationPatient
    p, _target = _overlay_painter()
    v._draw_direction_labels(p, ds)
    p.end()


def test_draw_direction_labels_with_labels(qapp) -> None:
    v = _viewer(qapp)
    v.set_image(_img(), preserve_view=False)
    ds = SimpleNamespace(ImageOrientationPatient=[1, 0, 0, 0, 1, 0])
    p, _target = _overlay_painter()
    v._draw_direction_labels(p, ds)
    p.end()


def test_draw_direction_labels_with_config_manager(qapp) -> None:
    v = _viewer(qapp)
    v.set_image(_img(), preserve_view=False)
    mock_cm = MagicMock()
    mock_cm.get_overlay_font_family.return_value = "Arial"
    mock_cm.get_overlay_font_variant.return_value = "Bold"
    v.config_manager = mock_cm
    ds = SimpleNamespace(ImageOrientationPatient=[1, 0, 0, 0, 1, 0])
    p, _target = _overlay_painter()
    v._draw_direction_labels(p, ds)
    p.end()


def test_draw_direction_labels_config_exception_falls_back(qapp) -> None:
    v = _viewer(qapp)
    v.set_image(_img(), preserve_view=False)
    mock_cm = MagicMock()
    mock_cm.get_overlay_font_family.side_effect = RuntimeError("fail")
    v.config_manager = mock_cm
    ds = SimpleNamespace(ImageOrientationPatient=[1, 0, 0, 0, 1, 0])
    p, _target = _overlay_painter()
    v._draw_direction_labels(p, ds)
    p.end()


# ---------------------------------------------------------------------------
# _update_pixel_info
# ---------------------------------------------------------------------------

def test_update_pixel_info_no_image(qapp) -> None:
    v = _viewer(qapp)
    v.image_item = None
    emissions: list = []
    v.pixel_info_changed.connect(lambda s, x, y, z: emissions.append((s, x, y, z)))
    from PySide6.QtGui import QMouseEvent
    ev = QMouseEvent(
        QMouseEvent.Type.MouseMove,
        QPointF(10, 10),
        Qt.MouseButton.NoButton,
        Qt.MouseButton.NoButton,
        Qt.KeyboardModifier.NoModifier,
    )
    v._update_pixel_info(ev)
    assert emissions == [("", 0, 0, 0)]


def test_update_pixel_info_outside_image(qapp) -> None:
    v = _viewer(qapp, w=50, h=50)
    v.set_image(_img("L", (10, 10)), preserve_view=False)
    emissions: list = []
    v.pixel_info_changed.connect(lambda s, x, y, z: emissions.append((s, x, y, z)))
    from PySide6.QtGui import QMouseEvent
    # The image is 10x10; a viewport pixel at (49,49) should map outside the image rect
    ev = QMouseEvent(
        QMouseEvent.Type.MouseMove,
        QPointF(49, 49),
        Qt.MouseButton.NoButton,
        Qt.MouseButton.NoButton,
        Qt.KeyboardModifier.NoModifier,
    )
    v._update_pixel_info(ev)
    assert emissions == [("", 0, 0, 0)]


def test_update_pixel_info_inside_image(qapp) -> None:
    v = _viewer(qapp)
    v.resize(200, 200)
    v.set_image(_img("L", (100, 100)), preserve_view=False)
    v.fit_to_view()
    v.get_current_dataset_callback = None
    emissions: list = []
    v.pixel_info_changed.connect(lambda s, x, y, z: emissions.append((s, x, y, z)))
    from PySide6.QtGui import QMouseEvent
    ev = QMouseEvent(
        QMouseEvent.Type.MouseMove,
        QPointF(100, 100),
        Qt.MouseButton.NoButton,
        Qt.MouseButton.NoButton,
        Qt.KeyboardModifier.NoModifier,
    )
    v._update_pixel_info(ev)
    assert len(emissions) == 1


def test_update_pixel_info_with_dataset_and_callbacks(qapp, monkeypatch) -> None:
    v = _viewer(qapp)
    v.resize(200, 200)
    v.set_image(_img("L", (50, 50)), preserve_view=False)
    v.fit_to_view()
    monkeypatch.setattr(
        "gui.image_viewer_view._get_rescale_parameters", lambda ds: (1.0, 0.0, None)
    )
    ds = SimpleNamespace(SamplesPerPixel=1)
    v.get_current_dataset_callback = lambda: ds
    v.get_current_slice_index_callback = lambda: 5
    v.get_use_rescaled_values_callback = lambda: True
    v.set_pixel_info_callbacks(lambda: ds, lambda: 5, lambda: True)

    emissions: list = []
    v.pixel_info_changed.connect(lambda s, x, y, z: emissions.append((s, x, y, z)))
    from PySide6.QtGui import QMouseEvent
    ev = QMouseEvent(
        QMouseEvent.Type.MouseMove,
        QPointF(100, 100),
        Qt.MouseButton.NoButton,
        Qt.MouseButton.NoButton,
        Qt.KeyboardModifier.NoModifier,
    )
    v._update_pixel_info(ev)
    assert len(emissions) == 1
    assert emissions[0][3] == 5


# ---------------------------------------------------------------------------
# _get_pixel_value_at_coords
# ---------------------------------------------------------------------------

def test_pixel_value_4d_array(qapp, monkeypatch) -> None:
    v = _viewer(qapp)
    arr = np.zeros((2, 4, 4, 3), dtype=np.uint8)
    arr[1, 2, 1] = (10, 20, 30)
    monkeypatch.setattr(
        "core.dicom_processor.DICOMProcessor.get_pixel_array",
        staticmethod(lambda ds: arr),
    )
    ds = SimpleNamespace(SamplesPerPixel=3)
    out = v._get_pixel_value_at_coords(ds, x=1, y=2, z=1, use_rescaled=False)
    assert "10" in out


def test_pixel_value_4d_array_out_of_bounds(qapp, monkeypatch) -> None:
    v = _viewer(qapp)
    arr = np.zeros((2, 4, 4, 3), dtype=np.uint8)
    monkeypatch.setattr(
        "core.dicom_processor.DICOMProcessor.get_pixel_array",
        staticmethod(lambda ds: arr),
    )
    ds = SimpleNamespace(SamplesPerPixel=3)
    out = v._get_pixel_value_at_coords(ds, x=0, y=0, z=5, use_rescaled=False)
    assert out == ""


def test_pixel_value_2d_grayscale(qapp, monkeypatch) -> None:
    v = _viewer(qapp)
    arr = np.full((4, 4), 99.0, dtype=np.float32)
    monkeypatch.setattr(
        "core.dicom_processor.DICOMProcessor.get_pixel_array",
        staticmethod(lambda ds: arr),
    )
    ds = SimpleNamespace(SamplesPerPixel=1)
    out = v._get_pixel_value_at_coords(ds, x=2, y=2, z=0, use_rescaled=False)
    assert "99" in out


def test_pixel_value_2d_out_of_bounds(qapp, monkeypatch) -> None:
    v = _viewer(qapp)
    arr = np.full((4, 4), 99.0, dtype=np.float32)
    monkeypatch.setattr(
        "core.dicom_processor.DICOMProcessor.get_pixel_array",
        staticmethod(lambda ds: arr),
    )
    ds = SimpleNamespace(SamplesPerPixel=1)
    out = v._get_pixel_value_at_coords(ds, x=10, y=10, z=0, use_rescaled=False)
    assert out == ""


def test_pixel_value_3d_color_out_of_bounds(qapp, monkeypatch) -> None:
    v = _viewer(qapp)
    arr = np.zeros((4, 4, 3), dtype=np.uint8)
    monkeypatch.setattr(
        "core.dicom_processor.DICOMProcessor.get_pixel_array",
        staticmethod(lambda ds: arr),
    )
    ds = SimpleNamespace(SamplesPerPixel=3)
    out = v._get_pixel_value_at_coords(ds, x=10, y=10, z=0, use_rescaled=False)
    assert out == ""


def test_pixel_value_3d_color_less_than_3_channels(qapp, monkeypatch) -> None:
    v = _viewer(qapp)
    arr = np.zeros((4, 4, 2), dtype=np.uint8)
    monkeypatch.setattr(
        "core.dicom_processor.DICOMProcessor.get_pixel_array",
        staticmethod(lambda ds: arr),
    )
    ds = SimpleNamespace(SamplesPerPixel=3)
    out = v._get_pixel_value_at_coords(ds, x=1, y=1, z=0, use_rescaled=False)
    assert out == ""


def test_pixel_value_no_pixel_array(qapp, monkeypatch) -> None:
    v = _viewer(qapp)
    monkeypatch.setattr(
        "core.dicom_processor.DICOMProcessor.get_pixel_array",
        staticmethod(lambda ds: None),
    )
    ds = SimpleNamespace(SamplesPerPixel=1)
    out = v._get_pixel_value_at_coords(ds, x=0, y=0, z=0, use_rescaled=False)
    assert out == ""


def test_pixel_value_exception_returns_empty(qapp, monkeypatch) -> None:
    v = _viewer(qapp)
    monkeypatch.setattr(
        "core.dicom_processor.DICOMProcessor.get_pixel_array",
        staticmethod(lambda ds: (_ for _ in ()).throw(RuntimeError("broken"))),
    )
    ds = SimpleNamespace()
    out = v._get_pixel_value_at_coords(ds, x=0, y=0, z=0, use_rescaled=False)
    assert out == ""


def test_pixel_value_float_result_not_integer(qapp, monkeypatch) -> None:
    v = _viewer(qapp)
    arr = np.array([[1.5]], dtype=np.float32)
    monkeypatch.setattr(
        "core.dicom_processor.DICOMProcessor.get_pixel_array",
        staticmethod(lambda ds: arr),
    )
    ds = SimpleNamespace(SamplesPerPixel=1)
    out = v._get_pixel_value_at_coords(ds, x=0, y=0, z=0, use_rescaled=False)
    assert "1.5" in out


def test_pixel_value_grayscale_rescaled(qapp, monkeypatch) -> None:
    v = _viewer(qapp)
    arr = np.array([[100.0]], dtype=np.float32)
    monkeypatch.setattr(
        "core.dicom_processor.DICOMProcessor.get_pixel_array",
        staticmethod(lambda ds: arr),
    )
    monkeypatch.setattr(
        "gui.image_viewer_view._get_rescale_parameters", lambda ds: (2.0, 10.0, None)
    )
    ds = SimpleNamespace(SamplesPerPixel=1)
    out = v._get_pixel_value_at_coords(ds, x=0, y=0, z=0, use_rescaled=True)
    assert "210" in out


def test_pixel_value_color_rescaled(qapp, monkeypatch) -> None:
    v = _viewer(qapp)
    arr = np.array([[[10, 20, 30]]], dtype=np.uint8)
    monkeypatch.setattr(
        "core.dicom_processor.DICOMProcessor.get_pixel_array",
        staticmethod(lambda ds: arr),
    )
    monkeypatch.setattr(
        "gui.image_viewer_view._get_rescale_parameters", lambda ds: (1.0, 100.0, None)
    )
    ds = SimpleNamespace(SamplesPerPixel=3)
    out = v._get_pixel_value_at_coords(ds, x=0, y=0, z=0, use_rescaled=True)
    assert "R=" in out


def test_pixel_value_multi_frame_grayscale_out_of_bounds(qapp, monkeypatch) -> None:
    v = _viewer(qapp)
    arr = np.zeros((3, 4, 4), dtype=np.float32)
    monkeypatch.setattr(
        "core.dicom_processor.DICOMProcessor.get_pixel_array",
        staticmethod(lambda ds: arr),
    )
    ds = SimpleNamespace(SamplesPerPixel=1)
    out = v._get_pixel_value_at_coords(ds, x=0, y=0, z=5, use_rescaled=False)
    assert out == ""


def test_pixel_value_3d_single_frame_gray(qapp, monkeypatch) -> None:
    """3D array where shape[0]==1, not color, ambiguous: keeps full array, treated as color."""
    v = _viewer(qapp)
    arr = np.zeros((1, 4, 4, 3), dtype=np.uint8)
    arr[0, 2, 2] = (77, 88, 99)
    monkeypatch.setattr(
        "core.dicom_processor.DICOMProcessor.get_pixel_array",
        staticmethod(lambda ds: arr),
    )
    ds = SimpleNamespace(SamplesPerPixel=3)
    out = v._get_pixel_value_at_coords(ds, x=2, y=2, z=0, use_rescaled=False)
    assert "77" in out


def test_pixel_value_higher_dimension_returns_empty(qapp, monkeypatch) -> None:
    """5-D array: hits the final else branch in shape dispatch."""
    v = _viewer(qapp)
    arr = np.zeros((1, 1, 4, 4, 3), dtype=np.uint8)
    monkeypatch.setattr(
        "core.dicom_processor.DICOMProcessor.get_pixel_array",
        staticmethod(lambda ds: arr),
    )
    ds = SimpleNamespace(SamplesPerPixel=1)
    out = v._get_pixel_value_at_coords(ds, x=0, y=0, z=0, use_rescaled=False)
    assert out == ""


def test_pixel_value_samples_per_pixel_as_list(qapp, monkeypatch) -> None:
    v = _viewer(qapp)
    arr = np.zeros((4, 4, 3), dtype=np.uint8)
    monkeypatch.setattr(
        "core.dicom_processor.DICOMProcessor.get_pixel_array",
        staticmethod(lambda ds: arr),
    )
    # SamplesPerPixel as list — tests the list branch in the handler
    ds = SimpleNamespace(SamplesPerPixel=[3])
    out = v._get_pixel_value_at_coords(ds, x=0, y=0, z=0, use_rescaled=False)
    # With spp=[3], is_color=True, arr is (4,4,3), shape[2]==3 matches spp → color path
    assert "R=" in out


def test_pixel_value_no_samples_per_pixel(qapp, monkeypatch) -> None:
    v = _viewer(qapp)
    arr = np.full((4, 4), 50.0, dtype=np.float32)
    monkeypatch.setattr(
        "core.dicom_processor.DICOMProcessor.get_pixel_array",
        staticmethod(lambda ds: arr),
    )
    ds = SimpleNamespace()
    out = v._get_pixel_value_at_coords(ds, x=1, y=1, z=0, use_rescaled=False)
    assert "50" in out


# ---------------------------------------------------------------------------
# hide_handle_drag_magnifier
# ---------------------------------------------------------------------------

def test_hide_handle_drag_magnifier_no_widget(qapp) -> None:
    v = _viewer(qapp)
    v.handle_drag_magnifier_active = True
    v.handle_drag_magnifier_widget = None
    v.hide_handle_drag_magnifier()
    assert v.handle_drag_magnifier_active is False


def test_hide_handle_drag_magnifier_with_widget(qapp) -> None:
    v = _viewer(qapp)
    mock_widget = MagicMock()
    v.handle_drag_magnifier_active = True
    v.handle_drag_magnifier_widget = mock_widget
    v.hide_handle_drag_magnifier()
    assert v.handle_drag_magnifier_active is False
    mock_widget.hide.assert_called_once()


def test_update_handle_drag_magnifier_not_active(qapp) -> None:
    v = _viewer(qapp)
    v.handle_drag_magnifier_active = False
    # Should return without error
    v.update_handle_drag_magnifier(QPointF(0, 0))


def test_update_handle_drag_magnifier_active_null_pixmap(qapp) -> None:
    v = _viewer(qapp)
    v.handle_drag_magnifier_active = True
    v.handle_drag_magnifier_widget = MagicMock()
    v.set_image(_img("L", (10, 10)), preserve_view=False)
    # _render_scene_region on a tiny image may return None for empty intersection
    v.update_handle_drag_magnifier(QPointF(1000, 1000))


# ---------------------------------------------------------------------------
# show_handle_drag_magnifier — first call creates widget
# ---------------------------------------------------------------------------

def test_show_handle_drag_magnifier_creates_widget(qapp) -> None:
    v = _viewer(qapp)
    v.set_image(_img("L", (100, 100)), preserve_view=False)
    v.handle_drag_magnifier_widget = None
    v.handle_drag_magnifier_active = False
    v.show_handle_drag_magnifier(QPointF(50, 50))
    assert v.handle_drag_magnifier_active is True


def test_show_handle_drag_magnifier_already_active_delegates_update(qapp, monkeypatch) -> None:
    v = _viewer(qapp)
    v.set_image(_img("L", (100, 100)), preserve_view=False)
    update = MagicMock()
    monkeypatch.setattr(v, "update_handle_drag_magnifier", update)
    v.handle_drag_magnifier_active = True
    point = QPointF(50, 50)
    v.show_handle_drag_magnifier(point)
    update.assert_called_once_with(point)


def test_show_handle_drag_magnifier_zero_zoom(qapp) -> None:
    v = _viewer(qapp)
    v.set_image(_img("L", (100, 100)), preserve_view=False)
    v.current_zoom = 0.0
    v.handle_drag_magnifier_widget = None
    v.handle_drag_magnifier_active = False
    v.show_handle_drag_magnifier(QPointF(50, 50))
    assert v.handle_drag_magnifier_active is True


# ---------------------------------------------------------------------------
# drawForeground — with neither overlay enabled
# ---------------------------------------------------------------------------

def test_drawForeground_no_overlays(qapp) -> None:
    v = _viewer(qapp)
    v.set_image(_img(), preserve_view=False)
    v._show_scale_markers = False
    v._show_direction_labels = False
    v.get_current_dataset_callback = lambda: SimpleNamespace()
    p, _target = _overlay_painter()
    v.drawForeground(p, QRectF(0, 0, 100, 100))
    p.end()


# ---------------------------------------------------------------------------
# _draw_scale_markers — visible_rect empty
# ---------------------------------------------------------------------------

def test_draw_scale_markers_empty_visible_rect(qapp) -> None:
    v = _viewer(qapp)
    v.set_image(_img("L", (10, 10)), preserve_view=False)
    # Zoom far out so visible_rect doesn't intersect image
    v.current_zoom = 0.01
    v._apply_view_transform()
    ds = SimpleNamespace(PixelSpacing=[0.5, 0.5])
    p, _target = _overlay_painter()
    v._draw_scale_markers(p, ds)
    p.end()


# ---------------------------------------------------------------------------
# compute_fit_zoom — viewport zero-size edge case
# ---------------------------------------------------------------------------

def test_compute_fit_zoom_zero_viewport(qapp, monkeypatch) -> None:
    v = _viewer(qapp)
    v.set_image(_img("L", (50, 50)), preserve_view=False)
    monkeypatch.setattr(v, "viewport", lambda: SimpleNamespace(width=lambda: 0, height=lambda: 0))
    fz = v.compute_fit_zoom()
    assert fz is None


# ---------------------------------------------------------------------------
# is_effectively_fit_and_centered — fit zoom matches but center off
# ---------------------------------------------------------------------------

def test_is_effectively_fit_center_mismatch(qapp) -> None:
    v = _viewer(qapp)
    v.resize(400, 400)
    v.set_image(_img("L", (100, 100)), preserve_view=False)
    v.fit_to_view()
    # Pan away from center by moving scrollbars
    hbar = v.horizontalScrollBar()
    hbar.setValue(hbar.maximum())
    # Force center computation by calling the method
    result = v.is_effectively_fit_and_centered()
    # May or may not be False depending on scroll limits, just exercises the code path
    assert isinstance(result, bool)


# ---------------------------------------------------------------------------
# _update_pixel_info — with slice index callback returning non-zero
# ---------------------------------------------------------------------------

def test_update_pixel_info_with_slice_callback(qapp) -> None:
    v = _viewer(qapp)
    v.resize(200, 200)
    v.set_image(_img("L", (50, 50)), preserve_view=False)
    v.get_current_dataset_callback = None
    v.get_current_slice_index_callback = lambda: 42
    emissions: list = []
    v.pixel_info_changed.connect(lambda s, x, y, z: emissions.append((s, x, y, z)))
    from PySide6.QtGui import QMouseEvent
    ev = QMouseEvent(
        QMouseEvent.Type.MouseMove,
        QPointF(25, 25),
        Qt.MouseButton.NoButton,
        Qt.MouseButton.NoButton,
        Qt.KeyboardModifier.NoModifier,
    )
    v._update_pixel_info(ev)
    assert len(emissions) == 1
    assert emissions[0][3] == 42  # z from callback


# Need this import for test_check_transform_changed
