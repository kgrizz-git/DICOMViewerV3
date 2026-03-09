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

from PySide6.QtCore import QPointF, QTimer
from typing import Optional, Callable, TYPE_CHECKING, Dict
from pydicom.dataset import Dataset
from tools.measurement_tool import MeasurementTool
from gui.image_viewer import ImageViewer
from utils.dicom_utils import get_composite_series_key

if TYPE_CHECKING:
    from utils.undo_redo import UndoRedoManager


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
        get_current_slice_index: Callable[[], int],
        undo_redo_manager: Optional['UndoRedoManager'] = None,
        update_undo_redo_state_callback: Optional[Callable[[], None]] = None
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
        self.undo_redo_manager = undo_redo_manager
        self.update_undo_redo_state_callback = update_undo_redo_state_callback
        
        # Measurement move tracking with batching
        self._measurement_move_tracking: Dict[object, Dict] = {}  # Tracks ongoing moves
        self._move_batch_timer: Optional[QTimer] = None  # Timer for debouncing
    
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
            series_uid = get_composite_series_key(current_dataset)
            # Use current slice index as instance identifier (array position)
            instance_identifier = self.get_current_slice_index()
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
        if self.image_viewer.scene is None:
            return
        
        measurement = self.measurement_tool.finish_measurement(self.image_viewer.scene)
        if measurement is not None:
            # Create undo/redo command for measurement addition
            if self.undo_redo_manager:
                from utils.undo_redo import MeasurementCommand
                current_dataset = self.get_current_dataset()
                study_uid = ""
                series_uid = ""
                instance_identifier = self.get_current_slice_index()
                if current_dataset is not None:
                    study_uid = getattr(current_dataset, 'StudyInstanceUID', '')
                    series_uid = get_composite_series_key(current_dataset)
                
                command = MeasurementCommand(
                    self.measurement_tool,
                    "add",
                    measurement,
                    self.image_viewer.scene,
                    study_uid,
                    series_uid,
                    instance_identifier
                )
                self.undo_redo_manager.execute_command(command)
                # Update undo/redo state after command execution
                if self.update_undo_redo_state_callback:
                    self.update_undo_redo_state_callback()
            
            # Set up movement callback for the newly created measurement
            if measurement is not None:
                measurement.on_moved_callback = lambda m=measurement: self._on_measurement_moved(m)
                # Set up mouse release callback for immediate finalization
                measurement.on_mouse_release_callback = lambda m=measurement: self.finalize_measurement_move_immediately(m)
    
    def handle_measurement_delete_requested(self, measurement_item) -> None:
        """
        Handle measurement deletion request from context menu.
        
        Args:
            measurement_item: MeasurementItem to delete
        """
        if self.image_viewer.scene is None:
            return
        
        # Get identifiers before deletion
        current_dataset = self.get_current_dataset()
        study_uid = ""
        series_uid = ""
        instance_identifier = self.get_current_slice_index()
        if current_dataset is not None:
            study_uid = getattr(current_dataset, 'StudyInstanceUID', '')
            series_uid = get_composite_series_key(current_dataset)
        
        # Create undo/redo command for measurement deletion
        if self.undo_redo_manager:
            from utils.undo_redo import MeasurementCommand
            command = MeasurementCommand(
                self.measurement_tool,
                "remove",
                measurement_item,
                self.image_viewer.scene,
                study_uid,
                series_uid,
                instance_identifier
            )
            self.undo_redo_manager.execute_command(command)
            # Update undo/redo state after command execution
            if self.update_undo_redo_state_callback:
                self.update_undo_redo_state_callback()
        else:
            # Fallback to direct deletion if undo/redo not available
            self.measurement_tool.delete_measurement(measurement_item, self.image_viewer.scene)
    
    def handle_clear_measurements(self) -> None:
        """
        Handle clear measurements request from toolbar or context menu.
        
        Clears all measurements on the current slice only.
        """
        if self.image_viewer.scene is None:
            return
        
        current_dataset = self.get_current_dataset()
        if current_dataset is None:
            return
        
        # Extract DICOM identifiers for current slice
        study_uid = getattr(current_dataset, 'StudyInstanceUID', '')
        series_uid = get_composite_series_key(current_dataset)
        
        if not study_uid or not series_uid:
            return
        
        # Use current slice index as instance identifier (array position)
        instance_identifier = self.get_current_slice_index()
        
        # Get all measurements for this slice before deletion
        key = (study_uid, series_uid, instance_identifier)
        measurements_to_delete = []
        if key in self.measurement_tool.measurements:
            measurements_to_delete = list(self.measurement_tool.measurements[key])
        
        if not measurements_to_delete:
            return  # Nothing to delete
        
        # Create a composite command for deleting all measurements
        if self.undo_redo_manager and self.image_viewer.scene:
            from utils.undo_redo import CompositeCommand, MeasurementCommand
            commands = []
            for measurement_item in measurements_to_delete:
                command = MeasurementCommand(
                    self.measurement_tool,
                    "remove",
                    measurement_item,
                    self.image_viewer.scene,
                    study_uid,
                    series_uid,
                    instance_identifier
                )
                commands.append(command)
            
            if commands:
                composite_command = CompositeCommand(commands)
                self.undo_redo_manager.execute_command(composite_command)
                if self.update_undo_redo_state_callback:
                    self.update_undo_redo_state_callback()
        else:
            # Fallback to direct deletion
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
    
    def _on_measurement_moved(self, measurement_item) -> None:
        """
        Handle measurement movement - track for undo/redo with batching.
        
        Handles both group moves (dragging the line) and handle drags.
        
        Args:
            measurement_item: MeasurementItem that was moved
        """
        try:
            # Check if measurement is still valid
            if measurement_item is None or not hasattr(measurement_item, 'start_point'):
                return
            
            # Check if handles are being updated (handle drag in progress)
            if hasattr(measurement_item, '_updating_handles') and measurement_item._updating_handles:
                # This is a handle drag, track both start and end points
                current_start = measurement_item.start_point
                current_end = measurement_item.end_point
                
                # Check if measurement is being tracked for movement
                if measurement_item not in self._measurement_move_tracking:
                    # Store initial positions and start tracking
                    self._measurement_move_tracking[measurement_item] = {
                        'initial_start': current_start,
                        'initial_end': current_end,
                        'current_start': current_start,
                        'current_end': current_end
                    }
                else:
                    # Update current positions (don't create command yet)
                    self._measurement_move_tracking[measurement_item]['current_start'] = current_start
                    self._measurement_move_tracking[measurement_item]['current_end'] = current_end
            else:
                # This is a group move (dragging the line)
                current_start = measurement_item.start_point
                current_end = measurement_item.end_point
                
                # Check if measurement is being tracked for movement
                if measurement_item not in self._measurement_move_tracking:
                    # Store initial positions and start tracking
                    self._measurement_move_tracking[measurement_item] = {
                        'initial_start': current_start,
                        'initial_end': current_end,
                        'current_start': current_start,
                        'current_end': current_end
                    }
                else:
                    # Update current positions (don't create command yet)
                    self._measurement_move_tracking[measurement_item]['current_start'] = current_start
                    self._measurement_move_tracking[measurement_item]['current_end'] = current_end
            
            # Start/restart batch timer (200ms delay)
            if self._move_batch_timer is not None:
                self._move_batch_timer.stop()
            
            self._move_batch_timer = QTimer()
            self._move_batch_timer.setSingleShot(True)
            self._move_batch_timer.timeout.connect(lambda: self._finalize_measurement_move(measurement_item))
            self._move_batch_timer.start(200)  # 200ms delay
        except Exception as e:
            import traceback
            traceback.print_exc()
    
    def _finalize_measurement_move(self, measurement_item) -> None:
        """
        Finalize measurement move by creating undo/redo command.
        
        Args:
            measurement_item: MeasurementItem that was moved
        """
        if measurement_item not in self._measurement_move_tracking:
            return
        
        tracking = self._measurement_move_tracking[measurement_item]
        initial_start = tracking['initial_start']
        initial_end = tracking['initial_end']
        final_start = tracking['current_start']
        final_end = tracking['current_end']
        
        # Only create command if position actually changed
        if (initial_start != final_start or initial_end != final_end) and self.undo_redo_manager and self.image_viewer.scene:
            from utils.undo_redo import MeasurementMoveCommand
            command = MeasurementMoveCommand(
                measurement_item,
                initial_start,
                initial_end,
                final_start,
                final_end,
                self.image_viewer.scene
            )
            self.undo_redo_manager.execute_command(command)
            # Update undo/redo state after command execution
            if self.update_undo_redo_state_callback:
                self.update_undo_redo_state_callback()
        
        # Clear tracking
        del self._measurement_move_tracking[measurement_item]
    
    def finalize_measurement_move_immediately(self, measurement_item) -> None:
        """
        Finalize measurement move immediately (called on mouse release).
        
        This ensures the undo command is created right away when the mouse is released,
        rather than waiting for the timer to fire. This fixes the issue where pressing
        undo before the timer fires would undo the wrong operation.
        
        Args:
            measurement_item: MeasurementItem that was moved
        """
        # Stop any pending timer for this measurement
        if self._move_batch_timer is not None:
            self._move_batch_timer.stop()
            self._move_batch_timer = None
        
        # Finalize the move immediately
        self._finalize_measurement_move(measurement_item)

