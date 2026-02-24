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

from typing import Optional, Callable, Any, Dict
from gui.dialogs.settings_dialog import SettingsDialog
from gui.dialogs.overlay_settings_dialog import OverlaySettingsDialog
from gui.dialogs.tag_viewer_dialog import TagViewerDialog
from gui.dialogs.overlay_config_dialog import OverlayConfigDialog
from gui.dialogs.annotation_options_dialog import AnnotationOptionsDialog
from gui.dialogs.tag_export_dialog import TagExportDialog
from gui.dialogs.export_dialog import ExportDialog
from gui.dialogs.quick_start_guide_dialog import QuickStartGuideDialog
from gui.dialogs.histogram_dialog import HistogramDialog
from gui.dialogs.about_this_file_dialog import AboutThisFileDialog
from gui.dialogs.fusion_technical_doc_dialog import FusionTechnicalDocDialog
from gui.main_window import MainWindow
from utils.config_manager import ConfigManager
from PySide6.QtWidgets import QMessageBox
from pydicom.dataset import Dataset


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
        tag_edit_history: Optional[Any] = None,
        get_histogram_callbacks_for_subwindow: Optional[Callable[[int], dict]] = None,
        get_focused_subwindow_index: Optional[Callable[[], int]] = None,
        undo_redo_manager: Optional[Any] = None,
        ui_refresh_callback: Optional[Callable[[], None]] = None
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
            get_histogram_callbacks_for_subwindow: Callback (idx) -> dict of callbacks for that subwindow's histogram
            get_focused_subwindow_index: Callback to get currently focused subwindow index (0-3)
        """
        self.config_manager = config_manager
        self.main_window = main_window
        self.get_current_studies = get_current_studies
        self.settings_applied_callback = settings_applied_callback
        self.undo_redo_manager = undo_redo_manager
        self.ui_refresh_callback = ui_refresh_callback
        self.overlay_config_applied_callback = overlay_config_applied_callback
        self.annotation_options_applied_callback = None  # Will be set from main.py
        self.tag_edit_history = tag_edit_history
        self.tag_edited_callback = None  # Will be set from main.py to handle tag edits
        
        # Per-subwindow histogram dialogs (up to 4, keyed by subwindow index)
        self.get_histogram_callbacks_for_subwindow = get_histogram_callbacks_for_subwindow
        self.get_focused_subwindow_index = get_focused_subwindow_index
        self.histogram_dialogs: Dict[int, Optional[HistogramDialog]] = {}
        
        # Tag viewer dialog (persistent)
        self.tag_viewer_dialog: Optional[TagViewerDialog] = None
        # About this File dialog (persistent)
        self.about_this_file_dialog: Optional[AboutThisFileDialog] = None
    
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
    
    def open_tag_viewer(self, current_dataset=None, privacy_mode: bool = False) -> None:
        """
        Handle tag viewer dialog request.
        
        Args:
            current_dataset: Optional current dataset to display
            privacy_mode: Whether privacy mode is enabled
        """
        if self.tag_viewer_dialog is None:
            self.tag_viewer_dialog = TagViewerDialog(self.main_window, 
                                                      undo_redo_manager=self.undo_redo_manager)
            # Set history manager if available (for tracking edited tags)
            if self.tag_edit_history is not None:
                self.tag_viewer_dialog.set_history_manager(self.tag_edit_history)
            # Set UI refresh callback
            if self.ui_refresh_callback is not None:
                self.tag_viewer_dialog.ui_refresh_callback = self.ui_refresh_callback
            # Connect tag_edited signal if callback is available
            if self.tag_edited_callback is not None:
                self.tag_viewer_dialog.tag_edited.connect(self.tag_edited_callback)
            # Set undo/redo callbacks if callback is available
            if hasattr(self, 'undo_redo_callbacks') and self.undo_redo_callbacks is not None:
                undo_cb, redo_cb, can_undo_cb, can_redo_cb = self.undo_redo_callbacks
                self.tag_viewer_dialog.set_undo_redo_callbacks(undo_cb, redo_cb, can_undo_cb, can_redo_cb)
        
        # Set privacy mode
        self.tag_viewer_dialog.set_privacy_mode(privacy_mode)
        
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
    
    def open_fusion_technical_doc(self) -> None:
        """Handle Fusion Technical Documentation dialog request."""
        dialog = FusionTechnicalDocDialog(self.config_manager, self.main_window)
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
        initial_fit_zoom: Optional[float] = None,
        use_rescaled_values: bool = False,
        roi_manager=None,
        overlay_manager=None,
        measurement_tool=None,
        projection_enabled: bool = False,
        projection_type: str = "aip",
        projection_slice_count: int = 4
    ) -> None:
        """
        Handle Export dialog request.
        
        Args:
            current_window_center: Optional current window center from viewer
            current_window_width: Optional current window width from viewer
            current_zoom: Optional current zoom level from viewer
            initial_fit_zoom: Optional initial fit-to-view zoom factor for font scaling
            use_rescaled_values: Whether to use rescaled values (matches viewer setting)
            roi_manager: Optional ROI manager for rendering ROIs
            overlay_manager: Optional overlay manager for rendering overlays
            measurement_tool: Optional measurement tool for rendering measurements
            projection_enabled: Whether intensity projection (combine slices) is enabled
            projection_type: Type of projection ("aip", "mip", or "minip")
            projection_slice_count: Number of slices to combine (2, 3, 4, 6, or 8)
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
            initial_fit_zoom=initial_fit_zoom,
            use_rescaled_values=use_rescaled_values,
            roi_manager=roi_manager,
            overlay_manager=overlay_manager,
            measurement_tool=measurement_tool,
            config_manager=self.config_manager,
            projection_enabled=projection_enabled,
            projection_type=projection_type,
            projection_slice_count=projection_slice_count,
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
    
    def open_histogram(self, subwindow_index: Optional[int] = None) -> None:
        """
        Open or show histogram dialog for a subwindow.
        If subwindow_index is None, uses the currently focused subwindow.
        Supports up to 4 histograms (one per subwindow index 0-3).
        """
        if self.get_focused_subwindow_index is None or self.get_histogram_callbacks_for_subwindow is None:
            return
        idx = subwindow_index if subwindow_index is not None else self.get_focused_subwindow_index()
        # Guard: only indices 0-3 are valid for histogram dialogs
        if idx < 0 or idx > 3:
            return
        if self.histogram_dialogs.get(idx) is None:
            callbacks = self.get_histogram_callbacks_for_subwindow(idx)
            if not callbacks:
                return
            self.histogram_dialogs[idx] = HistogramDialog(
                self.main_window,
                title_suffix=f" (View {idx + 1})",
                **callbacks
            )
        dialog = self.histogram_dialogs[idx]
        dialog.update_histogram()
        dialog.show()
        dialog.raise_()
        dialog.activateWindow()
    
    def update_histogram_for_subwindow(self, idx: int) -> None:
        """Update the histogram dialog for the given subwindow index if it exists and is visible."""
        if idx < 0 or idx > 3:
            return
        dialog = self.histogram_dialogs.get(idx)
        if dialog is not None and dialog.isVisible():
            dialog.update_histogram()
    
    def open_about_this_file(self, current_dataset: Optional[Dataset] = None, file_path: Optional[str] = None) -> None:
        """
        Handle About This File dialog request.
        
        Args:
            current_dataset: Optional current DICOM dataset
            file_path: Optional path to the DICOM file
        """
        if self.about_this_file_dialog is None:
            self.about_this_file_dialog = AboutThisFileDialog(self.main_window)
        
        # Update dialog with current information
        self.about_this_file_dialog.update_file_info(current_dataset, file_path)
        
        # Show dialog
        self.about_this_file_dialog.show()
        self.about_this_file_dialog.raise_()
        self.about_this_file_dialog.activateWindow()
    
    def update_about_this_file(self, current_dataset: Optional[Dataset] = None, file_path: Optional[str] = None) -> None:
        """
        Update About This File dialog with new dataset/file path.
        
        Args:
            current_dataset: Optional current DICOM dataset
            file_path: Optional path to the DICOM file
        """
        if self.about_this_file_dialog is not None and self.about_this_file_dialog.isVisible():
            self.about_this_file_dialog.update_file_info(current_dataset, file_path)

