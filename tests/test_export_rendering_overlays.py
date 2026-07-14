"""
Golden-image characterization tests for export_rendering.render_overlays_and_rois.

The export path is pixel output, so these tests render fixed scenarios and compare
against a digest of the raw pixel buffer captured from the pre-refactor
implementation. Any change to geometry, colour, clamping or draw order will move
the digest.

Font rasterization is *not* portable: FreeType hinting and font fallback differ
between macOS and the Linux CI runner, so hashing text drawn with the bundled
TrueType fonts produces different digests per platform. The ``deterministic_font``
fixture below pins every font lookup to Pillow's built-in bitmap font, which has
no FreeType or system-font dependency and rasterizes identically everywhere. Text
is still drawn (so draw.text and the textbbox-driven right-alignment are exercised)
— it is just drawn in a font that does not vary by OS.

The digests therefore depend only on the installed Pillow. A Pillow upgrade that
changes the default font will legitimately invalidate them; regenerate by clearing
GOLDENS, running, and pasting the reported digests back in — reviewing the diff.
"""

from __future__ import annotations

import hashlib
from typing import Any
from unittest.mock import MagicMock

import pytest
from PIL import Image, ImageFont
from pydicom.dataset import Dataset

from gui import export_rendering
from gui.export_rendering import render_overlays_and_rois
from tools.angle_measurement_items import AngleMeasurementItem


@pytest.fixture(autouse=True)
def deterministic_font(monkeypatch):
    """
    Pin every font lookup to Pillow's built-in bitmap font.

    Called with no size argument this is a fixed bitmap font: no FreeType, no
    system-font fallback, so it rasterizes identically on macOS and on the Linux
    CI runner. Without this, the golden digests below are platform-specific.
    """
    monkeypatch.setattr(
        export_rendering,
        "_load_font_with_fallback",
        lambda *_args, **_kwargs: ImageFont.load_default(),
    )


class _Pt:
    """Stand-in for QPointF."""

    def __init__(self, x: float, y: float) -> None:
        self._x, self._y = x, y

    def x(self) -> float:
        return self._x

    def y(self) -> float:
        return self._y


class _Rect:
    """Stand-in for QRectF as returned by ROI.get_bounds()."""

    def __init__(self, left: float, top: float, right: float, bottom: float) -> None:
        self._l, self._t, self._r, self._b = left, top, right, bottom

    def left(self) -> float:
        return self._l

    def top(self) -> float:
        return self._t

    def right(self) -> float:
        return self._r

    def bottom(self) -> float:
        return self._b


class _ROI:
    def __init__(self, shape_type, bounds, statistics=None, visible=None, show=True):
        self.shape_type = shape_type
        self._bounds = bounds
        self.statistics = statistics or {}
        self.visible_statistics = visible or []
        self.statistics_overlay_visible = show

    def get_bounds(self) -> _Rect:
        return self._bounds


class _Distance:
    def __init__(self, start: _Pt, end_rel: _Pt, label: str) -> None:
        self.start_point = start
        self.end_relative = end_rel
        self.distance_formatted = label


class _TextItem:
    def __init__(self, x: float, y: float, text: str) -> None:
        self._pos = _Pt(x, y)
        self._text = text

    def scenePos(self) -> _Pt:
        return self._pos

    def toPlainText(self) -> str:
        return self._text


class _ArrowItem:
    def __init__(self, x, y, start: _Pt, end: _Pt) -> None:
        self._pos = _Pt(x, y)
        self.start_point = start
        self.end_point = end

    def pos(self) -> _Pt:
        return self._pos


class _Config:
    """Config manager stub with the getters the renderer consults."""

    def get_roi_line_color(self):
        return (255, 0, 0)

    def get_roi_font_color(self):
        return (255, 255, 0)

    def get_roi_line_thickness(self):
        return 2

    def get_roi_font_size(self):
        return 6

    def get_roi_font_family(self):
        return "IBM Plex Sans"

    def get_roi_font_variant(self):
        return "Bold"

    def get_measurement_line_color(self):
        return (0, 255, 0)

    def get_measurement_font_color(self):
        return (0, 255, 0)

    def get_measurement_line_thickness(self):
        return 2

    def get_measurement_font_size(self):
        return 6

    def get_measurement_font_family(self):
        return "IBM Plex Sans"

    def get_measurement_font_variant(self):
        return "Bold"

    def get_text_annotation_font_size(self):
        return 6

    def get_text_annotation_color(self):
        return (0, 128, 255)

    def get_text_annotation_font_family(self):
        return "IBM Plex Sans"

    def get_text_annotation_font_variant(self):
        return "Bold"

    def get_arrow_annotation_size(self):
        return 3

    def get_arrow_annotation_color(self):
        return (255, 0, 255)

    def get_overlay_font_size(self):
        return 6

    def get_overlay_font_family(self):
        return "IBM Plex Sans"

    def get_overlay_font_variant(self):
        return "Bold"

    def get_overlay_tags(self, _modality):
        return {
            "upper_left": ["PatientName", "PatientID"],
            "upper_right": ["Modality"],
            # InstanceNumber carries the "Slice X/Y" + projection range/thickness text.
            "lower_left": ["StudyDate", "InstanceNumber", "SliceThickness"],
            "lower_right": ["SeriesDescription"],
        }


class _Overlay:
    font_color = (255, 255, 0)
    privacy_mode = False


STUDY = "1.2.3.4"
SERIES = "1.2.3.4.5"


def _dataset() -> Dataset:
    ds = Dataset()
    ds.StudyInstanceUID = STUDY
    ds.SeriesInstanceUID = SERIES
    ds.PatientName = "DOE^JANE"
    ds.PatientID = "PID-001"
    ds.Modality = "CT"
    ds.StudyDate = "20260101"
    ds.SeriesDescription = "AXIAL"
    ds.SliceThickness = "2.5"
    ds.InstanceNumber = 1
    ds.Rows = 128
    ds.Columns = 128
    return ds


def _series_key(ds: Dataset) -> str:
    from utils.dicom_utils import get_composite_series_key

    return get_composite_series_key(ds)


def _roi_manager(rois):
    m = MagicMock()
    m.get_rois_for_slice.return_value = rois
    return m


def _measurement_tool(ds: Dataset, measurements):
    m = MagicMock()
    m.measurements = {(STUDY, _series_key(ds), 0): measurements}
    return m


def _text_tool(items):
    m = MagicMock()
    m.get_annotations_for_slice.return_value = items
    return m


def _arrow_tool(items):
    m = MagicMock()
    m.get_arrows_for_slice.return_value = items
    return m


def _base_image() -> Image.Image:
    # Deterministic non-uniform grayscale so drawing is visible against it.
    img = Image.new("L", (128, 128))
    img.putdata([(x * 2 + y) % 256 for y in range(128) for x in range(128)])
    return img


def _digest(image: Image.Image) -> str:
    return hashlib.sha256(image.tobytes()).hexdigest()[:16]


def _render(**overrides: Any) -> Image.Image:
    ds = _dataset()
    kwargs: dict[str, Any] = {
        "image": _base_image(),
        "dataset": ds,
        "roi_manager": None,
        "overlay_manager": None,
        "measurement_tool": None,
        "config_manager": _Config(),
        "study_uid": STUDY,
        "series_uid": SERIES,
        "slice_index": 0,
        "total_slices": 10,
    }
    kwargs.update(overrides)
    return render_overlays_and_rois(**kwargs)


# --- structural invariants (font/Pillow independent) ------------------------

def test_grayscale_input_is_converted_to_rgb():
    out = _render()
    assert out.mode == "RGB"
    assert out.size == (128, 128)


def test_no_annotations_leaves_pixels_untouched():
    base = _base_image().convert("RGB")
    out = _render()
    assert out.tobytes() == base.tobytes()


def test_missing_slice_index_skips_all_annotation_drawing():
    base = _base_image().convert("RGB")
    ds = _dataset()
    out = _render(
        slice_index=None,
        roi_manager=_roi_manager([_ROI("rectangle", _Rect(10, 10, 60, 60))]),
        measurement_tool=_measurement_tool(ds, [_Distance(_Pt(5, 5), _Pt(40, 30), "10 mm")]),
    )
    assert out.tobytes() == base.tobytes()


def test_roi_bounds_are_clamped_to_the_image():
    """An ROI extending past the edges must not raise and must stay in-bounds."""
    out = _render(
        roi_manager=_roi_manager([_ROI("rectangle", _Rect(-500, -500, 5000, 5000))]),
    )
    assert out.size == (128, 128)


def test_unknown_shape_type_draws_nothing():
    base = _base_image().convert("RGB")
    out = _render(roi_manager=_roi_manager([_ROI("polygon", _Rect(10, 10, 60, 60))]))
    assert out.tobytes() == base.tobytes()


def test_statistics_hidden_when_overlay_not_visible():
    stats = {"mean": 12.0}
    visible_out = _render(
        roi_manager=_roi_manager(
            [_ROI("rectangle", _Rect(10, 10, 60, 60), stats, ["mean"], show=True)]
        )
    )
    hidden_out = _render(
        roi_manager=_roi_manager(
            [_ROI("rectangle", _Rect(10, 10, 60, 60), stats, ["mean"], show=False)]
        )
    )
    assert visible_out.tobytes() != hidden_out.tobytes()


def test_text_annotation_tool_failure_is_swallowed():
    tool = MagicMock()
    tool.get_annotations_for_slice.side_effect = RuntimeError("boom")
    out = _render(text_annotation_tool=tool)
    assert out.size == (128, 128)


def test_arrow_annotation_tool_failure_is_swallowed():
    tool = MagicMock()
    tool.get_arrows_for_slice.side_effect = RuntimeError("boom")
    out = _render(arrow_annotation_tool=tool)
    assert out.size == (128, 128)


def test_aggregate_managers_union_annotations_from_every_subwindow():
    single = _render(
        roi_manager=_roi_manager([_ROI("rectangle", _Rect(10, 10, 40, 40))]),
    )
    aggregate = _render(
        roi_manager=_roi_manager([_ROI("rectangle", _Rect(10, 10, 40, 40))]),
        subwindow_annotation_managers=[
            {"roi_manager": _roi_manager([_ROI("rectangle", _Rect(10, 10, 40, 40))])},
            {"roi_manager": _roi_manager([_ROI("ellipse", _Rect(70, 70, 110, 110))])},
        ],
    )
    # The aggregate pass must include the second subwindow's ellipse.
    assert aggregate.tobytes() != single.tobytes()


def test_coordinate_scale_moves_annotations():
    roi = [_ROI("rectangle", _Rect(10, 10, 40, 40))]
    a = _render(roi_manager=_roi_manager(roi))
    b = _render(roi_manager=_roi_manager(roi), coordinate_scale=2.0)
    assert a.tobytes() != b.tobytes()


# --- golden digests ---------------------------------------------------------
#
# Captured from the pre-refactor implementation. These pin exact pixel output.

GOLDENS: dict[str, str] = {
    "rois": "ceef38d0b43508b2",
    "measurements": "384341a11e605b12",
    "text_and_arrows": "ef1ea2459a22b44b",
    "overlay_corners": "e172c48717d3539e",
    "projection_overlay": "15dcc9d03026c0b8",
    "everything": "f555d4ecff134ca9",
}


def _scenario_rois() -> Image.Image:
    return _render(
        roi_manager=_roi_manager([
            _ROI(
                "rectangle",
                _Rect(10, 10, 60, 50),
                {"mean": 12.5, "std": 3.25, "min": 1.0, "max": 99.0,
                 "area": 42.0, "count": 7},
                ["mean", "std", "min", "max", "area", "count"],
            ),
            _ROI("ellipse", _Rect(70, 70, 120, 115)),
        ]),
    )


def _scenario_measurements() -> Image.Image:
    ds = _dataset()
    angle = MagicMock(spec=AngleMeasurementItem)
    angle.p1 = _Pt(10, 100)
    angle.p2 = _Pt(40, 60)
    angle.p3 = _Pt(90, 90)
    angle.angle_formatted = "42.0 deg"
    return _render(
        dataset=ds,
        measurement_tool=_measurement_tool(ds, [
            _Distance(_Pt(5, 5), _Pt(60, 40), "12.3 mm"),
            angle,
        ]),
    )


def _scenario_text_and_arrows() -> Image.Image:
    return _render(
        text_annotation_tool=_text_tool([
            _TextItem(20, 30, "lesion"),
            _TextItem(300, 300, "clamped"),
            _TextItem(50, 50, ""),
        ]),
        arrow_annotation_tool=_arrow_tool([
            _ArrowItem(10, 10, _Pt(0, 0), _Pt(40, 30)),
            _ArrowItem(60, 60, _Pt(0, 0), _Pt(-200, 200)),
        ]),
    )


def _scenario_overlay_corners() -> Image.Image:
    return _render(overlay_manager=_Overlay())


def _scenario_projection_overlay() -> Image.Image:
    ds = _dataset()
    return _render(
        dataset=ds,
        overlay_manager=_Overlay(),
        projection_enabled=True,
        projection_type="mip",
        projection_slice_count=3,
        studies={STUDY: {SERIES: [ds, _dataset(), _dataset(), _dataset()]}},
    )


def _scenario_everything() -> Image.Image:
    ds = _dataset()
    return _render(
        dataset=ds,
        overlay_manager=_Overlay(),
        roi_manager=_roi_manager([
            _ROI("rectangle", _Rect(10, 10, 60, 50), {"mean": 12.5}, ["mean"]),
        ]),
        measurement_tool=_measurement_tool(ds, [
            _Distance(_Pt(5, 5), _Pt(60, 40), "12.3 mm"),
        ]),
        text_annotation_tool=_text_tool([_TextItem(20, 30, "lesion")]),
        arrow_annotation_tool=_arrow_tool([_ArrowItem(10, 10, _Pt(0, 0), _Pt(40, 30))]),
        export_scale=2.0,
        scale_annotations_with_image=True,
    )


SCENARIOS = {
    "rois": _scenario_rois,
    "measurements": _scenario_measurements,
    "text_and_arrows": _scenario_text_and_arrows,
    "overlay_corners": _scenario_overlay_corners,
    "projection_overlay": _scenario_projection_overlay,
    "everything": _scenario_everything,
}


@pytest.mark.parametrize("name", sorted(SCENARIOS))
def test_golden_pixels(name):
    image = SCENARIOS[name]()
    expected = GOLDENS.get(name)
    assert expected is not None, (
        f"no golden recorded for {name!r}; got {_digest(image)}"
    )
    assert _digest(image) == expected, (
        f"pixel output changed for scenario {name!r}"
    )
