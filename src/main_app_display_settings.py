"""
DICOMViewerApp display, projection, settings, and layout mixin module.

Owns slice display/redisplay, projection toggles, privacy/settings dialogs, and
layout management handlers for ``DICOMViewerApp`` (see MAIN_PY_REFACTOR_PLAN Appendix A).
Methods extracted from ``main.py`` in Phase 5.
"""

from __future__ import annotations

# pyright: reportAttributeAccessIssue=false, reportArgumentType=false, reportUninitializedInstanceVariable=false
from core.overlay_settings_handlers import (
    apply_imported_customizations,
    cycle_overlay_detail_mode,
    on_overlay_config_applied,
    on_overlay_font_color_changed,
    on_overlay_font_size_changed,
    on_settings_applied,
    sync_all_overlay_managers_from_config,
)
from core.slice_display_handlers import (
    display_slice,
    on_slice_changed,
    redisplay_current_slice,
)
from core.study_navigation_handlers import (
    refresh_series_navigator_state,
    update_series_navigator_highlighting,
)
from core.view_state_handlers import (
    on_zoom_changed,
    update_zoom_preset_status_bar,
)
from core.window_level_preset_handler import apply_window_level_preset
from gui.actions import view_actions
from gui.layout_window_slot_controller import (
    on_expand_to_1x1_requested as layout_on_expand_to_1x1_requested,
)
from gui.layout_window_slot_controller import (
    on_layout_change_requested as layout_on_layout_change_requested,
)
from gui.layout_window_slot_controller import (
    on_layout_changed as layout_on_layout_changed,
)
from gui.layout_window_slot_controller import (
    on_main_window_layout_changed as layout_on_main_window_layout_changed,
)
from gui.layout_window_slot_controller import (
    on_swap_view_requested as layout_on_swap_view_requested,
)
from gui.layout_window_slot_controller import (
    refresh_window_slot_map_widgets as layout_refresh_window_slot_map_widgets,
)


class DisplayProjectionMixin:
    """
    Mixin: slice display, redisplay, and projection enable/change handlers for
    ``DICOMViewerApp``.
    """

    def _display_slice(self, dataset, preserve_view_override: bool | None = None) -> None:
        """Display a DICOM slice."""
        display_slice(self, dataset, preserve_view_override=preserve_view_override)

    def _redisplay_current_slice(self, preserve_view: bool = True) -> None:
        """Redisplay the current slice via SliceDisplayManager with optional preserve_view override."""
        redisplay_current_slice(self, preserve_view)

    def _on_projection_enabled_changed(self, enabled: bool) -> None:
        """
        Handle projection enabled state change.

        Slot for Qt signals; implementation lives in ``ProjectionAppFacade``.
        """
        self._projection_app_facade.on_projection_enabled_changed(enabled)

    def _on_projection_type_changed(self, projection_type: str) -> None:
        """Handle projection type change. Delegates to ``ProjectionAppFacade``."""
        self._projection_app_facade.on_projection_type_changed(projection_type)

    def _on_projection_slice_count_changed(self, count: int) -> None:
        """Handle projection slice count change. Delegates to ``ProjectionAppFacade``."""
        self._projection_app_facade.on_projection_slice_count_changed(count)

    def _on_smooth_when_zoomed_toggled(self, enabled: bool) -> None:
        """Handle smooth-when-zoomed toggle. Delegates to ``view_actions``."""
        view_actions.on_smooth_when_zoomed_toggled(self, enabled)

    def _refresh_overlays_after_privacy_change(self) -> None:
        """Refresh overlays after privacy view change for all subwindows that have loaded data. Delegates to privacy controller."""
        self._privacy_controller.refresh_overlays()

    def _sync_all_overlay_managers_from_config(self) -> None:
        """Apply persisted overlay mode and visibility state to every pane's OverlayManager."""
        sync_all_overlay_managers_from_config(self)

    def _cycle_overlay_detail_mode(self) -> None:
        """Cycle corner overlay detail across all panes: minimal -> detailed -> hidden -> minimal."""
        cycle_overlay_detail_mode(self)

    def _on_overlay_config_applied(self) -> None:
        """Handle overlay configuration being applied."""
        on_overlay_config_applied(self)

    def _schedule_histogram_wl_only(self) -> None:
        """Schedule a light W/L-only histogram update (no pixel refetch) so W/L sliders stay responsive."""
        if not hasattr(self, "dialog_coordinator"):
            return
        self._restart_single_shot_timer(
            "_histogram_wl_update_timer",
            100,
            self._do_update_histogram_wl_only,
        )

    def _do_update_histogram_wl_only(self) -> None:
        """Update only the W/L overlay in the histogram (called after W/L throttle delay)."""
        if hasattr(self, "dialog_coordinator"):
            self.dialog_coordinator.update_histogram_window_level_only_for_subwindow(
                self.focused_subwindow_index
            )

    def _on_zoom_changed(self, zoom_level: float) -> None:
        """Handle zoom level change."""
        on_zoom_changed(self, zoom_level)

    def _on_window_level_preset_selected(self, preset_index: int) -> None:
        """Handle window/level preset selection from context menu (logic in ``window_level_preset_handler``)."""
        apply_window_level_preset(self, preset_index)

    def _update_zoom_preset_status_bar(self) -> None:
        """Update the zoom and preset status bar widget."""
        update_zoom_preset_status_bar(self)

    def _on_overlay_font_size_changed(self, font_size: int) -> None:
        """Handle overlay font size change from toolbar - update ALL subwindows."""
        on_overlay_font_size_changed(self, font_size)

    def _on_overlay_font_color_changed(self, r: int, g: int, b: int) -> None:
        """Handle overlay font color change from toolbar - update ALL subwindows."""
        on_overlay_font_color_changed(self, r, g, b)

    def _on_slice_changed(self, slice_index: int) -> None:
        """Handle slice change from slice navigator (affects focused subwindow only)."""
        on_slice_changed(self, slice_index)


class SettingsLayoutMixin:
    """
    Mixin: privacy/settings toggles, settings dialog, swap/expand layout requests,
    and layout change orchestration for ``DICOMViewerApp``.
    """

    def _update_series_navigator_highlighting(self) -> None:
        """Update series navigator highlighting based on focused subwindow's series."""
        update_series_navigator_highlighting(self)

    def _refresh_series_navigator_state(self) -> None:
        """Push organizer-backed multiframe state and action enablement into the navigator UI."""
        refresh_series_navigator_state(self)

    def _on_layout_changed(self, layout_mode: str) -> None:
        """Handle layout mode change from multi-window layout. Body in ``core.layout_window_slot_controller``."""
        layout_on_layout_changed(self, layout_mode)

    def _on_main_window_layout_changed(self, layout_mode: str) -> None:
        """Handle layout mode change from main window menu. Body in ``core.layout_window_slot_controller``."""
        layout_on_main_window_layout_changed(self, layout_mode)

    def _on_layout_change_requested(self, layout_mode: str) -> None:
        """Handle layout change request from image viewer context menu."""
        layout_on_layout_change_requested(self, layout_mode)

    def _on_expand_to_1x1_requested(self) -> None:
        """Handle double-click: expand to 1x1 or, if already in 1x1, revert to last used layout (or 2x2)."""
        layout_on_expand_to_1x1_requested(self)

    def _on_swap_view_requested(self, other_index: int) -> None:
        """Handle Swap with View X from context menu: swap slot positions in all layouts; focus stays unchanged."""
        layout_on_swap_view_requested(self, other_index)

    def _refresh_window_slot_map_widgets(self) -> None:
        """Refresh the embedded and popup window-slot map widgets, if present."""
        layout_refresh_window_slot_map_widgets(self)

    def _on_series_navigator_selected(self, series_uid: str) -> None:
        """Handle series selection from series navigator (assigns to focused subwindow). Delegates to coordinator."""
        self._file_series_coordinator.on_series_navigator_selected(series_uid)

    def _on_series_navigator_instance_selected(self, study_uid: str, series_uid: str, slice_index: int) -> None:
        """Handle per-instance thumbnail selection from series navigator. Delegates to coordinator."""
        self._file_series_coordinator.on_series_navigator_instance_selected(study_uid, series_uid, slice_index)

    def _on_privacy_view_toggled(self, enabled: bool) -> None:
        """Handle privacy view toggle. Delegates to ``view_actions.on_privacy_view_toggled``."""
        view_actions.on_privacy_view_toggled(self, enabled)

    def _on_slice_sync_toggled(self, enabled: bool) -> None:
        """Handle View → Slice Sync → Enable Slice Sync toggle. Delegates to ``view_actions``."""
        view_actions.on_slice_sync_toggled(self, enabled)

    def _on_slice_sync_groups_changed(self, groups) -> None:
        """Receive updated group assignments from the Slice Sync dialog. Delegates to ``view_actions``."""
        view_actions.on_slice_sync_groups_changed(self, groups)

    def _apply_imported_customizations(self) -> None:
        """Apply imported customization settings: overlay font, overlay refresh, annotations, theme, metadata columns."""
        apply_imported_customizations(self)

    def _on_settings_applied(self) -> None:
        """Handle settings being applied."""
        on_settings_applied(self)

