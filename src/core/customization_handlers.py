"""
Customization and tag-preset export/import handlers.

This module provides a helper that handles file dialogs, path resolution,
config_manager export/import calls, and success/failure messages for:
- Export/import customizations (visual settings, overlay, theme, metadata columns)
- Export/import tag export presets

Inputs:
    - config_manager: application config (get/set paths, export/import methods)
    - main_window: parent for QFileDialog and QMessageBox
    - after_import_customizations: optional callable() invoked after successful
      import of customizations (e.g. apply overlay, theme, metadata panel)
    - on_tag_presets_imported: optional callable() invoked after successful
      import of tag presets (e.g. refresh tag export dialog)

Outputs:
    - None; methods show dialogs and messages and update config as appropriate.

Requirements:
    - PySide6.QtWidgets (QFileDialog, QMessageBox)
    - config_manager with get_last_path, get_last_export_path, set_last_export_path,
      export_customizations, import_customizations, get_tag_export_presets,
      export_tag_export_presets, import_tag_export_presets
"""

import os
from typing import Callable, Optional, Any

from PySide6.QtWidgets import QFileDialog, QMessageBox


class CustomizationHandlers:
    """
    Handles export/import of customizations and tag export presets:
    path resolution, file dialogs, config_manager calls, and user messages.
    """

    def __init__(
        self,
        config_manager: Any,
        main_window: Any,
        *,
        after_import_customizations: Optional[Callable[[], None]] = None,
        on_tag_presets_imported: Optional[Callable[[], None]] = None,
    ) -> None:
        self._config = config_manager
        self._main_window = main_window
        self._after_import_customizations = after_import_customizations
        self._on_tag_presets_imported = on_tag_presets_imported

    def export_customizations(self) -> None:
        """Run export customizations: resolve path, save dialog, export, update path and message."""
        last_export_path = self._config.get_last_export_path()
        if not last_export_path or not os.path.exists(last_export_path):
            last_export_path = os.getcwd()
        if os.path.isfile(last_export_path):
            last_export_path = os.path.dirname(last_export_path)
        default_filename = os.path.join(last_export_path, "dicom_viewer_customizations.json")

        file_path, _ = QFileDialog.getSaveFileName(
            self._main_window,
            "Export Customizations",
            default_filename,
            "JSON Files (*.json);;All Files (*)",
        )
        if not file_path:
            return
        if not file_path.endswith(".json"):
            file_path += ".json"

        if self._config.export_customizations(file_path):
            self._config.set_last_export_path(os.path.dirname(file_path))
            QMessageBox.information(
                self._main_window,
                "Export Successful",
                f"Customizations exported successfully to:\n{file_path}",
            )
        else:
            QMessageBox.warning(
                self._main_window,
                "Export Failed",
                f"Failed to export customizations to:\n{file_path}\n\n"
                "Please check file permissions and try again.",
            )

    def import_customizations(self) -> None:
        """Run import customizations: resolve path, open dialog, import; on success run callback and message."""
        last_path = self._config.get_last_path()
        if not last_path or not os.path.exists(last_path):
            last_path = os.getcwd()
        if os.path.isfile(last_path):
            last_path = os.path.dirname(last_path)

        file_path, _ = QFileDialog.getOpenFileName(
            self._main_window,
            "Import Customizations",
            last_path,
            "JSON Files (*.json);;All Files (*)",
        )
        if not file_path:
            return

        if self._config.import_customizations(file_path):
            if self._after_import_customizations:
                self._after_import_customizations()
            QMessageBox.information(
                self._main_window,
                "Import Successful",
                "Customizations imported successfully.\n\nAll settings have been applied.",
            )
        else:
            QMessageBox.warning(
                self._main_window,
                "Import Failed",
                f"Failed to import customizations from:\n{file_path}\n\n"
                "Please check that the file is a valid customization file and try again.",
            )

    def export_tag_presets(self) -> None:
        """Run export tag presets: if no presets show message and return; else path, save dialog, export, message."""
        presets = self._config.get_tag_export_presets()
        if not presets:
            QMessageBox.information(
                self._main_window,
                "No Tag Presets",
                "There are no tag export presets to export.",
            )
            return

        last_export_path = self._config.get_last_export_path()
        if not last_export_path or not os.path.exists(last_export_path):
            last_export_path = os.getcwd()
        if os.path.isfile(last_export_path):
            last_export_path = os.path.dirname(last_export_path)
        default_filename = os.path.join(last_export_path, "tag_export_presets.json")

        file_path, _ = QFileDialog.getSaveFileName(
            self._main_window,
            "Export Tag Presets",
            default_filename,
            "JSON Files (*.json);;All Files (*)",
        )
        if not file_path:
            return
        if not file_path.endswith(".json"):
            file_path += ".json"

        if self._config.export_tag_export_presets(file_path):
            self._config.set_last_export_path(os.path.dirname(file_path))
            QMessageBox.information(
                self._main_window,
                "Export Successful",
                f"Tag export presets exported successfully to:\n{file_path}",
            )
        else:
            QMessageBox.warning(
                self._main_window,
                "Export Failed",
                f"Failed to export tag export presets to:\n{file_path}\n\n"
                "Please check file permissions and try again.",
            )

    def import_tag_presets(self) -> None:
        """Run import tag presets: path, open dialog, import; show message; optionally run callback."""
        last_path = self._config.get_last_path()
        if not last_path or not os.path.exists(last_path):
            last_path = os.getcwd()
        if os.path.isfile(last_path):
            last_path = os.path.dirname(last_path)

        file_path, _ = QFileDialog.getOpenFileName(
            self._main_window,
            "Import Tag Presets",
            last_path,
            "JSON Files (*.json);;All Files (*)",
        )
        if not file_path:
            return

        result = self._config.import_tag_export_presets(file_path)
        if result is None:
            QMessageBox.critical(
                self._main_window,
                "Import Failed",
                "Failed to import tag export presets.\n\n"
                "Please verify that the file is a valid DICOM Viewer V3 tag presets file.",
            )
            return

        imported = result.get("imported", 0)
        skipped = result.get("skipped_conflicts", 0)

        if imported == 0 and skipped == 0:
            QMessageBox.information(
                self._main_window,
                "No Presets Imported",
                "The selected file did not contain any tag export presets.",
            )
        else:
            details_lines = [f"Presets imported: {imported}"]
            if skipped > 0:
                details_lines.append(
                    f"Presets skipped (already exist and were not overwritten): {skipped}"
                )
            details = "\n".join(details_lines)
            QMessageBox.information(
                self._main_window,
                "Import Complete",
                f"Tag export presets import completed.\n\n{details}",
            )

        if self._on_tag_presets_imported:
            self._on_tag_presets_imported()
