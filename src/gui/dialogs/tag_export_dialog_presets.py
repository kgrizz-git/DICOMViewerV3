"""
Preset save/load/import/export mixin for the DICOM tag export dialog.

Inputs:
    - ConfigManager tag-export presets and the live tag tree selection

Outputs:
    - Combo list refresh, Save / Save As / Reload / Delete / Import / Export flows

Requirements:
    - PySide6 dialog widgets on the owning TagExportDialog
    - gui.dialogs.tag_export_dialog_helpers preset merge helpers
"""
# Pyright: methods run only on ``TagExportDialog`` (combined Qt type); mixin bases
# cannot express cross-mixin ``self`` without a duplicate protocol surface.
# ``reportArgumentType`` is also off so ``self`` can be passed as a ``QWidget``
# parent to ``QMessageBox`` / ``QFileDialog`` without a Protocol cast surface.
# pyright: reportAttributeAccessIssue=false, reportUninitializedInstanceVariable=false, reportArgumentType=false
from __future__ import annotations

import os
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFileDialog,
    QMessageBox,
    QTreeWidgetItem,
)

from gui.dialogs.tag_export_dialog_helpers import (
    _ITEM_NO_PRESET,
    _TITLE_NO_CONFIG_MANAGER,
    merged_dict_with_preset_tags,
    tag_export_preset_match_keys,
)


class TagExportDialogPresetsMixin:
    """
    Mixin for tag-export preset list management and persistence.

    Expects the owning dialog to provide ``config_manager``, ``preset_combo``,
    ``selected_tags``, the tags tree helpers, and union refresh methods.
    """

    def _load_presets_list(self) -> None:
        """Load list of presets into combo box."""
        if not self.config_manager or self.preset_combo is None:
            return

        self.preset_combo.clear()
        presets = self.config_manager.get_tag_export_presets()
        if presets:
            self.preset_combo.addItems(sorted(presets.keys()))
        self.preset_combo.addItem(_ITEM_NO_PRESET)
        self.preset_combo.setCurrentIndex(self.preset_combo.count() - 1)

    def _on_preset_selected(self, preset_name: str) -> None:
        """Auto-load the preset when the user selects it from the dropdown."""
        if not preset_name or preset_name == _ITEM_NO_PRESET:
            return
        if not self.config_manager:
            return
        self._load_preset_by_name(preset_name, show_feedback=False)

    def _save_current_preset(self) -> None:
        """
        Overwrite the currently selected preset, or fall back to Save As….

        When ``(No preset)`` / empty is selected, delegates to ``_save_preset``
        so the user can name a new preset (no separate warning dialog).
        """
        if not self.config_manager:
            QMessageBox.warning(
                self,
                _TITLE_NO_CONFIG_MANAGER,
                "Preset saving is not available.",
            )
            return
        if self.preset_combo is None:
            return

        current_name = self.preset_combo.currentText()
        if not current_name or current_name == _ITEM_NO_PRESET:
            self._save_preset()
            return

        # Synchronize selection: blockSignals paths (toggle-all / load) skip
        # _on_tag_selection_changed, so selected_tags may be stale.
        self._update_selected_tags()
        if not self.selected_tags:
            QMessageBox.warning(
                self,
                "No Tags Selected",
                "Please select at least one tag to save as a preset.",
            )
            return

        self.config_manager.save_tag_export_preset(current_name, self.selected_tags)
        QMessageBox.information(
            self,
            "Preset Updated",
            f"Preset '{current_name}' updated.",
        )

    def _save_preset(self) -> None:
        """Save current tag selections as a new named preset (Save As…)."""
        if not self.config_manager:
            QMessageBox.warning(
                self,
                _TITLE_NO_CONFIG_MANAGER,
                "Preset saving is not available.",
            )
            return

        # Update selected tags first
        self._update_selected_tags()

        if not self.selected_tags:
            QMessageBox.warning(
                self,
                "No Tags Selected",
                "Please select at least one tag to save as a preset.",
            )
            return

        from PySide6.QtWidgets import QInputDialog

        preset_name, ok = QInputDialog.getText(
            self,
            "Save Preset",
            "Enter preset name:",
            text="",
        )

        if not ok or not preset_name.strip():
            return

        preset_name = preset_name.strip()

        self.config_manager.save_tag_export_preset(preset_name, self.selected_tags)
        self._load_presets_list()

        if self.preset_combo is None:
            return
        index = self.preset_combo.findText(preset_name)
        if index >= 0:
            self.preset_combo.setCurrentIndex(index)

        QMessageBox.information(
            self,
            "Preset Saved",
            f"Preset '{preset_name}' saved successfully.",
        )

    def _load_preset(self) -> None:
        """Re-apply the preset currently shown in the combo (Reload button)."""
        if not self.config_manager:
            QMessageBox.warning(
                self,
                _TITLE_NO_CONFIG_MANAGER,
                "Preset loading is not available.",
            )
            return
        if self.preset_combo is None:
            return

        preset_name = self.preset_combo.currentText()
        if not preset_name or preset_name == _ITEM_NO_PRESET:
            QMessageBox.warning(
                self,
                "No Preset Selected",
                "Please select a preset to reload.",
            )
            return

        self._load_preset_by_name(preset_name, show_feedback=True)

    def _load_preset_by_name(
        self,
        preset_name: str,
        *,
        show_feedback: bool = True,
    ) -> None:
        """
        Apply preset *preset_name* to the tag tree.

        Parameters
        ----------
        preset_name:
            Name of a stored tag-export preset.
        show_feedback:
            When True (Reload button), show a success modal. Auto-load from the
            dropdown passes False so selecting presets is not modal-noisy.
        """
        if not self.config_manager:
            return

        presets = self.config_manager.get_tag_export_presets()
        if preset_name not in presets:
            QMessageBox.warning(
                self,
                "Preset Not Found",
                f"Preset '{preset_name}' not found.",
            )
            return

        preset_tags = presets[preset_name]
        # Add the preset's missing tags to whichever union is on screen. Always merging
        # into the flat one would drop a preset tag from view while Include sequences is
        # ticked, since that renders from the nested union instead.
        sequences_on = self.include_sequences_checkbox.isChecked()
        active_union = (
            self._ensure_sequences_union() if sequences_on else self._tag_union_merged_full
        )
        merged, preset_added = merged_dict_with_preset_tags(active_union, preset_tags)
        if preset_added:
            if sequences_on:
                self._tag_union_merged_sequences = merged
            else:
                self._tag_union_merged_full = merged
            self._refresh_tag_tree()
        match_keys = tag_export_preset_match_keys(preset_tags)

        # Apply preset to tag tree (tree is fresh if we rebuilt above; otherwise
        # uncheck everything first, at any depth).
        self.tags_tree.blockSignals(True)
        root = self.tags_tree.invisibleRootItem()

        if not preset_added:
            for item in self._iter_all_tag_items(root):
                item.setCheckState(0, Qt.CheckState.Unchecked)

        # Check tags that are in the preset (may be a nested path key if
        # the preset was saved with "Include sequences" on), then recompute
        # every ancestor's tri-state up to the root.
        checked_items: list[QTreeWidgetItem] = []
        for tag_item in self._iter_all_tag_items(root):
            tag_str = tag_item.data(0, Qt.ItemDataRole.UserRole)
            if tag_str is not None and tag_str in match_keys:
                tag_item.setCheckState(0, Qt.CheckState.Checked)
                checked_items.append(tag_item)

        for tag_item in checked_items:
            self._update_ancestors_check_state(tag_item.parent())

        self.tags_tree.blockSignals(False)
        self._filter_tags(self.tag_search.text())
        self._update_selected_tags()
        self._refresh_select_all_checkbox_state()

        if show_feedback:
            QMessageBox.information(
                self,
                "Preset Reloaded",
                f"Preset '{preset_name}' reloaded successfully.",
            )

    def _delete_preset(self) -> None:
        """Delete the selected preset."""
        if not self.config_manager:
            QMessageBox.warning(
                self,
                _TITLE_NO_CONFIG_MANAGER,
                "Preset deletion is not available.",
            )
            return
        if self.preset_combo is None:
            return

        preset_name = self.preset_combo.currentText()
        if not preset_name or preset_name == _ITEM_NO_PRESET:
            QMessageBox.warning(
                self,
                "No Preset Selected",
                "Please select a preset to delete.",
            )
            return

        reply = QMessageBox.question(
            self,
            "Delete Preset",
            f"Are you sure you want to delete preset '{preset_name}'?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )

        if reply == QMessageBox.StandardButton.Yes:
            self.config_manager.delete_tag_export_preset(preset_name)
            self._load_presets_list()
            QMessageBox.information(
                self,
                "Preset Deleted",
                f"Preset '{preset_name}' deleted successfully.",
            )

    def _export_presets(self) -> None:
        """Export all tag export presets to a JSON file."""
        if not self.config_manager:
            QMessageBox.warning(
                self,
                _TITLE_NO_CONFIG_MANAGER,
                "Preset export is not available.",
            )
            return

        presets = self.config_manager.get_tag_export_presets()
        if not presets:
            QMessageBox.information(
                self,
                "No Tag Presets",
                "There are no tag export presets to export.",
            )
            return

        last_export_path = self.config_manager.get_last_export_path()
        if not last_export_path or not os.path.exists(last_export_path):
            last_export_path = os.getcwd()

        if os.path.isfile(last_export_path):
            last_export_path = os.path.dirname(last_export_path)

        default_filename = str(Path(last_export_path) / "tag_export_presets.json")

        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "Export Tag Presets",
            default_filename,
            "JSON Files (*.json);;All Files (*)",
        )

        if not file_path:
            return

        if not file_path.endswith(".json"):
            file_path += ".json"

        if self.config_manager.export_tag_export_presets(file_path):
            self.config_manager.set_last_export_path(str(Path(file_path).parent))
            QMessageBox.information(
                self,
                "Export Successful",
                f"Tag export presets exported successfully to:\n{file_path}",
            )
        else:
            QMessageBox.warning(
                self,
                "Export Failed",
                f"Failed to export tag export presets to:\n{file_path}\n\n"
                "Please check file permissions and try again.",
            )

    def _import_presets(self) -> None:
        """Import tag export presets from a JSON file."""
        if not self.config_manager:
            QMessageBox.warning(
                self,
                _TITLE_NO_CONFIG_MANAGER,
                "Preset import is not available.",
            )
            return

        last_path = self.config_manager.get_last_path()
        if not last_path or not os.path.exists(last_path):
            last_path = os.getcwd()

        if os.path.isfile(last_path):
            last_path = os.path.dirname(last_path)

        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Import Tag Presets",
            last_path,
            "JSON Files (*.json);;All Files (*)",
        )

        if not file_path:
            return

        result = self.config_manager.import_tag_export_presets(file_path)
        if result is None:
            QMessageBox.critical(
                self,
                "Import Failed",
                "Failed to import tag export presets.\n\n"
                "Please verify that the file is a valid DICOM Viewer V3 tag presets file.",
            )
            return

        imported = result.get("imported", 0)
        skipped = result.get("skipped_conflicts", 0)

        self._load_presets_list()

        if imported == 0 and skipped == 0:
            QMessageBox.information(
                self,
                "No Presets Imported",
                "The selected file did not contain any tag export presets.",
            )
        else:
            details_lines = [f"Presets imported: {imported}"]
            if skipped > 0:
                details_lines.append(
                    "Presets skipped (already exist and were not overwritten): "
                    f"{skipped}"
                )
            details = "\n".join(details_lines)
            QMessageBox.information(
                self,
                "Import Complete",
                f"Tag export presets import completed.\n\n{details}",
            )
