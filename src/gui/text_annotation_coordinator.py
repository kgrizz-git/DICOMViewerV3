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

from PySide6.QtCore import QPointF, QTimer
from typing import Optional, Callable, TYPE_CHECKING, Dict
from pydicom.dataset import Dataset
from tools.text_annotation_tool import TextAnnotationTool
from gui.image_viewer import ImageViewer
from utils.dicom_utils import get_composite_series_key
from utils.debug_log import debug_log, annotation_debug

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
        self._processing_finished = False  # Flag to prevent double-call
        self._annotation_in_progress = False  # Flag to prevent double initialization
        
        # Move tracking for undo/redo (similar to arrow annotations)
        from PySide6.QtCore import QTimer
        self._text_move_tracking: Dict = {}  # Track text annotation moves for batching
        self._text_move_batch_timer: Optional[QTimer] = None
    
    def handle_text_annotation_started(self, pos: QPointF) -> None:
        """
        Handle text annotation start.
        
        Args:
            pos: Starting position
        """
        # Prevent double initialization
        if self._annotation_in_progress:
            annotation_debug(f" TextAnnotationCoordinator.handle_text_annotation_started: Already in progress, skipping")
            return
        
        annotation_debug(f" TextAnnotationCoordinator.handle_text_annotation_started: called, pos={pos}")
        self._annotation_in_progress = True
        
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
            annotation_debug(f" TextAnnotationCoordinator.on_editing_finished: accept={accept}, _processing_finished={self._processing_finished}")
            # Prevent double-call
            if self._processing_finished:
                annotation_debug(f" TextAnnotationCoordinator.on_editing_finished: Already processing, skipping")
                return
            
            # Clear annotation state
            if hasattr(self.image_viewer, 'text_annotating'):
                self.image_viewer.text_annotating = False
                self.image_viewer.text_annotation_start_pos = None
            
            if accept:
                self._processing_finished = True
                self.handle_text_annotation_finished()
            else:
                # Cancel annotation
                if self.image_viewer.scene is not None:
                    self.text_annotation_tool.cancel_annotation(self.image_viewer.scene)
            # Clear in-progress flag
            self._annotation_in_progress = False
        
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
        annotation_debug(f" TextAnnotationCoordinator.handle_text_annotation_finished: called, _processing_finished={self._processing_finished}")
        
        if self.image_viewer.scene is None:
            annotation_debug(f" TextAnnotationCoordinator.handle_text_annotation_finished: scene is None, returning")
            self._processing_finished = False
            return
        
        annotation_debug(f" TextAnnotationCoordinator.handle_text_annotation_finished: calling finish_annotation")
        annotation = self.text_annotation_tool.finish_annotation(self.image_viewer.scene)
        annotation_debug(f" TextAnnotationCoordinator.handle_text_annotation_finished: finish_annotation returned, annotation={'exists' if annotation is not None else 'None'}")
        
        if annotation is not None:
            annotation_debug(f" TextAnnotationCoordinator.handle_text_annotation_finished: annotation={annotation}, creating undo command")
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
                
                annotation_debug(f" TextAnnotationCoordinator.handle_text_annotation_finished: creating command with key=({study_uid[:20] if study_uid else ''}..., {series_uid[:20] if series_uid else ''}..., {instance_identifier})")
                command = TextAnnotationCommand(
                    self.text_annotation_tool,
                    "add",
                    annotation,
                    self.image_viewer.scene,
                    study_uid,
                    series_uid,
                    instance_identifier
                )
                annotation_debug(f" TextAnnotationCoordinator.handle_text_annotation_finished: executing command")
                self.undo_redo_manager.execute_command(command)
                annotation_debug(f" TextAnnotationCoordinator.handle_text_annotation_finished: command executed, undo stack size={len(self.undo_redo_manager.undo_stack)}")
                
                # Set up move callback for undo/redo tracking
                annotation.on_moved_callback = self._on_text_annotation_moved
                # Set up text edit callback for future edits
                annotation.on_text_edit_finished = self._on_text_annotation_edited
                annotation_debug(f" TextAnnotationCoordinator.handle_text_annotation_finished: set up callbacks for new annotation, on_text_edit_finished={'exists' if annotation.on_text_edit_finished is not None else 'None'}")
                
                # Store initial position for move tracking
                if annotation not in self._text_move_tracking:
                    self._text_move_tracking[annotation] = {
                        'initial_position': annotation.pos(),
                        'current_position': annotation.pos(),
                        'initialized': True
                    }
                    annotation_debug(f" TextAnnotationCoordinator.handle_text_annotation_finished: stored initial position for text annotation")
                
                # Update undo/redo state after command execution
                if self.update_undo_redo_state_callback:
                    self.update_undo_redo_state_callback()
            else:
                annotation_debug(f" TextAnnotationCoordinator.handle_text_annotation_finished: no undo_redo_manager")
        else:
            annotation_debug(f" TextAnnotationCoordinator.handle_text_annotation_finished: annotation is None, not creating undo command")
        
        # Reset processing flag
        self._processing_finished = False
        self._annotation_in_progress = False
        annotation_debug(f" TextAnnotationCoordinator.handle_text_annotation_finished: completed, _processing_finished={self._processing_finished}, _annotation_in_progress={self._annotation_in_progress}")
    
    def _on_text_annotation_moved(self, text_item) -> None:
        """
        Handle text annotation movement - track for undo/redo with batching.
        
        Args:
            text_item: TextAnnotationItem that was moved
        """
        try:
            # Check if item is still valid
            if text_item is None:
                return
            
            # Get current position
            current_pos = text_item.pos()
            
            # Check if item is being tracked for movement
            is_tracked = text_item in self._text_move_tracking
            tracking_data = self._text_move_tracking.get(text_item, {}) if text_item in self._text_move_tracking else {}
            debug_log("text_annotation_coordinator.py:_on_text_annotation_moved", "Text annotation moved", {"item_id": str(id(text_item)), "is_tracked": is_tracked, "current_pos": str(current_pos), "tracking_initial_pos": str(tracking_data.get('initial_position', 'N/A')), "tracking_initialized": tracking_data.get('initialized', False)}, hypothesis_id="C")

            if not is_tracked:
                # Start tracking
                self._text_move_tracking[text_item] = {
                    'initial_position': current_pos,
                    'current_position': current_pos,
                    'initialized': True
                }
                annotation_debug(f" TextAnnotationCoordinator._on_text_annotation_moved: First move, starting tracking")
            else:
                # Update current position
                tracking = self._text_move_tracking[text_item]
                tracking['current_position'] = current_pos
            
            # Start/restart batch timer (200ms delay)
            if self._text_move_batch_timer is not None:
                self._text_move_batch_timer.stop()
            
            self._text_move_batch_timer = QTimer()
            self._text_move_batch_timer.setSingleShot(True)
            self._text_move_batch_timer.timeout.connect(lambda: self._finalize_text_move(text_item))
            self._text_move_batch_timer.start(200)  # 200ms delay
        except Exception as e:
            import traceback
            traceback.print_exc()
    
    def _on_text_annotation_edited(self, text_item, old_text: str, new_text: str) -> None:
        """
        Handle text annotation text edit - create undo/redo command.
        
        Args:
            text_item: TextAnnotationItem that was edited
            old_text: Original text content
            new_text: New text content
        """
        annotation_debug(f" TextAnnotationCoordinator._on_text_annotation_edited: called, text_item={'exists' if text_item is not None else 'None'}, undo_manager={'exists' if self.undo_redo_manager is not None else 'None'}, old_text='{old_text}', new_text='{new_text}'")
        
        if text_item is None or self.undo_redo_manager is None:
            annotation_debug(f" TextAnnotationCoordinator._on_text_annotation_edited: early return (text_item or undo_manager is None)")
            return
        
        # Only create command if text actually changed
        if old_text != new_text:
            from utils.undo_redo import TextAnnotationEditCommand
            command = TextAnnotationEditCommand(text_item, old_text, new_text)
            self.undo_redo_manager.execute_command(command)
            # Update undo/redo state after command execution
            if self.update_undo_redo_state_callback:
                self.update_undo_redo_state_callback()
            annotation_debug(f" TextAnnotationCoordinator._on_text_annotation_edited: created edit command, old_text='{old_text}', new_text='{new_text}'")
        else:
            annotation_debug(f" TextAnnotationCoordinator._on_text_annotation_edited: text unchanged, not creating command")
    
    def _finalize_text_move(self, text_item) -> None:
        """
        Finalize text annotation move by creating undo/redo command.
        
        Args:
            text_item: TextAnnotationItem that was moved
        """
        if text_item not in self._text_move_tracking:
            return
        
        tracking = self._text_move_tracking[text_item]
        initial_pos = tracking['initial_position']
        final_pos = tracking['current_position']
        debug_log("text_annotation_coordinator.py:_finalize_text_move", "Finalizing text move", {"item_id": str(id(text_item)), "initial_pos": str(initial_pos), "final_pos": str(final_pos), "position_changed": initial_pos != final_pos}, hypothesis_id="C")

        # Only create command if position actually changed
        if initial_pos != final_pos and self.undo_redo_manager and self.image_viewer.scene:
            from utils.undo_redo import TextAnnotationMoveCommand
            command = TextAnnotationMoveCommand(
                text_item,
                initial_pos,
                final_pos,
                self.image_viewer.scene
            )
            self.undo_redo_manager.execute_command(command)
            # Update undo/redo state after command execution
            if self.update_undo_redo_state_callback:
                self.update_undo_redo_state_callback()
        
        # Remove from tracking
        if text_item in self._text_move_tracking:
            del self._text_move_tracking[text_item]
    
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
        
        # Set up move callbacks and text edit callbacks for all displayed annotations
        annotations = self.text_annotation_tool.get_annotations_for_slice(study_uid, series_uid, instance_identifier)
        for annotation in annotations:
            annotation.on_moved_callback = self._on_text_annotation_moved
            # Set up text edit callback for existing annotations (not new ones)
            # The callback receives (text_item, old_text, new_text) from finish_editing
            annotation.on_text_edit_finished = self._on_text_annotation_edited
            annotation_debug(f" TextAnnotationCoordinator.display_annotations_for_slice: set up callbacks for annotation, on_text_edit_finished={'exists' if annotation.on_text_edit_finished is not None else 'None'}")
            # Store initial position if not already stored
            if annotation not in self._text_move_tracking:
                self._text_move_tracking[annotation] = {
                    'initial_position': annotation.pos(),
                    'current_position': annotation.pos(),
                    'initialized': True
                }
    
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
