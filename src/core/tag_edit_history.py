"""
DICOM Tag Edit History Manager

This module implements an undo/redo system for DICOM tag edits using
the command pattern.

Inputs:
    - Tag edit commands
    - Undo/redo requests
    
Outputs:
    - Command execution
    - State restoration
    
Requirements:
    - Standard library only
    - pydicom for dataset operations
"""

from typing import List, Optional, Any, Union, Tuple
from abc import ABC, abstractmethod
from pydicom.dataset import Dataset
from pydicom.tag import Tag


class TagEditCommand(ABC):
    """
    Abstract base class for tag edit commands.
    """
    
    @abstractmethod
    def execute(self) -> None:
        """Execute the command."""
        pass
    
    @abstractmethod
    def undo(self) -> None:
        """Undo the command."""
        pass


class EditTagCommand(TagEditCommand):
    """
    Command for editing a DICOM tag.
    """
    
    def __init__(self, dataset: Dataset, tag_identifier: Union[str, Tuple[int, int], Tag],
                 old_value: Any, new_value: Any, vr: Optional[str] = None):
        """
        Initialize the edit tag command.
        
        Args:
            dataset: DICOM dataset to edit
            tag_identifier: Tag as string, tuple, or Tag object
            old_value: Original tag value
            new_value: New tag value
            vr: Optional VR type
        """
        self.dataset = dataset
        self.tag_identifier = tag_identifier
        self.old_value = old_value
        self.new_value = new_value
        self.vr = vr
        self.tag: Optional[Tag] = None
        self._parse_tag()
    
    def _parse_tag(self) -> None:
        """Parse tag identifier into Tag object."""
        # Check if it's already a Tag object by checking for Tag-specific attributes
        if hasattr(self.tag_identifier, 'group') and hasattr(self.tag_identifier, 'element'):
            # It's likely a Tag object - use it directly
            self.tag = self.tag_identifier
        elif isinstance(self.tag_identifier, tuple) and len(self.tag_identifier) == 2:
            self.tag = Tag(self.tag_identifier[0], self.tag_identifier[1])
        elif isinstance(self.tag_identifier, str):
            # Parse string like "(0010,0010)"
            tag_str = self.tag_identifier.strip()
            if tag_str.startswith("(") and tag_str.endswith(")"):
                tag_str = tag_str[1:-1]
            parts = tag_str.split(",")
            if len(parts) == 2:
                try:
                    group = int(parts[0].strip(), 16)
                    element = int(parts[1].strip(), 16)
                    self.tag = Tag(group, element)
                except ValueError:
                    raise ValueError(f"Invalid tag format: {self.tag_identifier}")
            else:
                raise ValueError(f"Invalid tag format: {self.tag_identifier}")
        else:
            raise ValueError(f"Invalid tag identifier type: {type(self.tag_identifier)}")
    
    def get_target_dataset(self) -> Dataset:
        """
        Get the target dataset for editing.
        
        For multi-frame datasets (FrameDatasetWrapper), returns the original dataset.
        
        Returns:
            Dataset to edit
        """
        if hasattr(self.dataset, '_original_dataset'):
            return self.dataset._original_dataset
        return self.dataset
    
    def execute(self) -> None:
        """Execute the command - set new value."""
        if self.tag is None:
            return
        
        target_dataset = self.get_target_dataset()
        
        try:
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
                        vr = "LO"  # Default to Long String
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
        except Exception as e:
            print(f"Error undoing tag edit command: {e}")
            raise


class TagEditHistoryManager:
    """
    Manages undo/redo operations for DICOM tag edits.
    
    Features:
    - Execute tag edit commands
    - Undo/redo operations
    - Command history management per dataset
    - Configurable history depth
    """
    
    def __init__(self, max_history: int = 50):
        """
        Initialize the tag edit history manager.
        
        Args:
            max_history: Maximum number of commands to keep in history per dataset
        """
        self.max_history = max_history
        # Dictionary mapping dataset id to history stacks
        self.histories: dict = {}  # dataset_id -> {"undo": [], "redo": []}
    
    def _get_dataset_id(self, dataset: Dataset) -> int:
        """
        Get a unique identifier for a dataset.
        
        Args:
            dataset: DICOM dataset
            
        Returns:
            Unique identifier (memory address)
        """
        return id(dataset)
    
    def _get_history(self, dataset: Dataset) -> dict:
        """
        Get history stacks for a dataset.
        
        Args:
            dataset: DICOM dataset
            
        Returns:
            Dictionary with "undo" and "redo" stacks
        """
        dataset_id = self._get_dataset_id(dataset)
        if dataset_id not in self.histories:
            self.histories[dataset_id] = {"undo": [], "redo": []}
        return self.histories[dataset_id]
    
    def execute_command(self, command: TagEditCommand) -> None:
        """
        Execute a command and add it to undo stack.
        
        Args:
            command: TagEditCommand to execute
        """
        command.execute()
        
        history = self._get_history(command.dataset)
        history["undo"].append(command)
        
        # Clear redo stack when new command is executed
        history["redo"].clear()
        
        # Limit history size
        if len(history["undo"]) > self.max_history:
            history["undo"].pop(0)
    
    def undo(self, dataset: Dataset) -> bool:
        """
        Undo the last command for a dataset.
        
        Args:
            dataset: DICOM dataset
            
        Returns:
            True if undo was successful, False if no commands to undo
        """
        history = self._get_history(dataset)
        if not history["undo"]:
            return False
        
        command = history["undo"].pop()
        command.undo()
        history["redo"].append(command)
        return True
    
    def redo(self, dataset: Dataset) -> bool:
        """
        Redo the last undone command for a dataset.
        
        Args:
            dataset: DICOM dataset
            
        Returns:
            True if redo was successful, False if no commands to redo
        """
        history = self._get_history(dataset)
        if not history["redo"]:
            return False
        
        command = history["redo"].pop()
        command.execute()
        history["undo"].append(command)
        return True
    
    def can_undo(self, dataset: Dataset) -> bool:
        """
        Check if undo is possible for a dataset.
        
        Args:
            dataset: DICOM dataset
            
        Returns:
            True if undo is possible
        """
        history = self._get_history(dataset)
        return len(history["undo"]) > 0
    
    def can_redo(self, dataset: Dataset) -> bool:
        """
        Check if redo is possible for a dataset.
        
        Args:
            dataset: DICOM dataset
            
        Returns:
            True if redo is possible
        """
        history = self._get_history(dataset)
        return len(history["redo"]) > 0
    
    def clear_history(self, dataset: Optional[Dataset] = None) -> None:
        """
        Clear command history for a dataset or all datasets.
        
        Args:
            dataset: Optional DICOM dataset. If None, clears all histories.
        """
        if dataset is None:
            self.histories.clear()
        else:
            dataset_id = self._get_dataset_id(dataset)
            if dataset_id in self.histories:
                del self.histories[dataset_id]

