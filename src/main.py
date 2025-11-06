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
from PySide6.QtCore import Qt, QPointF
from PySide6.QtGui import QKeyEvent
from typing import Optional
import pydicom
from pydicom.dataset import Dataset

from gui.main_window import MainWindow
from gui.dialogs.file_dialog import FileDialog
from gui.dialogs.settings_dialog import SettingsDialog
from gui.dialogs.tag_viewer_dialog import TagViewerDialog
from gui.dialogs.overlay_config_dialog import OverlayConfigDialog
from gui.image_viewer import ImageViewer
from gui.metadata_panel import MetadataPanel
from gui.window_level_controls import WindowLevelControls
from gui.roi_statistics_panel import ROIStatisticsPanel
from gui.roi_list_panel import ROIListPanel
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


class DICOMViewerApp(QApplication):
    """
    Main application class for DICOM Viewer.
    
    Coordinates all components and handles application logic.
    """
    
    def __init__(self):
        """Initialize the application."""
        # Initialize managers
        self.config_manager = ConfigManager()
        self.dicom_loader = DICOMLoader()
        self.dicom_organizer = DICOMOrganizer()
        self.dicom_processor = DICOMProcessor()
        
        # Create main window
        self.main_window = MainWindow(self.config_manager)
        
        # Install event filter on main window for key events
        self.main_window.installEventFilter(self)
        
        # Create components
        self.file_dialog = FileDialog(self.config_manager)
        self.image_viewer = ImageViewer()
        self.metadata_panel = MetadataPanel()
        self.window_level_controls = WindowLevelControls()
        self.slice_navigator = SliceNavigator()
        self.roi_manager = ROIManager()
        self.measurement_tool = MeasurementTool()
        self.roi_statistics_panel = ROIStatisticsPanel()
        self.roi_list_panel = ROIListPanel()
        self.roi_list_panel.set_roi_manager(self.roi_manager)
        
        # Initialize overlay manager with config settings
        font_size = self.config_manager.get_overlay_font_size()
        font_color = self.config_manager.get_overlay_font_color()
        self.overlay_manager = OverlayManager(
            font_size=font_size, 
            font_color=font_color,
            config_manager=self.config_manager
        )
        
        # Set scroll wheel mode
        scroll_mode = self.config_manager.get_scroll_wheel_mode()
        self.image_viewer.set_scroll_wheel_mode(scroll_mode)
        self.slice_navigator.set_scroll_wheel_mode(scroll_mode)
        
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
        self.current_dataset: Optional[Dataset] = None
        
        # Tag viewer dialog (persistent)
        self.tag_viewer_dialog: Optional[TagViewerDialog] = None
    
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
        right_layout.addWidget(self.roi_list_panel)
        right_layout.addWidget(self.roi_statistics_panel)
    
    def _connect_signals(self) -> None:
        """Connect signals between components."""
        # File operations
        self.main_window.open_file_requested.connect(self._open_files)
        self.main_window.open_folder_requested.connect(self._open_folder)
        
        # Settings
        self.main_window.settings_requested.connect(self._open_settings)
        
        # Tag viewer
        self.main_window.tag_viewer_requested.connect(self._open_tag_viewer)
        
        # Overlay configuration
        self.main_window.overlay_config_requested.connect(self._open_overlay_config)
        
        # ROI tools
        self.main_window.roi_rectangle_action.triggered.connect(
            lambda: self._set_roi_mode("rectangle")
        )
        self.main_window.roi_ellipse_action.triggered.connect(
            lambda: self._set_roi_mode("ellipse")
        )
        self.main_window.roi_none_action.triggered.connect(
            lambda: self._set_roi_mode(None)
        )
        
        # ROI drawing signals
        self.image_viewer.roi_drawing_started.connect(self._on_roi_drawing_started)
        self.image_viewer.roi_drawing_updated.connect(self._on_roi_drawing_updated)
        self.image_viewer.roi_drawing_finished.connect(self._on_roi_drawing_finished)
        
        # ROI click signal
        self.image_viewer.roi_clicked.connect(self._on_roi_clicked)
        
        # ROI list panel signals
        self.roi_list_panel.roi_selected.connect(self._on_roi_selected)
        self.roi_list_panel.roi_deleted.connect(self._on_roi_deleted)
        
        # Monitor ROI item changes for movement
        self.image_viewer.scene.selectionChanged.connect(self._on_scene_selection_changed)
        
        # Scroll wheel for slice navigation
        self.image_viewer.wheel_event_for_slice.connect(
            lambda delta: self.slice_navigator.handle_wheel_event(delta)
        )
        
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
            # Store current dataset
            self.current_dataset = dataset
            
            # Convert to image
            image = self.dicom_processor.dataset_to_image(dataset)
            if image is None:
                return
            
            # Set image in viewer
            self.image_viewer.set_image(image)
            
            # Update metadata panel
            self.metadata_panel.set_dataset(dataset)
            
            # Update tag viewer if open
            if self.tag_viewer_dialog is not None and self.tag_viewer_dialog.isVisible():
                self.tag_viewer_dialog.set_dataset(dataset)
            
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
            
            # Display ROIs for current slice
            self._display_rois_for_slice(self.current_slice_index)
        
        except Exception as e:
            self.main_window.update_status(f"Error displaying slice: {str(e)}")
    
    def _display_rois_for_slice(self, slice_index: int) -> None:
        """
        Display ROIs for a slice.
        
        Args:
            slice_index: Slice index
        """
        rois = self.roi_manager.get_rois_for_slice(slice_index)
        for roi in rois:
            # Add ROI item to scene if not already there
            if roi.item.scene() != self.image_viewer.scene:
                self.image_viewer.scene.addItem(roi.item)
    
    def _open_settings(self) -> None:
        """Handle settings dialog request."""
        dialog = SettingsDialog(self.config_manager, self.main_window)
        dialog.settings_applied.connect(self._on_settings_applied)
        dialog.exec()
    
    def _open_tag_viewer(self) -> None:
        """Handle tag viewer dialog request."""
        if self.tag_viewer_dialog is None:
            self.tag_viewer_dialog = TagViewerDialog(self.main_window)
        
        # Update with current dataset if available
        if self.current_dataset is not None:
            self.tag_viewer_dialog.set_dataset(self.current_dataset)
        
        # Show dialog (brings to front if already open)
        self.tag_viewer_dialog.show()
        self.tag_viewer_dialog.raise_()
        self.tag_viewer_dialog.activateWindow()
    
    def _open_overlay_config(self) -> None:
        """Handle overlay configuration dialog request."""
        dialog = OverlayConfigDialog(self.config_manager, self.main_window)
        dialog.config_applied.connect(self._on_overlay_config_applied)
        dialog.exec()
    
    def _on_overlay_config_applied(self) -> None:
        """Handle overlay configuration being applied."""
        # Recreate overlay if we have a current dataset
        if self.current_studies and self.current_series_uid:
            datasets = self.current_studies[self.current_study_uid][self.current_series_uid]
            if self.current_slice_index < len(datasets):
                dataset = datasets[self.current_slice_index]
                parser = DICOMParser(dataset)
                self.overlay_manager.create_overlay_items(
                    self.image_viewer.scene,
                    parser
                )
    
    def _on_settings_applied(self) -> None:
        """Handle settings being applied."""
        # Update overlay manager with new settings
        font_size = self.config_manager.get_overlay_font_size()
        font_color = self.config_manager.get_overlay_font_color()
        self.overlay_manager.set_font_size(font_size)
        self.overlay_manager.set_font_color(*font_color)
        
        # Recreate overlay if we have a current dataset
        if self.current_studies and self.current_series_uid:
            datasets = self.current_studies[self.current_study_uid][self.current_series_uid]
            if self.current_slice_index < len(datasets):
                dataset = datasets[self.current_slice_index]
                parser = DICOMParser(dataset)
                self.overlay_manager.create_overlay_items(
                    self.image_viewer.scene,
                    parser
                )
    
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
                    # Recreate overlay to ensure it stays on top
                    parser = DICOMParser(dataset)
                    self.overlay_manager.create_overlay_items(
                        self.image_viewer.scene,
                        parser
                    )
    
    def _set_roi_mode(self, mode: Optional[str]) -> None:
        """
        Set ROI drawing mode.
        
        Args:
            mode: "rectangle", "ellipse", or None
        """
        self.image_viewer.set_roi_drawing_mode(mode)
    
    def _on_roi_drawing_started(self, pos: QPointF) -> None:
        """
        Handle ROI drawing start.
        
        Args:
            pos: Starting position
        """
        self.roi_manager.set_current_slice(self.current_slice_index)
        self.roi_manager.start_drawing(pos, self.image_viewer.roi_drawing_mode)
    
    def _on_roi_drawing_updated(self, pos: QPointF) -> None:
        """
        Handle ROI drawing update.
        
        Args:
            pos: Current position
        """
        self.roi_manager.update_drawing(pos, self.image_viewer.scene)
    
    def _on_roi_drawing_finished(self) -> None:
        """Handle ROI drawing finish."""
        roi_item = self.roi_manager.finish_drawing()
        
        # Update ROI list
        self.roi_list_panel.update_roi_list(self.current_slice_index)
        
        # Calculate and display statistics if ROI was created
        if roi_item is not None and self.current_dataset is not None:
            try:
                pixel_array = self.dicom_processor.get_pixel_array(self.current_dataset)
                if pixel_array is not None:
                    stats = self.roi_manager.calculate_statistics(roi_item, pixel_array)
                    self.roi_statistics_panel.update_statistics(stats)
            except Exception as e:
                print(f"Error calculating ROI statistics: {e}")
    
    def _on_roi_clicked(self, item) -> None:
        """
        Handle ROI click.
        
        Args:
            item: QGraphicsItem that was clicked
        """
        roi = self.roi_manager.find_roi_by_item(item)
        if roi:
            self.roi_manager.select_roi(roi)
            self.roi_list_panel.select_roi_in_list(roi)
            self._update_roi_statistics(roi)
    
    def _on_roi_selected(self, roi) -> None:
        """
        Handle ROI selection from list.
        
        Args:
            roi: Selected ROI item
        """
        self._update_roi_statistics(roi)
    
    def _on_roi_deleted(self, roi) -> None:
        """
        Handle ROI deletion.
        
        Args:
            roi: Deleted ROI item
        """
        # Clear statistics if this was the selected ROI
        if self.roi_manager.get_selected_roi() is None:
            self.roi_statistics_panel.clear_statistics()
    
    def _on_scene_selection_changed(self) -> None:
        """Handle scene selection change (e.g., when ROI is moved)."""
        selected_items = self.image_viewer.scene.selectedItems()
        if selected_items:
            # Find ROI for selected item
            for item in selected_items:
                roi = self.roi_manager.find_roi_by_item(item)
                if roi:
                    # Update statistics when ROI is moved/selected
                    self._update_roi_statistics(roi)
                    # Update list panel selection
                    self.roi_list_panel.select_roi_in_list(roi)
                    break
    
    def _update_roi_statistics(self, roi) -> None:
        """
        Update statistics panel for a ROI.
        
        Args:
            roi: ROI item
        """
        if roi is None or self.current_dataset is None:
            return
        
        try:
            pixel_array = self.dicom_processor.get_pixel_array(self.current_dataset)
            if pixel_array is not None:
                stats = self.roi_manager.calculate_statistics(roi, pixel_array)
                self.roi_statistics_panel.update_statistics(stats)
        except Exception as e:
            print(f"Error calculating ROI statistics: {e}")
    
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
            
            # Update ROI manager for current slice
            self.roi_manager.set_current_slice(slice_index)
            
            # Update ROI list panel
            self.roi_list_panel.update_roi_list(slice_index)
            
            # Display ROIs for this slice
            self._display_rois_for_slice(slice_index)
    
    def run(self) -> int:
        """
        Run the application.
        
        Returns:
            Exit code
        """
        self.main_window.show()
        return self.exec()


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

