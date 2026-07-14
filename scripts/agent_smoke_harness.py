#!/usr/bin/env python3
"""
Agent-oriented smoke checks: environment, imports, DICOM fixture, optional Qt.

Does not start the full GUI by default (CI-safe). Writes a JSON report with
--write-report for agent handoff.

Usage (from repository root, venv activated):
    python scripts/agent_smoke_harness.py
    python scripts/agent_smoke_harness.py --qt-smoke
    python scripts/agent_smoke_harness.py --write-report

Exit code: 0 if all enabled checks pass, 1 otherwise.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent
SRC = REPO_ROOT / "src"
FIXTURE = (
    REPO_ROOT
    / "tests"
    / "fixtures"
    / "dicom_rdsr"
    / "synthetic_ct_dose_comprehensive_sr.dcm"
)


def _ensure_src_on_path() -> None:
    src_str = str(SRC)
    if src_str not in sys.path:
        sys.path.insert(0, src_str)


def check_python_version(report: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    ver = sys.version_info
    report["python"] = f"{ver.major}.{ver.minor}.{ver.micro}"
    if ver < (3, 10):
        errors.append(f"Python {report['python']} < 3.10 (pylinac requirement)")
    return errors


def check_imports(report: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    _ensure_src_on_path()
    modules = (
        "version",
        "core.dicom_parser",
        "core.sr_sop_classes",
    )
    imported: list[str] = []
    for name in modules:
        try:
            __import__(name)
            imported.append(name)
        except Exception as exc:
            errors.append(f"import {name}: {exc}")
    report["imports_ok"] = imported
    return errors


def check_version(report: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    _ensure_src_on_path()
    try:
        from version import __version__  # type: ignore[import-not-found]

        report["app_version"] = __version__
    except Exception as exc:
        errors.append(f"version.__version__: {exc}")
    return errors


def check_dicom_fixture(report: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    if not FIXTURE.is_file():
        errors.append(f"missing fixture: {FIXTURE.relative_to(REPO_ROOT)}")
        return errors
    try:
        import pydicom

        ds = pydicom.dcmread(FIXTURE, stop_before_pixels=True)
        report["fixture"] = {
            "path": str(FIXTURE.relative_to(REPO_ROOT)),
            "sop_class": getattr(ds, "SOPClassUID", None),
            "modality": getattr(ds, "Modality", None),
        }
    except Exception as exc:
        errors.append(f"pydicom read fixture: {exc}")
    return errors


def check_qt_smoke(report: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    try:
        from PySide6.QtWidgets import QApplication
    except ImportError as exc:
        errors.append(f"PySide6 not available: {exc}")
        return errors

    app = QApplication.instance()
    created = False
    if app is None:
        app = QApplication(sys.argv)
        created = True
    report["qt"] = {"qapplication": "ok"}
    if created and app is not None:
        app.quit()
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--qt-smoke",
        action="store_true",
        help="Instantiate QApplication (headless-friendly on CI).",
    )
    parser.add_argument(
        "--write-report",
        action="store_true",
        help="Write logs/agent-smoke-report.json",
    )
    parser.add_argument(
        "--root",
        type=Path,
        default=REPO_ROOT,
        help="Repository root",
    )
    args = parser.parse_args()
    repo_root = args.root.resolve()

    report: dict[str, Any] = {
        "timestamp_utc": datetime.now(UTC).isoformat(),
        "repo_root": str(repo_root),
    }
    all_errors: list[str] = []
    all_errors.extend(check_python_version(report))
    all_errors.extend(check_version(report))
    all_errors.extend(check_imports(report))
    all_errors.extend(check_dicom_fixture(report))
    if args.qt_smoke:
        all_errors.extend(check_qt_smoke(report))

    report["status"] = "pass" if not all_errors else "fail"
    report["errors"] = all_errors
    report["launch_app"] = "python src/main.py"
    report["manual_smoke"] = "dev-docs/orchestration/AGENT_SMOKE.md"

    if args.write_report:
        log_dir = repo_root / "logs"
        log_dir.mkdir(parents=True, exist_ok=True)
        out = log_dir / "agent-smoke-report.json"
        out.write_text(json.dumps(report, indent=2), encoding="utf-8")
        print(f"Wrote {out.relative_to(repo_root)}")

    if all_errors:
        print("Agent smoke harness failed:", file=sys.stderr)
        for line in all_errors:
            print(f"  {line}", file=sys.stderr)
        return 1

    print(
        f"OK: agent smoke (version={report.get('app_version')}, "
        f"imports={len(report.get('imports_ok', []))}, "
        f"fixture={report.get('fixture', {}).get('path', 'n/a')})"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
