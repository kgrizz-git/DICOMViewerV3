"""On-demand DICOM tag and burned-in-pixel advisory review adapter."""

from __future__ import annotations

import json
from pathlib import Path

from .common import (
    PrivacyToolResult,
    ToolStatus,
    load_private_json,
    prepare_private_report,
    protected_workspace,
    resolve_executable,
    run_command,
)


def run_dicom_review(
    path: Path,
    *,
    executable: str = "dicom-phi-scan",
    timeout: float = 600,
) -> PrivacyToolResult:
    """Review one explicitly selected DICOM; ordinary viewer loading is unaffected."""
    resolved = resolve_executable(executable)
    if resolved is None:
        return PrivacyToolResult("dicom-review", ToolStatus.SKIP, reason="tool-missing")
    with protected_workspace("dvv-dicom-") as workspace:
        report = workspace / "raw.json"
        prepare_private_report(report)
        completed = run_command(
            [resolved, str(path), "--output", str(report), "--cpu"],
            timeout=timeout,
            cwd=workspace,
        )
        if completed.timed_out:
            return PrivacyToolResult(
                "dicom-review", ToolStatus.ERROR, reason="timeout", scanned_count=1
            )
        try:
            payload = load_private_json(report)
            if not isinstance(payload, dict):
                raise ValueError
            tags = payload.get("tag_findings", [])
            pixels = payload.get("pixel_findings", [])
            if not isinstance(tags, list) or not isinstance(pixels, list):
                raise ValueError
        except (OSError, ValueError, PermissionError, json.JSONDecodeError):
            return PrivacyToolResult(
                "dicom-review",
                ToolStatus.ERROR,
                reason="report-invalid",
                scanned_count=1,
            )
        if completed.returncode not in (0, 1):
            return PrivacyToolResult(
                "dicom-review", ToolStatus.ERROR, reason="tool-error", scanned_count=1
            )
        categories = {
            name: count
            for name, count in (("dicom-tag", len(tags)), ("pixel-ocr", len(pixels)))
            if count
        }
        count = sum(categories.values())
        return PrivacyToolResult(
            "dicom-review",
            ToolStatus.FINDINGS if count else ToolStatus.CLEAN,
            count,
            categories,
            scanned_count=1,
        )
