"""
Undo/Redo System

This module implements an undo/redo system using the command pattern
for ROI and measurement changes.

Inputs:
    - Commands to execute
    - Undo/redo requests
    
Outputs:
    - Command execution
    - State restoration
    
Requirements:
    - Standard library only
"""

from typing import List, Optional, Callable, Any
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
    """
    
    def __init__(self, roi_manager, action: str, roi_item, scene, slice_index: int):
        """
        Initialize ROI command.
        
        Args:
            roi_manager: ROIManager instance
            action: "add" or "remove"
            roi_item: ROI item
            scene: QGraphicsScene
            slice_index: Slice index
        """
        self.roi_manager = roi_manager
        self.action = action
        self.roi_item = roi_item
        self.scene = scene
        self.slice_index = slice_index
    
    def execute(self) -> None:
        """Execute the command."""
        if self.action == "add":
            # Add ROI
            if self.slice_index not in self.roi_manager.rois:
                self.roi_manager.rois[self.slice_index] = []
            if self.roi_item not in self.roi_manager.rois[self.slice_index]:
                self.roi_manager.rois[self.slice_index].append(self.roi_item)
                self.scene.addItem(self.roi_item.item)
        elif self.action == "remove":
            # Remove ROI
            if self.slice_index in self.roi_manager.rois:
                if self.roi_item in self.roi_manager.rois[self.slice_index]:
                    self.roi_manager.rois[self.slice_index].remove(self.roi_item)
                    self.scene.removeItem(self.roi_item.item)
    
    def undo(self) -> None:
        """Undo the command."""
        if self.action == "add":
            # Undo add = remove
            if self.slice_index in self.roi_manager.rois:
                if self.roi_item in self.roi_manager.rois[self.slice_index]:
                    self.roi_manager.rois[self.slice_index].remove(self.roi_item)
                    self.scene.removeItem(self.roi_item.item)
        elif self.action == "remove":
            # Undo remove = add
            if self.slice_index not in self.roi_manager.rois:
                self.roi_manager.rois[self.slice_index] = []
            if self.roi_item not in self.roi_manager.rois[self.slice_index]:
                self.roi_manager.rois[self.slice_index].append(self.roi_item)
                self.scene.addItem(self.roi_item.item)

