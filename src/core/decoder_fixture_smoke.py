"""Privacy-safe frozen-executable smoke runner for reviewed decoder fixtures."""

from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from collections.abc import Sequence
from pathlib import Path

import pydicom

from core.decoder_capabilities import decoder_backend_versions
from core.decoder_fixture_contract import (
    DECODER_FIXTURE_EXPECTATIONS,
    DecoderFixtureExpectation,
)


def _fixture_result(fixture: Path, expected: DecoderFixtureExpectation) -> dict[str, object]:
    dataset = pydicom.dcmread(fixture)
    pixels = dataset.pixel_array
    actual_hash = hashlib.sha256(pixels.tobytes()).hexdigest()
    return {
        "fixture": expected.filename,
        "transfer_syntax_uid": str(dataset.file_meta.TransferSyntaxUID),
        "shape": list(pixels.shape),
        "dtype": pixels.dtype.name,
        "hash_matches": actual_hash == expected.pixel_sha256,
    }


def _child_result(fixture: Path) -> int:
    expected = next(item for item in DECODER_FIXTURE_EXPECTATIONS if item.filename == fixture.name)
    result = _fixture_result(fixture, expected)
    print(json.dumps(result, sort_keys=True, separators=(",", ":")))
    return 0 if result["hash_matches"] else 1


def run_fixture_smoke(fixture_dir: Path) -> tuple[int, dict[str, object]]:
    """Decode every fixture and return a report containing no paths or raw exceptions."""
    results: list[dict[str, object]] = []
    passed = True
    for expected in DECODER_FIXTURE_EXPECTATIONS:
        fixture = fixture_dir / expected.filename
        result: dict[str, object]
        if expected.allowed_stderr:
            child_command = [sys.executable]
            if not getattr(sys, "frozen", False):
                child_command.append(str(Path(__file__).resolve().parents[1] / "main.py"))
            child_command.extend(("--decoder-fixture-child", str(fixture)))
            child = subprocess.run(
                child_command,
                capture_output=True,
                check=False,
            )
            try:
                parsed = json.loads(child.stdout)
                result = (
                    {str(key): value for key, value in parsed.items()}
                    if isinstance(parsed, dict)
                    else {"fixture": expected.filename, "hash_matches": False}
                )
            except json.JSONDecodeError:
                result = {"fixture": expected.filename, "hash_matches": False}
            diagnostic_matches = child.stderr == expected.allowed_stderr
            result["diagnostic_matches"] = diagnostic_matches
            result["child_exit_matches"] = child.returncode == 0
            passed = passed and diagnostic_matches and child.returncode == 0
        else:
            try:
                result = _fixture_result(fixture, expected)
            except Exception:
                result = {"fixture": expected.filename, "hash_matches": False}
        passed = passed and bool(result.get("hash_matches"))
        results.append(result)
    return (0 if passed else 1), {
        "decoder_backends": {
            expected.transfer_syntax_uid: decoder_backend_versions(expected.transfer_syntax_uid)
            for expected in DECODER_FIXTURE_EXPECTATIONS
        },
        "fixture_count": len(results),
        "fixtures": results,
        "passed": passed,
    }


def main(argv: Sequence[str]) -> int:
    if len(argv) == 2 and argv[0] == "--decoder-fixture-child":
        return _child_result(Path(argv[1]))
    if len(argv) == 2 and argv[0] == "--decoder-fixture-smoke":
        exit_code, report = run_fixture_smoke(Path(argv[1]))
        print(json.dumps(report, sort_keys=True, separators=(",", ":")))
        return exit_code
    return 2
