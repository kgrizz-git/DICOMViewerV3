"""Tests for AnnotationClipboard: serialization, offsets, and copy/paste states."""

from __future__ import annotations

from utils.annotation_clipboard import AnnotationClipboard


# Mock classes to duck-type PySide objects/items as expected by the serializer
class MockPoint:
    def __init__(self, x: float, y: float):
        self._x = x
        self._y = y

    def x(self) -> float:
        return self._x

    def y(self) -> float:
        return self._y


class MockColor:
    def __init__(self, r: int, g: int, b: int):
        self._r = r
        self._g = g
        self._b = b

    def red(self) -> int:
        return self._r

    def green(self) -> int:
        return self._g

    def blue(self) -> int:
        return self._b


class MockFont:
    def __init__(self, pt_size: int, pixel_size: int = -1):
        self._pt_size = pt_size
        self._pixel_size = pixel_size

    def pointSize(self) -> int:
        return self._pt_size

    def pixelSize(self) -> int:
        return self._pixel_size


class MockDistanceMeasurement:
    def __init__(self, start: MockPoint, end: MockPoint, spacing: tuple[float, float]):
        self.start_point = start
        self.end_point = end
        self.pixel_spacing = spacing


class MockAngleMeasurement:
    def __init__(
        self, p1: MockPoint, p2: MockPoint, p3: MockPoint, text_offset: MockPoint
    ):
        self.p1 = p1
        self.p2 = p2
        self.p3 = p3
        self.text_offset_viewport = text_offset


class MockCrosshair:
    def __init__(
        self,
        pos: MockPoint,
        val: str,
        x: float,
        y: float,
        z: float,
        text_offset: tuple[float, float],
    ):
        self.position = pos
        self.pixel_value_str = val
        self.x_coord = x
        self.y_coord = y
        self.z_coord = z
        self.text_offset_viewport = text_offset


class MockTextAnnotation:
    def __init__(self, text: str, pos: MockPoint, color: MockColor, font: MockFont):
        self._text = text
        self._pos = pos
        self._color = color
        self._font = font

    def toPlainText(self) -> str:
        return self._text

    def pos(self) -> MockPoint:
        return self._pos

    def defaultTextColor(self) -> MockColor:
        return self._color

    def font(self) -> MockFont:
        return self._font


class MockArrowAnnotation:
    def __init__(self, start: MockPoint, end: MockPoint, color: MockColor):
        self.start_point = start
        self.end_point = end
        self.color = color


def test_clipboard_initial_state() -> None:
    clip = AnnotationClipboard()
    assert clip.clipboard_data is None
    assert clip.source_slice_key is None
    assert clip.has_data() is False


def test_clipboard_clear() -> None:
    clip = AnnotationClipboard()
    clip.copy_annotations([], [], [], "study", "series", 1)
    assert clip.has_data() is True
    clip.clear()
    assert clip.clipboard_data is None
    assert clip.source_slice_key is None
    assert clip.has_data() is False


def test_clipboard_copy_empty() -> None:
    clip = AnnotationClipboard()
    res = clip.copy_annotations([], [], [], "study_uid", "series_uid", 5)
    assert res["type"] == "dicom_viewer_annotations"
    assert res["version"] == "1.0"
    assert res["rois"] == []
    assert res["measurements"] == []
    assert res["crosshairs"] == []
    assert res["text_annotations"] == []
    assert res["arrow_annotations"] == []
    assert clip.source_slice_key == ("study_uid", "series_uid", 5)


def test_paste_annotations() -> None:
    clip = AnnotationClipboard()
    assert clip.paste_annotations() is None
    res = clip.copy_annotations([], [], [], "study", "series", 1)
    assert clip.paste_annotations() == res


def test_get_source_slice_key() -> None:
    clip = AnnotationClipboard()
    assert clip.get_source_slice_key() is None
    clip.copy_annotations([], [], [], "study_abc", "series_xyz", 99)
    assert clip.get_source_slice_key() == ("study_abc", "series_xyz", 99)


def test_serialize_distance_measurement() -> None:
    clip = AnnotationClipboard()
    start = MockPoint(1.0, 2.0)
    end = MockPoint(3.0, 4.0)
    m = MockDistanceMeasurement(start, end, (0.5, 0.5))
    res = clip.copy_annotations([], [m], [], "study", "series", 1)

    measurements = res["measurements"]
    assert len(measurements) == 1
    assert measurements[0]["measurement_kind"] == "distance"
    assert measurements[0]["start_point"] == {"x": 1.0, "y": 2.0}
    assert measurements[0]["end_point"] == {"x": 3.0, "y": 4.0}
    assert measurements[0]["pixel_spacing"] == (0.5, 0.5)


def test_serialize_angle_measurement() -> None:
    clip = AnnotationClipboard()
    p1 = MockPoint(10.0, 10.0)
    p2 = MockPoint(20.0, 20.0)
    p3 = MockPoint(30.0, 10.0)
    text_offset = MockPoint(5.0, 5.0)
    m = MockAngleMeasurement(p1, p2, p3, text_offset)
    res = clip.copy_annotations([], [m], [], "study", "series", 1)

    measurements = res["measurements"]
    assert len(measurements) == 1
    assert measurements[0]["measurement_kind"] == "angle"
    assert measurements[0]["p1"] == {"x": 10.0, "y": 10.0}
    assert measurements[0]["p2"] == {"x": 20.0, "y": 20.0}
    assert measurements[0]["p3"] == {"x": 30.0, "y": 10.0}
    assert measurements[0]["text_offset_viewport"] == {"x": 5.0, "y": 5.0}


def test_serialize_crosshairs() -> None:
    clip = AnnotationClipboard()
    pos = MockPoint(15.0, 25.0)
    text_offset = (2.0, 2.0)
    c = MockCrosshair(pos, "120 HU", 10, 20, 30, text_offset)
    res = clip.copy_annotations([], [], [c], "study", "series", 1)

    crosshairs = res["crosshairs"]
    assert len(crosshairs) == 1
    assert crosshairs[0]["position"] == {"x": 15.0, "y": 25.0}
    assert crosshairs[0]["pixel_value_str"] == "120 HU"
    assert crosshairs[0]["x_coord"] == 10
    assert crosshairs[0]["y_coord"] == 20
    assert crosshairs[0]["z_coord"] == 30
    assert crosshairs[0]["text_offset_viewport"] == (2.0, 2.0)


def test_serialize_text_annotations() -> None:
    clip = AnnotationClipboard()
    pos = MockPoint(100.0, 200.0)
    color = MockColor(255, 0, 0)
    font = MockFont(12)
    t = MockTextAnnotation("Hello DICOM", pos, color, font)
    res = clip.copy_annotations([], [], [], "study", "series", 1, text_annotations=[t])

    texts = res["text_annotations"]
    assert len(texts) == 1
    assert texts[0]["text"] == "Hello DICOM"
    assert texts[0]["position"] == {"x": 100.0, "y": 200.0}
    assert texts[0]["font_size"] == 12
    assert texts[0]["color"] == {"r": 255, "g": 0, "b": 0}


def test_serialize_arrow_annotations() -> None:
    clip = AnnotationClipboard()
    start = MockPoint(5.0, 5.0)
    end = MockPoint(50.0, 50.0)
    color = MockColor(0, 255, 0)
    a = MockArrowAnnotation(start, end, color)
    res = clip.copy_annotations([], [], [], "study", "series", 1, arrow_annotations=[a])

    arrows = res["arrow_annotations"]
    assert len(arrows) == 1
    assert arrows[0]["start_point"] == {"x": 5.0, "y": 5.0}
    assert arrows[0]["end_point"] == {"x": 50.0, "y": 50.0}
    assert arrows[0]["color"] == {"r": 0, "g": 255, "b": 0}


def test_serialize_rois_delegation(monkeypatch) -> None:
    clip = AnnotationClipboard()
    captured_rois = []

    def serialize_rois(rois):
        captured_rois.extend(rois)
        return [{"roi_id": 999}]

    monkeypatch.setattr(
        "utils.annotation_clipboard.serialize_rois_for_clipboard",
        serialize_rois,
    )
    res = clip.copy_annotations(["dummy_roi"], [], [], "study", "series", 1)
    assert captured_rois == ["dummy_roi"]
    assert res["rois"] == [{"roi_id": 999}]


def test_serialize_text_annotation_uses_pixel_size_when_point_size_is_unset() -> None:
    clip = AnnotationClipboard()
    text = MockTextAnnotation(
        "Pixel-sized text",
        MockPoint(0.0, 0.0),
        MockColor(0, 0, 0),
        MockFont(0, pixel_size=18),
    )

    result = clip.copy_annotations(
        [], [], [], "study", "series", 1, text_annotations=[text]
    )

    assert result["text_annotations"][0]["font_size"] == 18


def test_has_data_state_transitions() -> None:
    clip = AnnotationClipboard()
    assert clip.has_data() is False
    clip.copy_annotations([], [], [], "study", "series", 1)
    assert clip.has_data() is True
    clip.clear()
    assert clip.has_data() is False
