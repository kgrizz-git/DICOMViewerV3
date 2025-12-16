"""
Text Annotation Coordinator

This module coordinates text annotation tool operations.

Inputs:
    - Text annotation drawing events
    - Text annotation deletion events
    
Outputs:
    - Text annotation operations coordinated with UI
    
Requirements:
    - TextAnnotationTool for text annotation operations
    - ImageViewer for scene operations
"""

from PySide6.QtCore import QPointF
from typing import Optional, Callable, TYPE_CHECKING
from pydicom.dataset import Dataset
from tools.text_annotation_tool import TextAnnotationTool
from gui.image_viewer import ImageViewer
from utils.dicom_utils import get_composite_series_key

if TYPE_CHECKING:
    from utils.undo_redo import UndoRedoManager


class TextAnnotationCoordinator:
    """
    Coordinates text annotation operations.
    
    Responsibilities:
    - Handle text annotation creation events
    - Handle text annotation deletion events
    - Handle text annotation visibility
    """
    
    def __init__(
        self,
        text_annotation_tool: TextAnnotationTool,
        image_viewer: ImageViewer,
        get_current_dataset: Callable[[], Optional[Dataset]],
        get_current_slice_index: Callable[[], int],
        undo_redo_manager: Optional['UndoRedoManager'] = None,
        update_undo_redo_state_callback: Optional[Callable[[], None]] = None
    ):
        """
        Initialize the text annotation coordinator.
        
        Args:
            text_annotation_tool: Text annotation tool instance
            image_viewer: Image viewer widget
            get_current_dataset: Callback to get current dataset
            get_current_slice_index: Callback to get current slice index
            undo_redo_manager: Optional undo/redo manager
            update_undo_redo_state_callback: Optional callback to update undo/redo state
        """
        self.text_annotation_tool = text_annotation_tool
        self.image_viewer = image_viewer
        self.get_current_dataset = get_current_dataset
        self.get_current_slice_index = get_current_slice_index
        self.undo_redo_manager = undo_redo_manager
        self.update_undo_redo_state_callback = update_undo_redo_state_callback
    
    def handle_text_annotation_started(self, pos: QPointF) -> None:
        """
        Handle text annotation start.
        
        Args:
            pos: Starting position
        """
        # Set current slice context before starting annotation
        current_dataset = self.get_current_dataset()
        if current_dataset is not None:
            study_uid = getattr(current_dataset, 'StudyInstanceUID', '')
            series_uid = get_composite_series_key(current_dataset)
            # Use current slice index as instance identifier (array position)
            instance_identifier = self.get_current_slice_index()
            self.text_annotation_tool.set_current_slice(study_uid, series_uid, instance_identifier)
        
        # Create callback for when editing finishes
        def on_editing_finished(accept: bool) -> None:
            """Handle editing finished - finish the annotation."""
            # Clear annotation state
            if hasattr(self.image_viewer, 'text_annotating'):
                self.image_viewer.text_annotating = False
                self.image_viewer.text_annotation_start_pos = None
            
            if accept:
                self.handle_text_annotation_finished()
            else:
                # Cancel annotation
                if self.image_viewer.scene is not None:
                    self.text_annotation_tool.cancel_annotation(self.image_viewer.scene)
        
        # Start annotation (creates item but doesn't start editing yet)
        self.text_annotation_tool.start_annotation(pos, on_editing_finished=on_editing_finished)
        
        # Add preview item to scene BEFORE starting editing (setFocus requires item to be in scene)
        if self.image_viewer.scene is not None and self.text_annotation_tool.current_item is not None:
            if self.text_annotation_tool.current_item.scene() != self.image_viewer.scene:
                self.image_viewer.scene.addItem(self.text_annotation_tool.current_item)
            
            # Now start editing after item is in scene
            self.text_annotation_tool.current_item.start_editing()
    
    def handle_text_annotation_finished(self) -> None:
        """Handle text annotation finish."""
        if self.image_viewer.scene is None:
            return
        
        annotation = self.text_annotation_tool.finish_annotation(self.image_viewer.scene)
        if annotation is not None:
            # Create undo/redo command for annotation addition
            if self.undo_redo_manager:
                from utils.undo_redo import TextAnnotationCommand
                current_dataset = self.get_current_dataset()
                study_uid = ""
                series_uid = ""
                instance_identifier = self.get_current_slice_index()
                if current_dataset is not None:
                    study_uid = getattr(current_dataset, 'StudyInstanceUID', '')
                    series_uid = get_composite_series_key(current_dataset)
                
                command = TextAnnotationCommand(
                    self.text_annotation_tool,
                    "add",
                    annotation,
                    self.image_viewer.scene,
                    study_uid,
                    series_uid,
                    instance_identifier
                )
                self.undo_redo_manager.execute_command(command)
                # Update undo/redo state after command execution
                if self.update_undo_redo_state_callback:
                    self.update_undo_redo_state_callback()
    
    def handle_text_annotation_delete_requested(self, annotation_item) -> None:
        """
        Handle text annotation deletion request from context menu or Delete key.
        
        Args:
            annotation_item: TextAnnotationItem to delete
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
        
        # Create undo/redo command for annotation deletion
        if self.undo_redo_manager:
            from utils.undo_redo import TextAnnotationCommand
            command = TextAnnotationCommand(
                self.text_annotation_tool,
                "remove",
                annotation_item,
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
            self.text_annotation_tool.delete_annotation(annotation_item, self.image_viewer.scene)
    
    def display_annotations_for_slice(self, study_uid: str, series_uid: str, instance_identifier: int) -> None:
        """
        Display text annotations for a slice.
        
        Args:
            study_uid: StudyInstanceUID
            series_uid: SeriesInstanceUID
            instance_identifier: Instance identifier
        """
        if self.image_viewer.scene is None:
            return
        
        self.text_annotation_tool.display_annotations_for_slice(
            study_uid, series_uid, instance_identifier, self.image_viewer.scene
        )
    
    def clear_annotations_from_other_slices(self, study_uid: str, series_uid: str, instance_identifier: int) -> None:
        """
        Clear annotations from other slices.
        
        Args:
            study_uid: StudyInstanceUID of current slice
            series_uid: SeriesInstanceUID of current slice
            instance_identifier: Instance identifier of current slice
        """
        if self.image_viewer.scene is None:
            return
        
        self.text_annotation_tool.clear_annotations_from_other_slices(
            study_uid, series_uid, instance_identifier, self.image_viewer.scene
        )
