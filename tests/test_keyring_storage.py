"""
Unit tests for core.study_index.keyring_storage (SQLCipher passphrase via OS
keyring). ``keyring`` is imported inside the function under test, so a fake
module is injected into sys.modules for isolation from the real OS credential
store.
"""

from __future__ import annotations

import sys
import types

from core.study_index.keyring_storage import (
    _KEYRING_SERVICE,
    _KEYRING_USER,
    get_or_create_study_index_passphrase,
)


def _install_fake_keyring(monkeypatch, initial_password=None):
    store = {}
    if initial_password is not None:
        store[(_KEYRING_SERVICE, _KEYRING_USER)] = initial_password

    fake_keyring = types.ModuleType("keyring")

    def get_password(service, user):
        return store.get((service, user))

    def set_password(service, user, password):
        store[(service, user)] = password

    fake_keyring.get_password = get_password
    fake_keyring.set_password = set_password
    monkeypatch.setitem(sys.modules, "keyring", fake_keyring)
    return store


def test_returns_existing_passphrase_without_creating_new_one(monkeypatch):
    store = _install_fake_keyring(monkeypatch, initial_password="existing-secret")
    result = get_or_create_study_index_passphrase()
    assert result == "existing-secret"
    assert store[(_KEYRING_SERVICE, _KEYRING_USER)] == "existing-secret"


def test_creates_and_persists_new_passphrase_when_missing(monkeypatch):
    store = _install_fake_keyring(monkeypatch, initial_password=None)
    result = get_or_create_study_index_passphrase()
    assert result
    assert isinstance(result, str)
    assert store[(_KEYRING_SERVICE, _KEYRING_USER)] == result


def test_new_passphrase_is_persisted_across_calls(monkeypatch):
    _install_fake_keyring(monkeypatch, initial_password=None)
    first = get_or_create_study_index_passphrase()
    second = get_or_create_study_index_passphrase()
    assert first == second
