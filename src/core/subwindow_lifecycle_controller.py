"""
Subwindow Lifecycle Controller

This module owns subwindow getters and (in later phases) focus/panel updates and
signal connect/disconnect/layout for the multi-subwindow DICOM viewer. Step 1
provides only getter methods; focus/panel and connect/disconnect methods are
added in Phase 3.3/3.4.

Purpose:
    - Provide a single place for subwindow index, dataset, slice, managers, and
      focused subwindow access so main.py and other coordinators can delegate here.

Inputs:
    - App reference (DICOMViewerApp instance) providing multi_window_layout,
      subwindow_managers, subwindow_data, focused_subwindow_index.

Outputs:
    - Subwindow/index and data: dataset, slice index, slice_display_manager,
      study_uid, series_uid; focused subwindow index; histogram callbacks per subwindow;
      focused subwindow container.

Requirements:
    - Typing for Optional, Dict. pydicom.dataset.Dataset for type hints.
"""

from typing import Optional, Dict, Any
from pydicom.dataset import Dataset


class SubwindowLifecycleController:
    """
    Holds subwindow getter logic for the main application.

    Receives the app instance and delegates all state access through it.
    Used by main.py and other modules (e.g. file_series_loading_coordinator,
    dialog_coordinator) to resolve current subwindow, dataset, slice, and managers.
    """

    def __init__(self, app: Any) -> None:
        """
        Initialize the controller with a reference to the main application.

        Args:
            app: The DICOMViewerApp instance (or any object providing
                 multi_window_layout, subwindow_managers, subwindow_data,
                 focused_subwindow_index).
        """
        self.app = app

    def get_subwindow_dataset(self, idx: int) -> Optional[Dataset]:
        """Get current dataset for a subwindow."""
        if idx in self.app.subwindow_data:
            return self.app.subwindow_data[idx].get('current_dataset')
        return None

    def get_subwindow_slice_index(self, idx: int) -> int:
        """Get current slice index for a subwindow."""
        if idx in self.app.subwindow_data:
            return self.app.subwindow_data[idx].get('current_slice_index', 0)
        return 0

    def get_subwindow_slice_display_manager(self, idx: int):
        """Get slice display manager for a subwindow."""
        if idx in self.app.subwindow_managers:
            return self.app.subwindow_managers[idx].get('slice_display_manager')
        return None

    def get_subwindow_study_uid(self, idx: int) -> str:
        """Get current study UID for a subwindow."""
        if idx in self.app.subwindow_data:
            return self.app.subwindow_data[idx].get('current_study_uid', '')
        return ''

    def get_subwindow_series_uid(self, idx: int) -> str:
        """Get current series UID for a subwindow."""
        if idx in self.app.subwindow_data:
            return self.app.subwindow_data[idx].get('current_series_uid', '')
        return ''

    def get_focused_subwindow_index(self) -> int:
        """Return the currently focused subwindow index (0-3). Used for histogram and other per-view features."""
        return self.app.focused_subwindow_index

    def get_histogram_callbacks_for_subwindow(self, idx: int) -> Dict[str, Any]:
        """
        Return a dict of callbacks for the histogram dialog tied to subwindow idx.
        Used so each histogram always shows the image currently displayed in that subwindow.
        """
        if idx not in self.app.subwindow_managers:
            return {}
        vsm = self.app.subwindow_managers[idx].get('view_state_manager')
        if vsm is None:
            return {}
        return {
            'get_current_dataset': lambda i=idx: self.get_subwindow_dataset(i),
            'get_current_slice_index': lambda i=idx: self.get_subwindow_slice_index(i),
            'get_window_center': lambda: vsm.current_window_center,
            'get_window_width': lambda: vsm.current_window_width,
            'get_use_rescaled': lambda: vsm.use_rescaled_values,
            'get_rescale_params': lambda: (
                vsm.rescale_slope,
                vsm.rescale_intercept,
                getattr(vsm, 'rescale_type', None)
            ),
        }

    def get_focused_subwindow(self):
        """
        Get the currently focused subwindow.

        Returns:
            SubWindowContainer or None if no subwindow is focused
        """
        return self.app.multi_window_layout.get_focused_subwindow()
