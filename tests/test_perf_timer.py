"""
Unit tests for utils.perf_timer (zero-overhead performance timing context manager).
"""

import logging

import pytest

import utils.perf_timer as perf_timer_module
from utils.perf_timer import perf_mark, perf_timer


def test_disabled_perf_log_yields_without_logging(monkeypatch, caplog):
    monkeypatch.setattr(perf_timer_module, "PERF_LOG", False)
    with caplog.at_level(logging.INFO, logger="perf"), perf_timer("disabled-block"):
        pass
    assert caplog.records == []


def test_enabled_perf_log_emits_perf_message(monkeypatch, caplog):
    monkeypatch.setattr(perf_timer_module, "PERF_LOG", True)
    with caplog.at_level(logging.INFO, logger="perf"), perf_timer(
        "first_paint.display_slice"
    ):
        pass
    assert len(caplog.records) == 1
    message = caplog.records[0].getMessage()
    assert "operation=performance.timer" in message
    assert "category=first_paint.display_slice" in message
    assert "elapsed_ms=" in message


def test_disabled_perf_mark_does_not_log(monkeypatch, caplog):
    monkeypatch.setattr(perf_timer_module, "PERF_LOG", False)
    with caplog.at_level(logging.INFO, logger="perf"):
        perf_mark("disabled-mark", field="value")
    assert caplog.records == []


def test_enabled_perf_mark_logs_fields(monkeypatch, caplog):
    monkeypatch.setattr(perf_timer_module, "PERF_LOG", True)
    with caplog.at_level(logging.INFO, logger="perf"):
        perf_mark(
            "first_paint.display_slice.returned",
            image_item_present=True,
            field="value",
        )
    assert len(caplog.records) == 1
    message = caplog.records[0].getMessage()
    assert "operation=performance.mark" in message
    assert "category=first_paint.display_slice.returned" in message
    assert "field=" not in message
    assert "metric=[REDACTED]" in message
    assert "image_item_present=true" in message


def test_enabled_perf_log_reraises_exceptions(monkeypatch):
    monkeypatch.setattr(perf_timer_module, "PERF_LOG", True)
    with pytest.raises(ValueError, match="boom"), perf_timer("error-block"):
        raise ValueError("boom")
