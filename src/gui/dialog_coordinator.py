"""
Dialog Coordinator

This module manages all dialog operations.

Inputs:
    - Dialog open requests
    - Settings changes
    
Outputs:
    - Dialog displays
    - Settings updates
    
Requirements:
    - Various dialog classes
    - ConfigManager for configuration
"""

from typing import Optional, Callable
from gui.dialogs.settings_dialog import SettingsDialog
from gui.dialogs.tag_viewer_dialog import TagViewerDialog
from gui.dialogs.overlay_config_dialog import OverlayConfigDialog
from gui.dialogs.tag_export_dialog import TagExportDialog
from gui.dialogs.quick_start_guide_dialog import QuickStartGuideDialog
from gui.main_window import MainWindow
from utils.config_manager import ConfigManager
from PySide6.QtWidgets import QMessageBox


class DialogCoordinator:
    """
    Manages all dialog operations.
    
    Responsibilities:
    - Open settings dialog
    - Open tag viewer dialog
    - Open overlay config dialog
    - Open quick start guide dialog
    - Open tag export dialog
    - Handle settings applied
    """
    
    def __init__(
        self,
        config_manager: ConfigManager,
        main_window: MainWindow,
        get_current_studies: Callable[[], dict],
        settings_applied_callback: Optional[Callable[[], None]] = None,
        overlay_config_applied_callback: Optional[Callable[[], None]] = None
    ):
        """
        Initialize the dialog coordinator.
        
        Args:
            config_manager: Configuration manager
            main_window: Main window for dialogs
            get_current_studies: Callback to get current studies
            settings_applied_callback: Optional callback when settings are applied
            overlay_config_applied_callback: Optional callback when overlay config is applied
        """
        self.config_manager = config_manager
        self.main_window = main_window
        self.get_current_studies = get_current_studies
        self.settings_applied_callback = settings_applied_callback
        self.overlay_config_applied_callback = overlay_config_applied_callback
        
        # Tag viewer dialog (persistent)
        self.tag_viewer_dialog: Optional[TagViewerDialog] = None
    
    def open_settings(self) -> None:
        """Handle settings dialog request."""
        dialog = SettingsDialog(self.config_manager, self.main_window)
        if self.settings_applied_callback:
            dialog.settings_applied.connect(self.settings_applied_callback)
        dialog.exec()
    
    def open_tag_viewer(self, current_dataset=None) -> None:
        """
        Handle tag viewer dialog request.
        
        Args:
            current_dataset: Optional current dataset to display
        """
        if self.tag_viewer_dialog is None:
            self.tag_viewer_dialog = TagViewerDialog(self.main_window)
        
        # Update with current dataset if available
        if current_dataset is not None:
            self.tag_viewer_dialog.set_dataset(current_dataset)
        
        # Show dialog (brings to front if already open)
        self.tag_viewer_dialog.show()
        self.tag_viewer_dialog.raise_()
        self.tag_viewer_dialog.activateWindow()
    
    def open_overlay_config(self) -> None:
        """Handle overlay configuration dialog request."""
        dialog = OverlayConfigDialog(self.config_manager, self.main_window)
        if self.overlay_config_applied_callback:
            dialog.config_applied.connect(self.overlay_config_applied_callback)
        dialog.exec()
    
    def open_quick_start_guide(self) -> None:
        """Handle Quick Start Guide dialog request."""
        dialog = QuickStartGuideDialog(self.config_manager, self.main_window)
        dialog.exec()
    
    def open_tag_export(self) -> None:
        """Handle Tag Export dialog request."""
        # Check if any studies are loaded
        current_studies = self.get_current_studies()
        if not current_studies:
            QMessageBox.warning(
                self.main_window,
                "No Data Loaded",
                "Please load DICOM files before exporting tags."
            )
            return
        
        dialog = TagExportDialog(current_studies, self.config_manager, self.main_window)
        dialog.exec()
    
    def handle_settings_applied(self) -> None:
        """Handle settings being applied."""
        # This will be handled by the callback if provided
        pass
    
    def update_tag_viewer(self, dataset) -> None:
        """
        Update tag viewer with new dataset.
        
        Args:
            dataset: DICOM dataset to display
        """
        if self.tag_viewer_dialog is not None and self.tag_viewer_dialog.isVisible():
            self.tag_viewer_dialog.set_dataset(dataset)

