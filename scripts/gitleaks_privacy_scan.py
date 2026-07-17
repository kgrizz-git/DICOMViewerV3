#!/usr/bin/env python3
"""Run Gitleaks without exposing matched values or durable raw reports."""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

APPROVAL_MANIFEST = "security/approved-gitleaks-fingerprints.json"
FINDINGS_EXIT_CODE = 7
SAFE_RULE_ID = re.compile(r"^[A-Za-z0-9_.-]{1,100}$")
OBJECT_ID = re.compile(r"^[0-9a-f]{40,64}$")
ScanMode = Literal["staged", "history"]


@dataclass(frozen=True)
class Approvals:
    fingerprints: frozenset[tuple[str, str, str]]
    blobs: frozenset[tuple[str, str, str, int]]


def load_approvals(root: Path) -> Approvals:
    manifest = root / APPROVAL_MANIFEST
    if not manifest.exists():
        return Approvals(frozenset(), frozenset())
    try:
        payload = json.loads(manifest.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"approval manifest unreadable ({type(exc).__name__})") from exc
    reviewed = payload.get("reviewed") if isinstance(payload, dict) else None
    reviewed_blobs = payload.get("reviewed_blobs", []) if isinstance(payload, dict) else None
    if not isinstance(reviewed, list) or not isinstance(reviewed_blobs, list):
        raise ValueError("approval manifest has invalid structure")
    approvals: set[tuple[str, str, str]] = set()
    for entry in reviewed:
        if not isinstance(entry, dict):
            raise ValueError("approval manifest contains an invalid entry")
        fingerprint = entry.get("fingerprint")
        path = entry.get("path")
        rule_id = entry.get("rule_id")
        if (
            not isinstance(fingerprint, str)
            or not fingerprint
            or not isinstance(path, str)
            or not path
            or not isinstance(rule_id, str)
            or not rule_id
        ):
            raise ValueError("approval manifest contains an incomplete entry")
        approvals.add((fingerprint, path, rule_id))
    blob_approvals: set[tuple[str, str, str, int]] = set()
    for entry in reviewed_blobs:
        if not isinstance(entry, dict):
            raise ValueError("approval manifest contains an invalid blob entry")
        object_id = entry.get("blob_oid")
        path = entry.get("path")
        rule_id = entry.get("rule_id")
        start_line = entry.get("start_line")
        if (
            not isinstance(object_id, str)
            or not OBJECT_ID.fullmatch(object_id)
            or not isinstance(path, str)
            or not path
            or not isinstance(rule_id, str)
            or not rule_id
            or not isinstance(start_line, int)
            or start_line < 1
        ):
            raise ValueError("approval manifest contains an incomplete blob entry")
        blob_approvals.add((object_id, path, rule_id, start_line))
    return Approvals(frozenset(approvals), frozenset(blob_approvals))


def _finding_key(finding: dict[str, Any]) -> tuple[str, str, str] | None:
    fingerprint = finding.get("Fingerprint")
    path = finding.get("File")
    rule_id = finding.get("RuleID")
    if (
        not isinstance(fingerprint, str)
        or not fingerprint
        or not isinstance(path, str)
        or not path
        or not isinstance(rule_id, str)
        or not rule_id
    ):
        return None
    return fingerprint, path, rule_id


def finding_blob_key(
    root: Path, finding: dict[str, Any], mode: ScanMode
) -> tuple[str, str, str, int] | None:
    """Bind a review to exact file bytes without depending on commit identity."""
    path = finding.get("File")
    rule_id = finding.get("RuleID")
    start_line = finding.get("StartLine")
    if (
        not isinstance(path, str)
        or not path
        or not isinstance(rule_id, str)
        or not rule_id
        or not isinstance(start_line, int)
        or start_line < 1
    ):
        return None
    commit = finding.get("Commit")
    object_spec = f":{path}"
    if mode == "history":
        if not isinstance(commit, str) or not OBJECT_ID.fullmatch(commit):
            return None
        object_spec = f"{commit}:{path}"
    completed = subprocess.run(
        ["git", "rev-parse", object_spec],
        cwd=root,
        capture_output=True,
        text=True,
        check=False,
    )
    object_id = completed.stdout.strip()
    if completed.returncode or not OBJECT_ID.fullmatch(object_id):
        return None
    return object_id, path, rule_id, start_line


def _safe_rule_id(value: object) -> str:
    return value if isinstance(value, str) and SAFE_RULE_ID.fullmatch(value) else "unknown-rule"


def _has_head(root: Path) -> bool:
    return (
        subprocess.run(
            ["git", "rev-parse", "--verify", "HEAD"],
            cwd=root,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=False,
        ).returncode
        == 0
    )


def run_scan(
    root: Path,
    mode: ScanMode,
    *,
    executable: str = "gitleaks",
    timeout_seconds: int = 120,
) -> tuple[int, str]:
    """Return an exit code and category-only status for one Gitleaks scan."""
    root = root.resolve()
    resolved_executable = shutil.which(executable)
    if resolved_executable is None:
        return 2, "ERROR: mandatory Gitleaks executable is unavailable"
    if mode == "history" and not _has_head(root):
        return 0, "CLEAN: no reachable commits to scan"
    try:
        approvals = load_approvals(root)
    except ValueError as exc:
        return 2, f"ERROR: {exc}"

    report_fd, report_name = tempfile.mkstemp(prefix="dv3-gitleaks-", suffix=".json")
    os.close(report_fd)
    report_path = Path(report_name)
    try:
        os.chmod(report_path, 0o600)
        command = [
            resolved_executable,
            "git",
            "--no-banner",
            "--no-color",
            "--redact=100",
            "--report-format=json",
            f"--report-path={report_path}",
            f"--exit-code={FINDINGS_EXIT_CODE}",
        ]
        if mode == "staged":
            command.append("--staged")
        else:
            command.append("--log-opts=HEAD")
        command.append(str(root))
        try:
            completed = subprocess.run(
                command,
                cwd=root,
                capture_output=True,
                check=False,
                timeout=timeout_seconds,
                env={**os.environ, "NO_COLOR": "1"},
            )
        except subprocess.TimeoutExpired:
            return 2, "ERROR: Gitleaks scan timed out"
        if completed.returncode not in (0, FINDINGS_EXIT_CODE):
            return 2, "ERROR: Gitleaks scan failed"
        try:
            payload = json.loads(report_path.read_text(encoding="utf-8") or "[]")
        except (OSError, json.JSONDecodeError):
            return 2, "ERROR: Gitleaks report could not be parsed"
        if not isinstance(payload, list):
            return 2, "ERROR: Gitleaks report has invalid structure"

        malformed = 0
        unapproved: list[dict[str, Any]] = []
        approved_count = 0
        for raw_finding in payload:
            if not isinstance(raw_finding, dict):
                malformed += 1
                continue
            key = _finding_key(raw_finding)
            if key is None:
                malformed += 1
            elif key in approvals.fingerprints or finding_blob_key(
                root, raw_finding, mode
            ) in approvals.blobs:
                approved_count += 1
            else:
                unapproved.append(raw_finding)
        if malformed:
            return 2, "ERROR: Gitleaks report contains malformed findings"
        if unapproved:
            categories = Counter(_safe_rule_id(item.get("RuleID")) for item in unapproved)
            summary = ", ".join(
                f"{rule_id}={count}" for rule_id, count in sorted(categories.items())
            )
            return 1, f"BLOCKED: {len(unapproved)} unapproved secret finding(s); categories: {summary}"
        if approved_count:
            return 0, f"CLEAN: {approved_count} exact reviewed finding(s), no unapproved findings"
        return 0, "CLEAN: no secret findings"
    finally:
        try:
            report_path.unlink(missing_ok=True)
        except OSError:
            pass


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=("staged", "history"))
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--executable", default="gitleaks", help=argparse.SUPPRESS)
    parser.add_argument("--timeout", type=int, default=120)
    args = parser.parse_args(argv)
    code, message = run_scan(
        args.root,
        args.mode,
        executable=args.executable,
        timeout_seconds=max(1, args.timeout),
    )
    stream = sys.stdout if code == 0 else sys.stderr
    print(f"[gitleaks:{args.mode}] {message}", file=stream)
    return code


if __name__ == "__main__":
    raise SystemExit(main())
