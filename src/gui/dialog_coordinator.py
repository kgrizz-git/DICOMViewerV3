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

from typing import Optional, Callable, Any
from gui.dialogs.settings_dialog import SettingsDialog
from gui.dialogs.overlay_settings_dialog import OverlaySettingsDialog
from gui.dialogs.tag_viewer_dialog import TagViewerDialog
from gui.dialogs.overlay_config_dialog import OverlayConfigDialog
from gui.dialogs.annotation_options_dialog import AnnotationOptionsDialog
from gui.dialogs.tag_export_dialog import TagExportDialog
from gui.dialogs.export_dialog import ExportDialog
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
    - Open export dialog
    - Handle settings applied
    """
    
    def __init__(
        self,
        config_manager: ConfigManager,
        main_window: MainWindow,
        get_current_studies: Callable[[], dict],
        settings_applied_callback: Optional[Callable[[], None]] = None,
        overlay_config_applied_callback: Optional[Callable[[], None]] = None,
        tag_edit_history: Optional[Any] = None
    ):
        """
        Initialize the dialog coordinator.
        
        Args:
            config_manager: Configuration manager
            main_window: Main window for dialogs
            get_current_studies: Callback to get current studies
            settings_applied_callback: Optional callback when settings are applied
            overlay_config_applied_callback: Optional callback when overlay config is applied
            tag_edit_history: Optional TagEditHistoryManager for tag editing undo/redo
        """
        self.config_manager = config_manager
        self.main_window = main_window
        self.get_current_studies = get_current_studies
        self.settings_applied_callback = settings_applied_callback
        self.overlay_config_applied_callback = overlay_config_applied_callback
        self.annotation_options_applied_callback = None  # Will be set from main.py
        self.tag_edit_history = tag_edit_history
        
        # Tag viewer dialog (persistent)
        self.tag_viewer_dialog: Optional[TagViewerDialog] = None
    
    def open_settings(self) -> None:
        """Handle settings dialog request."""
        dialog = SettingsDialog(self.config_manager, self.main_window)
        if self.settings_applied_callback:
            dialog.settings_applied.connect(self.settings_applied_callback)
        dialog.exec()
    
    def open_overlay_settings(self) -> None:
        """Handle overlay settings dialog request."""
        dialog = OverlaySettingsDialog(self.config_manager, self.main_window)
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
            # Set history manager if available
            if self.tag_edit_history is not None:
                self.tag_viewer_dialog.set_history_manager(self.tag_edit_history)
        
        # Update with current dataset if available
        if current_dataset is not None:
            self.tag_viewer_dialog.set_dataset(current_dataset)
        
        # Show dialog (brings to front if already open)
        self.tag_viewer_dialog.show()
        self.tag_viewer_dialog.raise_()
        self.tag_viewer_dialog.activateWindow()
    
    def open_overlay_config(self, current_modality: Optional[str] = None) -> None:
        """
        Handle overlay configuration dialog request.
        
        Args:
            current_modality: Optional current modality from loaded DICOM image.
                             If provided, the dialog will open to this modality.
                             If None or invalid, defaults to "default"
        """
        dialog = OverlayConfigDialog(self.config_manager, self.main_window, initial_modality=current_modality)
        if self.overlay_config_applied_callback:
            dialog.config_applied.connect(self.overlay_config_applied_callback)
        dialog.exec()
    
    def open_annotation_options(self) -> None:
        """Handle annotation options dialog request."""
        dialog = AnnotationOptionsDialog(self.config_manager, self.main_window)
        if self.annotation_options_applied_callback:
            dialog.settings_applied.connect(self.annotation_options_applied_callback)
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
    
    def open_export(
        self,
        current_window_center: Optional[float] = None,
        current_window_width: Optional[float] = None,
        current_zoom: Optional[float] = None,
        use_rescaled_values: bool = False,
        roi_manager=None,
        overlay_manager=None,
        measurement_tool=None
    ) -> None:
        """
        Handle Export dialog request.
        
        Args:
            current_window_center: Optional current window center from viewer
            current_window_width: Optional current window width from viewer
            current_zoom: Optional current zoom level from viewer
            use_rescaled_values: Whether to use rescaled values (matches viewer setting)
            roi_manager: Optional ROI manager for rendering ROIs
            overlay_manager: Optional overlay manager for rendering overlays
            measurement_tool: Optional measurement tool for rendering measurements
        """
        # Check if any studies are loaded
        current_studies = self.get_current_studies()
        if not current_studies:
            QMessageBox.warning(
                self.main_window,
                "No Data Loaded",
                "Please load DICOM files before exporting images."
            )
            return
        
        dialog = ExportDialog(
            current_studies,
            current_window_center=current_window_center,
            current_window_width=current_window_width,
            current_zoom=current_zoom,
            use_rescaled_values=use_rescaled_values,
            roi_manager=roi_manager,
            overlay_manager=overlay_manager,
            measurement_tool=measurement_tool,
            config_manager=self.config_manager,
            parent=self.main_window
        )
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
    
    def clear_tag_viewer_filter(self) -> None:
        """
        Clear the filter in the tag viewer dialog.
        Called when files are closed or new files are opened.
        """
        if self.tag_viewer_dialog is not None:
            self.tag_viewer_dialog.clear_filter()

