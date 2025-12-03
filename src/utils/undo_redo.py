"""
Undo/Redo System

This module implements an undo/redo system using the command pattern
for ROI, measurement, and crosshair changes.

Inputs:
    - Commands to execute
    - Undo/redo requests
    
Outputs:
    - Command execution
    - State restoration
    
Requirements:
    - Standard library only
    - PySide6.QtCore.QPointF for position tracking
"""

from typing import List, Optional, Callable, Any, Tuple
from abc import ABC, abstractmethod


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
            return False
        
        command = self.undo_stack.pop()
        command.undo()
        self.redo_stack.append(command)
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

