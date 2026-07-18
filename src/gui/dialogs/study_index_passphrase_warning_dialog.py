"""
Study Index Passphrase Warning Dialog

Shown each time the Study Index is opened until the user dismisses it
permanently via the "Don't show this again" checkbox.

Context: the local study index is encrypted with a random passphrase
stored in the OS credential store (Windows Credential Manager).  If that
credential is deleted the encrypted database becomes unrecoverable, so the
user needs to know it exists and how to back it up.

The passphrase is auto-generated and never chosen by the user.
"""

from __future__ import annotations

import platform

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QLabel,
    QVBoxLayout,
    QWidget,
)


def _credential_store_name() -> str:
    """Return the OS-appropriate name for the credential store."""
    system = platform.system()
    if system == "Windows":
        return "Windows Credential Manager"
    elif system == "Darwin":
        return "macOS Keychain"
    else:
        return "the system keyring (e.g. GNOME Keyring / KWallet)"


def _credential_how_to_open() -> str:
    system = platform.system()
    if system == "Windows":
        return (
            "Open <b>Control Panel → Credential Manager → Windows Credentials</b> "
            "and look for an entry named <b>DICOMViewerV3</b>."
        )
    elif system == "Darwin":
        return (
            "Open <b>Keychain Access</b> and search for <b>DICOMViewerV3</b>."
        )
    else:
        return (
            "Open your system keyring manager and look for the service "
            "<b>DICOMViewerV3</b>, user <b>study_index_sqlcipher_passphrase</b>."
        )


class StudyIndexPassphraseWarningDialog(QDialog):
    """
    Non-blocking informational dialog about the study index encryption key.

    Attributes:
        dismissed_permanently: True if the user ticked "Don't show this again".
    """

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Study Index — Encryption Key Notice")
        self.setMinimumWidth(520)
        self.dismissed_permanently: bool = False
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setSpacing(12)
        layout.setContentsMargins(16, 16, 16, 12)

        # ── Heading ──────────────────────────────────────────────────────────
        heading = QLabel("Your study index is encrypted")
        heading.setStyleSheet("font-weight: bold; font-size: 11pt;")
        layout.addWidget(heading)

        # ── Body text ────────────────────────────────────────────────────────
        body_text = (
            "The local study index is protected by an encryption key that was "
            "automatically generated when you first used the index. "
            "You did not choose this key and it is not visible in the app.<br><br>"
            f"The key is stored in <b>{_credential_store_name()}</b>. "
            "If that entry is deleted — for example after a Windows profile reset, "
            "a corporate IT policy sweep, or manual removal — "
            "<b>the index database becomes permanently unrecoverable</b>. "
            "No data is lost from your DICOM files themselves, but you would need "
            "to re-index all your folders from scratch.<br><br>"
            "<b>To back up the key:</b><br>"
            f"{_credential_how_to_open()} "
            "Save the password value somewhere secure (password manager, encrypted note, etc.)."
        )
        body = QLabel(body_text)
        body.setWordWrap(True)
        body.setTextFormat(Qt.TextFormat.RichText)
        body.setOpenExternalLinks(False)
        layout.addWidget(body)

        # ── "Don't show again" checkbox ───────────────────────────────────
        self._dont_show_cb = QCheckBox("Don't show this warning again")
        layout.addWidget(self._dont_show_cb)

        # ── Buttons ───────────────────────────────────────────────────────
        btn_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok)
        btn_box.accepted.connect(self._on_ok)
        layout.addWidget(btn_box)

    def _on_ok(self) -> None:
        self.dismissed_permanently = self._dont_show_cb.isChecked()
        self.accept()
