"""Focused tests for AnnotationPasteHandler selection helpers with fakes."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

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
