"""
Paths Config Mixin

Manages file and folder path settings: last opened path, last export path,
and the recent-files list (add, retrieve, remove, normalize).

Mixin contract:
    Expects `self.config` (dict) and `self.save_config()` to be provided by
    the concrete ConfigManager class that inherits this mixin.
"""

import os
from typing import List, Optional


class PathsConfigMixin:
    """Config mixin: last-opened path, last-export path, and recent files."""

    def get_last_path(self) -> str:
        """
        Get the last opened file or folder path.

        Returns:
            Path string, empty if not set
        """
        return self.config.get("last_path", "")

    def set_last_path(self, path: str) -> None:
        """
        Set the last opened file or folder path.

        Args:
            path: Path to save
        """
        self.config["last_path"] = path
        self.save_config()

    def get_last_export_path(self) -> str:
        """
        Get the last export directory path.

        Returns:
            Path string, empty if not set
        """
        return self.config.get("last_export_path", "")

    def set_last_export_path(self, path: str) -> None:
        """
        Set the last export directory path.

        Args:
            path: Path to save
        """
        self.config["last_export_path"] = path
        self.save_config()

    @staticmethod
    def normalize_path(file_path: str) -> Optional[str]:
        """
        Normalize a file or folder path for consistent storage.

        Removes trailing slashes, normalizes path separators, converts to absolute
        path, and handles edge cases like root directory and empty strings.

        Args:
            file_path: Path to normalize

        Returns:
            Normalized path string, or None if path is invalid or empty
        """
        if not file_path or not isinstance(file_path, str):
            return None

        file_path = file_path.strip()
        if not file_path:
            return None

        normalized = os.path.normpath(file_path)

        # Always resolve to absolute (even if path doesn't yet exist)
        normalized = os.path.abspath(normalized)

        # Remove trailing slashes except for filesystem roots
        if normalized != os.path.sep and normalized != "/":
            while normalized.endswith(os.path.sep) or normalized.endswith("/"):
                normalized = normalized.rstrip(os.path.sep).rstrip("/")
                if normalized == "":
                    normalized = os.path.sep
                    break

        if normalized == os.path.sep or normalized == "/":
            return normalized

        # Preserve Windows drive root (e.g. "C:\")
        if os.name == "nt" and len(normalized) == 3 and normalized[1:3] == ":\\":
            return normalized

        return normalized

    def get_recent_files(self) -> List[str]:
        """
        Get list of recently opened files and folders.

        Returns:
            List of file/folder paths (most recent first)
        """
        return self.config.get("recent_files", [])

    def add_recent_file(self, file_path: str) -> None:
        """
        Add a file or folder to recent files list.

        Removes duplicates and keeps only the most recent 20 items.
        Paths are normalized before being stored.

        Args:
            file_path: Path to file or folder
        """
        normalized_path = self.normalize_path(file_path)
        if not normalized_path:
            return

        recent_files = self.config.get("recent_files", [])

        if normalized_path in recent_files:
            recent_files.remove(normalized_path)

        recent_files.insert(0, normalized_path)
        recent_files = recent_files[:20]

        self.config["recent_files"] = recent_files
        self.save_config()

    def remove_recent_file(self, file_path: str) -> None:
        """
        Remove a file or folder from recent files list.

        Args:
            file_path: Path to file or folder to remove
        """
        recent_files = self.config.get("recent_files", [])
        if file_path in recent_files:
            recent_files.remove(file_path)
            self.config["recent_files"] = recent_files
            self.save_config()
