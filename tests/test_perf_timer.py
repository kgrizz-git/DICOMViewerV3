"""
Unit tests for utils.perf_timer (zero-overhead performance timing context manager).
"""

import logging

import utils.perf_timer as perf_timer_module
from utils.perf_timer import perf_mark, perf_timer


def test_disabled_perf_log_yields_without_logging(monkeypatch, caplog):
    monkeypatch.setattr(perf_timer_module, "PERF_LOG", False)
    with caplog.at_level(logging.INFO, logger="perf"), perf_timer("disabled-block"):
        pass
    assert caplog.records == []


def test_enabled_perf_log_emits_perf_message(monkeypatch, caplog):
    monkeypatch.setattr(perf_timer_module, "PERF_LOG", True)
    with caplog.at_level(logging.INFO, logger="perf"), perf_timer("enabled-block"):
        pass
    assert len(caplog.records) == 1
    message = caplog.records[0].getMessage()
    assert "[PERF]" in message
    assert "enabled-block" in message


def test_disabled_perf_mark_does_not_log(monkeypatch, caplog):
    monkeypatch.setattr(perf_timer_module, "PERF_LOG", False)
    with caplog.at_level(logging.INFO, logger="perf"):
        perf_mark("disabled-mark", field="value")
    assert caplog.records == []


def test_enabled_perf_mark_logs_fields(monkeypatch, caplog):
    monkeypatch.setattr(perf_timer_module, "PERF_LOG", True)
    with caplog.at_level(logging.INFO, logger="perf"):
        perf_mark("enabled-mark", field="value", count=2)
    assert len(caplog.records) == 1
    message = caplog.records[0].getMessage()
    assert "[PERF]" in message
    assert "enabled-mark" in message
    assert "field=value" in message
    assert "count=2" in message


def test_enabled_perf_log_reraises_exceptions(monkeypatch):
    monkeypatch.setattr(perf_timer_module, "PERF_LOG", True)
    try:
        with perf_timer("error-block"):
            raise ValueError("boom")
    except ValueError as exc:
        assert str(exc) == "boom"
    else:
        raise AssertionError("expected ValueError to propagate")
