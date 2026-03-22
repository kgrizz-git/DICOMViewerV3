"""
Transformation script: update main.py to delegate the five logic-bearing
_open_* handlers to dialog_action_handlers module functions.

Changes:
  1. Remove QuickWindowLevelDialog import (moves to dialog_action_handlers).
  2. Add: from core import dialog_action_handlers
  3. Replace the body of each of the five logic-bearing _open_* methods with
     a one-liner delegation call.
"""

import ast

TARGET = 'src/main.py'

with open(TARGET, 'r', encoding='utf-8') as f:
    content = f.read()

# ── 1. Remove QuickWindowLevelDialog import ───────────────────────────────────
OLD_IMPORT = 'from gui.dialogs.quick_window_level_dialog import QuickWindowLevelDialog\n'
assert OLD_IMPORT in content, 'QuickWindowLevelDialog import not found'
content = content.replace(OLD_IMPORT, '', 1)

# ── 2. Add `from core import dialog_action_handlers` ─────────────────────────
# Insert after `from core.dicom_parser import DICOMParser` (or any stable anchor)
# Use the line from gui.main_window import MainWindow as anchor
ANCHOR = 'from gui.main_window import MainWindow\n'
assert ANCHOR in content, 'Anchor import not found'
content = content.replace(
    ANCHOR,
    'from core import dialog_action_handlers\n' + ANCHOR,
    1,
)

# ── 3. Replace method bodies ──────────────────────────────────────────────────

# _open_about_this_file
content = content.replace(
    '''    def _open_about_this_file(self) -> None:
        """Handle About This File dialog request."""
        # Get current dataset and file path from focused subwindow
        focused_idx = self.focused_subwindow_index
        current_dataset = None
        file_path = None
        
        if focused_idx in self.subwindow_data:
            current_dataset = self.subwindow_data[focused_idx].get('current_dataset')
            if current_dataset:
                file_path = self._get_file_path_for_dataset(
                    current_dataset,
                    self.subwindow_data[focused_idx].get('current_study_uid', ''),
                    self.subwindow_data[focused_idx].get('current_series_uid', ''),
                    self.subwindow_data[focused_idx].get('current_slice_index', 0)
                )
        
        self.dialog_coordinator.open_about_this_file(current_dataset, file_path)''',
    '''    def _open_about_this_file(self) -> None:
        """Handle About This File dialog request."""
        dialog_action_handlers.open_about_this_file(self)''',
    1,
)

# _open_slice_sync_dialog
content = content.replace(
    '''    def _open_slice_sync_dialog(self) -> None:
        """Open the Manage Sync Groups dialog."""
        from gui.dialogs.slice_sync_dialog import SliceSyncDialog
        current_groups = self.config_manager.get_slice_sync_groups()
        dlg = SliceSyncDialog(current_groups, parent=self.main_window)
        dlg.groups_changed.connect(self._on_slice_sync_groups_changed)
        dlg.exec()''',
    '''    def _open_slice_sync_dialog(self) -> None:
        """Open the Manage Sync Groups dialog."""
        dialog_action_handlers.open_slice_sync_dialog(self)''',
    1,
)

# _open_overlay_config
content = content.replace(
    '''    def _open_overlay_config(self) -> None:
        """Handle overlay configuration dialog request."""
        # Extract modality from current dataset if available
        current_modality = None
        if self.current_dataset is not None:
            modality = getattr(self.current_dataset, 'Modality', None)
            if modality:
                # Normalize modality (strip whitespace)
                modality_str = str(modality).strip()
                # Valid modalities list (must match overlay_config_dialog.py, alphabetical order, default first)
                valid_modalities = ["default", "CR", "CT", "DX", "MG", "MR", "NM", "PT", "RF", "RT", "US", "XA"]
                if modality_str in valid_modalities:
                    current_modality = modality_str
                # If modality is not in valid list, current_modality remains None (will default to "default")
        
        self.dialog_coordinator.open_overlay_config(current_modality=current_modality)''',
    '''    def _open_overlay_config(self) -> None:
        """Handle overlay configuration dialog request."""
        dialog_action_handlers.open_overlay_config(self)''',
    1,
)

# _open_quick_window_level
content = content.replace(
    '''    def _open_quick_window_level(self) -> None:
        """Open Quick Window/Level dialog for the focused subwindow. Apply entered center/width via view_state_manager.handle_window_changed."""
        if not self.view_state_manager:
            return
        initial_center = self.view_state_manager.current_window_center
        initial_width = self.view_state_manager.current_window_width
        center_range = self.window_level_controls.center_range
        width_range = self.window_level_controls.width_range
        unit = getattr(self.view_state_manager, "rescale_type", None) or None
        apply_callback = self.view_state_manager.handle_window_changed
        dlg = QuickWindowLevelDialog(
            parent=self.main_window,
            initial_center=initial_center,
            initial_width=initial_width,
            center_range=center_range,
            width_range=width_range,
            apply_callback=apply_callback,
            unit=unit,
        )
        dlg.raise_()
        dlg.activateWindow()
        dlg.exec()''',
    '''    def _open_quick_window_level(self) -> None:
        """Open Quick Window/Level dialog for the focused subwindow."""
        dialog_action_handlers.open_quick_window_level(self)''',
    1,
)

# _open_export
content = content.replace(
    '''    def _open_export(self) -> None:
        """Handle Export dialog request. Resolution options are in the dialog (Native / 1.5\\u00d7 / 2\\u00d7 / 4\\u00d7)."""
        window_center, window_width = self.window_level_controls.get_window_level()
        use_rescaled_values = self.view_state_manager.use_rescaled_values
        projection_enabled = self.slice_display_manager.projection_enabled
        projection_type = self.slice_display_manager.projection_type
        projection_slice_count = self.slice_display_manager.projection_slice_count
        focused_subwindow_index = self.get_focused_subwindow_index()
        # Option B: aggregate annotations from all subwindows for export
        subwindow_annotation_managers = []
        for idx in sorted(self.subwindow_managers.keys()):
            m = self.subwindow_managers[idx]
            subwindow_annotation_managers.append({
                'roi_manager': m.get('roi_manager'),
                'measurement_tool': m.get('measurement_tool'),
                'text_annotation_tool': m.get('text_annotation_tool'),
                'arrow_annotation_tool': m.get('arrow_annotation_tool')
            })
        self.dialog_coordinator.open_export(
            current_window_center=window_center,
            current_window_width=window_width,
            focused_subwindow_index=focused_subwindow_index,
            use_rescaled_values=use_rescaled_values,
            roi_manager=self.roi_manager,
            overlay_manager=self.overlay_manager,
            measurement_tool=self.measurement_tool,
            text_annotation_tool=getattr(self, 'text_annotation_tool', None),
            arrow_annotation_tool=getattr(self, 'arrow_annotation_tool', None),
            projection_enabled=projection_enabled,
            projection_type=projection_type,
            projection_slice_count=projection_slice_count,
            subwindow_annotation_managers=subwindow_annotation_managers
        )''',
    '''    def _open_export(self) -> None:
        """Handle Export dialog request. Resolution options are in the dialog."""
        dialog_action_handlers.open_export(self)''',
    1,
)

# ── 4. Write and verify ───────────────────────────────────────────────────────
with open(TARGET, 'w', encoding='utf-8') as f:
    f.write(content)

try:
    ast.parse(content)
    total_lines = content.count('\n') + 1
    print(f'SYNTAX OK\nLines: {total_lines}')
except SyntaxError as e:
    print(f'SYNTAX ERROR: {e}')
