"""Unit tests for tools.annotation_manager.AnnotationManager."""

from __future__ import annotations

from types import SimpleNamespace

import numpy as np
from pydicom.dataelem import DataElement
from pydicom.dataset import Dataset
from pydicom.tag import Tag
from PySide6.QtGui import QColor
from PySide6.QtWidgets import QGraphicsScene, QGraphicsTextItem

from tools.annotation_manager import AnnotationManager


def _item(**kwargs):
    return SimpleNamespace(**kwargs)


class _OverlayDataset(dict):
    def get(self, key, default=None):
        return super().get(key, default)


def test_load_rt_struct_get_contours_and_create_overlay_items(qapp):
    manager = AnnotationManager()
    dataset = _item(
        SOPClassUID="1.2.840.10008.5.1.4.1.1.481.3",
        StructureSetROISequence=[
        _item(ROIName="Tumor", ROINumber=1),
        _item(ROIName="Skip", ROINumber=2),
        ],
        ROIContourSequence=[
        _item(
            ContourSequence=[
                _item(ContourData=[1.0, 2.0, 0.0, 3.0, 4.0, 0.0, 5.0, 6.0, 0.0]),
            ]
        ),
        _item(ContourSequence=[_item(ContourData=[0.0, 0.0, 0.0, 1.0, 1.0, 0.0])]),
        ],
    )

    assert manager.load_rt_struct(dataset) is True

    contours = manager.get_contours()
    assert len(contours) == 2
    assert contours[0]["roi_name"] == "Tumor"
    assert contours[0]["points"] == [(1.0, 2.0, 0.0), (3.0, 4.0, 0.0), (5.0, 6.0, 0.0)]

    scene = QGraphicsScene()
    first_items = manager.create_overlay_items(scene, contours)
    second_items = manager.create_overlay_items(scene, contours)

    assert len(first_items) == 1
    assert len(second_items) == 1
    assert len(scene.items()) == 1
    assert len(manager.annotations[scene]) == 1


def test_non_rt_struct_and_no_contours_return_empty():
    manager = AnnotationManager()
    dataset = Dataset()
    dataset.SOPClassUID = "1.2.3"

    assert manager.load_rt_struct(dataset) is False
    assert manager.get_contours() == []


def test_study_state_management_and_annotation_lookup_merges_sources(monkeypatch):
    manager = AnnotationManager()
    dataset = Dataset()
    dataset.SOPInstanceUID = "1.2.3.4.1"
    dataset.SeriesInstanceUID = "1.2.3.5.1"

    monkeypatch.setattr(
        manager,
        "_get_embedded_annotations",
        lambda ds: [{"type": "POINT", "coordinates": [(9, 9)], "source": "embedded"}],
    )
    monkeypatch.setattr(
        manager.presentation_state_handler,
        "parse_presentation_state",
        lambda ds: {
            "annotations": [{"type": "POLYLINE", "coordinates": [(1, 1), (2, 2)]}],
            "referenced_images": {"image_uids": [], "series_uids": ["1.2.3.5.1"]},
        },
    )
    monkeypatch.setattr(
        manager.key_object_handler,
        "parse_key_object",
        lambda ds: {
            "annotations": [{"text": "Marked", "type": "Bookmark", "value": 5.0, "units": "mm"}],
            "referenced_images": ["1.2.3.4.1"],
        },
    )

    manager.load_presentation_states({"study-1": [object()]})
    manager.load_key_objects({"study-1": [object()]})
    annotations = manager.get_annotations_for_image(dataset, "study-1")

    assert len(annotations) == 3
    assert annotations[0]["source"] == "embedded"
    assert annotations[1]["source"] == "presentation_state"
    assert annotations[2] == {
        "type": "TEXT",
        "text": "Marked",
        "coordinates": [(0, 0)],
        "color": (255, 255, 0),
        "layer": "Bookmark",
        "source": "key_object",
        "value": 5.0,
        "units": "mm",
    }

    manager.remove_study_annotations("study-1")
    assert manager.presentation_states == {}
    assert manager.key_objects == {}

    manager.load_presentation_states({"study-2": [object()]})
    manager.load_key_objects({"study-2": [object()]})
    manager.clear_all_ps_ko()
    assert manager.presentation_states == {}
    assert manager.key_objects == {}


def test_get_annotations_for_image_without_uid_or_when_parser_raises(monkeypatch):
    manager = AnnotationManager()

    assert manager.get_annotations_for_image(Dataset(), "study") == []

    dataset = Dataset()
    dataset.SOPInstanceUID = "1.2.3.4.2"
    dataset.SeriesInstanceUID = "1.2.3.5.2"
    manager.load_presentation_states({"study": [object()]})
    monkeypatch.setattr(manager, "_get_embedded_annotations", lambda ds: [])

    def _boom(_dataset):
        raise RuntimeError("parse failed")

    monkeypatch.setattr(manager.presentation_state_handler, "parse_presentation_state", _boom)
    assert manager.get_annotations_for_image(dataset, "study") == []


def test_transform_coordinates_covers_units_and_error_handling():
    manager = AnnotationManager()

    assert manager._transform_coordinates([(0.5, 0.25)], "NORMALIZED", 200, 100) == [(100.0, 25.0)]
    assert manager._transform_coordinates([(10, 20)], "PIXEL", 1, 1) == [(10.0, 20.0)]
    assert manager._transform_coordinates([(30, 40)], "DISPLAY", 1, 1) == [(30.0, 40.0)]
    assert manager._transform_coordinates([(50, 60)], "UNKNOWN", 1, 1) == [(50.0, 60.0)]
    assert manager._transform_coordinates([], "PIXEL", 1, 1) == []
    assert manager._transform_coordinates([("bad", 1)], "PIXEL", 1, 1) == []


def test_get_embedded_annotations_combines_graphic_and_overlay_sources(monkeypatch):
    manager = AnnotationManager()
    dataset = _item(GraphicAnnotationSequence=["graphic-seq"])

    monkeypatch.setattr(
        manager.presentation_state_handler,
        "parse_graphic_annotations",
        lambda seq: [{"type": "TEXT", "text": "embedded"}],
    )
    monkeypatch.setattr(
        manager,
        "_parse_overlay_data",
        lambda ds: [{"type": "OVERLAY", "source": "embedded_overlay"}],
    )

    annotations = manager._get_embedded_annotations(dataset)

    assert annotations == [
        {"type": "TEXT", "text": "embedded", "source": "embedded_graphics"},
        {"type": "OVERLAY", "source": "embedded_overlay"},
    ]


def test_parse_overlay_data_extracts_origin_and_converted_graphics(monkeypatch):
    manager = AnnotationManager()
    dataset = _OverlayDataset(
        {
            (0x6000, 0x3000): DataElement(Tag(0x6000, 0x3000), "OW", bytes([0b00001111])),
            (0x6000, 0x0010): _item(value=2),
            (0x6000, 0x0011): _item(value=2),
            (0x6000, 0x0050): _item(value=[3, 4]),
            (0x6000, 0x0040): _item(value="R"),
        }
    )

    monkeypatch.setattr(
        manager,
        "_convert_overlay_bitmap_to_graphics",
        lambda data, cols, rows, origin_x, origin_y: {
            "coordinates": [(origin_x, origin_y)],
            "paths": [[(origin_x, origin_y), (origin_x + 2, origin_y + 2)]],
        },
    )

    overlays = manager._parse_overlay_data(dataset)

    assert len(overlays) == 1
    overlay = overlays[0]
    assert overlay["overlay_cols"] == 2
    assert overlay["overlay_rows"] == 2
    assert overlay["overlay_origin_x"] == 3.0
    assert overlay["overlay_origin_y"] == 2.0
    assert overlay["coordinates"] == [(3.0, 2.0)]
    assert overlay["paths"] == [[(3.0, 2.0), (5.0, 4.0)]]
    assert overlay["overlay_data"] == bytes([0b00001111])


def test_convert_overlay_bitmap_to_graphics_uses_scipy_fallback(monkeypatch):
    manager = AnnotationManager()

    labeled = np.array([[1, 1], [0, 1]], dtype=np.int32)

    class _FakeNdimage:
        @staticmethod
        def label(bitmap):
            assert bitmap.shape == (2, 2)
            return labeled, 1

    def _fake_import_module(name):
        if name == "cv2":
            raise ImportError
        if name == "scipy.ndimage":
            return _FakeNdimage()
        raise ImportError(name)

    monkeypatch.setattr("tools.annotation_manager.importlib.import_module", _fake_import_module)

    result = manager._convert_overlay_bitmap_to_graphics(bytes([0b00001011]), 2, 2, 10.0, 20.0)

    assert sorted(result["coordinates"]) == [(10.0, 20.0), (11.0, 20.0), (11.0, 21.0)]
    assert result["paths"] == [[(10.0, 20.0), (11.0, 20.0), (11.0, 21.0)]]


def test_convert_overlay_bitmap_to_graphics_invalid_input_returns_empty():
    manager = AnnotationManager()
    result = manager._convert_overlay_bitmap_to_graphics(object(), 2, 2, 0.0, 0.0)
    assert result == {"coordinates": [], "paths": []}


def test_create_presentation_state_items_covers_shapes_and_overlay_fallback(qapp, monkeypatch):
    manager = AnnotationManager()
    scene = QGraphicsScene()
    monkeypatch.setattr(manager, "_create_overlay_bitmap_item", lambda *args, **kwargs: None)

    annotations = [
        {"type": "TEXT", "text": "note", "coordinates": [(5, 6)], "color": (1, 2, 3), "units": "PIXEL"},
        {"type": "TEXT", "text": "skip", "coordinates": [(500, 600)], "units": "PIXEL"},
        {"type": "POLYLINE", "coordinates": [(0, 0), (4, 4)], "units": "PIXEL"},
        {"type": "CIRCLE", "coordinates": [(10, 10), (13, 10)], "units": "PIXEL"},
        {"type": "ELLIPSE", "coordinates": [(20, 20), (24, 22), (21, 26)], "units": "PIXEL"},
        {"type": "POINT", "coordinates": [(30, 30)], "units": "PIXEL"},
        {
            "type": "OVERLAY",
            "coordinates": [(40, 40), (41, 41)],
            "paths": [[(40, 40), (44, 40), (44, 44), (40, 40)]],
            "overlay_rows": 2,
            "overlay_cols": 2,
            "overlay_origin_x": 40,
            "overlay_origin_y": 40,
            "overlay_data": b"",
            "units": "PIXEL",
        },
    ]

    items = manager.create_presentation_state_items(scene, annotations, 100, 100)

    assert len(items) == 6
    assert len(scene.items()) == 6
    assert len(manager.annotations[scene]) == 6


def test_create_presentation_state_items_uses_bitmap_item_when_available(qapp, monkeypatch):
    manager = AnnotationManager()
    scene = QGraphicsScene()
    bitmap_item = QGraphicsTextItem("bitmap")
    monkeypatch.setattr(manager, "_create_overlay_bitmap_item", lambda *args, **kwargs: bitmap_item)

    items = manager.create_presentation_state_items(
        scene,
        [
            {
                "type": "OVERLAY",
                "coordinates": [(0, 0)],
                "paths": [],
                "overlay_rows": 2,
                "overlay_cols": 2,
                "overlay_origin_x": 0,
                "overlay_origin_y": 0,
                "overlay_data": bytes([0b00000001]),
            }
        ],
        100,
        100,
    )

    assert items == [bitmap_item]
    assert scene.items()
    assert manager.annotations[scene] == [bitmap_item]


def test_create_overlay_bitmap_item_and_clear_annotations(qapp):
    manager = AnnotationManager()
    bitmap_item = manager._create_overlay_bitmap_item(
        bytes([0b00001111]),
        cols=2,
        rows=2,
        origin_x=7.0,
        origin_y=8.0,
        color=QColor(255, 0, 0),
    )

    assert bitmap_item is not None
    assert bitmap_item.pos().x() == 7.0
    assert bitmap_item.pos().y() == 8.0

    scene = QGraphicsScene()
    text_item = QGraphicsTextItem("tracked")
    scene.addItem(text_item)
    manager._add_annotation_to_scene(scene, text_item)
    scene.removeItem(text_item)
    manager.clear_annotations(scene)
    manager.clear_annotations(scene)

    assert manager.annotations[scene] == []
