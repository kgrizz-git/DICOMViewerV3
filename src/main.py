"""
DICOM Viewer V2 - Main Application Entry Point

This module is the main entry point for the DICOM viewer application.
It initializes the application, creates the main window, and sets up
the application event loop.

Inputs:
    - Command line arguments (optional)
    
Outputs:
    - Running DICOM viewer application
    
Requirements:
    - PySide6 for application framework
    - All other application modules
"""

import sys
import os
from pathlib import Path

# Add src directory to path
src_dir = Path(__file__).parent
sys.path.insert(0, str(src_dir))

from PySide6.QtWidgets import QApplication, QMessageBox
from PySide6.QtCore import Qt

from gui.main_window import MainWindow
from gui.dialogs.file_dialog import FileDialog
from gui.image_viewer import ImageViewer
from gui.metadata_panel import MetadataPanel
from gui.window_level_controls import WindowLevelControls
from gui.slice_navigator import SliceNavigator
from core.dicom_loader import DICOMLoader
from core.dicom_organizer import DICOMOrganizer
from core.dicom_parser import DICOMParser
from core.dicom_processor import DICOMProcessor
from utils.config_manager import ConfigManager
from tools.roi_manager import ROIManager
from tools.measurement_tool import MeasurementTool
from tools.histogram_widget import HistogramWidget
from gui.overlay_manager import OverlayManager


class DICOMViewerApp:
    """
    Main application class for DICOM Viewer.
    
    Coordinates all components and handles application logic.
    """
    
    def __init__(self):
        """Initialize the application."""
        # Create Qt application
        self.app = QApplication(sys.argv)
        self.app.setApplicationName("DICOM Viewer V2")
        
        # Initialize managers
        self.config_manager = ConfigManager()
        self.dicom_loader = DICOMLoader()
        self.dicom_organizer = DICOMOrganizer()
        self.dicom_processor = DICOMProcessor()
        
        # Create main window
        self.main_window = MainWindow(self.config_manager)
        
        # Create components
        self.file_dialog = FileDialog(self.config_manager)
        self.image_viewer = ImageViewer()
        self.metadata_panel = MetadataPanel()
        self.window_level_controls = WindowLevelControls()
        self.slice_navigator = SliceNavigator()
        self.roi_manager = ROIManager()
        self.measurement_tool = MeasurementTool()
        self.overlay_manager = OverlayManager()
        
        # Set up UI layout
        self._setup_ui()
        
        # Connect signals
        self._connect_signals()
        
        # Current data
        self.current_datasets: list = []
        self.current_studies: dict = {}
        self.current_slice_index = 0
        self.current_series_uid = ""
        self.current_study_uid = ""
    
    def _setup_ui(self) -> None:
        """Set up the user interface layout."""
        # Add image viewer to center panel
        center_layout = self.main_window.center_panel.layout()
        if center_layout is None:
            from PySide6.QtWidgets import QVBoxLayout
            center_layout = QVBoxLayout(self.main_window.center_panel)
        center_layout.addWidget(self.image_viewer)
        
        # Add metadata panel to left panel
        left_layout = self.main_window.left_panel.layout()
        if left_layout is None:
            from PySide6.QtWidgets import QVBoxLayout
            left_layout = QVBoxLayout(self.main_window.left_panel)
        left_layout.addWidget(self.metadata_panel)
        
        # Add controls to right panel
        right_layout = self.main_window.right_panel.layout()
        if right_layout is None:
            from PySide6.QtWidgets import QVBoxLayout
            right_layout = QVBoxLayout(self.main_window.right_panel)
        right_layout.addWidget(self.window_level_controls)
    
    def _connect_signals(self) -> None:
        """Connect signals between components."""
        # File operations
        self.main_window.open_file_requested.connect(self._open_files)
        self.main_window.open_folder_requested.connect(self._open_folder)
        
        # Window/level
        self.window_level_controls.window_changed.connect(self._on_window_changed)
        
        # Slice navigation
        self.slice_navigator.slice_changed.connect(self._on_slice_changed)
    
    def _open_files(self) -> None:
        """Handle open files request."""
        file_paths = self.file_dialog.open_files(self.main_window)
        if not file_paths:
            return
        
        try:
            # Load files
            datasets = self.dicom_loader.load_files(file_paths)
            
            if not datasets:
                self.file_dialog.show_error(
                    self.main_window,
                    "Error",
                    "No DICOM files could be loaded."
                )
                return
            
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
            self.current_datasets = datasets
            self.current_studies = self.dicom_organizer.organize(datasets, file_paths)
            
            # Display first slice
            self._load_first_slice()
            
            self.main_window.update_status(f"Loaded {len(datasets)} DICOM file(s)")
        
        except Exception as e:
            self.file_dialog.show_error(
                self.main_window,
                "Error",
                f"Error loading files: {str(e)}"
            )
    
    def _open_folder(self) -> None:
        """Handle open folder request."""
        folder_path = self.file_dialog.open_folder(self.main_window)
        if not folder_path:
            return
        
        try:
            # Load folder (recursive)
            datasets = self.dicom_loader.load_directory(folder_path, recursive=True)
            
            if not datasets:
                self.file_dialog.show_error(
                    self.main_window,
                    "Error",
                    "No DICOM files found in folder."
                )
                return
            
            # Show warnings
            failed = self.dicom_loader.get_failed_files()
            if failed:
                warning_msg = f"Warning: {len(failed)} file(s) could not be loaded."
                self.file_dialog.show_warning(self.main_window, "Loading Warnings", warning_msg)
            
            # Organize
            self.current_datasets = datasets
            self.current_studies = self.dicom_organizer.organize(datasets)
            
            # Display first slice
            self._load_first_slice()
            
            self.main_window.update_status(f"Loaded {len(datasets)} DICOM file(s) from folder")
        
        except Exception as e:
            self.file_dialog.show_error(
                self.main_window,
                "Error",
                f"Error loading folder: {str(e)}"
            )
    
    def _load_first_slice(self) -> None:
        """Load and display the first slice."""
        if not self.current_studies:
            return
        
        # Get first study and series
        study_uid = list(self.current_studies.keys())[0]
        series_uid = list(self.current_studies[study_uid].keys())[0]
        datasets = self.current_studies[study_uid][series_uid]
        
        if not datasets:
            return
        
        self.current_study_uid = study_uid
        self.current_series_uid = series_uid
        self.current_slice_index = 0
        
        # Set up slice navigator
        self.slice_navigator.set_total_slices(len(datasets))
        self.slice_navigator.set_current_slice(0)
        
        # Display slice
        self._display_slice(datasets[0])
    
    def _display_slice(self, dataset) -> None:
        """
        Display a DICOM slice.
        
        Args:
            dataset: pydicom Dataset
        """
        try:
            # Convert to image
            image = self.dicom_processor.dataset_to_image(dataset)
            if image is None:
                return
            
            # Set image in viewer
            self.image_viewer.set_image(image)
            
            # Update metadata panel
            self.metadata_panel.set_dataset(dataset)
            
            # Update window/level controls
            wc, ww = self.dicom_processor.get_window_level_from_dataset(dataset)
            if wc is not None and ww is not None:
                self.window_level_controls.set_window_level(wc, ww)
            
            # Update overlay
            parser = DICOMParser(dataset)
            self.overlay_manager.create_overlay_items(
                self.image_viewer.scene,
                parser
            )
        
        except Exception as e:
            self.main_window.update_status(f"Error displaying slice: {str(e)}")
    
    def _on_window_changed(self, center: float, width: float) -> None:
        """
        Handle window/level change.
        
        Args:
            center: Window center
            width: Window width
        """
        # Re-display current slice with new window/level
        if self.current_studies and self.current_series_uid:
            datasets = self.current_studies[self.current_study_uid][self.current_series_uid]
            if self.current_slice_index < len(datasets):
                dataset = datasets[self.current_slice_index]
                image = self.dicom_processor.dataset_to_image(
                    dataset,
                    window_center=center,
                    window_width=width
                )
                if image:
                    self.image_viewer.set_image(image)
    
    def _on_slice_changed(self, slice_index: int) -> None:
        """
        Handle slice index change.
        
        Args:
            slice_index: New slice index
        """
        if not self.current_studies or not self.current_series_uid:
            return
        
        datasets = self.current_studies[self.current_study_uid][self.current_series_uid]
        if 0 <= slice_index < len(datasets):
            self.current_slice_index = slice_index
            self._display_slice(datasets[slice_index])
    
    def run(self) -> int:
        """
        Run the application.
        
        Returns:
            Exit code
        """
        self.main_window.show()
        return self.app.exec()


def main():
    """Main entry point."""
    try:
        app = DICOMViewerApp()
        return app.run()
    except Exception as e:
        print(f"Fatal error: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())

