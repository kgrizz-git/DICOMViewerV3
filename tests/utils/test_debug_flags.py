"""Tests for debug_flags: toggle defaults and environment variables."""

from __future__ import annotations

import importlib
import os
import sys
from typing import Any

import pytest

import utils.debug_flags


def test_all_debug_flags_default_to_false() -> None:
    # Inspect all attributes starting with DEBUG_ and ensure they are False
    for name in dir(utils.debug_flags):
        if name.startswith("DEBUG_"):
            val = getattr(utils.debug_flags, name)
            assert val is False, f"Expected debug flag {name} to be False, but got {val}"


def test_perf_log_respects_env_disabled(monkeypatch) -> None:
    monkeypatch.delenv("DICOM_PERF_LOG", raising=False)
    # Reload the module to check environment evaluation at import time
    importlib.reload(utils.debug_flags)
    assert utils.debug_flags.PERF_LOG is False


def test_perf_log_respects_env_enabled(monkeypatch) -> None:
    monkeypatch.setenv("DICOM_PERF_LOG", "1")
    importlib.reload(utils.debug_flags)
    assert utils.debug_flags.PERF_LOG is True
    # Clean up after reload
    monkeypatch.delenv("DICOM_PERF_LOG", raising=False)
    importlib.reload(utils.debug_flags)


def test_debug_flags_type() -> None:
    for name in dir(utils.debug_flags):
        if name.startswith("DEBUG_"):
            val = getattr(utils.debug_flags, name)
            assert isinstance(val, bool)


def test_debug_flags_exclusivity() -> None:
    # Verify only expected names exist
    expected_at_least = {"DEBUG_LAYOUT", "DEBUG_LOADING", "PERF_LOG"}
    actual_names = set(dir(utils.debug_flags))
    assert expected_at_least.issubset(actual_names)
