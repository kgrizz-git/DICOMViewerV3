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

from PySide6.QtCore import QPointF, QTimer
from typing import Optional, Callable, TYPE_CHECKING, Dict
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
        
        # Move tracking for undo/redo
        self._arrow_move_tracking: Dict = {}  # Track arrow moves for batching
        self._move_batch_timer: Optional[QTimer] = None
    
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
            # Set up move callback for undo/redo tracking
            arrow.on_moved_callback = self._on_arrow_moved
            # Set up mouse release callback to finalize drag immediately
            arrow.on_mouse_release_callback = self._finalize_arrow_move
            
            # Store initial position for move tracking (before any moves happen)
            # This allows us to track the true initial position for undo
            if arrow not in self._arrow_move_tracking:
                # #region agent log
                with open('/Users/kevingrizzard/Documents/GitHub/DICOMViewerV3/.cursor/debug.log', 'a') as f:
                    import json
                    f.write(json.dumps({"sessionId":"debug-session","runId":"run1","hypothesisId":"B","location":"arrow_annotation_coordinator.py:110","message":"Storing initial position on arrow creation","data":{"arrow_id":str(id(arrow)),"start_point":str(arrow.start_point),"end_point":str(arrow.end_point)},"timestamp":int(__import__('time').time()*1000)}) + '\n')
                # #endregion
                # Store COPIES, not references
                from PySide6.QtCore import QPointF
                self._arrow_move_tracking[arrow] = {
                    'initial_start': QPointF(arrow.start_point),  # Create copy
                    'initial_end': QPointF(arrow.end_point),  # Create copy
                    'current_start': QPointF(arrow.start_point),  # Create copy
                    'current_end': QPointF(arrow.end_point),  # Create copy
                    'initialized': True  # Flag to indicate we have the true initial position
                }
                print(f"[ANNOTATION DEBUG] ArrowAnnotationCoordinator.handle_arrow_annotation_finished: stored initial position for arrow, start={arrow.start_point}, end={arrow.end_point}")
            
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
        
        # Set up move callbacks for all displayed arrows
        key = (study_uid, series_uid, instance_identifier)
        if key in self.arrow_annotation_tool.arrows:
            for arrow_item in self.arrow_annotation_tool.arrows[key]:
                arrow_item.on_moved_callback = self._on_arrow_moved
                # Set up mouse release callback to finalize drag immediately
                arrow_item.on_mouse_release_callback = self._finalize_arrow_move
                # Store initial position if not already stored (for arrows created before initialization)
                if arrow_item not in self._arrow_move_tracking:
                    # Store COPIES, not references
                    from PySide6.QtCore import QPointF
                    self._arrow_move_tracking[arrow_item] = {
                        'initial_start': QPointF(arrow_item.start_point),  # Create copy
                        'initial_end': QPointF(arrow_item.end_point),  # Create copy
                        'current_start': QPointF(arrow_item.start_point),  # Create copy
                        'current_end': QPointF(arrow_item.end_point),  # Create copy
                        'initialized': True
                    }
                    print(f"[ANNOTATION DEBUG] ArrowAnnotationCoordinator.display_arrows_for_slice: stored initial position for existing arrow")
    
    def _on_arrow_moved(self, arrow_item) -> None:
        """
        Handle arrow movement - track for undo/redo with batching.
        
        Args:
            arrow_item: ArrowAnnotationItem that was moved
        """
        try:
            # Check if arrow is still valid
            if arrow_item is None or not hasattr(arrow_item, 'start_point'):
                return
            
            # Skip if arrow is being updated programmatically (e.g., during undo/redo)
            if getattr(arrow_item, '_updating_position', False):
                print(f"[ANNOTATION DEBUG] ArrowAnnotationCoordinator._on_arrow_moved: skipping (programmatic update), _updating_position=True")
                return
            
            # Get positions BEFORE the move (stored in itemChange)
            # These are the true initial positions for this move
            pre_move_start = getattr(arrow_item, '_pre_move_start_point', None)
            pre_move_end = getattr(arrow_item, '_pre_move_end_point', None)
            
            # Get current positions (these have already been updated by itemChange)
            current_start = arrow_item.start_point
            current_end = arrow_item.end_point
            
            # Check if arrow is being tracked for movement
            is_tracked = arrow_item in self._arrow_move_tracking
            
            # #region agent log
            with open('/Users/kevingrizzard/Documents/GitHub/DICOMViewerV3/.cursor/debug.log', 'a') as f:
                import json
                tracking_data = self._arrow_move_tracking.get(arrow_item, {}) if arrow_item in self._arrow_move_tracking else {}
                f.write(json.dumps({"sessionId":"debug-session","runId":"run1","hypothesisId":"A","location":"arrow_annotation_coordinator.py:237","message":"_on_arrow_moved: callback called","data":{"arrow_id":str(id(arrow_item)),"is_tracked":is_tracked,"pre_move_start":str(pre_move_start) if pre_move_start else "None","pre_move_end":str(pre_move_end) if pre_move_end else "None","current_start":str(current_start),"current_end":str(current_end),"tracking_initial_start":str(tracking_data.get('initial_start', 'N/A')),"tracking_initial_end":str(tracking_data.get('initial_end', 'N/A')),"tracking_initialized":tracking_data.get('initialized', False)},"timestamp":int(__import__('time').time()*1000)}) + '\n')
            # #endregion
            
            print(f"[ANNOTATION DEBUG] ArrowAnnotationCoordinator._on_arrow_moved: arrow={arrow_item}, _updating_position={getattr(arrow_item, '_updating_position', False)}, tracking={is_tracked}, pre_move_start={pre_move_start}, pre_move_end={pre_move_end}, current_start={current_start}, current_end={current_end}")
            
            if not is_tracked:
                # First time tracking this arrow during this drag
                # Use pre_drag positions if available (captured on mouse press)
                pre_drag_start = getattr(arrow_item, '_pre_drag_start_point', None)
                pre_drag_end = getattr(arrow_item, '_pre_drag_end_point', None)
                
                if pre_drag_start is not None and pre_drag_end is not None:
                    # We have the true initial position from before drag started
                    from PySide6.QtCore import QPointF
                    initial_start = QPointF(pre_drag_start)  # Create copy
                    initial_end = QPointF(pre_drag_end)  # Create copy
                    print(f"[ANNOTATION DEBUG] ArrowAnnotationCoordinator._on_arrow_moved: First move, using pre_drag positions as initial")
                elif pre_move_start is not None and pre_move_end is not None:
                    # Fallback to pre_move positions
                    from PySide6.QtCore import QPointF
                    initial_start = QPointF(pre_move_start)  # Create copy
                    initial_end = QPointF(pre_move_end)  # Create copy
                    print(f"[ANNOTATION DEBUG] ArrowAnnotationCoordinator._on_arrow_moved: First move, using pre_move positions as initial")
                else:
                    # No pre_drag or pre_move - use current (will skip command if no change)
                    from PySide6.QtCore import QPointF
                    initial_start = QPointF(current_start)  # Create copy
                    initial_end = QPointF(current_end)  # Create copy
                    print(f"[ANNOTATION DEBUG] ArrowAnnotationCoordinator._on_arrow_moved: First move, no pre_drag/pre_move, using current")
                
                # Start tracking with COPIES
                from PySide6.QtCore import QPointF
                self._arrow_move_tracking[arrow_item] = {
                    'initial_start': QPointF(initial_start),  # Store copy
                    'initial_end': QPointF(initial_end),  # Store copy
                    'current_start': QPointF(current_start),  # Store copy
                    'current_end': QPointF(current_end),  # Store copy
                    'initialized': True
                }
            else:
                # Update current positions only (don't change initial - it's already set)
                tracking = self._arrow_move_tracking[arrow_item]
                from PySide6.QtCore import QPointF
                tracking['current_start'] = QPointF(current_start)  # Store copy
                tracking['current_end'] = QPointF(current_end)  # Store copy
                print(f"[ANNOTATION DEBUG] ArrowAnnotationCoordinator._on_arrow_moved: Continuing tracking, updated current positions")
            
            # Don't create command yet - just update tracking
            # Command will be created on mouse release via callback
        except Exception as e:
            import traceback
            traceback.print_exc()
    
    def _finalize_arrow_move(self, arrow_item) -> None:
        """
        Finalize arrow move by creating undo/redo command.
        
        Args:
            arrow_item: ArrowAnnotationItem that was moved
        """
        print(f"[ANNOTATION DEBUG] ArrowAnnotationCoordinator._finalize_arrow_move: called, arrow_item={'exists' if arrow_item is not None else 'None'}, in_tracking={arrow_item in self._arrow_move_tracking if arrow_item is not None else False}")
        
        if arrow_item not in self._arrow_move_tracking:
            print(f"[ANNOTATION DEBUG] ArrowAnnotationCoordinator._finalize_arrow_move: arrow not in tracking, returning")
            return
        
        # Verify arrow is still valid
        if arrow_item is None or not hasattr(arrow_item, 'start_point'):
            print(f"[ANNOTATION DEBUG] ArrowAnnotationCoordinator._finalize_arrow_move: arrow invalid, removing from tracking")
            if arrow_item in self._arrow_move_tracking:
                del self._arrow_move_tracking[arrow_item]
            return
        
        tracking = self._arrow_move_tracking[arrow_item]
        # Get copies to avoid reference issues
        from PySide6.QtCore import QPointF
        initial_start = QPointF(tracking['initial_start'])
        initial_end = QPointF(tracking['initial_end'])
        final_start = QPointF(tracking['current_start'])
        final_end = QPointF(tracking['current_end'])
        
        # #region agent log
        with open('/Users/kevingrizzard/Documents/GitHub/DICOMViewerV3/.cursor/debug.log', 'a') as f:
            import json
            f.write(json.dumps({"sessionId":"debug-session","runId":"run1","hypothesisId":"A","location":"arrow_annotation_coordinator.py:320","message":"_finalize_arrow_move: checking positions","data":{"arrow_id":str(id(arrow_item)),"initial_start":str(initial_start),"initial_end":str(initial_end),"final_start":str(final_start),"final_end":str(final_end),"initialized":tracking.get('initialized', False)},"timestamp":int(__import__('time').time()*1000)}) + '\n')
        # #endregion
        
        print(f"[ANNOTATION DEBUG] ArrowAnnotationCoordinator._finalize_arrow_move: positions - initial=({initial_start.x():.1f}, {initial_start.y():.1f}, {initial_end.x():.1f}, {initial_end.y():.1f}), final=({final_start.x():.1f}, {final_start.y():.1f}, {final_end.x():.1f}, {final_end.y():.1f})")
        
        # Check if position changed
        position_changed = (initial_start != final_start or initial_end != final_end)
        has_manager = self.undo_redo_manager is not None
        has_scene = self.image_viewer.scene is not None
        print(f"[ANNOTATION DEBUG] ArrowAnnotationCoordinator._finalize_arrow_move: position_changed={position_changed}, has_manager={has_manager}, has_scene={has_scene}")
        
        # Only create command if position actually changed
        if position_changed and has_manager and has_scene:
            from utils.undo_redo import ArrowAnnotationMoveCommand
            print(f"[ANNOTATION DEBUG] ArrowAnnotationCoordinator._finalize_arrow_move: creating ArrowAnnotationMoveCommand")
            command = ArrowAnnotationMoveCommand(
                arrow_item,
                initial_start,
                initial_end,
                final_start,
                final_end,
                self.image_viewer.scene
            )
            print(f"[ANNOTATION DEBUG] ArrowAnnotationCoordinator._finalize_arrow_move: executing command, undo stack size before={len(self.undo_redo_manager.undo_stack)}")
            self.undo_redo_manager.execute_command(command)
            print(f"[ANNOTATION DEBUG] ArrowAnnotationCoordinator._finalize_arrow_move: command executed, undo stack size after={len(self.undo_redo_manager.undo_stack)}")
            # Update undo/redo state after command execution
            if self.update_undo_redo_state_callback:
                self.update_undo_redo_state_callback()
        else:
            print(f"[ANNOTATION DEBUG] ArrowAnnotationCoordinator._finalize_arrow_move: NOT creating command (position_changed={position_changed}, has_manager={has_manager}, has_scene={has_scene})")
        
        # Remove from tracking (so next drag starts fresh)
        if arrow_item in self._arrow_move_tracking:
            del self._arrow_move_tracking[arrow_item]
        
        # Clear pre_drag positions
        if hasattr(arrow_item, '_pre_drag_start_point'):
            delattr(arrow_item, '_pre_drag_start_point')
        if hasattr(arrow_item, '_pre_drag_end_point'):
            delattr(arrow_item, '_pre_drag_end_point')
            print(f"[ANNOTATION DEBUG] ArrowAnnotationCoordinator._finalize_arrow_move: removed from tracking")
    
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
