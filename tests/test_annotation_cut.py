"""Tests for annotation cut (copy-then-delete) via ``AnnotationPasteHandler``."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from PySide6.QtCore import QRectF
from PySide6.QtWidgets import QGraphicsScene

from gui.annotation_paste_handler import AnnotationPasteHandler
from tools.roi_manager import ROIGraphicsRectItem, ROIItem
from utils.annotation_clipboard import AnnotationClipboard


def _make_handler_with_roi(
    *,
    selected: bool = True,
) -> tuple[AnnotationPasteHandler, ROIItem, MagicMock, MagicMock]:
    """Build handler, one rectangle ROI on a scene, and spy coordinators."""
    rect = QRectF(0.0, 0.0, 20.0, 20.0)
    item = ROIGraphicsRectItem(rect)
    roi = ROIItem("rectangle", item, pen_width=1, pen_color=(255, 255, 255))
    if selected:
        item.setSelected(True)

    scene = QGraphicsScene()
    scene.addItem(item)

    study_uid = "study-1"
    series_uid = "series-1"
    instance_id = 0
    key = (study_uid, series_uid, instance_id)

    roi_manager = SimpleNamespace(
        current_study_uid=study_uid,
        current_series_uid=series_uid,
        current_instance_identifier=instance_id,
        rois={key: [roi]},
    )

    roi_coordinator = MagicMock()
    measurement_coordinator = MagicMock()
    crosshair_coordinator = MagicMock()
    text_coordinator = MagicMock()
    arrow_coordinator = MagicMock()

    managers = {
        "roi_manager": roi_manager,
        "roi_coordinator": roi_coordinator,
        "measurement_coordinator": measurement_coordinator,
        "crosshair_coordinator": crosshair_coordinator,
        "text_annotation_coordinator": text_coordinator,
        "arrow_annotation_coordinator": arrow_coordinator,
    }

    image_viewer = SimpleNamespace(scene=scene)
    subwindow = SimpleNamespace(image_viewer=image_viewer)

    status_messages: list[str] = []
    main_window = SimpleNamespace(update_status=status_messages.append)

    multi_window_layout = SimpleNamespace(get_all_subwindows=lambda: [subwindow])

    app = SimpleNamespace(
        _get_focused_subwindow=lambda: subwindow,
        multi_window_layout=multi_window_layout,
        subwindow_managers={0: managers},
        annotation_clipboard=AnnotationClipboard(),
        main_window=main_window,
    )

    handler = AnnotationPasteHandler(app)
    return handler, roi, roi_coordinator, status_messages


@pytest.mark.qt
def test_cut_no_selection_shows_status(qapp) -> None:
    handler, _roi, roi_coordinator, status_messages = _make_handler_with_roi(selected=False)

    handler.cut_annotations()

    assert not handler._app.annotation_clipboard.has_data()
    roi_coordinator.handle_roi_delete_requested.assert_not_called()
    assert status_messages[-1] == "No annotations selected"


@pytest.mark.qt
def test_cut_selected_roi_copies_and_deletes(qapp) -> None:
    handler, roi, roi_coordinator, status_messages = _make_handler_with_roi(selected=True)
    roi_manager = handler._app.subwindow_managers[0]["roi_manager"]
    key = (
        roi_manager.current_study_uid,
        roi_manager.current_series_uid,
        roi_manager.current_instance_identifier,
    )

    handler.cut_annotations()

    assert handler._app.annotation_clipboard.has_data()
    data = handler._app.annotation_clipboard.paste_annotations()
    assert data is not None
    assert data.get("type") == "dicom_viewer_annotations"
    assert len(data.get("rois", [])) == 1
    assert data["rois"][0]["shape_type"] == "rectangle"

    roi_coordinator.handle_roi_delete_requested.assert_called_once_with(roi.item)
    assert status_messages[-1] == "Cut 1 annotation(s)"

    # Coordinator mock does not mutate manager; real app delete removes ROI from dict.
    assert roi in roi_manager.rois[key]
