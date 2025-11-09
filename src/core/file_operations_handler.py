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
        
        try:
            # Load files
            datasets = self.dicom_loader.load_files(file_paths)
            
            if not datasets:
                self.file_dialog.show_error(
                    self.main_window,
                    "Error",
                    "No DICOM files could be loaded."
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
            studies = self.dicom_organizer.organize(datasets, file_paths)
            
            # Display first slice
            self.load_first_slice_callback(studies)
            
            self.update_status_callback(f"Loaded {len(datasets)} DICOM file(s)")
            
            return datasets, studies
        
        except Exception as e:
            self.file_dialog.show_error(
                self.main_window,
                "Error",
                f"Error loading files: {str(e)}"
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
        
        try:
            # Load folder (recursive)
            datasets = self.dicom_loader.load_directory(folder_path, recursive=True)
            
            if not datasets:
                self.file_dialog.show_error(
                    self.main_window,
                    "Error",
                    "No DICOM files found in folder."
                )
                return None, None
            
            # Show warnings
            failed = self.dicom_loader.get_failed_files()
            if failed:
                warning_msg = f"Warning: {len(failed)} file(s) could not be loaded."
                self.file_dialog.show_warning(self.main_window, "Loading Warnings", warning_msg)
            
            # Organize
            studies = self.dicom_organizer.organize(datasets)
            
            # Display first slice
            self.load_first_slice_callback(studies)
            
            self.update_status_callback(f"Loaded {len(datasets)} DICOM file(s) from folder")
            
            return datasets, studies
        
        except Exception as e:
            self.file_dialog.show_error(
                self.main_window,
                "Error",
                f"Error loading folder: {str(e)}"
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
            try:
                datasets = self.dicom_loader.load_files([file_path])
                
                if not datasets:
                    self.file_dialog.show_error(
                        self.main_window,
                        "Error",
                        "No DICOM files could be loaded."
                    )
                    return None, None
                
                # Organize into studies/series
                studies = self.dicom_organizer.organize(datasets, [file_path])
                
                # Display first slice
                self.load_first_slice_callback(studies)
                
                self.update_status_callback(f"Loaded {len(datasets)} DICOM file(s)")
                
                return datasets, studies
                
            except Exception as e:
                self.file_dialog.show_error(
                    self.main_window,
                    "Error",
                    f"Error loading file: {str(e)}"
                )
                return None, None
        else:
            # Open as folder
            try:
                datasets = self.dicom_loader.load_directory(file_path, recursive=True)
                
                if not datasets:
                    self.file_dialog.show_error(
                        self.main_window,
                        "Error",
                        "No DICOM files found in folder."
                    )
                    return None, None
                
                # Organize
                studies = self.dicom_organizer.organize(datasets)
                
                # Display first slice
                self.load_first_slice_callback(studies)
                
                self.update_status_callback(f"Loaded {len(datasets)} DICOM file(s) from folder")
                
                return datasets, studies
                
            except Exception as e:
                self.file_dialog.show_error(
                    self.main_window,
                    "Error",
                    f"Error loading folder: {str(e)}"
                )
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

