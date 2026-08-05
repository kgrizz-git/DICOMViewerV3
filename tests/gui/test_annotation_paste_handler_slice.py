"""Focused tests for AnnotationPasteHandler selection helpers with fakes."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from PySide6.QtCore import QPointF
from PySide6.QtGui import QTransform
from PySide6.QtWidgets import QGraphicsScene

from gui.annotation_paste_handler import AnnotationPasteHandler


@pytest.mark.qt
def test_get_selected_rois_empty_without_scene(qapp) -> None:
    app = SimpleNamespace(
        multi_window_layout=MagicMock(),
        subwindow_managers={},
    )
    app.multi_window_layout.get_all_subwindows.return_value = []
    handler = AnnotationPasteHandler(app)
    sub = MagicMock()
    sub.image_viewer = None
    assert handler.get_selected_rois(sub) == []


@pytest.mark.qt
def test_get_selected_rois_matches_scene_item(qapp) -> None:
    roi_item_graphics = MagicMock()
    roi = MagicMock()
    roi.item = roi_item_graphics

    roi_manager = MagicMock()
    roi_manager.current_study_uid = "st"
    roi_manager.current_series_uid = "se"
    roi_manager.current_instance_identifier = 0
    roi_manager.rois = {("st", "se", 0): [roi]}

    scene = MagicMock()
    scene.selectedItems.return_value = [roi_item_graphics]
    viewer = MagicMock()
    viewer.scene = scene
    sub = MagicMock()
    sub.image_viewer = viewer

    layout = MagicMock()
    layout.get_all_subwindows.return_value = [sub]
    app = SimpleNamespace(
        multi_window_layout=layout,
        subwindow_managers={0: {"roi_manager": roi_manager}},
    )
    handler = AnnotationPasteHandler(app)
    assert handler.get_selected_rois(sub) == [roi]


def _make_paste_context(*, real_scene: bool = False):
    """Build a focused subwindow and its per-window annotation managers."""
    scene = QGraphicsScene() if real_scene else MagicMock()
    viewer = SimpleNamespace(
        scene=scene,
        transform=lambda: QTransform(),
        viewportTransform=lambda: QTransform(),
    )
    subwindow = SimpleNamespace(
        image_viewer=viewer,
        update_roi_list=MagicMock(),
    )
    key = ("study", "series", 3)
    roi_manager = SimpleNamespace(
        current_study_uid=key[0],
        current_series_uid=key[1],
        current_instance_identifier=key[2],
        rois={},
    )
    measurement_tool = SimpleNamespace(
        current_study_uid=key[0],
        current_series_uid=key[1],
        current_instance_identifier=key[2],
        measurements={},
    )
    crosshair_manager = SimpleNamespace(
        current_study_uid=key[0],
        current_series_uid=key[1],
        current_instance_identifier=key[2],
        crosshairs={},
        privacy_mode=False,
    )
    text_annotation_tool = SimpleNamespace(
        current_study_uid=key[0],
        current_series_uid=key[1],
        current_instance_identifier=key[2],
        annotations={},
    )
    arrow_annotation_tool = SimpleNamespace(
        current_study_uid=key[0],
        current_series_uid=key[1],
        current_instance_identifier=key[2],
        arrows={},
    )
    managers = {
        "roi_manager": roi_manager,
        "roi_coordinator": MagicMock(),
        "measurement_tool": measurement_tool,
        "measurement_coordinator": MagicMock(),
        "crosshair_manager": crosshair_manager,
        "crosshair_coordinator": MagicMock(),
        "text_annotation_tool": text_annotation_tool,
        "text_annotation_coordinator": MagicMock(),
        "arrow_annotation_tool": arrow_annotation_tool,
        "arrow_annotation_coordinator": MagicMock(),
    }
    clipboard = MagicMock()
    app = SimpleNamespace(
        _get_focused_subwindow=lambda: subwindow,
        multi_window_layout=SimpleNamespace(get_all_subwindows=lambda: [subwindow]),
        subwindow_managers={0: managers},
        annotation_clipboard=clipboard,
        main_window=SimpleNamespace(update_status=MagicMock()),
        undo_redo_manager=SimpleNamespace(execute_command=MagicMock()),
        config_manager=None,
    )
    return AnnotationPasteHandler(app), subwindow, managers, key, clipboard


@pytest.mark.qt
def test_copy_annotations_copies_all_selection_kinds(qapp) -> None:
    handler, _subwindow, managers, key, clipboard = _make_paste_context()
    roi = SimpleNamespace(item=MagicMock())
    measurement = MagicMock()
    crosshair = MagicMock()
    text_annotation = MagicMock()
    arrow_annotation = MagicMock()
    handler.get_selected_rois = MagicMock(return_value=[roi])
    handler.get_selected_measurements = MagicMock(return_value=[measurement])
    handler.get_selected_crosshairs = MagicMock(return_value=[crosshair])
    handler.get_selected_text_annotations = MagicMock(return_value=[text_annotation])
    handler.get_selected_arrow_annotations = MagicMock(return_value=[arrow_annotation])

    handler.copy_annotations()

    clipboard.copy_annotations.assert_called_once_with(
        [roi],
        [measurement],
        [crosshair],
        *key,
        text_annotations=[text_annotation],
        arrow_annotations=[arrow_annotation],
        operation="copy",
    )
    handler._app.main_window.update_status.assert_called_once_with(
        "Copied 5 annotation(s)"
    )
    assert managers["roi_manager"].rois == {}


@pytest.mark.qt
def test_delete_selected_annotations_delegates_to_each_available_coordinator(qapp) -> None:
    handler, _subwindow, managers, _key, _clipboard = _make_paste_context()
    roi_item = MagicMock()
    roi = SimpleNamespace(item=roi_item)
    measurement = MagicMock()
    crosshair = MagicMock()
    text_annotation = MagicMock()
    arrow_annotation = MagicMock()

    handler._delete_selected_annotations(
        managers,
        [roi],
        [measurement],
        [crosshair],
        [text_annotation],
        [arrow_annotation],
    )

    managers["roi_coordinator"].handle_roi_delete_requested.assert_called_once_with(
        roi_item
    )
    managers[
        "measurement_coordinator"
    ].handle_measurement_delete_requested.assert_called_once_with(measurement)
    managers["crosshair_coordinator"].handle_crosshair_delete_requested.assert_called_once_with(
        crosshair
    )
    managers[
        "text_annotation_coordinator"
    ].handle_text_annotation_delete_requested.assert_called_once_with(text_annotation)
    managers[
        "arrow_annotation_coordinator"
    ].handle_arrow_annotation_delete_requested.assert_called_once_with(arrow_annotation)


@pytest.mark.qt
def test_paste_annotations_dispatches_every_kind_and_selects_created_items(qapp) -> None:
    handler, subwindow, _managers, key, clipboard = _make_paste_context()
    clipboard.has_data.return_value = True
    clipboard.get_paste_offset.return_value = QPointF(10, 10)
    clipboard.paste_annotations.return_value = {
        "type": "dicom_viewer_annotations",
        "rois": [{"id": "roi"}],
        "measurements": [{"id": "measurement"}],
        "crosshairs": [{"id": "crosshair"}],
        "text_annotations": [{"id": "text"}],
        "arrow_annotations": [{"id": "arrow"}],
    }
    roi_graphics_item = MagicMock()
    measurement_item = MagicMock()
    crosshair_item = MagicMock()
    text_item = MagicMock()
    arrow_item = MagicMock()
    handler.paste_roi = MagicMock(return_value=SimpleNamespace(item=roi_graphics_item))
    handler.paste_measurement = MagicMock(return_value=measurement_item)
    handler.paste_crosshair = MagicMock(return_value=crosshair_item)
    handler.paste_text_annotation = MagicMock(return_value=text_item)
    handler.paste_arrow_annotation = MagicMock(return_value=arrow_item)

    handler.paste_annotations()

    clipboard.get_paste_offset.assert_called_once_with(key)
    handler.paste_roi.assert_called_once()
    handler.paste_measurement.assert_called_once()
    handler.paste_crosshair.assert_called_once()
    handler.paste_text_annotation.assert_called_once()
    handler.paste_arrow_annotation.assert_called_once()
    for item in (
        roi_graphics_item,
        measurement_item,
        crosshair_item,
        text_item,
        arrow_item,
    ):
        item.setSelected.assert_called_once_with(True)
    subwindow.image_viewer.scene.clearSelection.assert_called_once_with()
    subwindow.image_viewer.scene.update.assert_called_once_with()
    subwindow.update_roi_list.assert_called_once_with()
    handler._app.main_window.update_status.assert_called_once_with(
        "Pasted 5 annotation(s)"
    )


@pytest.mark.qt
def test_paste_annotations_returns_before_mutating_for_empty_or_invalid_clipboard(qapp) -> None:
    handler, subwindow, _managers, _key, clipboard = _make_paste_context()
    clipboard.has_data.return_value = False

    handler.paste_annotations()

    clipboard.paste_annotations.assert_not_called()
    subwindow.image_viewer.scene.clearSelection.assert_not_called()

    clipboard.has_data.return_value = True
    clipboard.paste_annotations.return_value = {"type": "other"}
    handler.paste_annotations()

    subwindow.image_viewer.scene.clearSelection.assert_not_called()
    handler._app.main_window.update_status.assert_not_called()


@pytest.mark.qt
def test_paste_roi_recreates_graphics_and_records_undo(qapp) -> None:
    handler, subwindow, managers, key, _clipboard = _make_paste_context(real_scene=True)

    roi = handler.paste_roi(
        subwindow,
        managers,
        {
            "shape_type": "ellipse",
            "rect": {"x": 2, "y": 3, "width": 20, "height": 10},
            "position": {"x": 4, "y": 5},
            "pen_width": 3,
            "pen_color": (1, 2, 3),
            "visible_statistics": ["mean"],
        },
        QPointF(10, 20),
    )

    assert roi is not None
    assert roi.shape_type == "ellipse"
    assert roi.item.pos() == QPointF(14, 25)
    assert managers["roi_manager"].rois[key] == [roi]
    handler._app.undo_redo_manager.execute_command.assert_called_once()
    managers["roi_coordinator"].update_roi_statistics_overlays.assert_called_once_with()


@pytest.mark.qt
def test_paste_distance_measurement_uses_offset_and_records_undo(qapp) -> None:
    handler, subwindow, managers, key, _clipboard = _make_paste_context(real_scene=True)

    measurement = handler.paste_measurement(
        subwindow,
        managers,
        {
            "start_point": {"x": 2, "y": 3},
            "end_point": {"x": 20, "y": 30},
            "pixel_spacing": (0.5, 0.5),
        },
        QPointF(10, 20),
    )

    assert measurement is not None
    assert measurement.start_point == QPointF(12, 23)
    assert measurement.end_point == QPointF(30, 50)
    assert managers["measurement_tool"].measurements[key] == [measurement]
    handler._app.undo_redo_manager.execute_command.assert_called_once()


@pytest.mark.qt
def test_paste_crosshair_text_and_arrow_recreate_and_record_each_undo(qapp) -> None:
    handler, subwindow, managers, key, _clipboard = _make_paste_context(real_scene=True)

    crosshair = handler.paste_crosshair(
        subwindow,
        managers,
        {
            "position": {"x": 2, "y": 3},
            "pixel_value_str": "42",
            "x_coord": 2,
            "y_coord": 3,
            "z_coord": 4,
        },
        QPointF(10, 20),
    )
    text = handler.paste_text_annotation(
        subwindow,
        managers,
        {
            "text": "note",
            "position": {"x": 2, "y": 3},
            "font_size": 15,
            "color": {"r": 2, "g": 3, "b": 4},
        },
        QPointF(10, 20),
    )
    arrow = handler.paste_arrow_annotation(
        subwindow,
        managers,
        {
            "start_point": {"x": 2, "y": 3},
            "end_point": {"x": 20, "y": 30},
            "color": {"r": 2, "g": 3, "b": 4},
        },
        QPointF(10, 20),
    )

    assert crosshair is not None
    assert crosshair.pos() == QPointF(12, 23)
    assert managers["crosshair_manager"].crosshairs[key] == [crosshair]
    assert text is not None
    assert text.pos() == QPointF(12, 23)
    assert managers["text_annotation_tool"].annotations[key] == [text]
    assert arrow is not None
    assert arrow.pos() == QPointF(12, 23)
    assert managers["arrow_annotation_tool"].arrows[key] == [arrow]
    assert handler._app.undo_redo_manager.execute_command.call_count == 3
