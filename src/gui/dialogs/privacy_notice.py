"""Small, consistently styled privacy notices for export dialogs."""

from __future__ import annotations

from PySide6.QtWidgets import QLabel, QWidget


def create_privacy_notice(text: str, object_name: str, parent: QWidget) -> QLabel:
    """Return a wrapped amber notice with a stable object name for UI tests."""
    notice = QLabel(text, parent)
    notice.setObjectName(object_name)
    notice.setWordWrap(True)
    notice.setStyleSheet("QLabel { color: #b45309; padding: 6px; background: #fffbeb; }")
    return notice


def create_tag_export_privacy_notice(parent: QWidget) -> QLabel:
    """Return the scope notice used by the tag-export dialog."""
    return create_privacy_notice(
        "<b>Privacy notice:</b> Tag exports can include patient and other identifying "
        "metadata. Private tags may contain additional identifying information. Review "
        "the selected fields and protect the exported file appropriately.",
        "tagExportPrivacyNotice",
        parent,
    )
