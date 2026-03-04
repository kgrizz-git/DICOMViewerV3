"""
Undo/Redo System

This module implements an undo/redo system using the command pattern
for ROI, measurement, crosshair changes, and DICOM tag edits.

Inputs:
    - Commands to execute
    - Undo/redo requests
    
Outputs:
    - Command execution
    - State restoration
    
Requirements:
    - Standard library only
    - PySide6.QtCore.QPointF for position tracking
    - pydicom for DICOM tag operations
"""

from typing import List, Optional, Callable, Any, Tuple, Union
from abc import ABC, abstractmethod

from utils.debug_log import debug_log, annotation_debug


class Command(ABC):
    """
    Abstract base class for commands.
    """
    
    @abstractmethod
    def execute(self) -> None:
        """Execute the command."""
        pass
    
    @abstractmethod
    def undo(self) -> None:
        """Undo the command."""
        pass


class UndoRedoManager:
    """
    Manages undo/redo operations.
    
    Features:
    - Execute commands
    - Undo/redo operations
    - Command history management
    """
    
    def __init__(self, max_history: int = 100):
        """
        Initialize the undo/redo manager.
        
        Args:
            max_history: Maximum number of commands to keep in history
        """
        self.undo_stack: List[Command] = []
        self.redo_stack: List[Command] = []
        self.max_history = max_history
    
    def execute_command(self, command: Command) -> None:
        """
        Execute a command and add it to undo stack.
        
        Args:
            command: Command to execute
        """
        command.execute()
        self.undo_stack.append(command)
        
        # Clear redo stack when new command is executed
        self.redo_stack.clear()
        
        # Limit history size
        if len(self.undo_stack) > self.max_history:
            self.undo_stack.pop(0)
    
    def undo(self) -> bool:
        """
        Undo the last command.
        
        Returns:
            True if undo was successful, False if no commands to undo
        """
        if not self.undo_stack:
            annotation_debug(f" UndoRedoManager.undo: no commands to undo")
            return False
        
        command = self.undo_stack.pop()
        command_type = type(command).__name__
        log_data = {"command_type": command_type, "undo_stack_size_before": len(self.undo_stack) + 1, "undo_stack_size_after": len(self.undo_stack)}
        if hasattr(command, 'action'):
            log_data["command_action"] = command.action
        if hasattr(command, 'arrow_item'):
            log_data["arrow_item_id"] = str(id(command.arrow_item))
        debug_log("undo_redo.py:90", "UndoRedoManager.undo: command being undone", log_data, hypothesis_id="D")

        annotation_debug(f" UndoRedoManager.undo: undoing command type={command_type}, undo stack size before={len(self.undo_stack) + 1}, after={len(self.undo_stack)}")
        
        # Log command details if it's an annotation command
        if hasattr(command, 'action'):
            annotation_debug(f" UndoRedoManager.undo: command action={command.action}")
        if hasattr(command, 'arrow_item'):
            annotation_debug(f" UndoRedoManager.undo: ArrowAnnotationMoveCommand, arrow_item={command.arrow_item}")
        
        command.undo()
        self.redo_stack.append(command)
        annotation_debug(f" UndoRedoManager.undo: undo completed, redo stack size={len(self.redo_stack)}")
        return True
    
    def redo(self) -> bool:
        """
        Redo the last undone command.
        
        Returns:
            True if redo was successful, False if no commands to redo
        """
        if not self.redo_stack:
            return False
        
        command = self.redo_stack.pop()
        command.execute()
        self.undo_stack.append(command)
        return True
    
    def can_undo(self) -> bool:
        """
        Check if undo is possible.
        
        Returns:
            True if undo is possible
        """
        return len(self.undo_stack) > 0
    
    def can_redo(self) -> bool:
        """
        Check if redo is possible.
        
        Returns:
            True if redo is possible
        """
        return len(self.redo_stack) > 0
    
    def clear(self) -> None:
        """Clear all command history."""
        self.undo_stack.clear()
        self.redo_stack.clear()


class ROICommand(Command):
    """
    Command for ROI operations (add, remove).
    Uses composite key: (study_uid, series_uid, instance_identifier)
    """
    
    def __init__(self, roi_manager, action: str, roi_item, scene, 
                 study_uid: str, series_uid: str, instance_identifier: int,
                 update_statistics_callback: Optional[Callable[[], None]] = None):
        """
        Initialize ROI command.
        
        Args:
            roi_manager: ROIManager instance
            action: "add" or "remove"
            roi_item: ROI item
            scene: QGraphicsScene
            study_uid: StudyInstanceUID
            series_uid: SeriesInstanceUID
            instance_identifier: InstanceNumber or slice_index
            update_statistics_callback: Optional callback to trigger statistics overlay update
        """
        self.roi_manager = roi_manager
        self.action = action
        self.roi_item = roi_item
        self.scene = scene
        self.key = (study_uid, series_uid, instance_identifier)
        self.update_statistics_callback = update_statistics_callback
    
    def execute(self) -> None:
        """Execute the command."""
        if self.scene is None:
            return
            
        if self.action == "add":
            # Add ROI
            if self.key not in self.roi_manager.rois:
                self.roi_manager.rois[self.key] = []
            if self.roi_item not in self.roi_manager.rois[self.key]:
                self.roi_manager.rois[self.key].append(self.roi_item)
                if self.roi_item.item.scene() != self.scene:
                    self.scene.addItem(self.roi_item.item)
                # Restore statistics overlay if it was visible (for redo)
                if self.update_statistics_callback:
                    self.update_statistics_callback()
        elif self.action == "remove":
            # Remove ROI
            if self.key in self.roi_manager.rois:
                if self.roi_item in self.roi_manager.rois[self.key]:
                    self.roi_manager.rois[self.key].remove(self.roi_item)
                    if self.roi_item.item.scene() == self.scene:
                        # Remove statistics overlay if present
                        if (hasattr(self.roi_item, 'statistics_overlay_item') and 
                            self.roi_item.statistics_overlay_item is not None):
                            self.roi_manager.remove_statistics_overlay(self.roi_item, self.scene)
                        self.scene.removeItem(self.roi_item.item)
    
    def undo(self) -> None:
        """Undo the command."""
        if self.scene is None:
            return
            
        if self.action == "add":
            # Undo add = remove
            if self.key in self.roi_manager.rois:
                if self.roi_item in self.roi_manager.rois[self.key]:
                    self.roi_manager.rois[self.key].remove(self.roi_item)
                    if self.roi_item.item.scene() == self.scene:
                        # Remove statistics overlay if present
                        if (hasattr(self.roi_item, 'statistics_overlay_item') and 
                            self.roi_item.statistics_overlay_item is not None):
                            self.roi_manager.remove_statistics_overlay(self.roi_item, self.scene)
                        self.scene.removeItem(self.roi_item.item)
        elif self.action == "remove":
            # Undo remove = add
            if self.key not in self.roi_manager.rois:
                self.roi_manager.rois[self.key] = []
            if self.roi_item not in self.roi_manager.rois[self.key]:
                self.roi_manager.rois[self.key].append(self.roi_item)
                if self.roi_item.item.scene() != self.scene:
                    self.scene.addItem(self.roi_item.item)
                # Restore statistics overlay if it was visible
                if (hasattr(self.roi_item, 'statistics_overlay_visible') and 
                    self.roi_item.statistics_overlay_visible and
                    hasattr(self.roi_item, 'statistics_overlay_item') and 
                    self.roi_item.statistics_overlay_item is not None):
                    overlay_item = self.roi_item.statistics_overlay_item
                    if overlay_item.scene() != self.scene:
                        self.scene.addItem(overlay_item)
                    overlay_item.setVisible(True)
                # Trigger statistics overlay update to recalculate and refresh text
                if self.update_statistics_callback:
                    self.update_statistics_callback()


class ROIMoveCommand(Command):
    """
    Command for ROI movement operations.
    """
    
    def __init__(self, roi_item, old_position: 'QPointF', new_position: 'QPointF', scene):
        """
        Initialize ROI move command.
        
        Args:
            roi_item: ROI item to move
            old_position: Original position (QPointF)
            new_position: New position (QPointF)
            scene: QGraphicsScene
        """
        self.roi_item = roi_item
        self.old_position = old_position
        self.new_position = new_position
        self.scene = scene
    
    def execute(self) -> None:
        """Execute the command - move to new position."""
        if self.roi_item is None or self.scene is None:
            return
        if self.roi_item.item.scene() == self.scene:
            self.roi_item.item.setPos(self.new_position)
    
    def undo(self) -> None:
        """Undo the command - move back to old position."""
        if self.roi_item is None or self.scene is None:
            return
        if self.roi_item.item.scene() == self.scene:
            self.roi_item.item.setPos(self.old_position)


class MeasurementCommand(Command):
    """
    Command for measurement operations (add, remove).
    Uses composite key: (study_uid, series_uid, instance_identifier)
    """
    
    def __init__(self, measurement_tool, action: str, measurement_item, scene,
                 study_uid: str, series_uid: str, instance_identifier: int):
        """
        Initialize measurement command.
        
        Args:
            measurement_tool: MeasurementTool instance
            action: "add" or "remove"
            measurement_item: MeasurementItem
            scene: QGraphicsScene
            study_uid: StudyInstanceUID
            series_uid: SeriesInstanceUID
            instance_identifier: InstanceNumber or slice_index
        """
        self.measurement_tool = measurement_tool
        self.action = action
        self.measurement_item = measurement_item
        self.scene = scene
        self.key = (study_uid, series_uid, instance_identifier)
    
    def execute(self) -> None:
        """Execute the command."""
        if self.scene is None:
            return
            
        if self.action == "add":
            # Add measurement
            if self.key not in self.measurement_tool.measurements:
                self.measurement_tool.measurements[self.key] = []
            if self.measurement_item not in self.measurement_tool.measurements[self.key]:
                self.measurement_tool.measurements[self.key].append(self.measurement_item)
                if self.measurement_item.scene() != self.scene:
                    self.scene.addItem(self.measurement_item)
                # Add text item if it exists
                if hasattr(self.measurement_item, 'text_item') and self.measurement_item.text_item is not None:
                    if self.measurement_item.text_item.scene() != self.scene:
                        self.scene.addItem(self.measurement_item.text_item)
        elif self.action == "remove":
            # Remove measurement
            if self.key in self.measurement_tool.measurements:
                if self.measurement_item in self.measurement_tool.measurements[self.key]:
                    self.measurement_tool.measurements[self.key].remove(self.measurement_item)
                    if self.measurement_item.scene() == self.scene:
                        # Remove text item first
                        if hasattr(self.measurement_item, 'text_item') and self.measurement_item.text_item is not None:
                            if self.measurement_item.text_item.scene() == self.scene:
                                self.scene.removeItem(self.measurement_item.text_item)
                        # Remove handles
                        if hasattr(self.measurement_item, 'hide_handles'):
                            self.measurement_item.hide_handles()
                        self.scene.removeItem(self.measurement_item)
    
    def undo(self) -> None:
        """Undo the command."""
        if self.scene is None:
            return
            
        if self.action == "add":
            # Undo add = remove
            if self.key in self.measurement_tool.measurements:
                if self.measurement_item in self.measurement_tool.measurements[self.key]:
                    self.measurement_tool.measurements[self.key].remove(self.measurement_item)
                    if self.measurement_item.scene() == self.scene:
                        if hasattr(self.measurement_item, 'text_item') and self.measurement_item.text_item is not None:
                            if self.measurement_item.text_item.scene() == self.scene:
                                self.scene.removeItem(self.measurement_item.text_item)
                        if hasattr(self.measurement_item, 'hide_handles'):
                            self.measurement_item.hide_handles()
                        self.scene.removeItem(self.measurement_item)
        elif self.action == "remove":
            # Undo remove = add
            if self.key not in self.measurement_tool.measurements:
                self.measurement_tool.measurements[self.key] = []
            if self.measurement_item not in self.measurement_tool.measurements[self.key]:
                self.measurement_tool.measurements[self.key].append(self.measurement_item)
                if self.measurement_item.scene() != self.scene:
                    self.scene.addItem(self.measurement_item)
                if hasattr(self.measurement_item, 'text_item') and self.measurement_item.text_item is not None:
                    if self.measurement_item.text_item.scene() != self.scene:
                        self.scene.addItem(self.measurement_item.text_item)
                    # Ensure text is visible and positioned correctly
                    self.measurement_item.text_item.setVisible(True)
                    # Update distance to refresh text position and content
                    if hasattr(self.measurement_item, 'update_distance'):
                        self.measurement_item.update_distance()


class TextAnnotationCommand(Command):
    """
    Command for text annotation operations (add, remove).
    Uses composite key: (study_uid, series_uid, instance_identifier)
    """
    
    def __init__(self, text_annotation_tool, action: str, annotation_item, scene,
                 study_uid: str, series_uid: str, instance_identifier: int):
        """
        Initialize text annotation command.
        
        Args:
            text_annotation_tool: TextAnnotationTool instance
            action: "add" or "remove"
            annotation_item: TextAnnotationItem
            scene: QGraphicsScene
            study_uid: StudyInstanceUID
            series_uid: SeriesInstanceUID
            instance_identifier: InstanceNumber or slice_index
        """
        self.text_annotation_tool = text_annotation_tool
        self.action = action
        self.annotation_item = annotation_item
        self.scene = scene
        self.key = (study_uid, series_uid, instance_identifier)
    
    def execute(self) -> None:
        """Execute the command."""
        if self.scene is None:
            return
        
        annotation_debug(f" TextAnnotationCommand.execute: action={self.action}, key={self.key}")
            
        if self.action == "add":
            # Add annotation
            if self.key not in self.text_annotation_tool.annotations:
                self.text_annotation_tool.annotations[self.key] = []
            if self.annotation_item not in self.text_annotation_tool.annotations[self.key]:
                self.text_annotation_tool.annotations[self.key].append(self.annotation_item)
                # Ensure item state is correct (no callback, not new annotation)
                self.annotation_item.on_editing_finished = None
                self.annotation_item._is_new_annotation = False
                if self.annotation_item.scene() != self.scene:
                    self.scene.addItem(self.annotation_item)
        elif self.action == "remove":
            # Remove annotation
            if self.key in self.text_annotation_tool.annotations:
                if self.annotation_item in self.text_annotation_tool.annotations[self.key]:
                    self.text_annotation_tool.annotations[self.key].remove(self.annotation_item)
                    if self.annotation_item.scene() == self.scene:
                        self.scene.removeItem(self.annotation_item)
    
    def undo(self) -> None:
        """Undo the command."""
        if self.scene is None:
            return
        
        callback_exists = self.annotation_item.on_editing_finished is not None
        is_new = getattr(self.annotation_item, '_is_new_annotation', False)
        annotation_debug(f" TextAnnotationCommand.undo: action={self.action}, key={self.key}, item state: callback={'exists' if callback_exists else 'None'}, _is_new_annotation={is_new}")
            
        if self.action == "add":
            # Undo add = remove
            if self.key in self.text_annotation_tool.annotations:
                if self.annotation_item in self.text_annotation_tool.annotations[self.key]:
                    self.text_annotation_tool.annotations[self.key].remove(self.annotation_item)
                    if self.annotation_item.scene() == self.scene:
                        self.scene.removeItem(self.annotation_item)
        elif self.action == "remove":
            # Undo remove = add
            if self.key not in self.text_annotation_tool.annotations:
                self.text_annotation_tool.annotations[self.key] = []
            if self.annotation_item not in self.text_annotation_tool.annotations[self.key]:
                self.text_annotation_tool.annotations[self.key].append(self.annotation_item)
                # Ensure item state is correct (no callback, not new annotation)
                self.annotation_item.on_editing_finished = None
                self.annotation_item._is_new_annotation = False
                if self.annotation_item.scene() != self.scene:
                    self.scene.addItem(self.annotation_item)


class ArrowAnnotationCommand(Command):
    """
    Command for arrow annotation operations (add, remove).
    Uses composite key: (study_uid, series_uid, instance_identifier)
    """
    
    def __init__(self, arrow_annotation_tool, action: str, arrow_item, scene,
                 study_uid: str, series_uid: str, instance_identifier: int):
        """
        Initialize arrow annotation command.
        
        Args:
            arrow_annotation_tool: ArrowAnnotationTool instance
            action: "add" or "remove"
            arrow_item: ArrowAnnotationItem
            scene: QGraphicsScene
            study_uid: StudyInstanceUID
            series_uid: SeriesInstanceUID
            instance_identifier: InstanceNumber or slice_index
        """
        self.arrow_annotation_tool = arrow_annotation_tool
        self.action = action
        self.arrow_item = arrow_item
        self.scene = scene
        self.key = (study_uid, series_uid, instance_identifier)
    
    def execute(self) -> None:
        """Execute the command."""
        if self.scene is None:
            return
            
        if self.action == "add":
            # Add arrow
            if self.key not in self.arrow_annotation_tool.arrows:
                self.arrow_annotation_tool.arrows[self.key] = []
            if self.arrow_item not in self.arrow_annotation_tool.arrows[self.key]:
                self.arrow_annotation_tool.arrows[self.key].append(self.arrow_item)
                if self.arrow_item.scene() != self.scene:
                    self.scene.addItem(self.arrow_item)
        elif self.action == "remove":
            # Remove arrow
            if self.key in self.arrow_annotation_tool.arrows:
                if self.arrow_item in self.arrow_annotation_tool.arrows[self.key]:
                    self.arrow_annotation_tool.arrows[self.key].remove(self.arrow_item)
                    if self.arrow_item.scene() == self.scene:
                        self.scene.removeItem(self.arrow_item)
    
    def undo(self) -> None:
        """Undo the command."""
        if self.scene is None:
            return
            
        if self.action == "add":
            # Undo add = remove
            if self.key in self.arrow_annotation_tool.arrows:
                if self.arrow_item in self.arrow_annotation_tool.arrows[self.key]:
                    self.arrow_annotation_tool.arrows[self.key].remove(self.arrow_item)
                    if self.arrow_item.scene() == self.scene:
                        self.scene.removeItem(self.arrow_item)
        elif self.action == "remove":
            # Undo remove = add
            if self.key not in self.arrow_annotation_tool.arrows:
                self.arrow_annotation_tool.arrows[self.key] = []
            if self.arrow_item not in self.arrow_annotation_tool.arrows[self.key]:
                self.arrow_annotation_tool.arrows[self.key].append(self.arrow_item)
                if self.arrow_item.scene() != self.scene:
                    self.scene.addItem(self.arrow_item)


class TextAnnotationEditCommand(Command):
    """
    Command for text annotation text content edits (not creation/deletion).
    """
    
    def __init__(self, text_annotation_item, old_text: str, new_text: str):
        """
        Initialize text annotation edit command.
        
        Args:
            text_annotation_item: TextAnnotationItem to edit
            old_text: Original text content
            new_text: New text content
        """
        self.text_annotation_item = text_annotation_item
        self.old_text = old_text
        self.new_text = new_text
    
    def execute(self) -> None:
        """Execute the command - set to new text."""
        if self.text_annotation_item is None:
            return
        debug_log("undo_redo.py:TextAnnotationEditCommand.execute", "Setting text annotation to new text", {"item_id": str(id(self.text_annotation_item)), "old_text": self.old_text, "new_text": self.new_text}, hypothesis_id="D")
        self.text_annotation_item.setPlainText(self.new_text)
    
    def undo(self) -> None:
        """Undo the command - restore old text."""
        if self.text_annotation_item is None:
            return
        debug_log("undo_redo.py:TextAnnotationEditCommand.undo", "Restoring text annotation to old text", {"item_id": str(id(self.text_annotation_item)), "old_text": self.old_text, "new_text": self.new_text}, hypothesis_id="D")
        self.text_annotation_item.setPlainText(self.old_text)


class TextAnnotationMoveCommand(Command):
    """
    Command for text annotation movement operations.
    """
    
    def __init__(self, text_annotation_item, old_position: 'QPointF', new_position: 'QPointF', scene):
        """
        Initialize text annotation move command.
        
        Args:
            text_annotation_item: TextAnnotationItem to move
            old_position: Original position (QPointF)
            new_position: New position (QPointF)
            scene: QGraphicsScene
        """
        self.text_annotation_item = text_annotation_item
        self.old_position = old_position
        self.new_position = new_position
        self.scene = scene
    
    def execute(self) -> None:
        """Execute the command - move to new position."""
        if self.text_annotation_item is None or self.scene is None:
            return
        if self.text_annotation_item.scene() == self.scene:
            debug_log("undo_redo.py:TextAnnotationMoveCommand.execute", "Moving text annotation to new position", {"item_id": str(id(self.text_annotation_item)), "old_pos": str(self.old_position), "new_pos": str(self.new_position)}, hypothesis_id="C")
            self.text_annotation_item.setPos(self.new_position)
    
    def undo(self) -> None:
        """Undo the command - restore old position."""
        if self.text_annotation_item is None or self.scene is None:
            return
        if self.text_annotation_item.scene() == self.scene:
            debug_log("undo_redo.py:TextAnnotationMoveCommand.undo", "Restoring text annotation to old position", {"item_id": str(id(self.text_annotation_item)), "old_pos": str(self.old_position), "new_pos": str(self.new_position)}, hypothesis_id="C")
            self.text_annotation_item.setPos(self.old_position)


class ArrowAnnotationMoveCommand(Command):
    """
    Command for arrow annotation movement operations.
    Tracks both start_point and end_point changes.
    """
    
    def __init__(self, arrow_item, old_start_point: 'QPointF', old_end_point: 'QPointF',
                 new_start_point: 'QPointF', new_end_point: 'QPointF', scene):
        """
        Initialize arrow annotation move command.
        
        Args:
            arrow_item: ArrowAnnotationItem to move
            old_start_point: Original start point (QPointF)
            old_end_point: Original end point (QPointF)
            new_start_point: New start point (QPointF)
            new_end_point: New end point (QPointF)
            scene: QGraphicsScene
        """
        self.arrow_item = arrow_item
        self.old_start_point = old_start_point
        self.old_end_point = old_end_point
        self.new_start_point = new_start_point
        self.new_end_point = new_end_point
        self.scene = scene
    
    def execute(self) -> None:
        """Execute the command - move to new positions."""
        if self.arrow_item is None or self.scene is None:
            return
        
        # Debug: log execute operation
        callback_state = self.arrow_item.on_moved_callback is not None
        annotation_debug(f" ArrowAnnotationMoveCommand.execute: moving to new positions, callback={'exists' if callback_state else 'None'}")
        
        if self.arrow_item.scene() == self.scene:
            # Save and temporarily clear callback to prevent recursive updates
            saved_callback = self.arrow_item.on_moved_callback
            self.arrow_item.on_moved_callback = None
            
            # Set flag to prevent recursive updates BEFORE any position changes
            self.arrow_item._updating_position = True
            
            # Update arrow points and position
            # Use update_endpoints which handles both position and line/arrowhead correctly
            self.arrow_item.update_endpoints(self.new_start_point, self.new_end_point)
            
            # Clear flag AFTER all position changes
            self.arrow_item._updating_position = False
            
            # Restore callback AFTER flag is cleared
            self.arrow_item.on_moved_callback = saved_callback
    
    def undo(self) -> None:
        """Undo the command - restore old positions."""
        annotation_debug(f" ArrowAnnotationMoveCommand.undo: called, arrow_item={'exists' if self.arrow_item is not None else 'None'}, scene={'exists' if self.scene is not None else 'None'}")
        
        if self.arrow_item is None or self.scene is None:
            annotation_debug(f" ArrowAnnotationMoveCommand.undo: early return (arrow_item or scene is None)")
            return
        
        # Debug: log undo operation
        callback_state = self.arrow_item.on_moved_callback is not None
        updating_state = getattr(self.arrow_item, '_updating_position', False)
        annotation_debug(f" ArrowAnnotationMoveCommand.undo: restoring positions from ({self.new_start_point.x():.1f}, {self.new_start_point.y():.1f}, {self.new_end_point.x():.1f}, {self.new_end_point.y():.1f}) to ({self.old_start_point.x():.1f}, {self.old_start_point.y():.1f}, {self.old_end_point.x():.1f}, {self.old_end_point.y():.1f})")
        annotation_debug(f" ArrowAnnotationMoveCommand.undo: initial state - callback={'exists' if callback_state else 'None'}, _updating_position={updating_state}")
        
        if self.arrow_item.scene() == self.scene:
            # Save and temporarily clear callback to prevent recursive updates
            saved_callback = self.arrow_item.on_moved_callback
            annotation_debug(f" ArrowAnnotationMoveCommand.undo: saved callback={'exists' if saved_callback is not None else 'None'}, clearing it")
            self.arrow_item.on_moved_callback = None
            
            # Set flag to prevent recursive updates BEFORE any position changes
            self.arrow_item._updating_position = True
            annotation_debug(f" ArrowAnnotationMoveCommand.undo: set _updating_position=True")
            
            # Restore arrow points and position using update_endpoints
            # This handles both position and line/arrowhead correctly
            self.arrow_item.update_endpoints(self.old_start_point, self.old_end_point)
            annotation_debug(f" ArrowAnnotationMoveCommand.undo: restored positions using update_endpoints")
            
            # Clear flag AFTER all position changes
            self.arrow_item._updating_position = False
            annotation_debug(f" ArrowAnnotationMoveCommand.undo: cleared _updating_position flag")
            
            # Restore callback AFTER flag is cleared
            self.arrow_item.on_moved_callback = saved_callback
            annotation_debug(f" ArrowAnnotationMoveCommand.undo: restored callback={'exists' if saved_callback is not None else 'None'}")
        else:
            annotation_debug(f" ArrowAnnotationMoveCommand.undo: arrow_item not in scene, skipping")


class MeasurementMoveCommand(Command):
    """
    Command for measurement movement operations.
    Tracks both start_point and end_point changes.
    """
    
    def __init__(self, measurement_item, old_start_point: 'QPointF', old_end_point: 'QPointF',
                 new_start_point: 'QPointF', new_end_point: 'QPointF', scene):
        """
        Initialize measurement move command.
        
        Args:
            measurement_item: MeasurementItem to move
            old_start_point: Original start point (QPointF)
            old_end_point: Original end point (QPointF)
            new_start_point: New start point (QPointF)
            new_end_point: New end point (QPointF)
            scene: QGraphicsScene
        """
        self.measurement_item = measurement_item
        self.old_start_point = old_start_point
        self.old_end_point = old_end_point
        self.new_start_point = new_start_point
        self.new_end_point = new_end_point
        self.scene = scene
    
    def execute(self) -> None:
        """Execute the command - move to new positions."""
        if self.measurement_item is None or self.scene is None:
            return
        if self.measurement_item.scene() == self.scene:
            # Update measurement points
            self.measurement_item.start_point = self.new_start_point
            self.measurement_item.end_point = self.new_end_point
            self.measurement_item.end_relative = self.new_end_point - self.new_start_point
            # Move group to new start point
            self.measurement_item.setPos(self.new_start_point)
            # Update line and text
            if hasattr(self.measurement_item, 'line_item'):
                self.measurement_item.line_item.prepareGeometryChange()
            # Update distance to recalculate line, text, and handle positions
            if hasattr(self.measurement_item, 'update_distance'):
                self.measurement_item.update_distance()
    
    def undo(self) -> None:
        """Undo the command - restore old positions."""
        if self.measurement_item is None or self.scene is None:
            return
        if self.measurement_item.scene() == self.scene:
            # Restore measurement points
            self.measurement_item.start_point = self.old_start_point
            self.measurement_item.end_point = self.old_end_point
            self.measurement_item.end_relative = self.old_end_point - self.old_start_point
            # Move group back to old start point
            self.measurement_item.setPos(self.old_start_point)
            # Update line and text
            if hasattr(self.measurement_item, 'line_item'):
                self.measurement_item.line_item.prepareGeometryChange()
            # Update distance to recalculate line, text, and handle positions
            if hasattr(self.measurement_item, 'update_distance'):
                self.measurement_item.update_distance()


class CrosshairCommand(Command):
    """
    Command for crosshair operations (add, remove).
    Uses composite key: (study_uid, series_uid, instance_identifier)
    """
    
    def __init__(self, crosshair_manager, action: str, crosshair_item, scene,
                 study_uid: str, series_uid: str, instance_identifier: int):
        """
        Initialize crosshair command.
        
        Args:
            crosshair_manager: CrosshairManager instance
            action: "add" or "remove"
            crosshair_item: CrosshairItem
            scene: QGraphicsScene
            study_uid: StudyInstanceUID
            series_uid: SeriesInstanceUID
            instance_identifier: InstanceNumber or slice_index
        """
        self.crosshair_manager = crosshair_manager
        self.action = action
        self.crosshair_item = crosshair_item
        self.scene = scene
        self.key = (study_uid, series_uid, instance_identifier)
    
    def execute(self) -> None:
        """Execute the command."""
        if self.scene is None:
            return
            
        if self.action == "add":
            # Add crosshair
            if self.key not in self.crosshair_manager.crosshairs:
                self.crosshair_manager.crosshairs[self.key] = []
            if self.crosshair_item not in self.crosshair_manager.crosshairs[self.key]:
                self.crosshair_manager.crosshairs[self.key].append(self.crosshair_item)
                if self.crosshair_item.scene() != self.scene:
                    self.scene.addItem(self.crosshair_item)
                # Add text item if it exists
                if hasattr(self.crosshair_item, 'text_item') and self.crosshair_item.text_item is not None:
                    if self.crosshair_item.text_item.scene() != self.scene:
                        self.scene.addItem(self.crosshair_item.text_item)
        elif self.action == "remove":
            # Remove crosshair
            if self.key in self.crosshair_manager.crosshairs:
                if self.crosshair_item in self.crosshair_manager.crosshairs[self.key]:
                    self.crosshair_manager.crosshairs[self.key].remove(self.crosshair_item)
                    if self.crosshair_item.scene() == self.scene:
                        # Remove text item first
                        if hasattr(self.crosshair_item, 'text_item') and self.crosshair_item.text_item is not None:
                            if self.crosshair_item.text_item.scene() == self.scene:
                                if hasattr(self.crosshair_item.text_item, 'mark_deleted'):
                                    self.crosshair_item.text_item.mark_deleted()
                                self.scene.removeItem(self.crosshair_item.text_item)
                        self.scene.removeItem(self.crosshair_item)
    
    def undo(self) -> None:
        """Undo the command."""
        if self.scene is None:
            return
            
        if self.action == "add":
            # Undo add = remove
            if self.key in self.crosshair_manager.crosshairs:
                if self.crosshair_item in self.crosshair_manager.crosshairs[self.key]:
                    self.crosshair_manager.crosshairs[self.key].remove(self.crosshair_item)
                    if self.crosshair_item.scene() == self.scene:
                        if hasattr(self.crosshair_item, 'text_item') and self.crosshair_item.text_item is not None:
                            if self.crosshair_item.text_item.scene() == self.scene:
                                if hasattr(self.crosshair_item.text_item, 'mark_deleted'):
                                    self.crosshair_item.text_item.mark_deleted()
                                self.scene.removeItem(self.crosshair_item.text_item)
                        self.scene.removeItem(self.crosshair_item)
        elif self.action == "remove":
            # Undo remove = add
            if self.key not in self.crosshair_manager.crosshairs:
                self.crosshair_manager.crosshairs[self.key] = []
            if self.crosshair_item not in self.crosshair_manager.crosshairs[self.key]:
                self.crosshair_manager.crosshairs[self.key].append(self.crosshair_item)
                if self.crosshair_item.scene() != self.scene:
                    self.scene.addItem(self.crosshair_item)
                # Restore text item if it exists
                if (hasattr(self.crosshair_item, 'text_item') and 
                    self.crosshair_item.text_item is not None):
                    if self.crosshair_item.text_item.scene() != self.scene:
                        self.scene.addItem(self.crosshair_item.text_item)
                    # Ensure text is visible
                    self.crosshair_item.text_item.setVisible(True)
                if hasattr(self.crosshair_item, 'text_item') and self.crosshair_item.text_item is not None:
                    if self.crosshair_item.text_item.scene() != self.scene:
                        self.scene.addItem(self.crosshair_item.text_item)


class CrosshairMoveCommand(Command):
    """
    Command for crosshair movement operations.
    """
    
    def __init__(self, crosshair_item, old_position: 'QPointF', new_position: 'QPointF', scene):
        """
        Initialize crosshair move command.
        
        Args:
            crosshair_item: CrosshairItem to move
            old_position: Original position (QPointF)
            new_position: New position (QPointF)
            scene: QGraphicsScene
        """
        self.crosshair_item = crosshair_item
        self.old_position = old_position
        self.new_position = new_position
        self.scene = scene
    
    def execute(self) -> None:
        """Execute the command - move to new position."""
        if self.crosshair_item is None or self.scene is None:
            return
        if self.crosshair_item.scene() == self.scene:
            self.crosshair_item.setPos(self.new_position)
            self.crosshair_item.position = self.new_position
            # Update text position if view is available
            if self.scene.views():
                view = self.scene.views()[0]
                if hasattr(self.crosshair_item, 'update_text_position'):
                    self.crosshair_item.update_text_position(view)
    
    def undo(self) -> None:
        """Undo the command - move back to old position."""
        if self.crosshair_item is None or self.scene is None:
            return
        if self.crosshair_item.scene() == self.scene:
            self.crosshair_item.setPos(self.old_position)
            self.crosshair_item.position = self.old_position
            # Update text position if view is available
            if self.scene.views():
                view = self.scene.views()[0]
                if hasattr(self.crosshair_item, 'update_text_position'):
                    self.crosshair_item.update_text_position(view)


class CompositeCommand(Command):
    """
    Command that executes multiple commands as a single operation.
    Useful for batch operations like "delete all" or "clear all".
    """
    
    def __init__(self, commands: List[Command]):
        """
        Initialize composite command.
        
        Args:
            commands: List of commands to execute together
        """
        self.commands = commands
    
    def execute(self) -> None:
        """Execute all commands in order."""
        for command in self.commands:
            command.execute()
    
    def undo(self) -> None:
        """Undo all commands in reverse order."""
        for command in reversed(self.commands):
            command.undo()


class TagEditCommand(Command):
    """
    Command for DICOM tag edit operations.
    Integrates tag edits into the unified undo/redo system.
    """
    
    def __init__(self, dataset, tag, old_value: Any, new_value: Any, vr: Optional[str] = None,
                 tag_edit_history_manager=None, ui_refresh_callback: Optional[Callable[[], None]] = None):
        """
        Initialize tag edit command.
        
        Args:
            dataset: DICOM dataset to edit
            tag: pydicom Tag object or tag tuple
            old_value: Original value (None if tag didn't exist)
            new_value: New value to set
            vr: Value Representation (optional)
            tag_edit_history_manager: TagEditHistoryManager for tracking edited tags
            ui_refresh_callback: Optional callback to refresh UI after edit
        """
        self.dataset = dataset
        self.tag = tag
        self.old_value = old_value
        self.new_value = new_value
        self.vr = vr
        self.tag_edit_history_manager = tag_edit_history_manager
        self.ui_refresh_callback = ui_refresh_callback
    
    def get_target_dataset(self):
        """Get the target dataset for editing (handles wrapped datasets)."""
        if hasattr(self.dataset, '_original_dataset'):
            return self.dataset._original_dataset
        return self.dataset
    
    def get_tag_string(self) -> str:
        """Get tag as string for tracking."""
        if self.tag is None:
            return ""
        # Convert tag to string format "(GGGG,EEEE)"
        try:
            from pydicom.tag import Tag as PydicomTag
            tag_obj = PydicomTag(self.tag) if not isinstance(self.tag, PydicomTag) else self.tag
            return f"({tag_obj.group:04X},{tag_obj.element:04X})"
        except:
            return str(self.tag)
    
    def execute(self) -> None:
        """Execute the command - set new value."""
        if self.tag is None:
            return
        
        target_dataset = self.get_target_dataset()
        
        try:
            # Store original value if this is the first edit
            if self.tag_edit_history_manager:
                tag_str = self.get_tag_string()
                if self.tag_edit_history_manager.get_original_value(self.dataset, tag_str) is None:
                    # First time editing this tag, store the old value as original
                    self.tag_edit_history_manager.store_original_value(self.dataset, tag_str, self.old_value)
            
            if self.new_value is None:
                # Delete the tag
                if self.tag in target_dataset:
                    del target_dataset[self.tag]
                if hasattr(self.dataset, '_original_dataset') and self.dataset is not target_dataset:
                    if self.tag in self.dataset:
                        del self.dataset[self.tag]
            else:
                # Set new value
                if self.tag in target_dataset:
                    target_dataset[self.tag].value = self.new_value
                else:
                    # Create new tag
                    from pydicom.dataelem import DataElement
                    if self.vr is None:
                        try:
                            from pydicom.datadict import dictionary_VR
                            vr = dictionary_VR(self.tag)
                        except (KeyError, AttributeError):
                            vr = "LO"
                    else:
                        vr = self.vr
                    new_elem = DataElement(self.tag, vr, self.new_value)
                    target_dataset.add(new_elem)
                
                # Also update wrapper if applicable
                if hasattr(self.dataset, '_original_dataset') and self.dataset is not target_dataset:
                    if self.tag in self.dataset:
                        self.dataset[self.tag].value = self.new_value
                    else:
                        from pydicom.dataelem import DataElement
                        if self.vr is None:
                            try:
                                from pydicom.datadict import dictionary_VR
                                vr = dictionary_VR(self.tag)
                            except (KeyError, AttributeError):
                                vr = "LO"
                        else:
                            vr = self.vr
                        new_elem = DataElement(self.tag, vr, self.new_value)
                        self.dataset.add(new_elem)
            
            # Mark tag as edited (compares with original value)
            if self.tag_edit_history_manager:
                self.tag_edit_history_manager.mark_tag_edited(self.dataset, self.get_tag_string(), self.new_value)
            
            # Refresh UI
            if self.ui_refresh_callback:
                self.ui_refresh_callback()
                
        except Exception as e:
            print(f"Error executing tag edit command: {e}")
            raise
    
    def undo(self) -> None:
        """Undo the command - restore old value."""
        if self.tag is None:
            return
        
        target_dataset = self.get_target_dataset()
        
        try:
            if self.old_value is None:
                # Tag didn't exist before, delete it
                if self.tag in target_dataset:
                    del target_dataset[self.tag]
                if hasattr(self.dataset, '_original_dataset') and self.dataset is not target_dataset:
                    if self.tag in self.dataset:
                        del self.dataset[self.tag]
            else:
                # Restore old value
                if self.tag in target_dataset:
                    target_dataset[self.tag].value = self.old_value
                else:
                    # Recreate tag with old value
                    from pydicom.dataelem import DataElement
                    if self.vr is None:
                        try:
                            from pydicom.datadict import dictionary_VR
                            vr = dictionary_VR(self.tag)
                        except (KeyError, AttributeError):
                            vr = "LO"
                    else:
                        vr = self.vr
                    new_elem = DataElement(self.tag, vr, self.old_value)
                    target_dataset.add(new_elem)
                
                # Also update wrapper if applicable
                if hasattr(self.dataset, '_original_dataset') and self.dataset is not target_dataset:
                    if self.tag in self.dataset:
                        self.dataset[self.tag].value = self.old_value
                    else:
                        from pydicom.dataelem import DataElement
                        if self.vr is None:
                            try:
                                from pydicom.datadict import dictionary_VR
                                vr = dictionary_VR(self.tag)
                            except (KeyError, AttributeError):
                                vr = "LO"
                        else:
                            vr = self.vr
                        new_elem = DataElement(self.tag, vr, self.old_value)
                        self.dataset.add(new_elem)
            
            # Update edited tags tracking after undo (compares with original value)
            if self.tag_edit_history_manager:
                tag_str = self.get_tag_string()
                self.tag_edit_history_manager.mark_tag_edited(self.dataset, tag_str, self.old_value)
            
            # Refresh UI
            if self.ui_refresh_callback:
                self.ui_refresh_callback()
                
        except Exception as e:
            print(f"Error undoing tag edit command: {e}")
            raise

