"""
Keyring helpers for the local study index SQLCipher passphrase.

Generates a random passphrase on first use and stores it in the OS credential
store (Windows Credential Manager, macOS Keychain, Freedesktop Secret Service).
"""

from __future__ import annotations

import secrets

_KEYRING_SERVICE = "DICOMViewerV3"
_KEYRING_USER = "study_index_sqlcipher_passphrase"


def get_or_create_study_index_passphrase() -> str:
    """
    Return the persisted SQLCipher passphrase, creating one if missing.

    Returns:
        Non-empty passphrase string suitable for ``PRAGMA key``.
    """
    import keyring

    existing = keyring.get_password(_KEYRING_SERVICE, _KEYRING_USER)
    if existing:
        return existing
    new_key = secrets.token_urlsafe(32)
    keyring.set_password(_KEYRING_SERVICE, _KEYRING_USER, new_key)
    return new_key
