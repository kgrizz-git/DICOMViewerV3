"""
Crosshair Coordinator

This module coordinates crosshair operations between the image viewer and crosshair manager.

Inputs:
    - Crosshair click events from image viewer
    - Slice change events
    
Outputs:
    - Crosshair annotations on images
    
Requirements:
    - PySide6 for graphics components
    - CrosshairManager for crosshair management
    - ImageViewer for scene access
"""

from PySide6.QtCore import QPointF, QTimer
from typing import Optional, Callable, TYPE_CHECKING, Dict
from pydicom.dataset import Dataset

from tools.crosshair_manager import CrosshairManager
from gui.image_viewer import ImageViewer
from utils.dicom_utils import get_composite_series_key

if TYPE_CHECKING:
    from utils.undo_redo import UndoRedoManager


class CrosshairCoordinator:
    """
    Coordinates crosshair operations.
    
    Responsibilities:
    - Handle crosshair creation requests
    - Manage crosshair display on slice changes
    - Handle crosshair deletion requests
    - Update crosshairs for privacy mode
    """
    
    def __init__(
        self,
        crosshair_manager: CrosshairManager,
        image_viewer: ImageViewer,
        get_current_dataset: Callable[[], Optional[Dataset]],
        get_current_slice_index: Callable[[], int],
        undo_redo_manager: Optional['UndoRedoManager'] = None,
        update_undo_redo_state_callback: Optional[Callable[[], None]] = None,
        get_use_rescaled_values: Optional[Callable[[], bool]] = None
    ):
        """
        Initialize the crosshair coordinator.
        
        Args:
            crosshair_manager: CrosshairManager instance
            image_viewer: ImageViewer instance
            get_current_dataset: Callback to get current dataset
            get_current_slice_index: Callback to get current slice index
        """
        self.crosshair_manager = crosshair_manager
        self.image_viewer = image_viewer
        self.get_current_dataset = get_current_dataset
        self.get_current_slice_index = get_current_slice_index
        self.undo_redo_manager = undo_redo_manager
        self.update_undo_redo_state_callback = update_undo_redo_state_callback
        self.get_use_rescaled_values = get_use_rescaled_values
        
        # Crosshair move tracking with batching
        self._crosshair_move_tracking: Dict[object, Dict] = {}  # Tracks ongoing moves
        self._move_batch_timer: Optional[QTimer] = None  # Timer for debouncing
    
    def handle_crosshair_clicked(self, pos: QPointF, pixel_value_str: str, x: int, y: int, z: int) -> None:
        """
        Handle crosshair click event.
        
        Args:
            pos: Position in scene coordinates
            pixel_value_str: Formatted pixel value string
            x: X coordinate (column)
            y: Y coordinate (row)
            z: Z coordinate (slice index)
        """
        if self.image_viewer.scene is None:
            return
        
        # Set current slice context
        current_dataset = self.get_current_dataset()
        if current_dataset is not None:
            from utils.dicom_utils import get_composite_series_key, pixel_to_patient_coordinates
            study_uid = getattr(current_dataset, 'StudyInstanceUID', '')
            series_uid = get_composite_series_key(current_dataset)
            instance_identifier = self.get_current_slice_index()
            self.crosshair_manager.set_current_slice(study_uid, series_uid, instance_identifier)
            
            # Calculate patient coordinates
            patient_coords = pixel_to_patient_coordinates(current_dataset, x, y, z)
            if patient_coords:
                # Format patient coordinates and append to pixel_value_str
                px, py, pz = patient_coords
                pixel_value_str = f"{pixel_value_str}\nPatient: ({px:.2f}, {py:.2f}, {pz:.2f}) mm"
        
        # Create crosshair annotation
        crosshair = self.crosshair_manager.create_crosshair(
            pos,
            pixel_value_str,
            x,
            y,
            z,
            self.image_viewer.scene
        )
        
        # Create undo/redo command for crosshair addition
        if crosshair and self.undo_redo_manager and self.image_viewer.scene:
            from utils.undo_redo import CrosshairCommand
            command = CrosshairCommand(
                self.crosshair_manager,
                "add",
                crosshair,
                self.image_viewer.scene,
                study_uid,
                series_uid,
                instance_identifier
            )
            self.undo_redo_manager.execute_command(command)
            # Update undo/redo state after command execution
            if self.update_undo_redo_state_callback:
                self.update_undo_redo_state_callback()
        
        # Set up movement callback for the newly created crosshair
        if crosshair is not None:
            crosshair.on_moved_callback = lambda c=crosshair: self._on_crosshair_moved(c)
    
    def handle_crosshair_delete_requested(self, crosshair_item) -> None:
        """
        Handle crosshair deletion request.
        
        Args:
            crosshair_item: CrosshairItem to delete
        """
        if self.image_viewer.scene is None:
            return
        
        # Get identifiers before deletion
        current_dataset = self.get_current_dataset()
        study_uid = ""
        series_uid = ""
        instance_identifier = self.get_current_slice_index()
        if current_dataset is not None:
            from utils.dicom_utils import get_composite_series_key
            study_uid = getattr(current_dataset, 'StudyInstanceUID', '')
            series_uid = get_composite_series_key(current_dataset)
        
        # Create undo/redo command for crosshair deletion
        if self.undo_redo_manager:
            from utils.undo_redo import CrosshairCommand
            command = CrosshairCommand(
                self.crosshair_manager,
                "remove",
                crosshair_item,
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
            self.crosshair_manager.delete_crosshair(crosshair_item, self.image_viewer.scene)
    
    def handle_clear_crosshairs(self) -> None:
        """
        Handle clear crosshairs request.
        
        Clears all crosshairs on the current slice only.
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
        
        # Get all crosshairs for this slice before deletion
        key = (study_uid, series_uid, instance_identifier)
        crosshairs_to_delete = []
        if key in self.crosshair_manager.crosshairs:
            crosshairs_to_delete = list(self.crosshair_manager.crosshairs[key])
        
        if not crosshairs_to_delete:
            return  # Nothing to delete
        
        # Create a composite command for deleting all crosshairs
        if self.undo_redo_manager and self.image_viewer.scene:
            from utils.undo_redo import CompositeCommand, CrosshairCommand
            commands = []
            for crosshair_item in crosshairs_to_delete:
                command = CrosshairCommand(
                    self.crosshair_manager,
                    "remove",
                    crosshair_item,
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
            self.crosshair_manager.clear_crosshairs_for_slice(self.image_viewer.scene)
    
    def update_crosshairs_for_slice(self) -> None:
        """
        Update crosshairs display for current slice.
        
        This should be called when slice changes to ensure crosshairs are displayed.
        """
        if self.image_viewer.scene is None:
            return
        
        # Set current slice context
        current_dataset = self.get_current_dataset()
        if current_dataset is not None:
            from utils.dicom_utils import get_composite_series_key
            study_uid = getattr(current_dataset, 'StudyInstanceUID', '')
            series_uid = get_composite_series_key(current_dataset)
            instance_identifier = self.get_current_slice_index()
            self.crosshair_manager.set_current_slice(study_uid, series_uid, instance_identifier)
        
        # Display crosshairs for current slice
        self.crosshair_manager.display_crosshairs_for_slice(self.image_viewer.scene)
    
    def update_privacy_mode(self, privacy_mode: bool) -> None:
        """
        Update privacy mode for all crosshairs.
        
        Args:
            privacy_mode: Whether privacy mode is enabled
        """
        self.crosshair_manager.set_privacy_mode(privacy_mode)
    
    def _on_crosshair_moved(self, crosshair_item) -> None:
        """
        Handle crosshair movement - track for undo/redo with batching.
        
        Args:
            crosshair_item: CrosshairItem that was moved
        """
        try:
            # Check if crosshair is still valid
            if crosshair_item is None or not hasattr(crosshair_item, 'pos'):
                return
            
            # Get current position
            current_pos = crosshair_item.pos()
            
            # Check if crosshair is being tracked for movement
            if crosshair_item not in self._crosshair_move_tracking:
                # Store initial position and start tracking
                self._crosshair_move_tracking[crosshair_item] = {
                    'initial_pos': current_pos,
                    'current_pos': current_pos
                }
            else:
                # Update current position (don't create command yet)
                self._crosshair_move_tracking[crosshair_item]['current_pos'] = current_pos
            
            # Start/restart batch timer (200ms delay)
            if self._move_batch_timer is not None:
                self._move_batch_timer.stop()
            
            self._move_batch_timer = QTimer()
            self._move_batch_timer.setSingleShot(True)
            self._move_batch_timer.timeout.connect(lambda: self._finalize_crosshair_move(crosshair_item))
            self._move_batch_timer.start(200)  # 200ms delay
        except Exception as e:
            import traceback
            traceback.print_exc()
    
    def _finalize_crosshair_move(self, crosshair_item) -> None:
        """
        Finalize crosshair move by creating undo/redo command and updating pixel values.
        
        Args:
            crosshair_item: CrosshairItem that was moved
        """
        if crosshair_item not in self._crosshair_move_tracking:
            return
        
        tracking = self._crosshair_move_tracking[crosshair_item]
        initial_pos = tracking['initial_pos']
        final_pos = tracking['current_pos']
        
        # Recalculate pixel values at new position
        self._update_crosshair_pixel_values(crosshair_item, final_pos)
        
        # Only create command if position actually changed
        if initial_pos != final_pos and self.undo_redo_manager and self.image_viewer.scene:
            from utils.undo_redo import CrosshairMoveCommand
            command = CrosshairMoveCommand(crosshair_item, initial_pos, final_pos, self.image_viewer.scene)
            self.undo_redo_manager.execute_command(command)
            # Update undo/redo state after command execution
            if self.update_undo_redo_state_callback:
                self.update_undo_redo_state_callback()
        
        # Clear tracking
        del self._crosshair_move_tracking[crosshair_item]
    
    def _update_crosshair_pixel_values(self, crosshair_item, new_pos: QPointF) -> None:
        """
        Update crosshair pixel values and coordinates at new position.
        
        Args:
            crosshair_item: CrosshairItem to update
            new_pos: New position in scene coordinates
        """
        try:
            # Get current dataset and slice index
            current_dataset = self.get_current_dataset()
            if current_dataset is None:
                return
            
            # Convert scene position to pixel coordinates
            x = int(new_pos.x())
            y = int(new_pos.y())
            z = self.get_current_slice_index()
            
            # Get pixel value
            use_rescaled = False
            if self.get_use_rescaled_values:
                use_rescaled = self.get_use_rescaled_values()
            
            pixel_value_str = self.image_viewer._get_pixel_value_at_coords(
                current_dataset, x, y, z, use_rescaled
            )
            
            # Get patient coordinates if available
            from utils.dicom_utils import pixel_to_patient_coordinates
            patient_coords = pixel_to_patient_coordinates(current_dataset, x, y, z)
            if patient_coords:
                px, py, pz = patient_coords
                pixel_value_str = f"{pixel_value_str}\nPatient: ({px:.2f}, {py:.2f}, {pz:.2f}) mm"
            
            # Update crosshair item's stored values and text display
            crosshair_item.update_pixel_values(pixel_value_str, x, y, z)
        except Exception as e:
            import traceback
            traceback.print_exc()

