#!/usr/bin/env python3
"""Report priority findings for exactly one local SonarQube component.

The command is deliberately opt-in and local-only. It queries all BLOCKER,
CRITICAL, and MAJOR issues for one component, regardless of issue type,
rejecting any response that contains another project's component key. This
prevents a mixed-project response from being triaged as a DICOM Viewer finding.

On success it archives a timestamped JSON dump under ignored
``tmp/sonarqube-findings/`` (plus ``latest.json``) so findings can be compared
over time. Pass ``--no-dump`` to skip the archive. Optional ``--output`` still
writes Markdown under ``tmp/`` for a one-off human-readable report.

Usage (with SONAR_TOKEN in the ignored .env file or exported, and the local
service running):
    python scripts/report_local_sonarqube_issues.py
    python scripts/report_local_sonarqube_issues.py --fail-on-findings
    python scripts/report_local_sonarqube_issues.py --no-dump
    python scripts/report_local_sonarqube_issues.py --output tmp/sonar-findings.md

Tokens remain in the environment and HTTP Authorization header; they are never
put in command arguments, output, or persisted state. Issue message text from
SonarQube is never written to reports.
"""

from __future__ import annotations

import argparse
import base64
import json
import os
import re
import subprocess
import sys
import tempfile
from collections import Counter
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from urllib.parse import urlencode

import requests

try:
    from scripts.privacy_console import print_redacted
    from scripts.run_local_sonarqube import (
        DEFAULT_HOST_URL,
        DEFAULT_PROJECT_KEY,
        get_server_status,
        load_dotenv,
        normalize_host_url,
    )
except ModuleNotFoundError:
    from privacy_console import print_redacted
    from run_local_sonarqube import (
        DEFAULT_HOST_URL,
        DEFAULT_PROJECT_KEY,
        get_server_status,
        load_dotenv,
        normalize_host_url,
    )

REPO_ROOT = Path(__file__).resolve().parent.parent
PAGE_SIZE = 500
REPORTED_QUERIES = (
    ("BLOCKER", {"severities": "BLOCKER"}),
    ("CRITICAL", {"severities": "CRITICAL"}),
    ("MAJOR", {"severities": "MAJOR"}),
)
DEFAULT_DUMP_DIRECTORY = Path("tmp/sonarqube-findings")
LATEST_JSON_NAME = "latest.json"
FINDINGS_SCHEMA_VERSION = 1
_SAFE_FILENAME_RE = re.compile(r"[^A-Za-z0-9._-]+")


class SonarReportError(RuntimeError):
    """Raised when SonarQube cannot produce a complete, scoped report."""


@dataclass(frozen=True)
class AnalysisMetadata:
    """The latest analysis identity returned by SonarQube, when available."""

    date: str | None
    revision: str | None


@dataclass(frozen=True)
class SonarIssue:
    """A safe, component-scoped subset of a SonarQube issue."""

    severity: str
    issue_type: str
    rule: str
    path: str
    line: int | None


@dataclass(frozen=True)
class SonarReport:
    """Complete severe-finding report for one requested project component."""

    project_key: str
    analysis: AnalysisMetadata
    issues: tuple[SonarIssue, ...]


def _authorization_header(token: str) -> str:
    """Return SonarQube Basic auth without ever placing the token in a URL."""
    encoded = base64.b64encode(f"{token}:".encode()).decode("ascii")
    return f"Basic {encoded}"


def _read_json(url: str, token: str) -> dict[str, Any]:
    """Fetch one JSON payload without reflecting server-provided error details."""
    try:
        url = normalize_host_url(url)
    except ValueError as exc:
        raise SonarReportError("SonarQube URL must be a loopback HTTP(S) endpoint") from exc
    try:
        response = requests.get(
            url,
            headers={
                "Accept": "application/json",
                "Authorization": _authorization_header(token),
            },
            timeout=10.0,
        )
        response.raise_for_status()
        payload = response.json()
    except (requests.RequestException, ValueError) as exc:
        raise SonarReportError("SonarQube request could not be completed") from exc
    if not isinstance(payload, dict):
        raise SonarReportError("SonarQube returned a malformed JSON payload")
    return payload


def _component_path(component: Any, project_key: str) -> str:
    """Validate an exact component prefix and return its safe relative path."""
    if not isinstance(component, str):
        raise SonarReportError("SonarQube returned an issue without a component key")
    prefix = f"{project_key}:"
    if not component.startswith(prefix):
        raise SonarReportError("SonarQube returned an issue for a different component")
    path = component.removeprefix(prefix)
    candidate = Path(path)
    if not path or candidate.is_absolute() or ".." in candidate.parts:
        raise SonarReportError("SonarQube returned an unsafe source path")
    return path


def _parse_issue(raw_issue: Any, project_key: str) -> SonarIssue:
    """Convert a complete Sonar issue into the metadata safe for this report."""
    if not isinstance(raw_issue, dict):
        raise SonarReportError("SonarQube returned a malformed issue")
    severity = raw_issue.get("severity")
    issue_type = raw_issue.get("type")
    rule = raw_issue.get("rule")
    if not isinstance(severity, str) or not severity:
        raise SonarReportError("SonarQube returned an issue without required metadata")
    if not isinstance(issue_type, str) or not issue_type:
        raise SonarReportError("SonarQube returned an issue without required metadata")
    if not isinstance(rule, str) or not rule:
        raise SonarReportError("SonarQube returned an issue without required metadata")
    line = raw_issue.get("line")
    if line is not None and (not isinstance(line, int) or isinstance(line, bool) or line < 1):
        raise SonarReportError("SonarQube returned an issue with an invalid line number")
    return SonarIssue(
        severity=severity,
        issue_type=issue_type,
        rule=rule,
        path=_component_path(raw_issue.get("component"), project_key),
        line=line,
    )


def fetch_issues(
    host_url: str,
    token: str,
    project_key: str,
    query: dict[str, str],
) -> tuple[SonarIssue, ...]:
    """Return every issue for one complete, component-filtered query."""
    expected_total: int | None = None
    issues: list[SonarIssue] = []
    page = 1
    while True:
        parameters = {
            "componentKeys": project_key,
            # Explicit open-set only. Omitting statuses on this SonarQube build
            # also returns CLOSED/FIXED issues, which falsely re-reports remediated
            # findings (S2245/S3923) after a successful analysis.
            "statuses": "OPEN,CONFIRMED,REOPENED",
            "p": str(page),
            "ps": str(PAGE_SIZE),
            **query,
        }
        payload = _read_json(f"{host_url}/api/issues/search?{urlencode(parameters)}", token)
        paging = payload.get("paging")
        raw_issues = payload.get("issues")
        if not isinstance(paging, dict) or not isinstance(raw_issues, list):
            raise SonarReportError("SonarQube returned an incomplete issue-search payload")
        total = paging.get("total")
        page_index = paging.get("pageIndex")
        if (
            not isinstance(total, int)
            or isinstance(total, bool)
            or total < 0
            or page_index != page
        ):
            raise SonarReportError("SonarQube returned invalid issue-search pagination")
        if expected_total is None:
            expected_total = total
        elif total != expected_total:
            raise SonarReportError("SonarQube issue-search total changed during pagination")
        issues.extend(_parse_issue(raw_issue, project_key) for raw_issue in raw_issues)
        if len(issues) == expected_total:
            return tuple(issues)
        if len(issues) > expected_total or not raw_issues:
            raise SonarReportError("SonarQube issue-search pagination was incomplete")
        page += 1


def fetch_latest_analysis(host_url: str, token: str, project_key: str) -> AnalysisMetadata:
    """Return the latest analysis date and revision, if SonarQube exposes them."""
    parameters = {"project": project_key, "ps": "1"}
    payload = _read_json(
        f"{host_url}/api/project_analyses/search?{urlencode(parameters)}", token
    )
    analyses = payload.get("analyses")
    if not isinstance(analyses, list):
        raise SonarReportError("SonarQube returned an invalid analysis payload")
    if not analyses:
        return AnalysisMetadata(date=None, revision=None)
    latest = analyses[0]
    if not isinstance(latest, dict):
        raise SonarReportError("SonarQube returned a malformed analysis record")
    date = latest.get("date")
    revision = latest.get("revision")
    if date is not None and not isinstance(date, str):
        raise SonarReportError("SonarQube returned an invalid analysis date")
    if revision is not None and not isinstance(revision, str):
        raise SonarReportError("SonarQube returned an invalid analysis revision")
    return AnalysisMetadata(date=date, revision=revision)


def collect_reported_findings(host_url: str, token: str, project_key: str) -> SonarReport:
    """Fetch the policy-defined priority findings and the latest analysis identity."""
    issues: list[SonarIssue] = []
    for _label, query in REPORTED_QUERIES:
        issues.extend(fetch_issues(host_url, token, project_key, query))
    analysis = fetch_latest_analysis(host_url, token, project_key)
    return SonarReport(project_key=project_key, analysis=analysis, issues=tuple(issues))


def current_git_head(repo_root: Path) -> str | None:
    """Return HEAD when Git metadata is available; otherwise None."""
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=repo_root,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
            check=False,
        )
    except OSError:
        return None
    revision = result.stdout.strip() if isinstance(result.stdout, str) else ""
    return revision if result.returncode == 0 and revision else None


def _count_by(issues: tuple[SonarIssue, ...], attr: str) -> dict[str, int]:
    """Return a stable sorted histogram for one issue attribute."""
    counter: Counter[str] = Counter(getattr(issue, attr) for issue in issues)
    return {key: counter[key] for key in sorted(counter)}


def build_findings_document(
    report: SonarReport,
    *,
    dumped_at_utc: datetime,
    git_head: str | None,
) -> dict[str, Any]:
    """Build the machine-readable archive document (no tokens or issue messages)."""
    return {
        "schema_version": FINDINGS_SCHEMA_VERSION,
        "dumped_at_utc": dumped_at_utc.astimezone(UTC).isoformat(),
        "project_key": report.project_key,
        "analysis": {
            "date": report.analysis.date,
            "revision": report.analysis.revision,
        },
        "git_head": git_head,
        "summary": {
            "total": len(report.issues),
            "by_severity": _count_by(report.issues, "severity"),
            "by_type": _count_by(report.issues, "issue_type"),
            "by_rule": _count_by(report.issues, "rule"),
        },
        "issues": [
            {
                "severity": issue.severity,
                "type": issue.issue_type,
                "rule": issue.rule,
                "path": issue.path,
                "line": issue.line,
            }
            for issue in report.issues
        ],
    }


def render_json_report(
    report: SonarReport,
    *,
    dumped_at_utc: datetime | None = None,
    git_head: str | None = None,
) -> str:
    """Serialize the findings document as indented JSON with a trailing newline."""
    document = build_findings_document(
        report,
        dumped_at_utc=dumped_at_utc or datetime.now(UTC),
        git_head=git_head,
    )
    return json.dumps(document, indent=2, sort_keys=False) + "\n"


def render_markdown_report(report: SonarReport) -> str:
    """Render a stable, concise Markdown report without server-supplied messages."""
    lines = [
        "# Local SonarQube Reported Findings",
        "",
        f"- Project: `{report.project_key}`",
        f"- Latest analysis: `{report.analysis.date or 'not available'}`",
        f"- Revision: `{report.analysis.revision or 'not available'}`",
        f"- Reported findings: {len(report.issues)}",
        "",
    ]
    if report.issues:
        lines.extend(["## Findings", ""])
        for issue in report.issues:
            location = issue.path if issue.line is None else f"{issue.path}:{issue.line}"
            lines.append(
                f"- [{issue.severity}] {issue.issue_type} [{issue.rule}] `{location}`"
            )
    else:
        lines.extend(["## Findings", "", "No matching findings."])
    return "\n".join(lines) + "\n"


def resolve_tmp_path(repo_root: Path, requested_path: Path, *, flag: str = "path") -> Path:
    """Allow a path only below this checkout's ignored ``tmp/`` root."""
    tmp_root = (repo_root / "tmp").resolve()
    candidate = requested_path if requested_path.is_absolute() else repo_root / requested_path
    resolved = candidate.resolve(strict=False)
    if resolved == tmp_root:
        raise SonarReportError(f"{flag} must name a file or directory below tmp/")
    try:
        resolved.relative_to(tmp_root)
    except ValueError as exc:
        raise SonarReportError(
            f"{flag} must stay below the ignored tmp/ directory"
        ) from exc
    return resolved


def resolve_output_path(repo_root: Path, requested_path: Path) -> Path:
    """Allow an optional Markdown report only below ignored ``tmp/``."""
    resolved = resolve_tmp_path(repo_root, requested_path, flag="--output")
    if resolved.is_dir() or requested_path.name in {"", ".", ".."}:
        raise SonarReportError("--output must name a file below tmp/")
    return resolved


def resolve_dump_directory(repo_root: Path, requested_directory: Path) -> Path:
    """Allow the findings archive directory only below ignored ``tmp/``."""
    return resolve_tmp_path(repo_root, requested_directory, flag="--dump-dir")


def _sanitize_filename_part(value: str) -> str:
    """Collapse unsafe characters so dump names stay portable."""
    cleaned = _SAFE_FILENAME_RE.sub("-", value).strip("-._")
    return cleaned or "unknown"


def dump_filename_stem(
    *,
    dumped_at_utc: datetime,
    project_key: str,
    revision: str | None,
) -> str:
    """Build a stable timestamped stem for one findings dump."""
    stamp = dumped_at_utc.astimezone(UTC).strftime("%Y%m%dT%H%M%SZ")
    project = _sanitize_filename_part(project_key)
    short_rev = _sanitize_filename_part((revision or "unknown")[:12])
    return f"{stamp}_{project}_{short_rev}"


def write_text_atomically(path: Path, content: str, *, purpose: str) -> None:
    """Atomically write text with owner-only permissions where supported."""
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        dir=path.parent,
        prefix=f".{path.name}.",
        suffix=".tmp",
        text=True,
    )
    temporary_path = Path(temporary_name)
    try:
        os.chmod(temporary_path, 0o600)
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as output_file:
            output_file.write(content)
        temporary_path.replace(path)
    except OSError as exc:
        temporary_path.unlink(missing_ok=True)
        raise SonarReportError(f"could not write the {purpose}") from exc


def write_markdown_report(path: Path, report: SonarReport) -> None:
    """Atomically write a local Markdown report under ignored ``tmp/``."""
    write_text_atomically(path, render_markdown_report(report), purpose="local SonarQube Markdown report")


def write_json_report(
    path: Path,
    report: SonarReport,
    *,
    dumped_at_utc: datetime | None = None,
    git_head: str | None = None,
    purpose: str = "local SonarQube JSON report",
) -> None:
    """Atomically write a local JSON findings dump under ignored ``tmp/``."""
    write_text_atomically(
        path,
        render_json_report(
            report,
            dumped_at_utc=dumped_at_utc,
            git_head=git_head,
        ),
        purpose=purpose,
    )


def archive_findings_json(
    dump_directory: Path,
    report: SonarReport,
    *,
    dumped_at_utc: datetime | None = None,
    git_head: str | None = None,
) -> tuple[Path, Path]:
    """Write a timestamped JSON dump and refresh ``latest.json`` in the same folder.

    The timestamped dump is written first, then ``latest.json``. A failure on the
    second write leaves the timestamped file in place; re-running the reporter
    refreshes ``latest.json``.
    """
    stamped = dumped_at_utc or datetime.now(UTC)
    revision = report.analysis.revision or git_head
    stem = dump_filename_stem(
        dumped_at_utc=stamped,
        project_key=report.project_key,
        revision=revision,
    )
    timestamped_path = dump_directory / f"{stem}.json"
    latest_path = dump_directory / LATEST_JSON_NAME
    write_json_report(
        timestamped_path,
        report,
        dumped_at_utc=stamped,
        git_head=git_head,
        purpose="timestamped SonarQube findings dump",
    )
    write_json_report(
        latest_path,
        report,
        dumped_at_utc=stamped,
        git_head=git_head,
        purpose="sonarqube-findings/latest.json pointer",
    )
    return timestamped_path, latest_path


def parse_args() -> argparse.Namespace:
    """Parse the intentionally narrow local reporting command."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--host-url",
        default=os.environ.get("SONAR_HOST_URL", DEFAULT_HOST_URL),
        help="SonarQube Community Build URL (default: %(default)s).",
    )
    parser.add_argument(
        "--project-key",
        default=DEFAULT_PROJECT_KEY,
        help="Exact SonarQube component key to report (default: %(default)s).",
    )
    parser.add_argument(
        "--expected-revision",
        help="Fail if SonarQube's latest analysis revision differs from this Git revision.",
    )
    parser.add_argument(
        "--fail-on-findings",
        action="store_true",
        help="Exit 1 when any scoped priority finding is present.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        help="Write Markdown only under this checkout's ignored tmp/ directory.",
    )
    parser.add_argument(
        "--no-dump",
        action="store_true",
        help="Skip the default timestamped JSON archive under tmp/sonarqube-findings/.",
    )
    parser.add_argument(
        "--dump-dir",
        type=Path,
        default=DEFAULT_DUMP_DIRECTORY,
        help=(
            "Directory under ignored tmp/ for timestamped JSON dumps "
            f"(default: {DEFAULT_DUMP_DIRECTORY.as_posix()})."
        ),
    )
    return parser.parse_args()


def main() -> int:
    """Run the component-safe report and return a conventional CLI exit code."""
    load_dotenv(REPO_ROOT)
    args = parse_args()
    token = os.environ.get("SONAR_TOKEN")
    if not token:
        print(
            "SONAR_TOKEN is not set. Add a local analysis token to the ignored .env "
            "file or export it before reporting.",
            file=sys.stderr,
        )
        return 2
    project_key = args.project_key.strip()
    if not project_key:
        print("--project-key must not be empty", file=sys.stderr)
        return 2
    output_path: Path | None = None
    dump_paths: tuple[Path, Path] | None = None
    try:
        host_url = normalize_host_url(args.host_url)
        if get_server_status(host_url) != "UP":
            print_redacted(f"SonarQube is not ready: {host_url} did not report UP.", file=sys.stderr)
            return 2
        report = collect_reported_findings(host_url, token, project_key)
        if args.expected_revision and report.analysis.revision != args.expected_revision:
            print(
                "SonarQube latest analysis revision does not match --expected-revision.",
                file=sys.stderr,
            )
            return 2
        git_head = current_git_head(REPO_ROOT)
        dumped_at = datetime.now(UTC)
        if not args.no_dump:
            dump_directory = resolve_dump_directory(REPO_ROOT, args.dump_dir)
            dump_paths = archive_findings_json(
                dump_directory,
                report,
                dumped_at_utc=dumped_at,
                git_head=git_head,
            )
        if args.output is not None:
            output_path = resolve_output_path(REPO_ROOT, args.output)
            write_markdown_report(output_path, report)
    except (RuntimeError, SonarReportError, ValueError) as exc:
        print_redacted(f"Local SonarQube report failed: {exc}", file=sys.stderr)
        return 2

    print("Local SonarQube reported-finding report completed.")
    print(f"Reported findings: {len(report.issues)}")
    if dump_paths is not None:
        timestamped_path, latest_path = dump_paths
        # Relative paths only — avoid printing identifiers that end in ``root``.
        archive_rel = timestamped_path.relative_to(REPO_ROOT).as_posix()
        latest_rel = latest_path.relative_to(REPO_ROOT).as_posix()
        print(f"JSON archive: {archive_rel} (latest: {latest_rel})")
    elif args.no_dump:
        print("JSON archive skipped (--no-dump).")
    if output_path is not None:
        print("Markdown report written under the ignored tmp/ directory.")
    else:
        print("Use --output tmp/<report>.md for an optional Markdown copy.")
    return 1 if args.fail_on_findings and report.issues else 0


if __name__ == "__main__":
    raise SystemExit(main())
