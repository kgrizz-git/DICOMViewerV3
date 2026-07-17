"""Positive semantics and negative canaries for typed structural output."""

from __future__ import annotations

import logging
import os
import subprocess
import sys
from io import StringIO
from pathlib import Path

from scripts import check_dependency_licenses as license_check
from scripts import decoder_corpus_report as decoder_report
from utils.privacy.console import print_redacted, print_structural_event
from utils.privacy.logging_filter import PrivacyLogFilter
from utils.privacy.structural_adapters import print_license_obligation
from utils.privacy.structural_events import log_structural_event


class _FlushStream(StringIO):
    def __init__(self) -> None:
        super().__init__()
        self.flush_count = 0

    def flush(self) -> None:
        self.flush_count += 1
        super().flush()


def test_structural_console_preserves_typed_metrics_and_print_controls() -> None:
    stream = _FlushStream()

    print_structural_event(
        "fusion.load_summary",
        metrics={"instance_count": 2, "series_count": 1},
        sep="|",
        end="<END>",
        file=stream,
        flush=True,
    )

    output = stream.getvalue()
    assert output.endswith("<END>")
    assert stream.flush_count == 1
    assert "operation=fusion.load_summary" in output
    assert "instance_count=2" in output
    assert "series_count=1" in output
    assert "|" in output


def test_structural_console_and_log_remove_nested_sensitive_canaries() -> None:
    marker = "SYNTHETIC-OUTPUT-CANARY-71A9"
    path = "/Users/private-user/studies/patient-file_71a9.dcm"
    uid = "2.25.999999999999999999999"
    stream = StringIO()

    print_structural_event(
        "application.startup",
        error=RuntimeError(f"failure {marker} {path}"),
        identifiers={
            "package": path,
            "version": uid,
            marker: marker,
        },
        metrics={marker: {"filename": path, "uid": uid}},
        file=stream,
    )

    handler = logging.StreamHandler(stream)
    handler.addFilter(PrivacyLogFilter())
    logger = logging.getLogger("privacy.structural.negative")
    logger.handlers = [handler]
    logger.propagate = False
    logger.setLevel(logging.INFO)
    try:
        log_structural_event(
            logger,
            logging.INFO,
            "fusion.load_summary",
            identifiers={"package": path},
            metrics={
                "instance_count": 2,
                "series_count": 1,
                marker: marker,
            },
        )
        logger.info(f"arbitrary {marker} {path} {uid}")
    finally:
        logger.handlers = []
        logger.propagate = True

    output = stream.getvalue()
    assert marker not in output
    assert path not in output
    assert uid not in output
    assert "failure" not in output
    assert "RuntimeError" in output
    assert "[REDACTED]" in output
    assert "operation=fusion.load_summary" in output
    assert "instance_count=2" in output


def test_license_and_decoder_reports_keep_meaningful_safe_rows(capsys) -> None:
    row = {
        "name": "example-package",
        "version": "3.2.1",
        "license": "GNU General Public License v3 or later (GPLv3+); OSI Approved",
        "source": "classifier",
        "category": license_check.OBLIGATION,
    }
    license_check.render_report([row], [], [row], "ignored")
    print_license_obligation(
        package="example-obligation",
        version="2.4.1",
        license_name="MPL-2.0",
        source="expression",
    )
    decoder_report.print_decoder_environment({"pydicom": "3.0.1"})
    decoder_report.print_syntax_summary(
        {
            "safe-key": {
                "name": "JPEG Baseline 8-bit",
                "at_risk": True,
                "total": 4,
                "decoded": 3,
                "failed": 1,
                "modalities": {"CT"},
            }
        }
    )

    output = capsys.readouterr().out
    assert "package=example-package" in output
    assert "version=3.2.1" in output
    assert (
        "license=GNU General Public License v3 or later (GPLv3+); OSI Approved"
        in output
    )
    assert "package=example-obligation" in output
    assert "version=2.4.1" in output
    assert "license=MPL-2.0" in output
    assert "package=pydicom" in output
    assert "version=3.0.1" in output
    assert "format=JPEG Baseline 8-bit" in output
    assert "total_count=4" in output
    assert "decoded_count=3" in output
    assert "failed_count=1" in output


def test_fusion_structural_event_preserves_dimensions_counts_and_metrics() -> None:
    stream = StringIO()
    print_structural_event(
        "fusion.series_summary",
        category="ct",
        metrics={
            "slice_count": 24,
            "rows": 512,
            "columns": 512,
            "pixel_spacing_mm": 0.75,
            "shape": (24, 512, 512),
        },
        file=stream,
    )
    output = stream.getvalue()
    assert "operation=fusion.series_summary" in output
    assert "category=ct" in output
    assert "slice_count=24" in output
    assert "rows=512" in output
    assert "columns=512" in output
    assert "pixel_spacing_mm=0.75" in output
    assert "shape=24x512x512" in output


def test_redacted_console_preserves_stream_separator_terminator_and_flush() -> None:
    stream = _FlushStream()
    print_redacted(2, True, sep="|", end="!", file=stream, flush=True)
    assert stream.getvalue() == "2|True!"
    assert stream.flush_count == 1


def test_structural_console_does_not_change_child_exit_status() -> None:
    root = Path(__file__).resolve().parents[1]
    code = (
        "from scripts.privacy_console import print_structural_event; "
        "print_structural_event('fusion.load_summary', "
        "metrics={'instance_count': 2, 'series_count': 1}); "
        "raise SystemExit(7)"
    )
    environment = os.environ.copy()
    environment["PYTHONPATH"] = str(root)
    completed = subprocess.run(
        [sys.executable, "-c", code],
        cwd=root,
        env=environment,
        capture_output=True,
        text=True,
        check=False,
        timeout=30,
    )

    assert completed.returncode == 7
    assert "operation=fusion.load_summary" in completed.stdout
    assert "instance_count=2" in completed.stdout
