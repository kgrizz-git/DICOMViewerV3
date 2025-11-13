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
import warnings
from pathlib import Path
from typing import List, Tuple, Optional
import pydicom
from pydicom.errors import InvalidDicomError
from core.multiframe_handler import is_multiframe, get_frame_count


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
        self._compression_error_files: set = set()  # Track files that have shown compression errors
    
    def validate_dicom_file(self, file_path: str) -> tuple[bool, Optional[str]]:
        """
        Validate DICOM file before loading pixel data.
        
        Checks for issues that might cause crashes:
        - Excessive padding in multi-frame files
        - Missing required tags
        - Corrupted or malformed data
        
        Note: Enhanced Multi-frame DICOMs (with PerFrameFunctionalGroupsSequence)
        are skipped from validation as they don't expose PixelData when loaded
        with stop_before_pixels=True.
        
        Args:
            file_path: Path to DICOM file
            
        Returns:
            Tuple of (is_valid, error_message)
            - is_valid: True if file appears safe to load, False otherwise
            - error_message: Description of the problem if not valid, None if valid
        """
        try:
            # Read metadata only, no pixel data
            ds = pydicom.dcmread(file_path, stop_before_pixels=True, force=True)
            
            # Skip validation for Enhanced Multi-frame DICOMs
            # These files use PerFrameFunctionalGroupsSequence and store pixel data
            # differently - they cannot be validated using stop_before_pixels
            if hasattr(ds, 'PerFrameFunctionalGroupsSequence'):
                print(f"[VALIDATION] Skipping validation for Enhanced Multi-frame DICOM: {os.path.basename(file_path)}")
                return True, None
            
            # Check for multi-frame
            num_frames = getattr(ds, 'NumberOfFrames', None)
            if num_frames and int(num_frames) > 1:
                # Validate required tags for multi-frame
                if not hasattr(ds, 'Rows') or not hasattr(ds, 'Columns'):
                    return False, "Multi-frame file missing Rows/Columns tags"
                
                # Calculate expected pixel data size
                rows = int(ds.Rows)
                cols = int(ds.Columns)
                frames = int(num_frames)
                bits_allocated = int(getattr(ds, 'BitsAllocated', 16))
                bytes_per_pixel = bits_allocated // 8
                
                expected_size = rows * cols * frames * bytes_per_pixel
                
                # Check if pixel data element exists and get its length
                if hasattr(ds, 'PixelData'):
                    actual_size = len(ds.PixelData)
                    padding_ratio = (actual_size - expected_size) / actual_size if actual_size > 0 else 0
                    
                    # Warn if excessive padding (>50%)
                    if padding_ratio > 0.5:
                        return False, (
                            f"Multi-frame file has excessive padding ({padding_ratio*100:.1f}%). "
                            f"This may indicate corruption or unsupported format. "
                            f"Expected {expected_size:,} bytes but found {actual_size:,} bytes."
                        )
            
            return True, None
        except Exception as e:
            return False, f"Validation failed: {str(e)}"
    
    def load_file(self, file_path: str, defer_size: Optional[int] = None) -> Optional[pydicom.Dataset]:
        """
        Load a single DICOM file.
        
        Args:
            file_path: Path to the DICOM file
            defer_size: Optional size threshold (in bytes) for deferring pixel data loading.
                       If file size exceeds this, pixel data will be loaded on-demand.
                       Default None means load all data immediately.
            
        Returns:
            pydicom.Dataset if successful, None otherwise
        """
        try:
            # Validate file before attempting to load pixel data
            is_valid, error_msg = self.validate_dicom_file(file_path)
            if not is_valid:
                print(f"Validation failed for {os.path.basename(file_path)}: {error_msg}")
                self.failed_files.append((file_path, error_msg))
                return None
            
            # Suppress excess padding warnings - these are informational and pydicom handles them automatically
            # The warnings don't cause errors, but we suppress them to reduce noise
            with warnings.catch_warnings():
                warnings.filterwarnings('ignore', message='.*excess padding.*', category=UserWarning)
                
                # Check file size if defer_size is specified
                if defer_size is not None:
                    file_size = os.path.getsize(file_path)
                    if file_size > defer_size:
                        # Use defer_size parameter to defer pixel data loading
                        dataset = pydicom.dcmread(file_path, force=True, defer_size=defer_size)
                    else:
                        dataset = pydicom.dcmread(file_path, force=True)
                else:
                    # Attempt to read the file as DICOM
                    dataset = pydicom.dcmread(file_path, force=True)
            
            # Detect multi-frame files (for informational purposes)
            # The actual frame splitting will be done in the organizer
            if is_multiframe(dataset):
                num_frames = get_frame_count(dataset)
                dataset._num_frames = num_frames
                dataset._is_multiframe = True
                
                # Debug logging for multi-frame files
                print(f"\n=== MULTI-FRAME DEBUG ===")
                print(f"File: {os.path.basename(file_path)}")
                print(f"Frames: {num_frames}")
                print(f"Dimensions: {getattr(dataset, 'Rows', 'N/A')} x {getattr(dataset, 'Columns', 'N/A')}")
                print(f"Bits Allocated: {getattr(dataset, 'BitsAllocated', 'N/A')}")
                print(f"Modality: {getattr(dataset, 'Modality', 'N/A')}")
                
                # Get transfer syntax safely
                transfer_syntax = 'N/A'
                if hasattr(dataset, 'file_meta') and hasattr(dataset.file_meta, 'TransferSyntaxUID'):
                    transfer_syntax = str(dataset.file_meta.TransferSyntaxUID)
                print(f"Transfer Syntax: {transfer_syntax}")
                
                if hasattr(dataset, 'PixelData'):
                    print(f"Pixel Data Length: {len(dataset.PixelData):,} bytes")
                    # Calculate expected vs actual
                    rows = int(getattr(dataset, 'Rows', 0))
                    cols = int(getattr(dataset, 'Columns', 0))
                    frames = num_frames
                    bits = int(getattr(dataset, 'BitsAllocated', 16))
                    expected = rows * cols * frames * (bits // 8)
                    actual = len(dataset.PixelData)
                    padding = actual - expected
                    padding_pct = (padding / actual * 100) if actual > 0 else 0
                    print(f"Expected Size: {expected:,} bytes")
                    print(f"Padding: {padding:,} bytes ({padding_pct:.1f}%)")
                
                # For Enhanced Multi-frame DICOMs, pre-load pixel array to ensure correct 3D shape
                # This is necessary because Enhanced Multi-frame files may not expose pixel data
                # correctly if accessed later after the dataset has been manipulated
                if hasattr(dataset, 'PerFrameFunctionalGroupsSequence'):
                    print(f"[LOADER] Enhanced Multi-frame detected, pre-loading pixel array...")
                    try:
                        pixel_array = dataset.pixel_array
                        print(f"[LOADER] Pixel array pre-loaded, shape: {pixel_array.shape}, dtype: {pixel_array.dtype}")
                        # Cache the pixel array in the dataset for later access
                        dataset._cached_pixel_array = pixel_array
                    except Exception as e:
                        error_msg = str(e)
                        # Check if this is a compressed DICOM decoding error
                        is_compression_error = (
                            "pylibjpeg-libjpeg" in error_msg.lower() or
                            "missing required dependencies" in error_msg.lower() or
                            "unable to convert" in error_msg.lower() or
                            "decode" in error_msg.lower()
                        )
                        
                        if is_compression_error:
                            error_detail = (
                                f"Compressed DICOM pixel data cannot be decoded. "
                                f"Install optional dependencies: pip install pylibjpeg pyjpegls"
                            )
                            # Only show error message once per file
                            if file_path not in self._compression_error_files:
                                self._compression_error_files.add(file_path)
                                print(f"[LOADER] Compression Error: {file_path}")
                                print(f"  {error_detail}")
                                print(f"  Error: {error_msg[:200]}")
                            # Add to failed files with descriptive message
                            self.failed_files.append((file_path, error_detail))
                            return None
                        else:
                            print(f"[LOADER] Warning: Failed to pre-load pixel array: {e}")
                
                print(f"========================\n")
            else:
                dataset._num_frames = 1
                dataset._is_multiframe = False
            
            return dataset
            
        except MemoryError as e:
            error_msg = (
                f"Memory error: File too large to load. "
                f"Try closing other applications or use a system with more memory. "
                f"Error: {str(e)}"
            )
            self.failed_files.append((file_path, error_msg))
            return None
        except InvalidDicomError as e:
            self.failed_files.append((file_path, f"Invalid DICOM file: {str(e)}"))
            return None
        except OSError as e:
            # Handle file system errors (file not found, permission denied, etc.)
            self.failed_files.append((file_path, f"File system error: {str(e)}"))
            return None
        except Exception as e:
            error_msg_str = str(e)
            # Check if this is a compressed DICOM decoding error
            is_compression_error = (
                "pylibjpeg-libjpeg" in error_msg_str.lower() or
                "missing required dependencies" in error_msg_str.lower() or
                "unable to convert" in error_msg_str.lower() or
                "decode" in error_msg_str.lower()
            )
            
            if is_compression_error:
                error_msg = (
                    f"Compressed DICOM pixel data cannot be decoded. "
                    f"Install optional dependencies: pip install pylibjpeg pyjpegls"
                )
                # Only show error message once per file
                if file_path not in self._compression_error_files:
                    self._compression_error_files.add(file_path)
                    print(f"[LOADER] Compression Error: {file_path}")
                    print(f"  {error_msg}")
                    print(f"  Error: {error_msg_str[:200]}")
            else:
                error_msg = f"Error reading file: {error_msg_str}"
            # Include error type for debugging
            error_type = type(e).__name__
            if error_type not in error_msg:
                error_msg = f"{error_type}: {error_msg}"
            self.failed_files.append((file_path, error_msg))
            return None
    
    def load_files(self, file_paths: List[str], defer_size: Optional[int] = None) -> List[pydicom.Dataset]:
        """
        Load multiple DICOM files.
        
        Args:
            file_paths: List of file paths to load
            defer_size: Optional size threshold (in bytes) for deferring pixel data loading.
                       If file size exceeds this, pixel data will be loaded on-demand.
            
        Returns:
            List of successfully loaded DICOM datasets
        """
        self.loaded_files = []
        self.failed_files = []
        
        for file_path in file_paths:
            try:
                dataset = self.load_file(file_path, defer_size=defer_size)
                if dataset is not None:
                    self.loaded_files.append(dataset)
            except Exception as e:
                # Additional safety net for unexpected errors
                error_msg = f"Unexpected error loading file: {str(e)}"
                error_type = type(e).__name__
                if error_type not in error_msg:
                    error_msg = f"{error_type}: {error_msg}"
                self.failed_files.append((file_path, error_msg))
        
        return self.loaded_files
    
    def load_directory(self, directory_path: str, recursive: bool = True, defer_size: Optional[int] = None) -> List[pydicom.Dataset]:
        """
        Load all DICOM files from a directory.
        
        Args:
            directory_path: Path to the directory
            recursive: If True, search subdirectories recursively
            defer_size: Optional size threshold (in bytes) for deferring pixel data loading.
                       If file size exceeds this, pixel data will be loaded on-demand.
            
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
            try:
                dataset = self.load_file(file_path, defer_size=defer_size)
                if dataset is not None:
                    self.loaded_files.append(dataset)
            except Exception as e:
                # Additional safety net for unexpected errors
                error_msg = f"Unexpected error loading file: {str(e)}"
                error_type = type(e).__name__
                if error_type not in error_msg:
                    error_msg = f"{error_type}: {error_msg}"
                self.failed_files.append((file_path, error_msg))
        
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

