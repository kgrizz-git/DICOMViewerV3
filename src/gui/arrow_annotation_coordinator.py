"""
Arrow Annotation Coordinator

This module coordinates arrow annotation tool operations.

Inputs:
    - Arrow annotation drawing events
    - Arrow annotation deletion events
    
Outputs:
    - Arrow annotation operations coordinated with UI
    
Requirements:
    - ArrowAnnotationTool for arrow annotation operations
    - ImageViewer for scene operations
"""

from PySide6.QtCore import QPointF
from typing import Optional, Callable, TYPE_CHECKING
from pydicom.dataset import Dataset
from tools.arrow_annotation_tool import ArrowAnnotationTool
from gui.image_viewer import ImageViewer
from utils.dicom_utils import get_composite_series_key

if TYPE_CHECKING:
    from utils.undo_redo import UndoRedoManager


class ArrowAnnotationCoordinator:
    """
    Coordinates arrow annotation operations.
    
    Responsibilities:
    - Handle arrow annotation drawing events
    - Handle arrow annotation deletion events
    - Handle arrow annotation visibility
    """
    
    def __init__(
        self,
        arrow_annotation_tool: ArrowAnnotationTool,
        image_viewer: ImageViewer,
        get_current_dataset: Callable[[], Optional[Dataset]],
        get_current_slice_index: Callable[[], int],
        undo_redo_manager: Optional['UndoRedoManager'] = None,
        update_undo_redo_state_callback: Optional[Callable[[], None]] = None
    ):
        """
        Initialize the arrow annotation coordinator.
        
        Args:
            arrow_annotation_tool: Arrow annotation tool instance
            image_viewer: Image viewer widget
            get_current_dataset: Callback to get current dataset
            get_current_slice_index: Callback to get current slice index
            undo_redo_manager: Optional undo/redo manager
            update_undo_redo_state_callback: Optional callback to update undo/redo state
        """
        self.arrow_annotation_tool = arrow_annotation_tool
        self.image_viewer = image_viewer
        self.get_current_dataset = get_current_dataset
        self.get_current_slice_index = get_current_slice_index
        self.undo_redo_manager = undo_redo_manager
        self.update_undo_redo_state_callback = update_undo_redo_state_callback
    
    def handle_arrow_annotation_started(self, pos: QPointF) -> None:
        """
        Handle arrow annotation start.
        
        Args:
            pos: Starting position
        """
        # Set current slice context before starting arrow
        current_dataset = self.get_current_dataset()
        if current_dataset is not None:
            study_uid = getattr(current_dataset, 'StudyInstanceUID', '')
            series_uid = get_composite_series_key(current_dataset)
            # Use current slice index as instance identifier (array position)
            instance_identifier = self.get_current_slice_index()
            self.arrow_annotation_tool.set_current_slice(study_uid, series_uid, instance_identifier)
        
        self.arrow_annotation_tool.start_arrow(pos)
    
    def handle_arrow_annotation_updated(self, pos: QPointF) -> None:
        """
        Handle arrow annotation update during drag.
        
        Args:
            pos: Current mouse position
        """
        if self.image_viewer.scene is not None:
            self.arrow_annotation_tool.update_arrow(pos, self.image_viewer.scene)
    
    def handle_arrow_annotation_finished(self) -> None:
        """Handle arrow annotation finish."""
        if self.image_viewer.scene is None:
            return
        
        arrow = self.arrow_annotation_tool.finish_arrow(self.image_viewer.scene)
        if arrow is not None:
            # Create undo/redo command for arrow addition
            if self.undo_redo_manager:
                from utils.undo_redo import ArrowAnnotationCommand
                current_dataset = self.get_current_dataset()
                study_uid = ""
                series_uid = ""
                instance_identifier = self.get_current_slice_index()
                if current_dataset is not None:
                    study_uid = getattr(current_dataset, 'StudyInstanceUID', '')
                    series_uid = get_composite_series_key(current_dataset)
                
                command = ArrowAnnotationCommand(
                    self.arrow_annotation_tool,
                    "add",
                    arrow,
                    self.image_viewer.scene,
                    study_uid,
                    series_uid,
                    instance_identifier
                )
                self.undo_redo_manager.execute_command(command)
                # Update undo/redo state after command execution
                if self.update_undo_redo_state_callback:
                    self.update_undo_redo_state_callback()
    
    def handle_arrow_annotation_delete_requested(self, arrow_item) -> None:
        """
        Handle arrow annotation deletion request from context menu or Delete key.
        
        Args:
            arrow_item: ArrowAnnotationItem to delete
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
        
        # Create undo/redo command for arrow deletion
        if self.undo_redo_manager:
            from utils.undo_redo import ArrowAnnotationCommand
            command = ArrowAnnotationCommand(
                self.arrow_annotation_tool,
                "remove",
                arrow_item,
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
            self.arrow_annotation_tool.delete_arrow(arrow_item, self.image_viewer.scene)
    
    def display_arrows_for_slice(self, study_uid: str, series_uid: str, instance_identifier: int) -> None:
        """
        Display arrow annotations for a slice.
        
        Args:
            study_uid: StudyInstanceUID
            series_uid: SeriesInstanceUID
            instance_identifier: Instance identifier
        """
        if self.image_viewer.scene is None:
            return
        
        self.arrow_annotation_tool.display_arrows_for_slice(
            study_uid, series_uid, instance_identifier, self.image_viewer.scene
        )
    
    def clear_arrows_from_other_slices(self, study_uid: str, series_uid: str, instance_identifier: int) -> None:
        """
        Clear arrows from other slices.
        
        Args:
            study_uid: StudyInstanceUID of current slice
            series_uid: SeriesInstanceUID of current slice
            instance_identifier: Instance identifier of current slice
        """
        if self.image_viewer.scene is None:
            return
        
        self.arrow_annotation_tool.clear_arrows_from_other_slices(
            study_uid, series_uid, instance_identifier, self.image_viewer.scene
        )
