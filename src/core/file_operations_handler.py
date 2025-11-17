"""
File Operations Handler

This module handles all file-related operations including opening files, folders,
and recent files, as well as loading the first slice.

Inputs:
    - File paths (single or multiple)
    - Folder paths
    - Recent file paths
    
Outputs:
    - Loaded DICOM datasets
    - Organized studies/series
    - First slice displayed
    
Requirements:
    - DICOMLoader for loading files
    - DICOMOrganizer for organizing
    - FileDialog for user dialogs
    - ConfigManager for configuration
"""

import os
from typing import Callable, Optional
from PySide6.QtWidgets import QApplication
from core.dicom_loader import DICOMLoader
from core.dicom_organizer import DICOMOrganizer
from gui.dialogs.file_dialog import FileDialog
from utils.config_manager import ConfigManager
from gui.main_window import MainWindow

class FileOperationsHandler:
    """
    Handles file operations including opening files, folders, and recent files.
    
    Responsibilities:
    - Open single or multiple DICOM files
    - Open folders (recursive)
    - Open recent files/folders
    - Load and organize DICOM datasets
    - Display first slice after loading
    - Clear existing data when opening new files
    """
    
    def __init__(
        self,
        dicom_loader: DICOMLoader,
        dicom_organizer: DICOMOrganizer,
        file_dialog: FileDialog,
        config_manager: ConfigManager,
        main_window: MainWindow,
        clear_data_callback: Callable,
        load_first_slice_callback: Callable,
        update_status_callback: Callable
    ):
        """
        Initialize the file operations handler.
        
        Args:
            dicom_loader: DICOM loader instance
            dicom_organizer: DICOM organizer instance
            file_dialog: File dialog instance
            config_manager: Configuration manager
            main_window: Main window for dialogs
            clear_data_callback: Callback to clear existing data (ROIs, measurements, etc.)
            load_first_slice_callback: Callback to load and display first slice
            update_status_callback: Callback to update status bar
        """
        self.dicom_loader = dicom_loader
        self.dicom_organizer = dicom_organizer
        self.file_dialog = file_dialog
        self.config_manager = config_manager
        self.main_window = main_window
        self.clear_data_callback = clear_data_callback
        self.load_first_slice_callback = load_first_slice_callback
        self.update_status_callback = update_status_callback
    
    def _format_source_name(self, file_paths: list[str]) -> str:
        """
        Format source name for status display.
        
        Args:
            file_paths: List of file paths
            
        Returns:
            Formatted source name string
        """
        if len(file_paths) == 1:
            return os.path.basename(file_paths[0])
        elif len(file_paths) > 1:
            return os.path.basename(file_paths[0]) + "..."
        return ""
    
    def _format_final_status(self, studies: dict, num_files: int, source_name: str) -> str:
        """
        Format final status message with studies/series/file counts.
        
        Args:
            studies: Dictionary of organized studies/series
            num_files: Number of files loaded
            source_name: Name of source (folder or file)
            
        Returns:
            Formatted status message
        """
        num_studies = len(studies)
        num_series = sum(len(series_dict) for series_dict in studies.values())
        
        study_text = f"{num_studies} study" + ("ies" if num_studies != 1 else "")
        series_text = f"{num_series} series"
        file_text = f"{num_files} file" + ("s" if num_files != 1 else "")
        
        return f"{study_text}, {series_text}, {file_text} loaded from {source_name}"
    
    def open_files(self) -> tuple[list, dict]:
        """
        Handle open files request.
        
        Returns:
            Tuple of (datasets list, studies dict) or (None, None) if cancelled/error
        """
        file_paths = self.file_dialog.open_files(self.main_window)
        if not file_paths:
            return None, None
        
        # Clear all ROIs when opening new files
        self.clear_data_callback()
        
        # Add first file to recent files (representing this file selection)
        if file_paths:
            self.config_manager.add_recent_file(file_paths[0])
            self.main_window.update_recent_menu()
        
        # Format source name for status display
        source_name = self._format_source_name(file_paths)
        
        try:
            # Update status: start loading
            self.update_status_callback(f"Loading files from {source_name}...")
            QApplication.processEvents()
            
            # Create progress callback
            def progress_callback(current: int, total: int, filename: str) -> None:
                if filename:
                    self.update_status_callback(f"Loading file {current}/{total}: {filename}...")
                else:
                    self.update_status_callback(f"Loaded {total} file(s). Organizing into studies/series...")
                QApplication.processEvents()
            
            # Load files
            datasets = self.dicom_loader.load_files(file_paths, progress_callback=progress_callback)
            
            if not datasets:
                # Check if there were specific errors
                failed = self.dicom_loader.get_failed_files()
                if failed:
                    error_msg = "No DICOM files could be loaded.\n\nErrors:\n"
                    for path, error in failed[:5]:  # Show first 5
                        error_msg += f"\n{os.path.basename(path)}: {error}"
                    if len(failed) > 5:
                        error_msg += f"\n... and {len(failed) - 5} more"
                else:
                    error_msg = "No DICOM files could be loaded."
                
                self.file_dialog.show_error(
                    self.main_window,
                    "Error",
                    error_msg
                )
                return None, None
            
            # Validate datasets before processing
            # Multi-frame detection kept for potential future use, but no filtering
            validated_datasets = []
            validated_paths = []
            
            for ds, path in zip(datasets, file_paths):
                validated_datasets.append(ds)
                validated_paths.append(path)
            
            # Update datasets and paths to validated ones
            datasets = validated_datasets
            file_paths = validated_paths
            
            if not datasets:
                self.file_dialog.show_error(
                    self.main_window,
                    "No Valid Files",
                    "All selected files were skipped due to safety checks. No files to display."
                )
                return None, None
            
            # Show warnings for failed files
            failed = self.dicom_loader.get_failed_files()
            if failed:
                warning_msg = f"Warning: {len(failed)} file(s) could not be loaded:\n"
                for path, error in failed[:5]:  # Show first 5
                    warning_msg += f"\n{os.path.basename(path)}: {error}"
                if len(failed) > 5:
                    warning_msg += f"\n... and {len(failed) - 5} more"
                
                self.file_dialog.show_warning(self.main_window, "Loading Warnings", warning_msg)
            
            # Organize into studies/series
            try:
                studies = self.dicom_organizer.organize(datasets, file_paths)
            except MemoryError as e:
                self.file_dialog.show_error(
                    self.main_window,
                    "Memory Error",
                    f"Out of memory while organizing DICOM files. "
                    f"Try closing other applications or loading fewer files.\n\nError: {str(e)}"
                )
                return None, None
            except Exception as e:
                self.file_dialog.show_error(
                    self.main_window,
                    "Error",
                    f"Error organizing DICOM files: {str(e)}"
                )
                return None, None
            
            # Display first slice
            try:
                self.load_first_slice_callback(studies)
            except MemoryError as e:
                self.file_dialog.show_error(
                    self.main_window,
                    "Memory Error",
                    f"Out of memory while displaying image. "
                    f"Try closing other applications.\n\nError: {str(e)}"
                )
                return None, None
            except Exception as e:
                self.file_dialog.show_error(
                    self.main_window,
                    "Error",
                    f"Error displaying first slice: {str(e)}"
                )
                return None, None
            
            # Format and display final status
            final_status = self._format_final_status(studies, len(datasets), source_name)
            
            # Check for compression errors and append guidance if needed
            failed = self.dicom_loader.get_failed_files()
            compression_errors = [f for f in failed if "Compressed DICOM" in f[1] or "pylibjpeg" in f[1].lower()]
            if compression_errors:
                compression_count = len(compression_errors)
                final_status += f". {compression_count} compressed file(s) require pylibjpeg: pip install pylibjpeg pyjpegls"
            
            self.update_status_callback(final_status)
            QApplication.processEvents()
            
            return datasets, studies
        
        except SystemExit:
            raise  # Don't catch system exit
        except KeyboardInterrupt:
            raise  # Don't catch Ctrl+C
        except MemoryError as e:
            self.file_dialog.show_error(
                self.main_window,
                "Memory Error",
                f"Out of memory while loading files. "
                f"Try closing other applications or use a system with more memory.\n\nError: {str(e)}"
            )
            return None, None
        except BaseException as e:
            # Catch everything else including C extension errors that make it to Python
            error_type = type(e).__name__
            error_msg = f"A critical error occurred during file loading.\n\n"
            error_msg += f"Error: {error_type}: {str(e)}\n\n"
            error_msg += f"This may be due to corrupted or unsupported DICOM files."
            
            print(f"Critical error in open_files: {error_type}: {e}")
            import traceback
            traceback.print_exc()
            
            self.file_dialog.show_error(
                self.main_window,
                "Critical Error",
                error_msg
            )
            return None, None
    
    def open_folder(self) -> tuple[list, dict]:
        """
        Handle open folder request.
        
        Returns:
            Tuple of (datasets list, studies dict) or (None, None) if cancelled/error
        """
        folder_path = self.file_dialog.open_folder(self.main_window)
        if not folder_path:
            return None, None
        
        # Clear all ROIs when opening new folder
        self.clear_data_callback()
        
        # Add folder to recent files
        self.config_manager.add_recent_file(folder_path)
        self.main_window.update_recent_menu()
        
        # Format source name for status display
        source_name = os.path.basename(folder_path)
        
        try:
            # Update status: start loading
            self.update_status_callback(f"Loading files from {source_name}...")
            QApplication.processEvents()
            
            # Create progress callback
            def progress_callback(current: int, total: int, filename: str) -> None:
                if filename:
                    self.update_status_callback(f"Loading file {current}/{total}: {filename}...")
                else:
                    self.update_status_callback(f"Loaded {total} file(s). Organizing into studies/series...")
                QApplication.processEvents()
            
            # Load folder (recursive)
            datasets = self.dicom_loader.load_directory(folder_path, recursive=True, progress_callback=progress_callback)
            
            if not datasets:
                # Check if there were specific errors
                failed = self.dicom_loader.get_failed_files()
                if failed:
                    error_msg = f"No DICOM files found in folder.\n\n{len(failed)} file(s) could not be loaded."
                else:
                    error_msg = "No DICOM files found in folder."
                
                self.file_dialog.show_error(
                    self.main_window,
                    "Error",
                    error_msg
                )
                return None, None
            
            # Show warnings
            failed = self.dicom_loader.get_failed_files()
            if failed:
                warning_msg = f"Warning: {len(failed)} file(s) could not be loaded."
                self.file_dialog.show_warning(self.main_window, "Loading Warnings", warning_msg)
            
            # Organize
            try:
                studies = self.dicom_organizer.organize(datasets)
            except MemoryError as e:
                self.file_dialog.show_error(
                    self.main_window,
                    "Memory Error",
                    f"Out of memory while organizing DICOM files. "
                    f"Try closing other applications or loading fewer files.\n\nError: {str(e)}"
                )
                return None, None
            except Exception as e:
                self.file_dialog.show_error(
                    self.main_window,
                    "Error",
                    f"Error organizing DICOM files: {str(e)}"
                )
                return None, None
            
            # Display first slice
            try:
                self.load_first_slice_callback(studies)
            except MemoryError as e:
                self.file_dialog.show_error(
                    self.main_window,
                    "Memory Error",
                    f"Out of memory while displaying image. "
                    f"Try closing other applications.\n\nError: {str(e)}"
                )
                return None, None
            except Exception as e:
                self.file_dialog.show_error(
                    self.main_window,
                    "Error",
                    f"Error displaying first slice: {str(e)}"
                )
                return None, None
            
            # Format and display final status
            final_status = self._format_final_status(studies, len(datasets), source_name)
            self.update_status_callback(final_status)
            QApplication.processEvents()
            
            return datasets, studies
        
        except SystemExit:
            raise  # Don't catch system exit
        except KeyboardInterrupt:
            raise  # Don't catch Ctrl+C
        except MemoryError as e:
            self.file_dialog.show_error(
                self.main_window,
                "Memory Error",
                f"Out of memory while loading folder. "
                f"Try closing other applications or use a system with more memory.\n\nError: {str(e)}"
            )
            return None, None
        except BaseException as e:
            # Catch everything else including C extension errors that make it to Python
            error_type = type(e).__name__
            error_msg = f"A critical error occurred during folder loading.\n\n"
            error_msg += f"Error: {error_type}: {str(e)}\n\n"
            error_msg += f"This may be due to corrupted or unsupported DICOM files."
            
            print(f"Critical error in open_folder: {error_type}: {e}")
            import traceback
            traceback.print_exc()
            
            self.file_dialog.show_error(
                self.main_window,
                "Critical Error",
                error_msg
            )
            return None, None
    
    def open_recent_file(self, file_path: str) -> tuple[list, dict]:
        """
        Handle open recent file/folder request.
        
        Args:
            file_path: Path to file or folder to open
            
        Returns:
            Tuple of (datasets list, studies dict) or (None, None) if cancelled/error
        """
        # Clear all ROIs when opening new file/folder
        self.clear_data_callback()
        
        # Check if path exists
        if not os.path.exists(file_path):
            self.file_dialog.show_error(
                self.main_window,
                "Error",
                f"File or folder not found:\n{file_path}"
            )
            # Remove from recent files if it doesn't exist
            recent_files = self.config_manager.get_recent_files()
            if file_path in recent_files:
                recent_files.remove(file_path)
                self.config_manager.config["recent_files"] = recent_files
                self.config_manager.save_config()
                self.main_window.update_recent_menu()
            return None, None
        
        # Determine if it's a file or folder
        if os.path.isfile(file_path):
            # Open as file
            source_name = os.path.basename(file_path)
            try:
                # Update status: start loading
                self.update_status_callback(f"Loading files from {source_name}...")
                QApplication.processEvents()
                
                # Create progress callback
                def progress_callback(current: int, total: int, filename: str) -> None:
                    if filename:
                        self.update_status_callback(f"Loading file {current}/{total}: {filename}...")
                    else:
                        self.update_status_callback(f"Loaded {total} file(s). Organizing into studies/series...")
                    QApplication.processEvents()
                
                datasets = self.dicom_loader.load_files([file_path], progress_callback=progress_callback)
                
                if not datasets:
                    # Check if there were specific errors
                    failed = self.dicom_loader.get_failed_files()
                    if failed:
                        error_msg = "No DICOM files could be loaded.\n\nErrors:\n"
                        for path, error in failed[:5]:  # Show first 5
                            error_msg += f"\n{os.path.basename(path)}: {error}"
                        if len(failed) > 5:
                            error_msg += f"\n... and {len(failed) - 5} more"
                    else:
                        error_msg = "No DICOM files could be loaded."
                    
                    self.file_dialog.show_error(
                        self.main_window,
                        "Error",
                        error_msg
                    )
                    return None, None
                
                # Organize into studies/series
                try:
                    studies = self.dicom_organizer.organize(datasets, [file_path])
                except MemoryError as e:
                    self.file_dialog.show_error(
                        self.main_window,
                        "Memory Error",
                        f"Out of memory while organizing DICOM files. "
                        f"Try closing other applications or loading fewer files.\n\nError: {str(e)}"
                    )
                    return None, None
                except Exception as e:
                    self.file_dialog.show_error(
                        self.main_window,
                        "Error",
                        f"Error organizing DICOM files: {str(e)}"
                    )
                    return None, None
                
                # Display first slice
                try:
                    self.load_first_slice_callback(studies)
                except MemoryError as e:
                    self.file_dialog.show_error(
                        self.main_window,
                        "Memory Error",
                        f"Out of memory while displaying image. "
                        f"Try closing other applications.\n\nError: {str(e)}"
                    )
                    return None, None
                except Exception as e:
                    self.file_dialog.show_error(
                        self.main_window,
                        "Error",
                    f"Error displaying first slice: {str(e)}"
                )
                    return None, None
                
                # Format and display final status
                final_status = self._format_final_status(studies, len(datasets), source_name)
                
                # Check for compression errors and append guidance if needed
                failed = self.dicom_loader.get_failed_files()
                compression_errors = [f for f in failed if "Compressed DICOM" in f[1] or "pylibjpeg" in f[1].lower()]
                if compression_errors:
                    compression_count = len(compression_errors)
                    final_status += f". {compression_count} compressed file(s) require pylibjpeg: pip install pylibjpeg pyjpegls"
                
                self.update_status_callback(final_status)
                QApplication.processEvents()
                
                return datasets, studies
                
            except MemoryError as e:
                self.file_dialog.show_error(
                    self.main_window,
                    "Memory Error",
                    f"Out of memory while loading file. "
                    f"Try closing other applications or use a system with more memory.\n\nError: {str(e)}"
                )
                return None, None
            except Exception as e:
                error_type = type(e).__name__
                error_msg = f"Error loading file: {str(e)}"
                if error_type not in error_msg:
                    error_msg = f"{error_type}: {error_msg}"
                self.file_dialog.show_error(
                    self.main_window,
                    "Error",
                    error_msg
                )
                return None, None
        else:
            # Open as folder
            source_name = os.path.basename(file_path)
            try:
                # Update status: start loading
                self.update_status_callback(f"Loading files from {source_name}...")
                QApplication.processEvents()
                
                # Create progress callback
                def progress_callback(current: int, total: int, filename: str) -> None:
                    if filename:
                        self.update_status_callback(f"Loading file {current}/{total}: {filename}...")
                    else:
                        self.update_status_callback(f"Loaded {total} file(s). Organizing into studies/series...")
                    QApplication.processEvents()
                
                datasets = self.dicom_loader.load_directory(file_path, recursive=True, progress_callback=progress_callback)
                
                if not datasets:
                    # Check if there were specific errors
                    failed = self.dicom_loader.get_failed_files()
                    if failed:
                        error_msg = f"No DICOM files found in folder.\n\n{len(failed)} file(s) could not be loaded."
                    else:
                        error_msg = "No DICOM files found in folder."
                    
                    self.file_dialog.show_error(
                        self.main_window,
                        "Error",
                        error_msg
                    )
                    return None, None
                
                # Organize
                try:
                    studies = self.dicom_organizer.organize(datasets)
                except MemoryError as e:
                    self.file_dialog.show_error(
                        self.main_window,
                        "Memory Error",
                        f"Out of memory while organizing DICOM files. "
                        f"Try closing other applications or loading fewer files.\n\nError: {str(e)}"
                    )
                    return None, None
                except Exception as e:
                    self.file_dialog.show_error(
                        self.main_window,
                        "Error",
                        f"Error organizing DICOM files: {str(e)}"
                    )
                    return None, None
                
                # Display first slice
                try:
                    self.load_first_slice_callback(studies)
                except MemoryError as e:
                    self.file_dialog.show_error(
                        self.main_window,
                        "Memory Error",
                        f"Out of memory while displaying image. "
                        f"Try closing other applications.\n\nError: {str(e)}"
                    )
                    return None, None
                except Exception as e:
                    self.file_dialog.show_error(
                        self.main_window,
                        "Error",
                    f"Error displaying first slice: {str(e)}"
                )
                    return None, None
                
                # Format and display final status
                final_status = self._format_final_status(studies, len(datasets), source_name)
                self.update_status_callback(final_status)
                QApplication.processEvents()
                
                return datasets, studies
                
            except MemoryError as e:
                self.file_dialog.show_error(
                    self.main_window,
                    "Memory Error",
                    f"Out of memory while loading folder. "
                    f"Try closing other applications or use a system with more memory.\n\nError: {str(e)}"
                )
                return None, None
            except Exception as e:
                error_type = type(e).__name__
                error_msg = f"Error loading folder: {str(e)}"
                if error_type not in error_msg:
                    error_msg = f"{error_type}: {error_msg}"
                self.file_dialog.show_error(
                    self.main_window,
                    "Error",
                    error_msg
                )
                return None, None
    
    def open_paths(self, paths: list[str]) -> tuple[list, dict]:
        """
        Handle open files/folders from drag-and-drop or direct paths.
        
        Args:
            paths: List of file or folder paths to open
            
        Returns:
            Tuple of (datasets list, studies dict) or (None, None) if cancelled/error
        """
        if not paths:
            return None, None
        
        # Separate files and folders
        files = []
        folders = []
        
        for path in paths:
            if not os.path.exists(path):
                continue
            if os.path.isfile(path):
                files.append(path)
            elif os.path.isdir(path):
                folders.append(path)
        
        # Priority: process folders first (if any), then files
        if folders:
            # Process first folder (prioritize folders)
            folder_path = folders[0]
            
            # Clear all ROIs when opening new folder
            self.clear_data_callback()
            
            # Add folder to recent files
            self.config_manager.add_recent_file(folder_path)
            self.main_window.update_recent_menu()
            
            # Format source name for status display
            source_name = os.path.basename(folder_path)
            
            try:
                # Update status: start loading
                self.update_status_callback(f"Loading files from {source_name}...")
                QApplication.processEvents()
                
                # Create progress callback
                def progress_callback(current: int, total: int, filename: str) -> None:
                    if filename:
                        self.update_status_callback(f"Loading file {current}/{total}: {filename}...")
                    else:
                        self.update_status_callback(f"Loaded {total} file(s). Organizing into studies/series...")
                    QApplication.processEvents()
                
                # Load folder (recursive)
                datasets = self.dicom_loader.load_directory(folder_path, recursive=True, progress_callback=progress_callback)
                
                if not datasets:
                    # Check if there were specific errors
                    failed = self.dicom_loader.get_failed_files()
                    if failed:
                        error_msg = f"No DICOM files found in folder.\n\n{len(failed)} file(s) could not be loaded."
                    else:
                        error_msg = "No DICOM files found in folder."
                    
                    self.file_dialog.show_error(
                        self.main_window,
                        "Error",
                        error_msg
                    )
                    return None, None
                
                # Show warnings
                failed = self.dicom_loader.get_failed_files()
                if failed:
                    warning_msg = f"Warning: {len(failed)} file(s) could not be loaded."
                    self.file_dialog.show_warning(self.main_window, "Loading Warnings", warning_msg)
                
                # Organize
                try:
                    studies = self.dicom_organizer.organize(datasets)
                except MemoryError as e:
                    self.file_dialog.show_error(
                        self.main_window,
                        "Memory Error",
                        f"Out of memory while organizing DICOM files. "
                        f"Try closing other applications or loading fewer files.\n\nError: {str(e)}"
                    )
                    return None, None
                except Exception as e:
                    self.file_dialog.show_error(
                        self.main_window,
                        "Error",
                        f"Error organizing DICOM files: {str(e)}"
                    )
                    return None, None
                
                # Display first slice
                try:
                    self.load_first_slice_callback(studies)
                except MemoryError as e:
                    self.file_dialog.show_error(
                        self.main_window,
                        "Memory Error",
                        f"Out of memory while displaying image. "
                        f"Try closing other applications.\n\nError: {str(e)}"
                    )
                    return None, None
                except Exception as e:
                    self.file_dialog.show_error(
                        self.main_window,
                        "Error",
                        f"Error displaying first slice: {str(e)}"
                    )
                    return None, None
                
                # Format and display final status
                final_status = self._format_final_status(studies, len(datasets), source_name)
                self.update_status_callback(final_status)
                QApplication.processEvents()
                
                return datasets, studies
            
            except SystemExit:
                raise  # Don't catch system exit
            except KeyboardInterrupt:
                raise  # Don't catch Ctrl+C
            except MemoryError as e:
                self.file_dialog.show_error(
                    self.main_window,
                    "Memory Error",
                    f"Out of memory while loading folder. "
                    f"Try closing other applications or use a system with more memory.\n\nError: {str(e)}"
                )
                return None, None
            except BaseException as e:
                # Catch everything else including C extension errors that make it to Python
                error_type = type(e).__name__
                error_msg = f"A critical error occurred during folder loading.\n\n"
                error_msg += f"Error: {error_type}: {str(e)}\n\n"
                error_msg += f"This may be due to corrupted or unsupported DICOM files."
                
                print(f"Critical error in open_paths (folder): {error_type}: {e}")
                import traceback
                traceback.print_exc()
                
                self.file_dialog.show_error(
                    self.main_window,
                    "Critical Error",
                    error_msg
                )
                return None, None
        
        elif files:
            # Process all files together
            # Clear all ROIs when opening new files
            self.clear_data_callback()
            
            # Add first file to recent files (representing this file selection)
            if files:
                self.config_manager.add_recent_file(files[0])
                self.main_window.update_recent_menu()
            
            # Format source name for status display
            source_name = self._format_source_name(files)
            
            try:
                # Update status: start loading
                self.update_status_callback(f"Loading files from {source_name}...")
                QApplication.processEvents()
                
                # Create progress callback
                def progress_callback(current: int, total: int, filename: str) -> None:
                    if filename:
                        self.update_status_callback(f"Loading file {current}/{total}: {filename}...")
                    else:
                        self.update_status_callback(f"Loaded {total} file(s). Organizing into studies/series...")
                    QApplication.processEvents()
                
                # Load files
                datasets = self.dicom_loader.load_files(files, progress_callback=progress_callback)
                
                if not datasets:
                    # Check if there were specific errors
                    failed = self.dicom_loader.get_failed_files()
                    if failed:
                        error_msg = "No DICOM files could be loaded.\n\nErrors:\n"
                        for path, error in failed[:5]:  # Show first 5
                            error_msg += f"\n{os.path.basename(path)}: {error}"
                        if len(failed) > 5:
                            error_msg += f"\n... and {len(failed) - 5} more"
                    else:
                        error_msg = "No DICOM files could be loaded."
                    
                    self.file_dialog.show_error(
                        self.main_window,
                        "Error",
                        error_msg
                    )
                    return None, None
                
                # Validate datasets before processing
                # Multi-frame detection kept for potential future use, but no filtering
                validated_datasets = []
                validated_paths = []
                
                for ds, path in zip(datasets, files):
                    validated_datasets.append(ds)
                    validated_paths.append(path)
                
                # Update datasets and paths to validated ones
                datasets = validated_datasets
                files = validated_paths
                
                if not datasets:
                    self.file_dialog.show_error(
                        self.main_window,
                        "No Valid Files",
                        "All selected files were skipped due to safety checks. No files to display."
                    )
                    return None, None
                
                # Show warnings for failed files
                failed = self.dicom_loader.get_failed_files()
                if failed:
                    warning_msg = f"Warning: {len(failed)} file(s) could not be loaded:\n"
                    for path, error in failed[:5]:  # Show first 5
                        warning_msg += f"\n{os.path.basename(path)}: {error}"
                    if len(failed) > 5:
                        warning_msg += f"\n... and {len(failed) - 5} more"
                    
                    self.file_dialog.show_warning(self.main_window, "Loading Warnings", warning_msg)
                
                # Organize into studies/series
                try:
                    studies = self.dicom_organizer.organize(datasets, files)
                except MemoryError as e:
                    self.file_dialog.show_error(
                        self.main_window,
                        "Memory Error",
                        f"Out of memory while organizing DICOM files. "
                        f"Try closing other applications or loading fewer files.\n\nError: {str(e)}"
                    )
                    return None, None
                except Exception as e:
                    self.file_dialog.show_error(
                        self.main_window,
                        "Error",
                        f"Error organizing DICOM files: {str(e)}"
                    )
                    return None, None
                
                # Display first slice
                try:
                    self.load_first_slice_callback(studies)
                except MemoryError as e:
                    self.file_dialog.show_error(
                        self.main_window,
                        "Memory Error",
                        f"Out of memory while displaying image. "
                        f"Try closing other applications.\n\nError: {str(e)}"
                    )
                    return None, None
                except Exception as e:
                    self.file_dialog.show_error(
                        self.main_window,
                        "Error",
                        f"Error displaying first slice: {str(e)}"
                    )
                    return None, None
                
                # Format and display final status
                final_status = self._format_final_status(studies, len(datasets), source_name)
                
                # Check for compression errors and append guidance if needed
                failed = self.dicom_loader.get_failed_files()
                compression_errors = [f for f in failed if "Compressed DICOM" in f[1] or "pylibjpeg" in f[1].lower()]
                if compression_errors:
                    compression_count = len(compression_errors)
                    final_status += f". {compression_count} compressed file(s) require pylibjpeg: pip install pylibjpeg pyjpegls"
                
                self.update_status_callback(final_status)
                QApplication.processEvents()
                
                return datasets, studies
            
            except SystemExit:
                raise  # Don't catch system exit
            except KeyboardInterrupt:
                raise  # Don't catch Ctrl+C
            except MemoryError as e:
                self.file_dialog.show_error(
                    self.main_window,
                    "Memory Error",
                    f"Out of memory while loading files. "
                    f"Try closing other applications or use a system with more memory.\n\nError: {str(e)}"
                )
                return None, None
            except BaseException as e:
                # Catch everything else including C extension errors that make it to Python
                error_type = type(e).__name__
                error_msg = f"A critical error occurred during file loading.\n\n"
                error_msg += f"Error: {error_type}: {str(e)}\n\n"
                error_msg += f"This may be due to corrupted or unsupported DICOM files."
                
                print(f"Critical error in open_paths (files): {error_type}: {e}")
                import traceback
                traceback.print_exc()
                
                self.file_dialog.show_error(
                    self.main_window,
                    "Critical Error",
                    error_msg
                )
                return None, None
        
        # No valid files or folders
        return None, None
    
    def load_first_slice(self, studies: dict) -> dict:
        """
        Load and return information about the first slice.
        
        Args:
            studies: Dictionary of organized studies/series
            
        Returns:
            Dictionary with first slice information: study_uid, series_uid, slice_index, dataset
            or None if no studies available
        """
        if not studies:
            return None
        
        # Get first study
        study_uid = list(studies.keys())[0]
        
        # Get all series for this study and sort by SeriesNumber
        series_list = []
        for series_uid, datasets in studies[study_uid].items():
            if datasets:
                # Extract SeriesNumber from first dataset
                first_dataset = datasets[0]
                series_number = getattr(first_dataset, 'SeriesNumber', None)
                # Convert to int if possible, otherwise use 0 (or a large number to put at end)
                try:
                    series_num = int(series_number) if series_number is not None else 0
                except (ValueError, TypeError):
                    series_num = 0
                series_list.append((series_num, series_uid, datasets))
        
        # Sort by SeriesNumber (ascending)
        series_list.sort(key=lambda x: x[0])
        
        # Select series with lowest SeriesNumber (first in sorted list)
        if not series_list:
            return None
        
        _, series_uid, datasets = series_list[0]
        
        if not datasets:
            return None
        
        # Return the first slice information
        return {
            'study_uid': study_uid,
            'series_uid': series_uid,
            'slice_index': 0,
            'dataset': datasets[0],
            'total_slices': len(datasets)
        }

