"""Tests for the privacy-safe frozen decoder fixture smoke runner."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from core.decoder_fixture_smoke import run_fixture_smoke

_ROOT = Path(__file__).resolve().parents[2]
_FIXTURE_DIR = _ROOT / "tests" / "fixtures" / "dicom_decoder"


def test_run_fixture_smoke_enforces_hashes_and_exact_12_bit_diagnostic() -> None:
    exit_code, report = run_fixture_smoke(_FIXTURE_DIR)

    assert exit_code == 0
    assert report["passed"] is True
    assert report["fixture_count"] == 9
    extended = next(
        item
        for item in report["fixtures"]
        if item["fixture"] == "synthetic_monochrome_jpeg_extended_12_bit.dcm"
    )
    assert extended["hash_matches"] is True
    assert extended["diagnostic_matches"] is True
    assert extended["child_exit_matches"] is True


def test_main_decoder_fixture_smoke_reports_no_local_fixture_path() -> None:
    result = subprocess.run(
        [sys.executable, "src/main.py", "--decoder-fixture-smoke", str(_FIXTURE_DIR)],
        cwd=_ROOT,
        capture_output=True,
        check=False,
        text=True,
    )

    assert result.returncode == 0
    assert result.stderr == ""
    report = json.loads(result.stdout)
    assert report["passed"] is True
    assert str(_FIXTURE_DIR) not in result.stdout
