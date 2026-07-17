"""First-use consent prompt for automatic encrypted study-index persistence."""

from __future__ import annotations

from PySide6.QtWidgets import QMessageBox, QWidget

from utils.config_manager import ConfigManager


def ensure_study_index_auto_add_consent(
    config: ConfigManager,
    parent: QWidget | None,
) -> bool:
    """Prompt once when consent is unrecorded and return the effective choice."""

    if config.has_study_index_auto_add_consent():
        return config.get_study_index_auto_add_on_open()

    prefix = (
        "This version now requires an explicit privacy choice for automatic indexing. "
        if config.is_study_index_auto_add_consent_migration()
        else ""
    )
    answer = QMessageBox.question(
        parent,
        "Local Study Index",
        prefix
        + "Automatically add successfully opened DICOM files to the encrypted local "
        "study index? The index stores clinical metadata and file locations on this "
        "device. Automatic indexing is off unless you choose Enable. You can change "
        "this later and clear the index in Settings.",
        QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        QMessageBox.StandardButton.No,
    )
    enabled = answer == QMessageBox.StandardButton.Yes
    if not config.set_study_index_auto_add_on_open(enabled):
        QMessageBox.warning(
            parent,
            "Choice Not Saved",
            "Automatic indexing remains off because the privacy choice could not be saved.",
        )
        return False
    return enabled
