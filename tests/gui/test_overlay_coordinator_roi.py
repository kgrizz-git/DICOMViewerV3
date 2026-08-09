"""Tests for OverlayCoordinator ROI-related methods."""

from __future__ import annotations

from unittest.mock import MagicMock

from PySide6.QtWidgets import QGraphicsEllipseItem, QGraphicsRectItem

from gui.overlay_coordinator import OverlayCoordinator


class TestHideRoiLabels:
    def test_hide_roi_labels_is_noop(
        self, overlay_coordinator: OverlayCoordinator
    ):
        # This method is documented as a no-op for now
        overlay_coordinator.hide_roi_labels(True)
        overlay_coordinator.hide_roi_labels(False)

        # Should not raise or do anything
        assert True


class TestHideRoiGraphics:
    def test_delegates_to_callback_when_provided(
        self, overlay_manager, image_viewer
    ):
        hide_roi_graphics = MagicMock()

        coordinator = OverlayCoordinator(
            overlay_manager=overlay_manager,
            image_viewer=image_viewer,
            get_current_dataset=lambda: None,
            get_current_studies=lambda: {},
            get_current_study_uid=lambda: "study_1",
            get_current_series_uid=lambda: "series_1",
            get_current_slice_index=lambda: 0,
            hide_roi_graphics=hide_roi_graphics,
        )

        coordinator.hide_roi_graphics(True)

        hide_roi_graphics.assert_called_once_with(True)

    def test_returns_early_when_callback_provided(
        self, overlay_manager, image_viewer
    ):
        hide_roi_graphics = MagicMock()

        coordinator = OverlayCoordinator(
            overlay_manager=overlay_manager,
            image_viewer=image_viewer,
            get_current_dataset=lambda: None,
            get_current_studies=lambda: {},
            get_current_study_uid=lambda: "study_1",
            get_current_series_uid=lambda: "series_1",
            get_current_slice_index=lambda: 0,
            hide_roi_graphics=hide_roi_graphics,
        )

        coordinator.hide_roi_graphics(True)

        # Should not iterate scene items
        image_viewer.scene.items.assert_not_called()

    def test_returns_early_when_scene_is_none(
        self, overlay_coordinator: OverlayCoordinator
    ):
        overlay_coordinator.image_viewer.scene = None
        overlay_coordinator._hide_roi_graphics_callback = None

        overlay_coordinator.hide_roi_graphics(True)

        # Should not raise
        assert True

    def test_hides_rect_items_when_no_callback(
        self, overlay_coordinator: OverlayCoordinator
    ):
        rect_item = MagicMock(spec=QGraphicsRectItem)
        ellipse_item = MagicMock(spec=QGraphicsEllipseItem)
        overlay_coordinator.image_viewer.scene.items = MagicMock(
            return_value=[rect_item, ellipse_item]
        )
        overlay_coordinator.image_viewer.image_item = MagicMock()

        overlay_coordinator.hide_roi_graphics(True)

        rect_item.setVisible.assert_called_once_with(False)
        ellipse_item.setVisible.assert_called_once_with(False)

    def test_shows_rect_items_when_no_callback(
        self, overlay_coordinator: OverlayCoordinator
    ):
        rect_item = MagicMock(spec=QGraphicsRectItem)
        ellipse_item = MagicMock(spec=QGraphicsEllipseItem)
        overlay_coordinator.image_viewer.scene.items = MagicMock(
            return_value=[rect_item, ellipse_item]
        )
        overlay_coordinator.image_viewer.image_item = MagicMock()

        overlay_coordinator.hide_roi_graphics(False)

        rect_item.setVisible.assert_called_once_with(True)
        ellipse_item.setVisible.assert_called_once_with(True)

    def test_does_not_hide_image_item(
        self, overlay_coordinator: OverlayCoordinator
    ):
        rect_item = MagicMock(spec=QGraphicsRectItem)
        overlay_coordinator.image_viewer.scene.items = MagicMock(
            return_value=[rect_item]
        )
        overlay_coordinator.image_viewer.image_item = rect_item

        overlay_coordinator.hide_roi_graphics(True)

        rect_item.setVisible.assert_not_called()

    def test_filters_non_roi_items(
        self, overlay_coordinator: OverlayCoordinator
    ):
        rect_item = MagicMock(spec=QGraphicsRectItem)
        other_item = MagicMock()
        overlay_coordinator.image_viewer.scene.items = MagicMock(
            return_value=[rect_item, other_item]
        )
        overlay_coordinator.image_viewer.image_item = MagicMock()

        overlay_coordinator.hide_roi_graphics(True)

        rect_item.setVisible.assert_called_once_with(False)
        other_item.setVisible.assert_not_called()

    def test_handles_empty_scene(
        self, overlay_coordinator: OverlayCoordinator
    ):
        overlay_coordinator.image_viewer.scene.items = MagicMock(return_value=[])
        overlay_coordinator.image_viewer.image_item = MagicMock()

        overlay_coordinator.hide_roi_graphics(True)

        # Should not raise
        assert True

    def test_handles_mixed_scene_items(
        self, overlay_coordinator: OverlayCoordinator
    ):
        rect_item = MagicMock(spec=QGraphicsRectItem)
        ellipse_item = MagicMock(spec=QGraphicsEllipseItem)
        text_item = MagicMock()
        line_item = MagicMock()
        overlay_coordinator.image_viewer.scene.items = MagicMock(
            return_value=[rect_item, ellipse_item, text_item, line_item]
        )
        overlay_coordinator.image_viewer.image_item = MagicMock()

        overlay_coordinator.hide_roi_graphics(True)

        rect_item.setVisible.assert_called_once_with(False)
        ellipse_item.setVisible.assert_called_once_with(False)
        text_item.setVisible.assert_not_called()
        line_item.setVisible.assert_not_called()

    def test_handles_image_item_being_rect(
        self, overlay_coordinator: OverlayCoordinator
    ):
        rect_item = MagicMock(spec=QGraphicsRectItem)
        overlay_coordinator.image_viewer.scene.items = MagicMock(
            return_value=[rect_item]
        )
        overlay_coordinator.image_viewer.image_item = rect_item

        overlay_coordinator.hide_roi_graphics(True)

        # Image item should not be hidden
        rect_item.setVisible.assert_not_called()

    def test_handles_image_item_being_ellipse(
        self, overlay_coordinator: OverlayCoordinator
    ):
        ellipse_item = MagicMock(spec=QGraphicsEllipseItem)
        overlay_coordinator.image_viewer.scene.items = MagicMock(
            return_value=[ellipse_item]
        )
        overlay_coordinator.image_viewer.image_item = ellipse_item

        overlay_coordinator.hide_roi_graphics(True)

        # Image item should not be hidden
        ellipse_item.setVisible.assert_not_called()
