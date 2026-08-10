"""
MainWindow overlay + view-option helpers (refactor Extraction #6).

Mixin used by `gui.main_window.MainWindow` for the View-menu / toolbar
toggle handlers, check-state sync helpers, and font/color picker callbacks
that back the on-screen overlays (scale markers, direction labels, slice
location lines, privacy view, corner-overlay font).

Mixed in before ``QMainWindow`` on ``MainWindow`` (mirrors the
``ImageViewerViewMixin`` / ``ImageViewerInputMixin`` pattern on
``gui.image_viewer.ImageViewer``): each method here accesses
``self.config_manager``, ``self.<QAction>`` attributes, and emits signals
declared on ``MainWindow`` — none of those are declared in this module.

Inputs:
    - Qt toggle/trigger callbacks from View-menu actions, context-menu
      actions, and toolbar buttons (``checked: bool`` or ``mode/placement:
      str`` arguments).
    - ``self.config_manager`` (``ConfigManager``) for persisted view-option
      state.

Outputs:
    - Persists view-option changes via ``self.config_manager``.
    - Emits the corresponding ``Signal`` declared on ``MainWindow`` (e.g.
      ``privacy_view_toggled``, ``scale_markers_toggled``).
    - Syncs ``QAction`` check state (via ``blockSignals``) without emitting,
      for programmatic updates driven by other components.

Requirements:
    - PySide6 (QColor, QColorDialog, QToolButton).
"""
# Pyright: methods run only on ``MainWindow`` (combined Qt type); this mixin's
# base class alone cannot express access to host attributes/signals without a
# duplicate protocol surface. See ``image_viewer_view.py`` for the same pattern.
# ``reportArgumentType`` is also off so ``self`` can be passed as a ``QWidget``
# parent to ``QColorDialog`` without a Protocol cast surface (see
# ``dialogs/tag_export_dialog_presets.py`` for the same pattern).
# pyright: reportAttributeAccessIssue=false, reportUninitializedInstanceVariable=false, reportArgumentType=false
from __future__ import annotations

from PySide6.QtGui import QColor
from PySide6.QtWidgets import QColorDialog, QToolButton


class MainWindowOverlayOptionsMixin:
    """Overlay/view-option toggle handlers, check-state sync, and font/color pickers."""

    def _on_privacy_toggled(self, checked: bool) -> None:
        """Handle privacy view toggle from the shared privacy_action (menu, toolbar, or shortcut).

        Args:
            checked: True if privacy view is now enabled, False otherwise.
        """
        self.config_manager.set_privacy_view(checked)
        self.privacy_view_toggled.emit(checked)
        self._update_privacy_action()

    def _on_privacy_view_toggled(self, checked: bool) -> None:
        """Backward-compat shim for external callers (e.g. context-menu via viewer signal).

        Syncs the shared action's check state, then delegates to _on_privacy_toggled.
        """
        if self.privacy_action is not None:
            self.privacy_action.blockSignals(True)
            self.privacy_action.setChecked(checked)
            self.privacy_action.blockSignals(False)
        self._on_privacy_toggled(checked)

    def _on_smooth_when_zoomed_toggled(self, checked: bool) -> None:
        """
        Handle smooth-when-zoomed toggle from View menu or context menu.

        Args:
            checked: True if smooth when zoomed is enabled, False otherwise
        """
        self.config_manager.set_smooth_image_when_zoomed(checked)
        self.smooth_when_zoomed_toggled.emit(checked)

    def _on_scale_markers_toggled(self, checked: bool) -> None:
        """
        Handle scale markers toggle from View menu or context menu.

        Args:
            checked: True if scale markers are enabled, False otherwise
        """
        self.config_manager.set_show_scale_markers(checked)
        self.scale_markers_toggled.emit(checked)

    def _on_direction_labels_toggled(self, checked: bool) -> None:
        """
        Handle direction labels toggle from View menu or context menu.

        Args:
            checked: True if direction labels are enabled, False otherwise
        """
        self.config_manager.set_show_direction_labels(checked)
        self.direction_labels_toggled.emit(checked)

    def set_smooth_when_zoomed_checked(self, checked: bool) -> None:
        """Sync the View menu Image Smoothing action check state without emitting triggered."""
        if self.smooth_when_zoomed_action is None:
            return
        self.smooth_when_zoomed_action.blockSignals(True)
        self.smooth_when_zoomed_action.setChecked(checked)
        self.smooth_when_zoomed_action.blockSignals(False)

    def set_scale_markers_checked(self, checked: bool) -> None:
        """Sync the View menu Show Scale Markers action check state without emitting triggered."""
        if self.scale_markers_action is None:
            return
        self.scale_markers_action.blockSignals(True)
        self.scale_markers_action.setChecked(checked)
        self.scale_markers_action.blockSignals(False)

    def set_direction_labels_checked(self, checked: bool) -> None:
        """Sync the View menu Show Direction Labels action check state without emitting triggered."""
        if self.direction_labels_action is None:
            return
        self.direction_labels_action.blockSignals(True)
        self.direction_labels_action.setChecked(checked)
        self.direction_labels_action.blockSignals(False)

    def set_slice_slider_checked(self, checked: bool) -> None:
        """Sync the View menu Show In-View Slice/Frame Slider action check state without emitting triggered."""
        if self.slice_slider_action is None:
            return
        self.slice_slider_action.blockSignals(True)
        self.slice_slider_action.setChecked(checked)
        self.slice_slider_action.blockSignals(False)

    def set_slice_slider_placement_checked(self, placement: str) -> None:
        """Sync the View menu slider placement action without emitting triggered."""
        for key, action in self.slice_slider_placement_actions.items():
            action.blockSignals(True)
            action.setChecked(key == placement)
            action.blockSignals(False)

    def set_slice_slider_direction_checked(self, direction: str) -> None:
        """Sync the View menu slider direction action without emitting triggered."""
        for key, action in self.slice_slider_direction_actions.items():
            action.blockSignals(True)
            action.setChecked(key == direction)
            action.blockSignals(False)

    def _on_show_instances_separately_toggled(self, checked: bool) -> None:
        """Handle the View menu toggle for multi-frame instance expansion."""
        self.config_manager.set_show_instances_separately(checked)
        self.show_instances_separately_toggled.emit(checked)

    def set_show_instances_separately_checked(self, checked: bool) -> None:
        """Sync the View menu Show Instances Separately action check state without emitting triggered."""
        if self.show_instances_separately_action is None:
            return
        self.show_instances_separately_action.blockSignals(True)
        self.show_instances_separately_action.setChecked(checked)
        self.show_instances_separately_action.blockSignals(False)

    def set_show_instances_separately_enabled(self, enabled: bool) -> None:
        """Enable or disable the View menu Show Instances Separately action."""
        if self.show_instances_separately_action is None:
            return
        self.show_instances_separately_action.setEnabled(enabled)

    def set_3d_view_actions_enabled(self, enabled: bool, tooltip: str = "") -> None:
        """Enable or disable toolbar/menu 3D volume render actions."""
        tip = tooltip or "Open 3D Volume Render of current series"
        for action in (self.view_3d_action, self.create_3d_action):
            if action is None:
                continue
            action.setEnabled(enabled)
            action.setToolTip(tip)
            if action is self.create_3d_action:
                action.setStatusTip(tip)

    def set_slice_location_lines_checked(self, checked: bool) -> None:
        """Sync the View menu Show Slice Location Lines → Enable/Disable action check state without emitting triggered."""
        if self.slice_location_lines_enable_action is None:
            return
        self.slice_location_lines_enable_action.blockSignals(True)
        self.slice_location_lines_enable_action.setChecked(checked)
        self.slice_location_lines_enable_action.blockSignals(False)

    def set_slice_location_lines_same_group_only_checked(self, checked: bool) -> None:
        """Sync the View menu Show Slice Location Lines → Only Show For Same Group action check state without emitting triggered."""
        if self.slice_location_lines_same_group_only_action is None:
            return
        self.slice_location_lines_same_group_only_action.blockSignals(True)
        self.slice_location_lines_same_group_only_action.setChecked(checked)
        self.slice_location_lines_same_group_only_action.blockSignals(False)

    def set_slice_location_lines_focused_only_checked(self, checked: bool) -> None:
        """Sync the View menu Show Slice Location Lines → Show Only For Focused Window action check state without emitting triggered."""
        if self.slice_location_lines_focused_only_action is None:
            return
        self.slice_location_lines_focused_only_action.blockSignals(True)
        self.slice_location_lines_focused_only_action.setChecked(checked)
        self.slice_location_lines_focused_only_action.blockSignals(False)

    def set_slice_location_lines_slab_bounds_checked(self, mode: str) -> None:
        """Sync the View menu slab-bounds action check state without emitting triggered.

        Args:
            mode: "middle" or "begin_end".  Action is checked when mode == "begin_end".
        """
        if self.slice_location_lines_show_slab_bounds_action is None:
            return
        self.slice_location_lines_show_slab_bounds_action.blockSignals(True)
        self.slice_location_lines_show_slab_bounds_action.setChecked(mode == "begin_end")
        self.slice_location_lines_show_slab_bounds_action.blockSignals(False)

    def _update_privacy_action(self) -> None:
        """Update the shared privacy_action icon, text, tooltip, and toolbar button styling."""
        if self.privacy_action is None:
            return

        privacy_enabled = self.privacy_action.isChecked()

        if privacy_enabled:
            self.privacy_action.setText("Privacy ON")
            self.privacy_action.setToolTip("Privacy view ON — identifiers masked  (Ctrl+P)")
            icon = getattr(self, '_privacy_icon_on', None)
            if icon is not None:
                self.privacy_action.setIcon(icon)
            if self.main_toolbar is not None:
                for tb in self.main_toolbar.findChildren(QToolButton):
                    if tb.defaultAction() == self.privacy_action:
                        tb.setStyleSheet("")
                        break
        else:
            self.privacy_action.setText("Privacy OFF")
            self.privacy_action.setToolTip("Privacy view OFF — identifiers visible  (Ctrl+P)")
            icon = getattr(self, '_privacy_icon_off', None)
            if icon is not None:
                self.privacy_action.setIcon(icon)
            # Red background when privacy is OFF (data is exposed)
            if self.main_toolbar is not None:
                for tb in self.main_toolbar.findChildren(QToolButton):
                    if tb.defaultAction() == self.privacy_action:
                        tb.setStyleSheet("QToolButton { background-color: #c0392b; border-radius: 4px; }")
                        break

    # Backward-compat alias (called by old code paths before refactor)
    _update_privacy_mode_button = _update_privacy_action

    def _on_font_size_decrease(self) -> None:
        """Handle font size decrease button click."""
        self.adjust_overlay_font_size(-1)

    def _on_font_size_increase(self) -> None:
        """Handle font size increase button click."""
        self.adjust_overlay_font_size(1)

    def adjust_overlay_font_size(self, delta: int) -> None:
        """Adjust the shared corner-overlay font size, clamped to its supported range."""
        current_size = self.config_manager.get_overlay_font_size()
        new_size = max(1, min(24, current_size + delta))
        if new_size != current_size:
            self.config_manager.set_overlay_font_size(new_size)
            self.overlay_font_size_changed.emit(new_size)

    def _on_font_color_picker(self) -> None:
        """Handle font color picker button click."""
        # Get current color from config
        current_color = self.config_manager.get_overlay_font_color()
        qcolor = QColor(current_color[0], current_color[1], current_color[2])

        # Open color dialog
        color = QColorDialog.getColor(qcolor, self, "Select Overlay Font Color")

        if color.isValid():
            # Save to config and emit signal
            self.config_manager.set_overlay_font_color(color.red(), color.green(), color.blue())
            self.overlay_font_color_changed.emit(color.red(), color.green(), color.blue())

    def _on_scale_markers_color_picker(self) -> None:
        """Handle scale markers color picker menu action."""
        current_color = self.config_manager.get_scale_markers_color()
        qcolor = QColor(current_color[0], current_color[1], current_color[2])
        color = QColorDialog.getColor(qcolor, self, "Select Scale Markers Color")
        if color.isValid():
            self.config_manager.set_scale_markers_color(color.red(), color.green(), color.blue())
            self.scale_markers_color_changed.emit(color.red(), color.green(), color.blue())

    def _on_direction_labels_color_picker(self) -> None:
        """Handle direction labels color picker menu action."""
        current_color = self.config_manager.get_direction_labels_color()
        qcolor = QColor(current_color[0], current_color[1], current_color[2])
        color = QColorDialog.getColor(qcolor, self, "Select Direction Labels Color")
        if color.isValid():
            self.config_manager.set_direction_labels_color(color.red(), color.green(), color.blue())
            self.direction_labels_color_changed.emit(color.red(), color.green(), color.blue())
