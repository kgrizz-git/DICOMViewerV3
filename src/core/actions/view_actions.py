"""
View menu and related slots extracted from ``DICOMViewerApp``.

Each function receives the application instance as ``app`` and mirrors the
previous ``DICOMViewerApp._on_*`` behavior. ``app_signal_wiring`` still connects
Qt signals to methods on ``DICOMViewerApp`` that delegate here.

Inputs:
    ``app``: running ``DICOMViewerApp`` instance.
    Handler-specific arguments from Qt signals (bools, RGB tuples, mode strings).

Outputs:
    Side effects only (config persistence, coordinator updates, viewer state).

Requirements:
    PySide6; ``core.subwindow_image_viewer_sync`` helpers for multi-pane propagation.
"""

from __future__ import annotations

# Pyright may report a false-positive import cycle via TYPE_CHECKING → main.
# pyright: reportImportCycles=false

from typing import TYPE_CHECKING

from core.subwindow_image_viewer_sync import (
    set_direction_labels_all,
    set_direction_labels_color_all,
    set_scale_markers_all,
    set_scale_markers_color_all,
    set_slice_slider_all,
    set_smooth_when_zoomed_all,
)

if TYPE_CHECKING:  # pragma: no cover
    from main import DICOMViewerApp


def on_privacy_view_toggled(app: "DICOMViewerApp", enabled: bool) -> None:
    """
    Handle privacy view toggle.

    Propagates privacy mode state to all components that display tags
    via the privacy controller.

    Args:
        app: Application root.
        enabled: True if privacy view is enabled, False otherwise.
    """
    app.privacy_view_enabled = enabled
    app._privacy_controller.apply_privacy(enabled)
    if hasattr(app, "series_navigator") and app.series_navigator is not None:
        app.series_navigator.set_privacy_mode(enabled)
        app._refresh_series_navigator_state()
        app.series_navigator.set_subwindow_assignments(app._get_subwindow_assignments())


def on_slice_sync_toggled(app: "DICOMViewerApp", enabled: bool) -> None:
    """
    Handle the View → Slice Sync → Enable Slice Sync toggle.

    Persists the new state and pushes it to the coordinator.
    """
    app.config_manager.set_slice_sync_enabled(enabled)
    app._slice_sync_coordinator.set_enabled(enabled)
    subwindows = app.multi_window_layout.get_all_subwindows()
    for subwindow in subwindows:
        if subwindow and subwindow.image_viewer:
            subwindow.image_viewer.set_slice_sync_enabled_state(enabled)
    app._refresh_slice_sync_group_indicators()


def on_slice_sync_groups_changed(app: "DICOMViewerApp", groups) -> None:
    """
    Receive updated group assignments from the Slice Sync dialog.

    Persists to config, updates the coordinator, and invalidates the
    geometry cache so stale stacks aren't reused.

    Args:
        groups: List[List[int]] — new group assignments.
    """
    app.config_manager.set_slice_sync_groups(groups)
    app._slice_sync_coordinator.set_groups(groups)
    app._slice_sync_coordinator.invalidate_cache()
    app._slice_location_line_coordinator.refresh_all()
    app._refresh_slice_sync_group_indicators()


def on_slice_location_lines_toggled(app: "DICOMViewerApp", visible: bool) -> None:
    """Handle View → Show Slice Location Lines → Enable/Disable toggle."""
    app.config_manager.set_slice_location_lines_visible(visible)
    app._slice_location_line_coordinator.refresh_all()
    app.main_window.set_slice_location_lines_checked(visible)


def on_slice_location_lines_same_group_only_toggled(
    app: "DICOMViewerApp", same_group_only: bool
) -> None:
    """Handle View → Show Slice Location Lines → Only Show For Same Group toggle."""
    app.config_manager.set_slice_location_lines_same_group_only(same_group_only)
    app._slice_location_line_coordinator.refresh_all()
    app.main_window.set_slice_location_lines_same_group_only_checked(same_group_only)


def on_slice_location_lines_focused_only_toggled(
    app: "DICOMViewerApp", focused_only: bool
) -> None:
    """Handle View → Show Slice Location Lines → Show Only For Focused Window toggle."""
    app.config_manager.set_slice_location_lines_focused_only(focused_only)
    app._slice_location_line_coordinator.refresh_all()
    app.main_window.set_slice_location_lines_focused_only_checked(focused_only)


def on_slice_location_lines_mode_toggled(app: "DICOMViewerApp", mode: str) -> None:
    """Handle View → Show Slice Location Lines → Show Slab Boundaries toggle."""
    app.config_manager.set_slice_location_line_mode(mode)
    app._slice_location_line_coordinator.refresh_all()
    app.main_window.set_slice_location_lines_slab_bounds_checked(mode)


def on_smooth_when_zoomed_toggled(app: "DICOMViewerApp", enabled: bool) -> None:
    """
    Handle smooth-when-zoomed toggle from View menu or image viewer context menu.
    Persists setting and pushes state to all image viewers; syncs View menu check state.
    """
    app.config_manager.set_smooth_image_when_zoomed(enabled)
    set_smooth_when_zoomed_all(app, enabled)
    app.main_window.set_smooth_when_zoomed_checked(enabled)


def on_orientation_flip_h(app: "DICOMViewerApp") -> None:
    """Toggle horizontal flip on the currently focused image viewer."""
    if app.image_viewer is not None:
        app.image_viewer.flip_h()


def on_orientation_flip_v(app: "DICOMViewerApp") -> None:
    """Toggle vertical flip on the currently focused image viewer."""
    if app.image_viewer is not None:
        app.image_viewer.flip_v()


def on_orientation_rotate_cw(app: "DICOMViewerApp") -> None:
    """Rotate the currently focused image viewer 90° clockwise."""
    if app.image_viewer is not None:
        app.image_viewer.rotate_cw()


def on_orientation_rotate_ccw(app: "DICOMViewerApp") -> None:
    """Rotate the currently focused image viewer 90° counter-clockwise."""
    if app.image_viewer is not None:
        app.image_viewer.rotate_ccw()


def on_orientation_rotate_180(app: "DICOMViewerApp") -> None:
    """Rotate the currently focused image viewer 180°."""
    if app.image_viewer is not None:
        app.image_viewer.rotate_180()


def on_orientation_reset(app: "DICOMViewerApp") -> None:
    """Reset orientation of the currently focused image viewer to default."""
    if app.image_viewer is not None:
        app.image_viewer.reset_orientation()


def on_scale_markers_toggled(app: "DICOMViewerApp", enabled: bool) -> None:
    """Handle scale markers toggle from View menu or image viewer context menu."""
    app.config_manager.set_show_scale_markers(enabled)
    set_scale_markers_all(app, enabled)
    app.main_window.set_scale_markers_checked(enabled)


def on_direction_labels_toggled(app: "DICOMViewerApp", enabled: bool) -> None:
    """Handle direction labels toggle from View menu or image viewer context menu."""
    app.config_manager.set_show_direction_labels(enabled)
    set_direction_labels_all(app, enabled)
    app.main_window.set_direction_labels_checked(enabled)


def on_slice_slider_toggled(app: "DICOMViewerApp", enabled: bool) -> None:
    """Handle the in-view slice/frame slider toggle from the View menu."""
    app.config_manager.set_show_slice_slider(enabled)
    set_slice_slider_all(app, enabled)
    app.main_window.set_slice_slider_checked(enabled)


def on_scale_markers_color_changed(app: "DICOMViewerApp", r: int, g: int, b: int) -> None:
    """Handle scale markers color change from the View menu."""
    app.config_manager.set_scale_markers_color(r, g, b)
    set_scale_markers_color_all(app, (r, g, b))


def on_direction_labels_color_changed(app: "DICOMViewerApp", r: int, g: int, b: int) -> None:
    """Handle direction labels color change from the View menu."""
    app.config_manager.set_direction_labels_color(r, g, b)
    set_direction_labels_color_all(app, (r, g, b))


def on_show_instances_separately_toggled(app: "DICOMViewerApp", enabled: bool) -> None:
    """Handle the View → Show Instances Separately toggle."""
    app.config_manager.set_show_instances_separately(enabled)
    app.series_navigator.set_show_instances_separately(enabled)
    app.series_navigator.update_series_list(
        app.current_studies,
        app.current_study_uid,
        app.current_series_uid,
    )
    app._refresh_series_navigator_state()
    app.series_navigator.set_subwindow_assignments(app._get_subwindow_assignments())
