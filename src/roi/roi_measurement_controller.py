"""
ROI and measurement controller module.

Coordinates ROI management, measurement tools, annotations, and associated
panels for the DICOM Viewer application. This controller centralizes creation
and basic wiring of ROI-related components that were previously constructed
directly by DICOMViewerApp.

Inputs / dependencies:
- Config manager instance

Outputs / responsibilities:
- Creates and owns the shared/initial instances of:
  - ROIManager
  - MeasurementTool
  - AnnotationManager
  - ROIStatisticsPanel
  - ROIListPanel
- Wires ROIListPanel to use the ROIManager for displaying ROIs.
- Tracks the currently active (focused-subwindow) roi_manager and
  measurement_tool so callers can delegate style updates and other
  operations to the correct per-subwindow managers.

Requirements:
- This module does not depend on a QApplication instance directly, but the
  widgets it creates assume that Qt has already been initialized by the caller.
"""

from __future__ import annotations

from typing import Optional

from tools.roi_manager import ROIManager
from tools.measurement_tool import MeasurementTool
from tools.annotation_manager import AnnotationManager
from gui.roi_statistics_panel import ROIStatisticsPanel
from gui.roi_list_panel import ROIListPanel


class ROIMeasurementController:
    """
    Controller that owns and coordinates ROI, measurement, and annotation tools.

    The controller holds the shared/initial instances of all ROI-related
    objects. Because each image-viewer subwindow has its own per-window
    ROIManager and MeasurementTool, callers should call
    ``update_focused_managers`` whenever the focused subwindow changes so
    that delegation methods like ``update_styles`` always operate on the
    correct managers.
    """

    def __init__(self, config_manager) -> None:
        self._config_manager = config_manager

        # Core tools (shared/initial instances)
        self.roi_manager = ROIManager(config_manager=self._config_manager)
        self.measurement_tool = MeasurementTool(config_manager=self._config_manager)
        self.annotation_manager = AnnotationManager()

        # Panels
        self.roi_statistics_panel = ROIStatisticsPanel()
        self.roi_list_panel = ROIListPanel()

        # Wire list panel to the initial ROI manager.
        self.roi_list_panel.set_roi_manager(self.roi_manager)

        # Track the currently active (focused subwindow) managers.
        # These start as the shared instances but are updated by
        # update_focused_managers() when a subwindow receives focus.
        self._active_roi_manager: Optional[ROIManager] = self.roi_manager
        self._active_measurement_tool: Optional[MeasurementTool] = self.measurement_tool

    # ------------------------------------------------------------------
    # Focus tracking
    # ------------------------------------------------------------------

    def update_focused_managers(
        self,
        roi_manager: Optional[ROIManager],
        measurement_tool: Optional[MeasurementTool],
    ) -> None:
        """
        Update the controller's references to the currently focused subwindow's
        ROI manager and measurement tool.

        Called by DICOMViewerApp whenever the focused subwindow changes so
        that subsequent delegated operations target the correct per-window
        managers.

        Args:
            roi_manager: The focused subwindow's ROIManager, or None.
            measurement_tool: The focused subwindow's MeasurementTool, or None.
        """
        if roi_manager is not None:
            self._active_roi_manager = roi_manager
        if measurement_tool is not None:
            self._active_measurement_tool = measurement_tool

    # ------------------------------------------------------------------
    # Style updates
    # ------------------------------------------------------------------

    def update_styles(self, config_manager) -> None:
        """
        Update visual styles for ROIs and measurements using the given config.

        Applies style updates to the currently active (focused subwindow)
        roi_manager and measurement_tool, falling back to the shared instances
        if no focused managers have been set.
        """
        mgr = self._active_roi_manager or self.roi_manager
        tool = self._active_measurement_tool or self.measurement_tool
        if mgr is not None:
            mgr.update_all_roi_styles(config_manager)
        if tool is not None:
            tool.update_all_measurement_styles(config_manager)

    # ------------------------------------------------------------------
    # Panel delegation helpers
    # ------------------------------------------------------------------

    def clear_statistics(self) -> None:
        """Clear the ROI statistics panel."""
        self.roi_statistics_panel.clear_statistics()

    def update_roi_list(
        self, study_uid: str, series_uid: str, instance_identifier
    ) -> None:
        """
        Update the ROI list panel for the given study/series/instance.

        Args:
            study_uid: DICOM study UID.
            series_uid: DICOM series UID.
            instance_identifier: Instance identifier (e.g. slice index).
        """
        self.roi_list_panel.update_roi_list(study_uid, series_uid, instance_identifier)

    def select_roi_in_list(self, roi) -> None:
        """
        Select the given ROI in the list panel.

        Args:
            roi: The ROI object to select.
        """
        self.roi_list_panel.select_roi_in_list(roi)

