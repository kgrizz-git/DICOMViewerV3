"""
Privacy controller.

Owns privacy-mode propagation when the user toggles privacy view. Called from
DICOMViewerApp._on_privacy_view_toggled. Propagates the enabled flag to
metadata panel, shared and per-subwindow overlay managers, crosshair managers,
and all image viewers; then refreshes overlays for subwindows with loaded data.
"""

from typing import Callable, Dict, List, Any


class PrivacyController:
    """
    Centralizes privacy view propagation and overlay refresh after privacy change.

    Receives config_manager, metadata_controller, overlay_manager, and callables
    to resolve subwindow managers and subwindows so it stays up-to-date without
    holding stale references.
    """

    def __init__(
        self,
        *,
        config_manager: Any,
        metadata_controller: Any,
        overlay_manager: Any,
        dialog_coordinator: Any = None,
        get_subwindow_managers: Callable[[], Dict[int, Dict[str, Any]]],
        get_all_subwindows: Callable[[], List[Any]],
        get_focused_subwindow_index: Callable[[], int],
        get_subwindow_data: Callable[[], Dict[int, Any]],
    ) -> None:
        """
        Initialize the privacy controller.

        Args:
            config_manager: Application config manager (for persist/load if needed).
            metadata_controller: Metadata controller; must have set_privacy_mode(enabled).
            overlay_manager: Shared (focused) overlay manager; must have set_privacy_mode(enabled).
            dialog_coordinator: Dialog coordinator; may expose apply_privacy_mode(enabled).
            get_subwindow_managers: Callable returning the subwindow_managers dict (idx -> managers).
            get_all_subwindows: Callable returning list of subwindow widgets (e.g. multi_window_layout.get_all_subwindows).
            get_focused_subwindow_index: Callable returning the current focused subwindow index.
            get_subwindow_data: Callable returning the app's subwindow_data dict; used to skip subwindows that have no loaded data (avoid redisplaying stale slice_display_manager state).
        """
        self._config_manager = config_manager
        self._metadata_controller = metadata_controller
        self._overlay_manager = overlay_manager
        self._dialog_coordinator = dialog_coordinator
        self._get_subwindow_managers = get_subwindow_managers
        self._get_all_subwindows = get_all_subwindows
        self._get_focused_subwindow_index = get_focused_subwindow_index
        self._get_subwindow_data = get_subwindow_data

    def apply_privacy(self, enabled: bool) -> None:
        """
        Propagate privacy mode to all components and refresh overlays.

        Updates metadata panel, shared overlay manager, per-subwindow overlay
        and crosshair managers, and all image viewer privacy state; then
        calls refresh_overlays() so overlays reflect the new mode.

        Args:
            enabled: True if privacy view is enabled, False otherwise.
        """
        if hasattr(self._metadata_controller, "set_privacy_mode") and self._metadata_controller:
            self._metadata_controller.set_privacy_mode(enabled)

        if hasattr(self._overlay_manager, "set_privacy_mode") and self._overlay_manager:
            self._overlay_manager.set_privacy_mode(enabled)

        if hasattr(self._dialog_coordinator, "apply_privacy_mode") and self._dialog_coordinator:
            self._dialog_coordinator.apply_privacy_mode(enabled)

        for _subwindow_idx, managers in self._get_subwindow_managers().items():
            overlay_mgr = managers.get("overlay_manager")
            if overlay_mgr and hasattr(overlay_mgr, "set_privacy_mode"):
                overlay_mgr.set_privacy_mode(enabled)
            # Crosshairs are not updated for privacy: they always show full content (pixel value, coords)
            # and do not hide anything in privacy mode, so no need to call crosshair_manager.set_privacy_mode.

        for subwindow in self._get_all_subwindows():
            if subwindow and getattr(subwindow, "image_viewer", None):
                subwindow.image_viewer.set_privacy_view_state(enabled)

        self.refresh_overlays()

    def refresh_overlays(self) -> None:
        """
        Refresh overlays after privacy change for all subwindows that have loaded data.

        For each subwindow with loaded data, calls slice_display_manager.display_slice(...)
        with update_metadata only for the focused subwindow. On exception, falls back
        to overlay_manager.create_overlay_items using DICOMParser.
        """
        subwindows = self._get_all_subwindows()
        managers_by_idx = self._get_subwindow_managers()
        subwindow_data = self._get_subwindow_data()
        focused_idx = self._get_focused_subwindow_index()

        for idx, subwindow in enumerate(subwindows):
            if not subwindow or not getattr(subwindow, "image_viewer", None):
                continue
            # Only refresh subwindows that have loaded data (entry in subwindow_data).
            # Otherwise we would redisplay from slice_display_manager's cached state, which
            # can be stale for windows that were not updated when a different study was loaded.
            if idx not in subwindow_data:
                continue
            if idx not in managers_by_idx:
                continue
            managers = managers_by_idx[idx]
            slice_display_manager = managers.get("slice_display_manager")
            if not slice_display_manager or not hasattr(slice_display_manager, "current_dataset"):
                continue
            if (
                slice_display_manager.current_dataset is None
                or not hasattr(slice_display_manager, "current_studies")
                or not hasattr(slice_display_manager, "current_study_uid")
                or not hasattr(slice_display_manager, "current_series_uid")
                or not hasattr(slice_display_manager, "current_slice_index")
            ):
                continue
            try:
                slice_display_manager.display_slice(
                    slice_display_manager.current_dataset,
                    slice_display_manager.current_studies,
                    slice_display_manager.current_study_uid,
                    slice_display_manager.current_series_uid,
                    slice_display_manager.current_slice_index,
                    update_metadata=(idx == focused_idx),
                )
            except Exception:
                overlay_manager = managers.get("overlay_manager")
                if overlay_manager and slice_display_manager.current_dataset:
                    from core.dicom_parser import DICOMParser

                    parser = DICOMParser(slice_display_manager.current_dataset)
                    overlay_manager.create_overlay_items(
                        subwindow.image_viewer.scene,
                        parser,
                        multiframe_context=slice_display_manager.get_multiframe_overlay_context(),
                    )
