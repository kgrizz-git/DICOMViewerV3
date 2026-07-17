"""PhiScan adapter restricted to materialized staged data-like Git blobs."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

from .common import (
    PrivacyToolResult,
    ToolStatus,
    category_counts,
    load_private_json,
    local_only_environment,
    prepare_private_report,
    protected_workspace,
    resolve_executable,
    run_command,
)

DATA_EXTENSIONS = frozenset(
    {
        ".cfg",
        ".csv",
        ".fhir",
        ".hl7",
        ".html",
        ".ini",
        ".json",
        ".md",
        ".ndjson",
        ".tsv",
        ".txt",
        ".xml",
        ".yaml",
        ".yml",
    }
)


def staged_data_blobs(root: Path, target: Path) -> int:
    """Materialize data-like blobs from the Git index using opaque filenames."""
    names = subprocess.run(
        [
            "git",
            "-C",
            str(root),
            "diff",
            "--cached",
            "--name-only",
            "--diff-filter=ACMR",
        ],
        capture_output=True,
        text=True,
        check=True,
    ).stdout.splitlines()
    count = 0
    for relative in names:
        suffix = Path(relative).suffix.lower()
        if suffix not in DATA_EXTENSIONS:
            continue
        blob = subprocess.run(
            ["git", "-C", str(root), "show", f":{relative}"],
            capture_output=True,
            check=True,
        ).stdout
        output = target / f"item-{count:04d}{suffix}"
        output.write_bytes(blob)
        output.chmod(0o600)
        count += 1
    return count


def run_phiscan(
    root: Path,
    *,
    executable: str = "phi-scan",
    timeout: float = 300,
) -> PrivacyToolResult:
    """Run PhiScan only against protected copies of staged data-like blobs."""
    resolved = resolve_executable(executable)
    if resolved is None:
        return PrivacyToolResult("phiscan", ToolStatus.SKIP, reason="tool-missing")
    with protected_workspace("dvv-phiscan-") as workspace:
        staged = workspace / "staged"
        staged.mkdir(mode=0o700)
        try:
            scanned_count = staged_data_blobs(root, staged)
        except (OSError, subprocess.SubprocessError):
            return PrivacyToolResult(
                "phiscan", ToolStatus.ERROR, reason="git-index-error"
            )
        if not scanned_count:
            return PrivacyToolResult(
                "phiscan", ToolStatus.SKIP, reason="no-staged-data"
            )
        report = workspace / "raw.json"
        prepare_private_report(report)
        config = workspace / "config.yml"
        config.write_text(
            'output:\n  format: json\naudit:\n  database_path: "'
            + str(workspace / "audit.db")
            + '"\nnotifications:\n  email_enabled: false\n  webhook_enabled: false\nai:\n  enable_ai_review: false\n',
            encoding="utf-8",
        )
        config.chmod(0o600)
        completed = run_command(
            [
                resolved,
                "scan",
                str(staged),
                "--output",
                "json",
                "--report-path",
                str(report),
                "--config",
                str(config),
                "--quiet",
                "--no-cache",
            ],
            timeout=timeout,
            cwd=workspace,
            environment=local_only_environment({"HOME": str(workspace)}),
        )
        if completed.timed_out:
            return PrivacyToolResult(
                "phiscan",
                ToolStatus.ERROR,
                reason="timeout",
                scanned_count=scanned_count,
            )
        try:
            payload = load_private_json(report)
            if not isinstance(payload, dict) or not isinstance(
                payload.get("findings"), list
            ):
                raise ValueError
            findings = payload["findings"]
        except (OSError, ValueError, PermissionError, json.JSONDecodeError):
            return PrivacyToolResult(
                "phiscan",
                ToolStatus.ERROR,
                reason="report-invalid",
                scanned_count=scanned_count,
            )
        if completed.returncode not in (0, 1):
            return PrivacyToolResult(
                "phiscan",
                ToolStatus.ERROR,
                reason="tool-error",
                scanned_count=scanned_count,
            )
        categories = category_counts(
            findings, "entity_type", "hipaa_category", "category"
        )
        count = len(findings)
        return PrivacyToolResult(
            "phiscan",
            ToolStatus.FINDINGS if count else ToolStatus.CLEAN,
            count,
            categories,
            scanned_count=scanned_count,
        )
