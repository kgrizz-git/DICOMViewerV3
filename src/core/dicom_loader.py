"""
DICOM File Loader

This module handles loading DICOM files from various sources including:
- Single files
- Multiple files
- Directories (with recursive search)
- Files regardless of extension

Inputs:
    - File paths (single or multiple)
    - Directory paths
    - File objects
    
Outputs:
    - List of successfully loaded DICOM datasets
    - List of files that failed to load (with error messages)
    
Requirements:
    - pydicom library for DICOM file reading
    - pathlib for path handling
    - os for file system operations
"""

import os
from pathlib import Path
from typing import List, Tuple, Optional
import pydicom
from pydicom.errors import InvalidDicomError


class DICOMLoader:
    """
    Handles loading DICOM files from various sources.
    
    Supports:
    - Single file loading
    - Multiple file loading
    - Recursive directory scanning
    - Extension-agnostic file loading (attempts to load all files as DICOM)
    """
    
    def __init__(self):
        """Initialize the DICOM loader."""
        self.loaded_files: List[pydicom.Dataset] = []
        self.failed_files: List[Tuple[str, str]] = []  # (path, error_message)
    
    def load_file(self, file_path: str) -> Optional[pydicom.Dataset]:
        """
        Load a single DICOM file.
        
        Args:
            file_path: Path to the DICOM file
            
        Returns:
            pydicom.Dataset if successful, None otherwise
        """
        try:
            # Attempt to read the file as DICOM
            dataset = pydicom.dcmread(file_path, force=True)
            return dataset
        except InvalidDicomError as e:
            self.failed_files.append((file_path, f"Invalid DICOM file: {str(e)}"))
            return None
        except Exception as e:
            self.failed_files.append((file_path, f"Error reading file: {str(e)}"))
            return None
    
    def load_files(self, file_paths: List[str]) -> List[pydicom.Dataset]:
        """
        Load multiple DICOM files.
        
        Args:
            file_paths: List of file paths to load
            
        Returns:
            List of successfully loaded DICOM datasets
        """
        self.loaded_files = []
        self.failed_files = []
        
        for file_path in file_paths:
            dataset = self.load_file(file_path)
            if dataset is not None:
                self.loaded_files.append(dataset)
        
        return self.loaded_files
    
    def load_directory(self, directory_path: str, recursive: bool = True) -> List[pydicom.Dataset]:
        """
        Load all DICOM files from a directory.
        
        Args:
            directory_path: Path to the directory
            recursive: If True, search subdirectories recursively
            
        Returns:
            List of successfully loaded DICOM datasets
        """
        self.loaded_files = []
        self.failed_files = []
        
        dir_path = Path(directory_path)
        
        if not dir_path.exists() or not dir_path.is_dir():
            self.failed_files.append((directory_path, "Directory does not exist or is not a directory"))
            return []
        
        # Get all files in directory (and subdirectories if recursive)
        if recursive:
            file_paths = [str(p) for p in dir_path.rglob('*') if p.is_file()]
        else:
            file_paths = [str(p) for p in dir_path.iterdir() if p.is_file()]
        
        # Attempt to load each file as DICOM (regardless of extension)
        for file_path in file_paths:
            dataset = self.load_file(file_path)
            if dataset is not None:
                self.loaded_files.append(dataset)
        
        return self.loaded_files
    
    def get_failed_files(self) -> List[Tuple[str, str]]:
        """
        Get list of files that failed to load with error messages.
        
        Returns:
            List of tuples (file_path, error_message)
        """
        return self.failed_files.copy()
    
    def clear(self) -> None:
        """Clear loaded files and failed files lists."""
        self.loaded_files = []
        self.failed_files = []

