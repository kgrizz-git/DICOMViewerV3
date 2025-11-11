"""
DICOM Tag Editor

This module provides functionality for editing DICOM tags, including
value conversion based on VR types and handling multi-frame datasets.

Inputs:
    - pydicom.Dataset objects
    - Tag identifiers (tag string or tuple)
    - New tag values
    
Outputs:
    - Updated DICOM datasets
    - Validation results
    
Requirements:
    - pydicom library
    - typing for type hints
"""

from typing import Optional, Any, Tuple, Union
import pydicom
from pydicom.dataset import Dataset
from pydicom.tag import Tag
from pydicom.dataelem import DataElement


class DICOMEditor:
    """
    Handles editing of DICOM tags in datasets.
    
    Features:
    - Update tag values with VR type conversion
    - Handle tag creation (if tag doesn't exist)
    - Validate tag values before setting
    - Support for multi-frame datasets
    """
    
    def __init__(self, dataset: Optional[Dataset] = None):
        """
        Initialize the DICOM editor.
        
        Args:
            dataset: Optional pydicom Dataset to edit
        """
        self.dataset = dataset
    
    def set_dataset(self, dataset: Dataset) -> None:
        """
        Set the dataset to edit.
        
        Args:
            dataset: pydicom Dataset
        """
        self.dataset = dataset
    
    def get_target_dataset(self) -> Dataset:
        """
        Get the target dataset for editing.
        
        For multi-frame datasets (FrameDatasetWrapper), returns the original dataset.
        For regular datasets, returns the dataset itself.
        
        Returns:
            Dataset to edit
        """
        if self.dataset is None:
            raise ValueError("No dataset set")
        
        # Check if this is a frame wrapper
        if hasattr(self.dataset, '_original_dataset'):
            # For multi-frame, edit the original dataset
            return self.dataset._original_dataset
        return self.dataset
    
    def parse_tag(self, tag_identifier: Union[str, Tuple[int, int], Tag]) -> Tag:
        """
        Parse a tag identifier into a Tag object.
        
        Args:
            tag_identifier: Tag as string "(0010,0010)", tuple (0x0010, 0x0010), or Tag object
            
        Returns:
            Tag object
        """
        if isinstance(tag_identifier, Tag):
            return tag_identifier
        elif isinstance(tag_identifier, tuple):
            return Tag(tag_identifier[0], tag_identifier[1])
        elif isinstance(tag_identifier, str):
            # Parse string like "(0010,0010)"
            tag_identifier = tag_identifier.strip()
            if tag_identifier.startswith("(") and tag_identifier.endswith(")"):
                tag_identifier = tag_identifier[1:-1]
            parts = tag_identifier.split(",")
            if len(parts) == 2:
                try:
                    group = int(parts[0].strip(), 16) if parts[0].strip().startswith(("0x", "0X")) else int(parts[0].strip(), 16)
                    element = int(parts[1].strip(), 16) if parts[1].strip().startswith(("0x", "0X")) else int(parts[1].strip(), 16)
                    return Tag(group, element)
                except ValueError:
                    raise ValueError(f"Invalid tag format: {tag_identifier}")
            else:
                raise ValueError(f"Invalid tag format: {tag_identifier}")
        else:
            raise ValueError(f"Invalid tag identifier type: {type(tag_identifier)}")
    
    def update_tag(self, tag_identifier: Union[str, Tuple[int, int], Tag],
                   value: Any, vr: Optional[str] = None) -> bool:
        """
        Update a tag value in the dataset.
        
        Args:
            tag_identifier: Tag as string, tuple, or Tag object
            value: New value for the tag
            vr: Optional VR type (if None, will try to infer from existing tag or use default)
            
        Returns:
            True if successful, False otherwise
        """
        if self.dataset is None:
            return False
        
        try:
            target_dataset = self.get_target_dataset()
            tag = self.parse_tag(tag_identifier)
            
            # Check if tag exists
            if tag in target_dataset:
                # Get existing element to preserve VR
                existing_elem = target_dataset[tag]
                existing_vr = existing_elem.VR if hasattr(existing_elem, 'VR') else vr
            
            # Convert value based on VR type if needed
            converted_value = self._convert_value(value, vr or existing_vr if 'existing_vr' in locals() else None)
            
            # Update or create tag
            if tag in target_dataset:
                # Update existing tag
                target_dataset[tag].value = converted_value
            else:
                # Create new tag
                if vr is None:
                    # Try to infer VR from tag dictionary
                    try:
                        from pydicom.datadict import dictionary_VR
                        vr = dictionary_VR(tag)
                    except (KeyError, AttributeError):
                        # Default to LO (Long String) if can't determine
                        vr = "LO"
                
                # Create new DataElement
                new_elem = DataElement(tag, vr, converted_value)
                target_dataset.add(new_elem)
            
            # If this was a frame wrapper, also update the wrapper's copy
            if hasattr(self.dataset, '_original_dataset') and self.dataset is not target_dataset:
                # Update the wrapper's copy of the tag
                if tag in self.dataset:
                    self.dataset[tag].value = converted_value
                else:
                    # Add to wrapper
                    if vr is None:
                        try:
                            from pydicom.datadict import dictionary_VR
                            vr = dictionary_VR(tag)
                        except (KeyError, AttributeError):
                            vr = "LO"
                    new_elem = DataElement(tag, vr, converted_value)
                    self.dataset.add(new_elem)
            
            return True
        except Exception as e:
            print(f"Error updating tag {tag_identifier}: {e}")
            return False
    
    def _convert_value(self, value: Any, vr: Optional[str] = None) -> Any:
        """
        Convert value to appropriate type based on VR.
        
        Args:
            value: Value to convert
            vr: Optional VR type
            
        Returns:
            Converted value
        """
        if vr is None:
            return value
        
        vr = vr.upper()
        
        # Numeric types
        if vr == "FL":  # Float
            try:
                return float(value)
            except (ValueError, TypeError):
                return value
        elif vr == "FD":  # Double
            try:
                return float(value)
            except (ValueError, TypeError):
                return value
        elif vr in {"SL", "SS", "UL", "US"}:  # Integer types
            try:
                return int(value)
            except (ValueError, TypeError):
                return value
        
        # String types - ensure it's a string
        elif vr in {"AE", "AS", "AT", "CS", "DA", "DS", "DT", "IS", "LO",
                    "LT", "PN", "SH", "ST", "TM", "UI", "UT"}:
            return str(value) if value is not None else ""
        
        # Default: return as-is
        return value
    
    def delete_tag(self, tag_identifier: Union[str, Tuple[int, int], Tag]) -> bool:
        """
        Delete a tag from the dataset.
        
        Args:
            tag_identifier: Tag as string, tuple, or Tag object
            
        Returns:
            True if successful, False otherwise
        """
        if self.dataset is None:
            return False
        
        try:
            target_dataset = self.get_target_dataset()
            tag = self.parse_tag(tag_identifier)
            
            # Don't allow deletion of required tags (group 0000, 0002, 0008, etc.)
            if tag.group in {0x0000, 0x0002, 0x0008}:
                print(f"Warning: Cannot delete required tag {tag}")
                return False
            
            if tag in target_dataset:
                del target_dataset[tag]
                
                # Also delete from wrapper if applicable
                if hasattr(self.dataset, '_original_dataset') and self.dataset is not target_dataset:
                    if tag in self.dataset:
                        del self.dataset[tag]
                
                return True
            return False
        except Exception as e:
            print(f"Error deleting tag {tag_identifier}: {e}")
            return False

