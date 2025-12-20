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
import time
import gc
import sys
from pathlib import Path
from typing import List, Tuple, Optional, Callable
import pydicom
from pydicom.errors import InvalidDicomError
from PySide6.QtWidgets import QApplication
from core.multiframe_handler import is_multiframe, get_frame_count

# Default defer size: 250MB - files larger than this will defer pixel data loading
# This balances fast initial load with responsive slice navigation
DEFAULT_DEFER_SIZE = 262144000  # 250 MB in bytes


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
        
        For small files (< 1MB), validation is skipped to improve loading speed,
        as these files are unlikely to have padding issues.
        
        Args:
            file_path: Path to DICOM file
            
        Returns:
            Tuple of (is_valid, error_message)
            - is_valid: True if file appears safe to load, False otherwise
            - error_message: Description of the problem if not valid, None if valid
        """
        try:
            # Skip validation for small files (< 1MB) to improve loading speed
            # Small files are unlikely to have the padding issues we're checking for
            file_size = os.path.getsize(file_path)
            if file_size < 1048576:  # 1 MB
                return True, None
            
            # Read metadata only, no pixel data
            ds = pydicom.dcmread(file_path, stop_before_pixels=True, force=True)
            
            # Skip validation for Enhanced Multi-frame DICOMs
            # These files use PerFrameFunctionalGroupsSequence and store pixel data
            # differently - they cannot be validated using stop_before_pixels
            if hasattr(ds, 'PerFrameFunctionalGroupsSequence'):
                # print(f"[VALIDATION] Skipping validation for Enhanced Multi-frame DICOM: {os.path.basename(file_path)}")
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
    
    def load_file(self, file_path: str, defer_size: Optional[int] = None, 
                  progress_callback: Optional[Callable[[str, Optional[int], Optional[int]], None]] = None) -> Optional[pydicom.Dataset]:
        """
        Load a single DICOM file.
        
        Args:
            file_path: Path to the DICOM file
            defer_size: Optional size threshold (in bytes) for deferring pixel data loading.
                       If file size exceeds this, pixel data will be loaded on-demand.
                       Default None means load all data immediately.
            progress_callback: Optional callback function for progress updates.
                              Signature: (message: str, current_frames: Optional[int], total_frames: Optional[int]) -> None
            
        Returns:
            pydicom.Dataset if successful, None otherwise
        """
        try:
            filename = os.path.basename(file_path)
            file_start_time = time.time()
            
            # Notify start of loading
            if progress_callback:
                progress_callback(f"Loading {filename}...", None, None)
                # Process events to allow timer to start and UI to update
                QApplication.processEvents()
            
            # Validate file before attempting to load pixel data
            validation_start = time.time()
            is_valid, error_msg = self.validate_dicom_file(file_path)
            validation_time = time.time() - validation_start
            
            if not is_valid:
                print(f"Validation failed for {os.path.basename(file_path)}: {error_msg}")
                self.failed_files.append((file_path, error_msg))
                return None
            
            # Suppress excess padding warnings - these are informational and pydicom handles them automatically
            # The warnings don't cause errors, but we suppress them to reduce noise
            with warnings.catch_warnings():
                warnings.filterwarnings('ignore', message='.*excess padding.*', category=UserWarning)
                
                # Process events before blocking read operation to allow timer to fire
                QApplication.processEvents()
                
                # Check file size if defer_size is specified
                read_start = time.time()
                if defer_size is not None:
                    file_size = os.path.getsize(file_path)
                    if file_size > defer_size:
                        # Use defer_size parameter to defer pixel data loading
                        file_size_mb = file_size / (1024 * 1024)
                        defer_size_mb = defer_size / (1024 * 1024)
                        # Notify that pixel data loading is being deferred
                        if progress_callback:
                            progress_callback(
                                f"Deferring pixel data loading for {filename} ({file_size_mb:.1f} MB > {defer_size_mb:.0f} MB threshold)",
                                None,
                                None
                            )
                            QApplication.processEvents()
                        dataset = pydicom.dcmread(file_path, force=True, defer_size=defer_size)
                    else:
                        dataset = pydicom.dcmread(file_path, force=True)
                else:
                    # Attempt to read the file as DICOM
                    dataset = pydicom.dcmread(file_path, force=True)
                read_time = time.time() - read_start
            
            # Track compression info for debugging
            compression_type = None
            pixel_load_time = 0
            
            # Check compression type (for all files, not just multi-frame)
            if hasattr(dataset, 'file_meta') and hasattr(dataset.file_meta, 'TransferSyntaxUID'):
                transfer_syntax = str(dataset.file_meta.TransferSyntaxUID)
                # List of compressed transfer syntaxes
                compressed_syntaxes = {
                    '1.2.840.10008.1.2.4': 'RLE Lossless',
                    '1.2.840.10008.1.2.4.50': 'JPEG Baseline',
                    '1.2.840.10008.1.2.4.51': 'JPEG Extended',
                    '1.2.840.10008.1.2.4.57': 'JPEG Lossless',
                    '1.2.840.10008.1.2.4.70': 'JPEG Lossless',
                    '1.2.840.10008.1.2.4.80': 'JPEG-LS Lossless',
                    '1.2.840.10008.1.2.4.81': 'JPEG-LS Lossy',
                    '1.2.840.10008.1.2.4.90': 'JPEG 2000 Lossless',
                    '1.2.840.10008.1.2.4.91': 'JPEG 2000',
                }
                if transfer_syntax in compressed_syntaxes:
                    compression_type = compressed_syntaxes[transfer_syntax]
            
            # Detect multi-frame files (for informational purposes)
            # The actual frame splitting will be done in the organizer
            if is_multiframe(dataset):
                num_frames = get_frame_count(dataset)
                dataset._num_frames = num_frames
                dataset._is_multiframe = True
                
                # Debug logging for multi-frame files (only if verbose)
                # Commented out to reduce noise - uncomment if needed for debugging
                # print(f"\n=== MULTI-FRAME DEBUG ===")
                # print(f"File: {os.path.basename(file_path)}")
                # print(f"Frames: {num_frames}")
                # print(f"Dimensions: {getattr(dataset, 'Rows', 'N/A')} x {getattr(dataset, 'Columns', 'N/A')}")
                # print(f"Bits Allocated: {getattr(dataset, 'BitsAllocated', 'N/A')}")
                # print(f"Transfer Syntax: {transfer_syntax}")
                
                # For Enhanced Multi-frame DICOMs, pre-load pixel array to ensure correct 3D shape
                # This is necessary because Enhanced Multi-frame files may not expose pixel data
                # correctly if accessed later after the dataset has been manipulated
                if hasattr(dataset, 'PerFrameFunctionalGroupsSequence'):
                    # Notify about frame loading
                    if progress_callback:
                        progress_callback(f"Loading {num_frames} frames from {filename}...", None, num_frames)
                        # Process events before blocking operation to allow timer to fire
                        QApplication.processEvents()
                    
                    # Check estimated memory requirement before loading
                    rows = int(getattr(dataset, 'Rows', 512))
                    cols = int(getattr(dataset, 'Columns', 512))
                    bits_allocated = int(getattr(dataset, 'BitsAllocated', 16))
                    bytes_per_pixel = bits_allocated // 8
                    samples_per_pixel = int(getattr(dataset, 'SamplesPerPixel', 1))
                    estimated_memory_mb = (num_frames * rows * cols * samples_per_pixel * bytes_per_pixel) / (1024 * 1024)
                    
                    # Skip pre-loading if estimated size is very large (>200MB) to avoid memory pressure
                    # The pixel array will be loaded on-demand later when needed
                    if estimated_memory_mb > 200:
                        # Don't pre-load, but mark as multi-frame
                        dataset._num_frames = num_frames
                        dataset._is_multiframe = True
                    else:
                        try:
                            pixel_load_start = time.time()
                            pixel_array = dataset.pixel_array
                            pixel_load_time = time.time() - pixel_load_start
                            # Cache the pixel array in the dataset for later access
                            dataset._cached_pixel_array = pixel_array
                            # Notify completion
                            if progress_callback:
                                progress_callback(f"Loaded {num_frames} frames from {filename}", num_frames, num_frames)
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
                
            else:
                dataset._num_frames = 1
                dataset._is_multiframe = False
            
            # Log timing breakdown for slow files
            total_time = time.time() - file_start_time
            if total_time > 0.5:  # Log breakdown for files taking > 0.5s
                timing_parts = [f"Total {total_time:.3f}s"]
                if validation_time > 0.05:
                    timing_parts.append(f"validation: {validation_time:.3f}s")
                if read_time > 0.05:
                    timing_parts.append(f"read: {read_time:.3f}s")
                if pixel_load_time > 0.05:
                    timing_parts.append(f"pixel_load: {pixel_load_time:.3f}s")
                # Always show compression type for slow files to help diagnose
                if compression_type:
                    timing_parts.append(f"compressed: {compression_type}")
                else:
                    timing_parts.append("uncompressed")
                # print(f"[LOAD DEBUG] {filename}: {' | '.join(timing_parts)}")
            
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
    
    def load_files(self, file_paths: List[str], defer_size: Optional[int] = None, 
                   progress_callback: Optional[Callable[[int, int, str], None]] = None) -> List[pydicom.Dataset]:
        """
        Load multiple DICOM files.
        
        Args:
            file_paths: List of file paths to load
            defer_size: Optional size threshold (in bytes) for deferring pixel data loading.
                       If file size exceeds this, pixel data will be loaded on-demand.
                       Defaults to DEFAULT_DEFER_SIZE (1MB) if None.
            progress_callback: Optional callback function called during loading.
                              Signature: (current: int, total: int, filename: str) -> None
            
        Returns:
            List of successfully loaded DICOM datasets
        """
        # Use default defer size if not specified
        if defer_size is None:
            defer_size = DEFAULT_DEFER_SIZE
        
        self.loaded_files = []
        self.failed_files = []
        
        total_files = len(file_paths)
        last_update_time = time.time()
        update_interval = 0.05  # Update every 50ms
        
        # Debugging: Track loading performance
        load_start_time = time.time()
        slow_files = []  # Track files that take > 0.5 seconds
        file_times = []  # Track all file load times
        gc_times = []  # Track GC overhead
        
        # print(f"[LOAD DEBUG] Starting load of {total_files} files (defer_size={defer_size/1024/1024:.1f}MB)")
        
        for idx, file_path in enumerate(file_paths):
            file_load_start = time.time()
            
            # Call progress callback with throttling (every 5 files or 50ms)
            if progress_callback and (idx % 5 == 0 or time.time() - last_update_time >= update_interval):
                filename = os.path.basename(file_path)
                progress_callback(idx + 1, total_files, filename)
                last_update_time = time.time()
                # Process events more frequently to keep UI responsive
                QApplication.processEvents()
            
            try:
                # Get file size for debugging
                try:
                    file_size = os.path.getsize(file_path)
                    file_size_mb = file_size / (1024 * 1024)
                except Exception:
                    file_size = 0
                    file_size_mb = 0
                
                # For single file loading, pass a progress callback that formats messages
                file_progress_callback = None
                if total_files == 1 and progress_callback:
                    def single_file_progress(message: str, current_frames: Optional[int], total_frames: Optional[int]) -> None:
                        # Format message for single file case - pass message as filename parameter
                        # This handles both loading messages and defer messages
                        progress_callback(1, 1, message)
                    file_progress_callback = single_file_progress
                elif progress_callback:
                    # For multiple files, create a callback that can handle defer messages
                    def multi_file_progress(message: str, current_frames: Optional[int], total_frames: Optional[int]) -> None:
                        # If message starts with "Deferring", show it as a status message
                        if message.startswith("Deferring"):
                            # Pass the defer message as the filename parameter so it shows in status bar
                            progress_callback(idx + 1, total_files, message)
                        # Otherwise, it's a normal loading message which is handled by the main progress callback
                    file_progress_callback = multi_file_progress
                
                dataset = self.load_file(file_path, defer_size=defer_size, progress_callback=file_progress_callback)
                file_load_time = time.time() - file_load_start
                file_times.append(file_load_time)
                
                if dataset is not None:
                    self.loaded_files.append(dataset)
                    
                    # Track slow files
                    if file_load_time > 0.5:
                        filename = os.path.basename(file_path)
                        slow_files.append((filename, file_load_time, file_size_mb))
                        # print(f"[LOAD DEBUG] Slow file: {filename} took {file_load_time:.3f}s ({file_size_mb:.2f}MB)")
                    
                    # Periodic garbage collection every 50 files to prevent memory buildup
                    if len(self.loaded_files) % 50 == 0:
                        gc_start = time.time()
                        gc.collect()
                        gc_time = time.time() - gc_start
                        gc_times.append(gc_time)
                        QApplication.processEvents()  # Keep UI responsive during GC
                        # print(f"[LOAD DEBUG] GC at file {len(self.loaded_files)}: {gc_time:.3f}s")
                    # More frequent GC for large file counts
                    elif len(self.loaded_files) > 200 and len(self.loaded_files) % 25 == 0:
                        gc_start = time.time()
                        gc.collect()
                        gc_time = time.time() - gc_start
                        gc_times.append(gc_time)
                        QApplication.processEvents()
                        # print(f"[LOAD DEBUG] GC at file {len(self.loaded_files)}: {gc_time:.3f}s")
                    
                    # Debug: Log every 100 files
                    if len(self.loaded_files) % 100 == 0:
                        elapsed = time.time() - load_start_time
                        avg_time = elapsed / len(self.loaded_files)
                        # print(f"[LOAD DEBUG] Loaded {len(self.loaded_files)}/{total_files} files in {elapsed:.1f}s (avg {avg_time*1000:.1f}ms/file)")
            except Exception as e:
                # Additional safety net for unexpected errors
                error_msg = f"Unexpected error loading file: {str(e)}"
                error_type = type(e).__name__
                if error_type not in error_msg:
                    error_msg = f"{error_type}: {error_msg}"
                self.failed_files.append((file_path, error_msg))
                file_load_time = time.time() - file_load_start
                # print(f"[LOAD DEBUG] Error loading {os.path.basename(file_path)}: {error_msg} (took {file_load_time:.3f}s)")
        
        # Final progress update
        if progress_callback and total_files > 0:
            progress_callback(total_files, total_files, "")
        
        # Debugging summary
        total_time = time.time() - load_start_time
        if file_times:
            avg_time = sum(file_times) / len(file_times)
            max_time = max(file_times)
            min_time = min(file_times)
            total_gc_time = sum(gc_times) if gc_times else 0
            # print(f"[LOAD DEBUG] ===== Loading Summary =====")
            # print(f"[LOAD DEBUG] Total files: {len(self.loaded_files)}/{total_files}")
            # print(f"[LOAD DEBUG] Total time: {total_time:.2f}s")
            # print(f"[LOAD DEBUG] Avg time/file: {avg_time*1000:.1f}ms")
            # print(f"[LOAD DEBUG] Min time/file: {min_time*1000:.1f}ms")
            # print(f"[LOAD DEBUG] Max time/file: {max_time*1000:.1f}ms")
            # print(f"[LOAD DEBUG] GC overhead: {total_gc_time:.2f}s ({total_gc_time/total_time*100:.1f}%)")
            # if slow_files:
            #     print(f"[LOAD DEBUG] Slow files (>0.5s): {len(slow_files)}")
            #     for filename, load_time, size_mb in slow_files[:5]:  # Show top 5
            #         print(f"[LOAD DEBUG]   - {filename}: {load_time:.3f}s ({size_mb:.2f}MB)")
            # print(f"[LOAD DEBUG] ============================")
        
        return self.loaded_files
    
    def load_directory(self, directory_path: str, recursive: bool = True, defer_size: Optional[int] = None,
                      progress_callback: Optional[Callable[[int, int, str], None]] = None) -> List[pydicom.Dataset]:
        """
        Load all DICOM files from a directory.
        
        Args:
            directory_path: Path to the directory
            recursive: If True, search subdirectories recursively
            defer_size: Optional size threshold (in bytes) for deferring pixel data loading.
                       If file size exceeds this, pixel data will be loaded on-demand.
                       Defaults to DEFAULT_DEFER_SIZE (1MB) if None.
            progress_callback: Optional callback function called during loading.
                              Signature: (current: int, total: int, filename: str) -> None
            
        Returns:
            List of successfully loaded DICOM datasets
        """
        # Use default defer size if not specified
        if defer_size is None:
            defer_size = DEFAULT_DEFER_SIZE
        
        self.loaded_files = []
        self.failed_files = []
        
        dir_path = Path(directory_path)
        
        if not dir_path.exists() or not dir_path.is_dir():
            self.failed_files.append((directory_path, "Directory does not exist or is not a directory"))
            return []
        
        # Get all files in directory (and subdirectories if recursive)
        scan_start = time.time()
        if recursive:
            file_paths = [str(p) for p in dir_path.rglob('*') if p.is_file()]
        else:
            file_paths = [str(p) for p in dir_path.iterdir() if p.is_file()]
        scan_time = time.time() - scan_start
        # print(f"[LOAD DEBUG] Scanned directory in {scan_time:.2f}s, found {len(file_paths)} files")
        
        total_files = len(file_paths)
        last_update_time = time.time()
        update_interval = 0.05  # Update every 50ms
        
        # Debugging: Track loading performance
        load_start_time = time.time()
        slow_files = []  # Track files that take > 0.5 seconds
        file_times = []  # Track all file load times
        gc_times = []  # Track GC overhead
        
        # print(f"[LOAD DEBUG] Starting load of {total_files} files (defer_size={defer_size/1024/1024:.1f}MB)")
        
        # Attempt to load each file as DICOM (regardless of extension)
        for idx, file_path in enumerate(file_paths):
            file_load_start = time.time()
            
            # Call progress callback with throttling (every 5 files or 50ms)
            if progress_callback and (idx % 5 == 0 or time.time() - last_update_time >= update_interval):
                filename = os.path.basename(file_path)
                progress_callback(idx + 1, total_files, filename)
                last_update_time = time.time()
                # Process events more frequently to keep UI responsive
                QApplication.processEvents()
            
            try:
                # Get file size for debugging
                try:
                    file_size = os.path.getsize(file_path)
                    file_size_mb = file_size / (1024 * 1024)
                except Exception:
                    file_size = 0
                    file_size_mb = 0
                
                # Create progress callback wrapper for load_file
                file_progress_callback = None
                if progress_callback:
                    def multi_file_progress(message: str, current_frames: Optional[int], total_frames: Optional[int]) -> None:
                        # If message starts with "Deferring", show it as a status message
                        if message.startswith("Deferring"):
                            # Pass the defer message as the filename parameter so it shows in status bar
                            progress_callback(idx + 1, total_files, message)
                        # Otherwise, it's a normal loading message which is handled by the main progress callback
                    file_progress_callback = multi_file_progress
                
                dataset = self.load_file(file_path, defer_size=defer_size, progress_callback=file_progress_callback)
                file_load_time = time.time() - file_load_start
                file_times.append(file_load_time)
                
                if dataset is not None:
                    self.loaded_files.append(dataset)
                    
                    # Track slow files
                    if file_load_time > 0.5:
                        filename = os.path.basename(file_path)
                        slow_files.append((filename, file_load_time, file_size_mb))
                        # print(f"[LOAD DEBUG] Slow file: {filename} took {file_load_time:.3f}s ({file_size_mb:.2f}MB)")
                    
                    # Periodic garbage collection every 50 files to prevent memory buildup
                    if len(self.loaded_files) % 50 == 0:
                        gc_start = time.time()
                        gc.collect()
                        gc_time = time.time() - gc_start
                        gc_times.append(gc_time)
                        QApplication.processEvents()  # Keep UI responsive during GC
                        # print(f"[LOAD DEBUG] GC at file {len(self.loaded_files)}: {gc_time:.3f}s")
                    # More frequent GC for large file counts
                    elif len(self.loaded_files) > 200 and len(self.loaded_files) % 25 == 0:
                        gc_start = time.time()
                        gc.collect()
                        gc_time = time.time() - gc_start
                        gc_times.append(gc_time)
                        QApplication.processEvents()
                        # print(f"[LOAD DEBUG] GC at file {len(self.loaded_files)}: {gc_time:.3f}s")
                    
                    # Debug: Log every 100 files
                    if len(self.loaded_files) % 100 == 0:
                        elapsed = time.time() - load_start_time
                        avg_time = elapsed / len(self.loaded_files)
                        # print(f"[LOAD DEBUG] Loaded {len(self.loaded_files)}/{total_files} files in {elapsed:.1f}s (avg {avg_time*1000:.1f}ms/file)")
            except Exception as e:
                # Additional safety net for unexpected errors
                error_msg = f"Unexpected error loading file: {str(e)}"
                error_type = type(e).__name__
                if error_type not in error_msg:
                    error_msg = f"{error_type}: {error_msg}"
                self.failed_files.append((file_path, error_msg))
                file_load_time = time.time() - file_load_start
                # print(f"[LOAD DEBUG] Error loading {os.path.basename(file_path)}: {error_msg} (took {file_load_time:.3f}s)")
        
        # Final progress update
        if progress_callback and total_files > 0:
            progress_callback(total_files, total_files, "")
        
        # Debugging summary
        total_time = time.time() - load_start_time
        if file_times:
            avg_time = sum(file_times) / len(file_times)
            max_time = max(file_times)
            min_time = min(file_times)
            total_gc_time = sum(gc_times) if gc_times else 0
            # print(f"[LOAD DEBUG] ===== Loading Summary =====")
            # print(f"[LOAD DEBUG] Total files: {len(self.loaded_files)}/{total_files}")
            # print(f"[LOAD DEBUG] Total time: {total_time:.2f}s")
            # print(f"[LOAD DEBUG] Avg time/file: {avg_time*1000:.1f}ms")
            # print(f"[LOAD DEBUG] Min time/file: {min_time*1000:.1f}ms")
            # print(f"[LOAD DEBUG] Max time/file: {max_time*1000:.1f}ms")
            # print(f"[LOAD DEBUG] GC overhead: {total_gc_time:.2f}s ({total_gc_time/total_time*100:.1f}%)")
            # if slow_files:
            #     print(f"[LOAD DEBUG] Slow files (>0.5s): {len(slow_files)}")
            #     for filename, load_time, size_mb in slow_files[:5]:  # Show top 5
            #         print(f"[LOAD DEBUG]   - {filename}: {load_time:.3f}s ({size_mb:.2f}MB)")
            # print(f"[LOAD DEBUG] ============================")
        
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

