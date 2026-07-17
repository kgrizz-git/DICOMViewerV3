"""End-to-end synthetic canaries for runtime privacy output boundaries."""

from __future__ import annotations

import logging
from io import StringIO
from pathlib import Path

from PySide6.QtWidgets import QMessageBox

from utils import debug_log as debug_log_module
from utils.privacy.console import print_redacted
from utils.privacy.dialogs import generic_error_message
from utils.privacy.logging_filter import install_privacy_filter
from utils.privacy.reports import write_redacted_json_report


def _canaries(tmp_path: Path) -> tuple[str, str]:
    marker = "-".join(("SYNTHETIC", "SINK", "CANARY", "8F31D2"))
    path = str(tmp_path / "synthetic-sensitive-name_8f31d2.dcm")
    return marker, path


def test_console_stdout_and_stderr_fail_closed(tmp_path: Path) -> None:
    marker, path = _canaries(tmp_path)
    stdout = StringIO()
    stderr = StringIO()

    print_redacted(f"event {marker} {path}", file=stdout)
    print_redacted(ValueError(f"failure {marker} {path}"), file=stderr)

    combined = stdout.getvalue() + stderr.getvalue()
    assert marker not in combined
    assert path not in combined


def test_caplog_boundary_removes_exception_path_and_free_text(
    caplog, tmp_path: Path
) -> None:
    marker, path = _canaries(tmp_path)
    logger = logging.getLogger("privacy-sink-canary")
    logger.propagate = True
    install_privacy_filter(logger)

    with caplog.at_level(logging.ERROR, logger=logger.name):
        logger.error("operation failed: %s", f"{marker} {path}")

    assert marker not in caplog.text
    assert path not in caplog.text

    caplog.clear()
    with caplog.at_level(logging.ERROR, logger=logger.name):
        logger.error(f"directly formatted {marker} {path}")
    assert marker not in caplog.text
    assert path not in caplog.text


def test_dialog_boundary_uses_only_generic_error_copy(
    qapp, monkeypatch, tmp_path: Path
) -> None:
    _ = qapp
    marker, path = _canaries(tmp_path)
    captured: list[str] = []
    monkeypatch.setattr(
        QMessageBox,
        "critical",
        lambda _parent, _title, message, *_args, **_kwargs: captured.append(message),
    )

    error = RuntimeError(f"failure {marker} {path}")
    QMessageBox.critical(None, "Operation Failed", generic_error_message(error))

    rendered = "\n".join(captured)
    assert marker not in rendered
    assert path not in rendered
    assert "RuntimeError" in rendered


def test_report_and_internal_storage_remove_nested_canaries(tmp_path: Path) -> None:
    marker, path = _canaries(tmp_path)
    checkout = tmp_path / "checkout"
    report = tmp_path / "private" / "report.json"
    checkout.mkdir()

    write_redacted_json_report(
        report,
        {
            "operation": "privacy.canary",
            "count": 1,
            "nested": {marker: path, "error": f"failure {marker} {path}"},
        },
        source_root=checkout,
    )

    persisted = report.read_text(encoding="utf-8")
    assert marker not in persisted
    assert path not in persisted
    assert "privacy.canary" in persisted


def test_debug_file_removes_nested_canaries(tmp_path: Path) -> None:
    marker, path = _canaries(tmp_path)
    target = tmp_path / "private" / "debug.jsonl"
    debug_log_module.configure_debug_logging(True, path=target)
    try:
        debug_log_module.debug_log(
            "synthetic:1",
            f"failure {marker} {path}",
            {"operation": "privacy.canary", "nested": {marker: path}},
        )
        persisted = target.read_text(encoding="utf-8")
        assert marker not in persisted
        assert path not in persisted
    finally:
        debug_log_module.configure_debug_logging(False, path=None)
