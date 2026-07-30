"""Tests for the privacy-safe frozen decoder fixture smoke runner."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from core import decoder_fixture_smoke
from core.decoder_fixture_smoke import run_fixture_smoke

_ROOT = Path(__file__).resolve().parents[2]
_FIXTURE_DIR = _ROOT / "tests" / "fixtures" / "dicom_decoder"


def test_run_fixture_smoke_enforces_hashes_and_exact_12_bit_diagnostic() -> None:
    exit_code, report = run_fixture_smoke(_FIXTURE_DIR)

    assert exit_code == 0
    assert report["passed"] is True
    assert report["fixture_count"] == 9
    assert all(item["diagnostic_matches"] is True for item in report["fixtures"])
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


def test_run_fixture_smoke_rejects_unallowlisted_output(monkeypatch) -> None:
    def unexpected_output(*_args, **_kwargs):
        return subprocess.CompletedProcess(
            args=[],
            returncode=0,
            stdout=b'{"fixture":"synthetic_rgb_no_color_markers_jpeg_baseline.dcm","hash_matches":true}',
            stderr=b"unexpected native output\n",
        )

    monkeypatch.setattr(decoder_fixture_smoke.subprocess, "run", unexpected_output)

    exit_code, report = run_fixture_smoke(_FIXTURE_DIR)

    assert exit_code == 1
    assert report["passed"] is False
    assert all(item["diagnostic_matches"] is False for item in report["fixtures"])


def test_unknown_child_fixture_fails_without_raw_exception(capsys) -> None:
    exit_code = decoder_fixture_smoke.main(["--decoder-fixture-child", "unknown.dcm"])

    captured = capsys.readouterr()
    assert exit_code == 1
    assert json.loads(captured.out) == {"fixture": "unknown.dcm", "hash_matches": False}
    assert captured.err == ""
