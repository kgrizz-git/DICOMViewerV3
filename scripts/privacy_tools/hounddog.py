"""Hounddog local-only advisory adapter."""

from __future__ import annotations

import json
import re
from pathlib import Path

from .common import (
    PrivacyToolResult,
    ToolStatus,
    load_private_json,
    local_only_environment,
    prepare_private_report,
    protected_workspace,
    resolve_executable,
    run_command,
)


def run_hounddog(
    root: Path,
    *,
    config_path: Path,
    executable: str = "hounddog",
    timeout: float = 300,
) -> PrivacyToolResult:
    """Scan project source with no Git/SCM metadata and no cloud credential."""
    resolved = resolve_executable(executable)
    if resolved is None:
        return PrivacyToolResult("hounddog", ToolStatus.SKIP, reason="tool-missing")
    try:
        config = json.loads(config_path.read_text(encoding="utf-8"))
        sources = _string_list(config, "data_elements")
        sinks = _string_list(config, "data_sinks")
    except (OSError, ValueError, json.JSONDecodeError):
        return PrivacyToolResult("hounddog", ToolStatus.ERROR, reason="config-invalid")

    version_run = run_command([resolved, "--version"], timeout=min(timeout, 10))
    version_match = re.search(
        r"\d+(?:\.\d+){1,3}", version_run.stdout + version_run.stderr
    )
    version = version_match.group(0) if version_match else "unknown"
    with protected_workspace("dvv-hounddog-") as workspace:
        report = workspace / "raw.json"
        prepare_private_report(report)
        command = [
            resolved,
            "scan",
            str(root / "src"),
            "--no-git",
            "--no-color",
            "--no-tips",
            "--no-file-stats",
            "--output-format",
            "json",
            "--output-path",
            str(report),
        ]
        for source in sources:
            command.extend(("--include-data-element", source))
        for sink in sinks:
            command.extend(("--include-data-sink", sink))
        completed = run_command(
            command,
            timeout=timeout,
            cwd=root,
            environment=local_only_environment(),
        )
        if completed.timed_out:
            return PrivacyToolResult(
                "hounddog", ToolStatus.ERROR, version=version, reason="timeout"
            )
        try:
            payload = load_private_json(report)
            if not isinstance(payload, dict) or not isinstance(
                payload.get("dataflows"), list
            ):
                raise ValueError
            dataflows = payload["dataflows"]
        except (OSError, ValueError, PermissionError, json.JSONDecodeError):
            return PrivacyToolResult(
                "hounddog", ToolStatus.ERROR, version=version, reason="report-invalid"
            )
        if completed.returncode not in (0, 1):
            return PrivacyToolResult(
                "hounddog", ToolStatus.ERROR, version=version, reason="tool-error"
            )
        count = len(dataflows)
        status = ToolStatus.FINDINGS if count else ToolStatus.CLEAN
        return PrivacyToolResult(
            "hounddog",
            status,
            count,
            {"dataflow": count} if count else {},
            version,
            scanned_count=1,
        )


def _string_list(config: object, key: str) -> list[str]:
    if not isinstance(config, dict) or not isinstance(config.get(key), list):
        raise ValueError(key)
    values = config[key]
    if not all(isinstance(value, str) and value for value in values):
        raise ValueError(key)
    return list(values)
