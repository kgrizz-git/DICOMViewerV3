"""Tests for debug_flags: toggle defaults and environment variables."""

from __future__ import annotations

import importlib
import os

import utils.debug_flags


def test_all_debug_flags_default_to_false() -> None:
    # Inspect all attributes starting with DEBUG_ and ensure they are False
    for name in dir(utils.debug_flags):
        if name.startswith("DEBUG_"):
            val = getattr(utils.debug_flags, name)
            assert val is False, (
                f"Expected debug flag {name} to be False, but got {val}"
            )


def test_perf_log_respects_env_disabled(monkeypatch) -> None:
    for value in (None, "0", "true"):
        if value is None:
            monkeypatch.delenv("DICOM_PERF_LOG", raising=False)
        else:
            monkeypatch.setenv("DICOM_PERF_LOG", value)
        importlib.reload(utils.debug_flags)
        assert utils.debug_flags.PERF_LOG is False


def test_perf_log_respects_env_enabled(monkeypatch) -> None:
    original_value = os.environ.get("DICOM_PERF_LOG")
    try:
        monkeypatch.setenv("DICOM_PERF_LOG", "1")
        importlib.reload(utils.debug_flags)
        assert utils.debug_flags.PERF_LOG is True
    finally:
        if original_value is None:
            monkeypatch.delenv("DICOM_PERF_LOG", raising=False)
        else:
            monkeypatch.setenv("DICOM_PERF_LOG", original_value)
        importlib.reload(utils.debug_flags)


def test_debug_flags_type() -> None:
    for name in dir(utils.debug_flags):
        if name.startswith("DEBUG_"):
            val = getattr(utils.debug_flags, name)
            assert isinstance(val, bool)
