"""Shared, UI-agnostic helpers describing where the local study index lives.

Used by the first-open indexing prompt and the Study Index dialog so the
"where is this saved / what does it store" copy stays consistent.
"""

from __future__ import annotations

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
