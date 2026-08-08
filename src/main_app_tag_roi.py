"""
DICOMViewerApp tag editing and ROI workflow mixin module.

Owns tag viewer/edit/undo/redo, tag-export union coordination, and ROI display/list/
keyboard-delete handlers for ``DICOMViewerApp`` (see MAIN_PY_REFACTOR_PLAN Appendix A).
Methods extracted from ``main.py`` in Phase 5.
"""

from __future__ import annotations

# pyright: reportAttributeAccessIssue=false, reportArgumentType=false, reportUninitializedInstanceVariable=false
from typing import Any, cast

from pydicom.dataset import Dataset
from PySide6.QtCore import QPointF

from core.actions import customization_actions
from core.slice_display_handlers import (
    display_measurements_for_slice,
    display_rois_for_slice,
    update_roi_list,
)
from gui.actions import dialog_actions
from tools.roi_manager import ROIItem


class TagEditingMixin:
    """
    Mixin: tag viewer updates, tag edit/undo/redo, and tag-export union workflow
    for ``DICOMViewerApp``.
    """

    def get_tag_export_union_snapshot(self) -> tuple[int, dict[str, Any] | None]:
        """Current load generation and merged tag map, if background union has finished."""
        return self.tag_export_union_host.get_snapshot()

    def _drain_tag_export_union_worker(self, timeout_sec: float = 180.0) -> None:
        """
        Stop and join the tag-export union QThread before replacing it.

        Body in ``gui.tag_export_union_host.TagExportUnionHost.drain_worker``.
        """
        self.tag_export_union_host.drain_worker(timeout_sec)

    def _schedule_tag_export_union_rebuild(self) -> None:
        """Rebuild in-memory tag union off the GUI thread (no disk cache)."""
        self.tag_export_union_host.schedule_rebuild()

    def _update_tag_viewer(self, dataset: Dataset) -> None:
        """Update tag viewer with dataset."""
        self.dialog_coordinator.update_tag_viewer(dataset)

    def _on_tag_edited(self, _tag_str: str, _new_value) -> None:
        """
        Handle tag edit from either panel - refresh both panels.
        
        Args:
            tag_str: Tag string that was edited
            new_value: New tag value
        """
        # Refresh metadata panel via controller
        search_text = self.metadata_panel.search_edit.text()
        self.metadata_controller.refresh_panel_tags(search_text)

        # Refresh tag viewer dialog if open
        if self.dialog_coordinator.tag_viewer_dialog:
            search_text = self.dialog_coordinator.tag_viewer_dialog.search_edit.text()
            self.dialog_coordinator.tag_viewer_dialog._cached_tags = None
            # Clear parser cache so it re-reads from updated dataset
            if self.dialog_coordinator.tag_viewer_dialog.parser is not None:
                self.dialog_coordinator.tag_viewer_dialog.parser._tag_cache.clear()
            self.dialog_coordinator.tag_viewer_dialog._populate_tags(search_text)

        # Update undo/redo state
        self._update_undo_redo_state()

    def _undo_tag_edit(self) -> None:
        """Handle undo tag edit request."""
        success = self.metadata_controller.undo_tag_edit(self.current_dataset)
        if success:
            # Refresh metadata panel via controller
            self.metadata_controller.refresh_panel_tags()
            # Refresh tag viewer dialog if open
            if self.dialog_coordinator.tag_viewer_dialog:
                search_text = self.dialog_coordinator.tag_viewer_dialog.search_edit.text()
                if self.dialog_coordinator.tag_viewer_dialog.parser is not None:
                    self.dialog_coordinator.tag_viewer_dialog.parser._tag_cache.clear()
                self.dialog_coordinator.tag_viewer_dialog._populate_tags(search_text)
            # Update undo/redo state
            self._update_undo_redo_state()

    def _redo_tag_edit(self) -> None:
        """Handle redo tag edit request."""
        success = self.metadata_controller.redo_tag_edit(self.current_dataset)
        if success:
            # Refresh metadata panel via controller
            self.metadata_controller.refresh_panel_tags()
            # Refresh tag viewer dialog if open
            if self.dialog_coordinator.tag_viewer_dialog:
                search_text = self.dialog_coordinator.tag_viewer_dialog.search_edit.text()
                if self.dialog_coordinator.tag_viewer_dialog.parser is not None:
                    self.dialog_coordinator.tag_viewer_dialog.parser._tag_cache.clear()
                self.dialog_coordinator.tag_viewer_dialog._populate_tags(search_text)
            # Update undo/redo state
            self._update_undo_redo_state()

    def _update_undo_redo_state(self) -> None:
        """Update undo/redo menu item states."""
        # Use unified undo/redo manager for all operations
        can_undo = self.undo_redo_manager.can_undo() if self.undo_redo_manager else False
        can_redo = self.undo_redo_manager.can_redo() if self.undo_redo_manager else False

        self.main_window.update_undo_redo_state(can_undo, can_redo)

    def _refresh_tag_ui(self) -> None:
        """Refresh both metadata panel and tag viewer dialog after tag changes."""
        # Refresh metadata panel
        if self.metadata_panel and self.metadata_panel.dataset:
            search_text = self.metadata_panel.search_edit.text()
            self.metadata_panel._cached_tags = None
            # Clear parser cache so it re-reads from updated dataset
            if self.metadata_panel.parser is not None:
                self.metadata_panel.parser._tag_cache.clear()
            self.metadata_panel._populate_tags(search_text)

        # Refresh tag viewer dialog if open
        if self.dialog_coordinator.tag_viewer_dialog:
            search_text = self.dialog_coordinator.tag_viewer_dialog.search_edit.text()
            self.dialog_coordinator.tag_viewer_dialog._cached_tags = None
            # Clear parser cache so it re-reads from updated dataset
            if self.dialog_coordinator.tag_viewer_dialog.parser is not None:
                self.dialog_coordinator.tag_viewer_dialog.parser._tag_cache.clear()
            self.dialog_coordinator.tag_viewer_dialog._populate_tags(search_text)

    def _open_tag_viewer(self) -> None:
        """Handle tag viewer dialog request."""
        dialog_actions.open_tag_viewer(self)

    def _open_tag_export(self) -> None:
        """Handle Tag Export dialog request."""
        dialog_actions.open_tag_export(self)

    def _on_export_tag_presets(self) -> None:
        """Handle Export Tag Presets request."""
        customization_actions.on_export_tag_presets(self)

    def _on_import_tag_presets(self) -> None:
        """Handle Import Tag Presets request."""
        customization_actions.on_import_tag_presets(self)


class ROIWorkflowMixin:
    """
    Mixin: ROI display per subwindow, ROI list updates, and keyboard ROI delete
    for ``DICOMViewerApp``.
    """

    def _display_rois_for_subwindow(self, idx: int, preserve_view: bool = False) -> None:
        """Display ROIs for a specific subwindow. Delegates to subwindow lifecycle controller."""
        self._subwindow_lifecycle_controller.display_rois_for_subwindow(idx, preserve_view)

    def _keyboard_delete_roi(self, roi: object) -> None:
        """Delete ROI invoked from keyboard; supports wrapper objects with .item or bare ROIItem."""
        item = getattr(roi, "item", None)
        if item is not None:
            self.roi_coordinator.handle_roi_delete_requested(item)
            return
        if roi is not None and self.image_viewer is not None:
            self.roi_manager.delete_roi(cast(ROIItem, roi), self.image_viewer.scene)

    def _update_roi_list(self) -> None:
        """Update ROI list panel."""
        update_roi_list(self)

    def _display_rois_for_slice(self, dataset) -> None:
        """Display ROIs for a slice."""
        display_rois_for_slice(self, dataset)

    def _display_measurements_for_slice(self, dataset) -> None:
        """Display measurements for a slice."""
        display_measurements_for_slice(self, dataset)

    def _open_export_roi_statistics(self) -> None:
        """Handle Export ROI Statistics request (from menu or image viewer context menu)."""
        self._export_app_facade.open_export_roi_statistics()

    def _set_roi_mode(self, mode: str | None) -> None:
        """
        Set ROI drawing mode (legacy method for backward compatibility).
        
        Args:
            mode: "rectangle", "ellipse", or None
        """
        self.mouse_mode_handler.set_roi_mode(mode)

    def _on_roi_drawing_started(self, pos: QPointF) -> None:
        """
        Handle ROI drawing start.
        
        Args:
            pos: Starting position
        """
        self.roi_coordinator.handle_roi_drawing_started(pos)

    def _on_roi_drawing_updated(self, pos: QPointF) -> None:
        """
        Handle ROI drawing update.
        
        Args:
            pos: Current position
        """
        self.roi_coordinator.handle_roi_drawing_updated(pos)

    def _on_roi_drawing_finished(self) -> None:
        """Handle ROI drawing finish."""
        self.roi_coordinator.handle_roi_drawing_finished()

    def _on_roi_clicked(self, item) -> None:
        """
        Handle ROI click.
        
        Args:
            item: QGraphicsItem that was clicked
        """
        self.roi_coordinator.handle_roi_clicked(item)

    def _on_image_clicked_no_roi(self) -> None:
        """Handle image click when not on an ROI - deselect current ROI."""
        self.roi_coordinator.handle_image_clicked_no_roi()

    def _on_measurement_started(self, pos: QPointF) -> None:
        """
        Handle measurement start.
        
        Args:
            pos: Starting position
        """
        self.measurement_coordinator.handle_measurement_started(pos)

    def _on_measurement_updated(self, pos: QPointF) -> None:
        """
        Handle measurement update.
        
        Args:
            pos: Current position
        """
        self.measurement_coordinator.handle_measurement_updated(pos)

    def _on_measurement_finished(self) -> None:
        """Handle measurement finish."""
        self.measurement_coordinator.handle_measurement_finished()

    def _on_measurement_delete_requested(self, measurement_item) -> None:
        """
        Handle measurement deletion request from context menu.
        
        Args:
            measurement_item: MeasurementItem to delete
        """
        self.measurement_coordinator.handle_measurement_delete_requested(measurement_item)

    def _on_clear_measurements_requested(self) -> None:
        """
        Handle clear measurements request from toolbar or context menu.
        """
        self.measurement_coordinator.handle_clear_measurements()

    def _on_roi_selected(self, roi) -> None:
        """
        Handle ROI selection from list.
        
        Args:
            roi: Selected ROI item
        """
        self.roi_coordinator.handle_roi_selected(roi)

    def _on_roi_delete_requested(self, item) -> None:
        """
        Handle ROI deletion request from context menu.
        
        Args:
            item: QGraphicsItem to delete
        """
        self.roi_coordinator.handle_roi_delete_requested(item)

    def _on_roi_deleted(self, roi) -> None:
        """
        Handle ROI deletion.
        
        Args:
            roi: Deleted ROI item
        """
        self.roi_coordinator.handle_roi_deleted(roi)

    def _delete_all_rois_current_slice(self) -> None:
        """
        Delete all ROIs and crosshairs on the current slice.
        """
        self.roi_coordinator.delete_all_rois_current_slice()
        # Also delete all crosshairs
        if hasattr(self, 'crosshair_coordinator') and self.crosshair_coordinator:
            self.crosshair_coordinator.handle_clear_crosshairs()

    def _on_scene_selection_changed(self) -> None:
        """Handle scene selection change (e.g., when ROI is moved)."""
        self.roi_coordinator.handle_scene_selection_changed()

    def _update_roi_statistics(self, roi) -> None:
        """
        Update statistics panel for a ROI.
        
        Args:
            roi: ROI item
        """
        self.roi_coordinator.update_roi_statistics(roi)

    def _hide_measurement_labels(self, hide: bool) -> None:
        """
        Hide or show measurement labels.
        
        Args:
            hide: True to hide labels, False to show them
        """
        self.measurement_coordinator.hide_measurement_labels(hide)

    def _hide_roi_labels(self, hide: bool) -> None:
        """
        Hide or show ROI labels.
        
        Args:
            hide: True to hide labels, False to show them
        """
        self.overlay_coordinator.hide_roi_labels(hide)

    def _hide_measurement_graphics(self, hide: bool) -> None:
        """
        Hide or show measurement graphics (lines and handles).
        
        Args:
            hide: True to hide graphics, False to show them
        """
        self.measurement_coordinator.hide_measurement_graphics(hide)

    def _hide_roi_graphics(self, hide: bool) -> None:
        """
        Hide or show ROI graphics (shapes).
        
        Args:
            hide: True to hide graphics, False to show them
        """
        self.overlay_coordinator.hide_roi_graphics(hide)

