"""
File Selection Dialog

This module provides file and folder selection dialogs with proper
window focus behavior and last path memory.

Inputs:
    - User file/folder selections
    - Configuration for last path
    
Outputs:
    - Selected file/folder paths
    - Updated configuration
    
Requirements:
    - PySide6 for dialogs
    - ConfigManager for path memory
"""

import os
import platform

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFileDialog, QMessageBox

from utils.config_manager import ConfigManager


class FileDialog:
    """
    Handles file and folder selection dialogs.
    
    Features:
    - Multiple file selection
    - Last path memory
    - Proper window focus (appears on top initially)
    - Extension-agnostic file filtering
    """

    def __init__(self, config_manager: ConfigManager | None = None):
        """
        Initialize the file dialog handler.
        
        Args:
            config_manager: Optional ConfigManager instance
        """
        self.config_manager = config_manager or ConfigManager()

    def open_files(self, parent=None) -> list[str]:
        """
        Open file selection dialog for multiple files.
        
        Args:
            parent: Parent widget for the dialog
            
        Returns:
            List of selected file paths
        """
        # Get last path or use current directory
        last_path = self.config_manager.get_last_path()
        if not last_path or not os.path.exists(last_path):
            last_path = os.getcwd()

        # If last path is a file, use its directory
        if os.path.isfile(last_path):
            last_path = os.path.dirname(last_path)

        # On macOS, use static method to get native file dialog with sidebar
        if platform.system() == "Darwin":
            # Use static method for native macOS dialog (shows sidebar with shortcuts, iCloud, etc.)
            # Use "*" instead of "*.*" to show all files including those without extensions
            selected_files, _ = QFileDialog.getOpenFileNames(
                parent,
                "Open DICOM File(s)",
                last_path,
                "All Files (*);;DICOM Files (*.dcm)"
            )

            if selected_files:
                # Save last path
                self.config_manager.set_last_path(selected_files[0])
                return selected_files

            return []
        else:
            # For other platforms, use the existing instance-based approach
            # Create file dialog
            dialog = QFileDialog(parent)
            dialog.setWindowTitle("Open DICOM File(s)")
            dialog.setFileMode(QFileDialog.FileMode.ExistingFiles)
            dialog.setDirectory(last_path)

            # Accept all files (extension-agnostic)
            # Use "*" instead of "*.*" to show all files including those without extensions
            dialog.setNameFilter("All Files (*);;DICOM Files (*.dcm)")

            # Ensure dialog appears on top
            dialog.setWindowFlags(dialog.windowFlags() | Qt.WindowType.WindowStaysOnTopHint)
            dialog.activateWindow()
            dialog.raise_()

            # Show dialog
            if dialog.exec():
                selected_files = dialog.selectedFiles()
                if selected_files:
                    # Save last path
                    self.config_manager.set_last_path(selected_files[0])
                    return selected_files

            return []

    def open_folder(self, parent=None) -> str | None:
        """
        Open folder selection dialog.
        
        Args:
            parent: Parent widget for the dialog
            
        Returns:
            Selected folder path or None
        """
        # Get last path or use current directory
        last_path = self.config_manager.get_last_path()
        if not last_path or not os.path.exists(last_path):
            last_path = os.getcwd()

        # If last path is a file, use its directory
        if os.path.isfile(last_path):
            last_path = os.path.dirname(last_path)
        elif os.path.isdir(last_path):
            pass  # Already a directory
        else:
            last_path = os.getcwd()

        # On macOS, use static method to get native file dialog with sidebar
        if platform.system() == "Darwin":
            # Use static method for native macOS dialog (shows sidebar with shortcuts, iCloud, etc.)
            selected_folder = QFileDialog.getExistingDirectory(
                parent,
                "Open DICOM Folder",
                last_path
            )

            if selected_folder:
                # Save last path
                self.config_manager.set_last_path(selected_folder)
                return selected_folder

            return None
        else:
            # For other platforms, use the existing instance-based approach
            # Create folder dialog
            dialog = QFileDialog(parent)
            dialog.setWindowTitle("Open DICOM Folder")
            dialog.setFileMode(QFileDialog.FileMode.Directory)
            dialog.setDirectory(last_path)

            # Ensure dialog appears on top
            dialog.setWindowFlags(dialog.windowFlags() | Qt.WindowType.WindowStaysOnTopHint)
            dialog.activateWindow()
            dialog.raise_()

            # Show dialog
            if dialog.exec():
                selected_folders = dialog.selectedFiles()
                if selected_folders:
                    folder_path = selected_folders[0]
                    # Save last path
                    self.config_manager.set_last_path(folder_path)
                    return folder_path

            return None

    def show_warning(self, parent=None, title: str = "Warning",
                    message: str = "") -> None:
        """
        Show a warning dialog.
        
        Args:
            parent: Parent widget
            title: Dialog title
            message: Warning message
        """
        msg_box = QMessageBox(parent)
        msg_box.setIcon(QMessageBox.Icon.Warning)
        msg_box.setWindowTitle(title)
        msg_box.setText(message)

        # Ensure dialog appears on top
        msg_box.setWindowFlags(msg_box.windowFlags() | Qt.WindowType.WindowStaysOnTopHint)
        msg_box.activateWindow()
        msg_box.raise_()

        msg_box.exec()

    def confirm_large_files(
        self,
        parent=None,
        large_files: list[tuple[str, float]] | None = None,
        threshold_mb: float = 25.0,
    ) -> bool:
        """
        Ask whether to open files that exceed the large-file size threshold.

        Args:
            parent: Parent widget for the dialog.
            large_files: ``(filename, size_mb)`` pairs to list in the message.
            threshold_mb: Threshold used for detection (shown in the prompt).

        Returns:
            True if the user chooses **Continue**; False for **Cancel**.
        """
        if not large_files:
            return True

        threshold_label = int(threshold_mb)
        summary = (
            f"{len(large_files)} large file(s) exceed {threshold_label} MB.\n"
            "Loading may make the application temporarily unresponsive.\n\n"
            "Files:\n"
        )
        for filename, size_mb in large_files[:10]:
            summary += f"  • {filename} ({size_mb:.1f} MB)\n"
        if len(large_files) > 10:
            summary += f"  … and {len(large_files) - 10} more\n"

        msg_box = QMessageBox(parent)
        msg_box.setIcon(QMessageBox.Icon.Warning)
        msg_box.setWindowTitle("Large Files")
        msg_box.setText(
            f"One or more files are larger than {threshold_label} MB.\n"
            "Continue loading?"
        )
        msg_box.setInformativeText(summary.strip())

        continue_btn = msg_box.addButton(
            "Continue", QMessageBox.ButtonRole.AcceptRole
        )
        msg_box.addButton("Cancel", QMessageBox.ButtonRole.RejectRole)
        msg_box.setDefaultButton(continue_btn)

        msg_box.setWindowFlags(
            msg_box.windowFlags() | Qt.WindowType.WindowStaysOnTopHint
        )
        msg_box.activateWindow()
        msg_box.raise_()

        msg_box.exec()
        return msg_box.clickedButton() is continue_btn

    def show_error(self, parent=None, title: str = "Error",
                  message: str = "") -> None:
        """
        Show an error dialog.
        
        Args:
            parent: Parent widget
            title: Dialog title
            message: Error message
        """
        msg_box = QMessageBox(parent)
        msg_box.setIcon(QMessageBox.Icon.Critical)
        msg_box.setWindowTitle(title)
        msg_box.setText(message)

        # Ensure dialog appears on top
        msg_box.setWindowFlags(msg_box.windowFlags() | Qt.WindowType.WindowStaysOnTopHint)
        msg_box.activateWindow()
        msg_box.raise_()

        msg_box.exec()

