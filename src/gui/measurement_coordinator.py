"""
Measurement Coordinator

This module coordinates measurement tool operations.

Inputs:
    - Measurement drawing events
    - Measurement deletion events
    
Outputs:
    - Measurement operations coordinated with UI
    
Requirements:
    - MeasurementTool for measurement operations
    - ImageViewer for scene operations
"""

from PySide6.QtCore import QPointF
from typing import Optional, Callable
from pydicom.dataset import Dataset
from tools.measurement_tool import MeasurementTool
from gui.image_viewer import ImageViewer


class MeasurementCoordinator:
    """
    Coordinates measurement operations.
    
    Responsibilities:
    - Handle measurement drawing events
    - Handle measurement deletion events
    - Handle measurement visibility
    """
    
    def __init__(
        self,
        measurement_tool: MeasurementTool,
        image_viewer: ImageViewer,
        get_current_dataset: Callable[[], Optional[Dataset]],
        get_current_slice_index: Callable[[], int]
    ):
        """
        Initialize the measurement coordinator.
        
        Args:
            measurement_tool: Measurement tool instance
            image_viewer: Image viewer widget
            get_current_dataset: Callback to get current dataset
            get_current_slice_index: Callback to get current slice index
        """
        self.measurement_tool = measurement_tool
        self.image_viewer = image_viewer
        self.get_current_dataset = get_current_dataset
        self.get_current_slice_index = get_current_slice_index
    
    def handle_measurement_started(self, pos: QPointF) -> None:
        """
        Handle measurement start.
        
        Args:
            pos: Starting position
        """
        # Set current slice context before starting measurement
        current_dataset = self.get_current_dataset()
        if current_dataset is not None:
            study_uid = getattr(current_dataset, 'StudyInstanceUID', '')
            series_uid = getattr(current_dataset, 'SeriesInstanceUID', '')
            instance_number = getattr(current_dataset, 'InstanceNumber', None)
            if instance_number is None:
                instance_identifier = self.get_current_slice_index()
            else:
                instance_identifier = int(instance_number)
            self.measurement_tool.set_current_slice(study_uid, series_uid, instance_identifier)
        
        self.measurement_tool.start_measurement(pos)
    
    def handle_measurement_updated(self, pos: QPointF) -> None:
        """
        Handle measurement update.
        
        Args:
            pos: Current position
        """
        if self.image_viewer.scene is not None:
            self.measurement_tool.update_measurement(pos, self.image_viewer.scene)
    
    def handle_measurement_finished(self) -> None:
        """Handle measurement finish."""
        if self.image_viewer.scene is not None:
            measurement = self.measurement_tool.finish_measurement(self.image_viewer.scene)
            if measurement is not None:
                # Measurement completed successfully
                pass
    
    def handle_measurement_delete_requested(self, measurement_item) -> None:
        """
        Handle measurement deletion request from context menu.
        
        Args:
            measurement_item: MeasurementItem to delete
        """
        if self.image_viewer.scene is not None:
            self.measurement_tool.delete_measurement(measurement_item, self.image_viewer.scene)
    
    def handle_clear_measurements(self) -> None:
        """
        Handle clear measurements request from toolbar or context menu.
        
        Clears all measurements on the current slice only.
        """
        if self.image_viewer.scene is not None:
            current_dataset = self.get_current_dataset()
            if current_dataset is not None:
                # Extract DICOM identifiers for current slice
                study_uid = getattr(current_dataset, 'StudyInstanceUID', '')
                series_uid = getattr(current_dataset, 'SeriesInstanceUID', '')
                instance_number = getattr(current_dataset, 'InstanceNumber', None)
                if instance_number is None:
                    instance_identifier = self.get_current_slice_index()
                else:
                    instance_identifier = int(instance_number)
                
                # Clear measurements for current slice
                self.measurement_tool.clear_slice_measurements(
                    study_uid, series_uid, instance_identifier, self.image_viewer.scene
                )
    
    def hide_measurement_labels(self, hide: bool) -> None:
        """
        Hide or show measurement labels.
        
        Args:
            hide: True to hide labels, False to show them
        """
        if self.image_viewer.scene is None:
            return
        
        from tools.measurement_tool import MeasurementItem
        for item in self.image_viewer.scene.items():
            if isinstance(item, MeasurementItem):
                # Hide/show the text item within the measurement
                if hasattr(item, 'text_item') and item.text_item is not None:
                    item.text_item.setVisible(not hide)
    
    def hide_measurement_graphics(self, hide: bool) -> None:
        """
        Hide or show measurement graphics (lines and handles).
        
        Args:
            hide: True to hide graphics, False to show them
        """
        if self.image_viewer.scene is None:
            return
        
        from tools.measurement_tool import MeasurementItem
        for item in self.image_viewer.scene.items():
            if isinstance(item, MeasurementItem):
                item.setVisible(not hide)

