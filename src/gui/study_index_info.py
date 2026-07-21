"""Shared, UI-agnostic helpers describing where the local study index lives.

Used by the first-open indexing prompt and the Study Index dialog so the
"where is this saved / what does it store" copy stays consistent.
"""

from __future__ import annotations

import sys
from datetime import datetime
from pathlib import Path

from PySide6.QtCore import QUrl
from PySide6.QtGui import QDesktopServices

from utils.config_manager import ConfigManager


def study_index_db_path(config: ConfigManager) -> str:
    """Return the resolved study-index database path (user override or default)."""
    return config.get_study_index_db_path()


def study_index_about_lines(config: ConfigManager) -> list[str]:
    """Human-readable lines describing the index location and what it stores."""
    return [
        "Saved on this device at:",
        study_index_db_path(config),
        "Stores clinical metadata and file locations — not image pixel data — "
        "and is encrypted at rest.",
        "You can change the location or clear the index later in Edit → Settings.",
    ]


def credential_store_label() -> str:
    """Human name of the OS credential store holding the index encryption key."""
    if sys.platform == "darwin":
        return "macOS Keychain"
    if sys.platform.startswith("win"):
        return "Windows Credential Manager"
    return "the system credential store (Secret Service / libsecret)"


def credential_store_note() -> str:
    """One-line note describing where the SQLCipher key is kept."""
    return (
        f"The encryption key is stored in {credential_store_label()} "
        "under service “DICOMViewerV3”."
    )


def format_size_on_disk(num_bytes: int | None) -> str:
    """Human-readable file size, or a placeholder when the DB does not exist yet."""
    if num_bytes is None:
        return "Not created yet"
    size = float(num_bytes)
    for unit in ("bytes", "KB", "MB", "GB"):
        if size < 1024 or unit == "GB":
            if unit == "bytes":
                return f"{int(size)} bytes"
            return f"{size:.1f} {unit}"
        size /= 1024
    return f"{size:.1f} GB"


def format_last_modified(mtime: float | None) -> str:
    """Local ``YYYY-MM-DD HH:MM`` for a DB mtime, or a placeholder when absent."""
    if mtime is None:
        return "Not created yet"
    try:
        return datetime.fromtimestamp(mtime).strftime("%Y-%m-%d %H:%M")
    except (OverflowError, OSError, ValueError):
        return ""


def open_study_index_location(config: ConfigManager) -> bool:
    """Reveal the index folder in the OS file manager.

    The database file may not exist yet (e.g. before anything is indexed), so
    open the nearest existing ancestor directory. Returns whether the open
    request was accepted by the platform.
    """
    folder = Path(study_index_db_path(config)).parent
    while not folder.exists() and folder != folder.parent:
        folder = folder.parent
    return QDesktopServices.openUrl(QUrl.fromLocalFile(str(folder)))
