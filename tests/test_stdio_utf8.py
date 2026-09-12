"""Tests for scripts/stdio_utf8.py."""

from __future__ import annotations

import importlib.util
import io
from pathlib import Path

_SCRIPT = Path(__file__).resolve().parent.parent / "scripts" / "stdio_utf8.py"
_spec = importlib.util.spec_from_file_location("stdio_utf8", _SCRIPT)
assert _spec and _spec.loader
stdio_utf8 = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(stdio_utf8)


def test_ensure_stdout_utf8_reconfigures_real_text_io_wrapper(monkeypatch):
    wrapper = io.TextIOWrapper(io.BytesIO(), encoding="latin-1")
    assert isinstance(wrapper, io.TextIOWrapper)
    assert wrapper.encoding == "latin-1"
    monkeypatch.setattr(stdio_utf8.sys, "stdout", wrapper)
    try:
        stdio_utf8.ensure_stdout_utf8()
        assert wrapper.encoding == "utf-8"
    finally:
        wrapper.close()


def test_ensure_stdout_utf8_noop_for_non_wrapper(monkeypatch):
    class _NotWrapper:
        pass

    fake = _NotWrapper()
    monkeypatch.setattr(stdio_utf8.sys, "stdout", fake)
    stdio_utf8.ensure_stdout_utf8()  # must not raise


def test_ensure_stdout_utf8_swallows_reconfigure_errors(monkeypatch):
    class _BoomWrapper(io.TextIOWrapper):
        def reconfigure(self, **_kwargs):  # type: ignore[override]
            raise ValueError("refused")

    wrapper = _BoomWrapper(io.BytesIO(), encoding="latin-1")
    monkeypatch.setattr(stdio_utf8.sys, "stdout", wrapper)
    try:
        stdio_utf8.ensure_stdout_utf8()  # must not raise
    finally:
        wrapper.close()
