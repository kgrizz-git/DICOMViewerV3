#!/usr/bin/env python3
"""Report severe findings for exactly one local SonarQube component.

The command is deliberately opt-in and local-only. It queries all BLOCKER
issues plus CRITICAL BUG and VULNERABILITY issues for one component, rejecting
any response that contains another project's component key. This prevents a
mixed-project response from being triaged as a DICOM Viewer finding.

Usage (with SONAR_TOKEN set and the local service running):
    python scripts/report_local_sonarqube_issues.py
    python scripts/report_local_sonarqube_issues.py --fail-on-findings
    python scripts/report_local_sonarqube_issues.py --output tmp/sonar-severe.md

The optional report path is restricted to the ignored ``tmp/`` directory.
Tokens remain in the environment and HTTP Authorization header; they are never
put in command arguments, output, or persisted state.
"""

from __future__ import annotations

import argparse
import base64
import json
import os
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

try:
    from scripts.privacy_console import print_redacted
    from scripts.run_local_sonarqube import (
        DEFAULT_HOST_URL,
        DEFAULT_PROJECT_KEY,
        get_server_status,
        normalize_host_url,
    )
except ModuleNotFoundError:
    from privacy_console import print_redacted
    from run_local_sonarqube import (
        DEFAULT_HOST_URL,
        DEFAULT_PROJECT_KEY,
        get_server_status,
        normalize_host_url,
    )

REPO_ROOT = Path(__file__).resolve().parent.parent
PAGE_SIZE = 500
SEVERE_QUERIES = (
    ("BLOCKER", {"severities": "BLOCKER"}),
    ("CRITICAL BUG/VULNERABILITY", {"severities": "CRITICAL", "types": "BUG,VULNERABILITY"}),
)


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
    request = Request(
        url,
        headers={
            "Accept": "application/json",
            "Authorization": _authorization_header(token),
        },
    )
    try:
        # The CLI normalizes host_url to an HTTP(S) loopback endpoint before this call.
        # nosemgrep: python.lang.security.audit.dynamic-urllib-use-detected.dynamic-urllib-use-detected
        with urlopen(request, timeout=10.0) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except (HTTPError, OSError, URLError, UnicodeDecodeError, json.JSONDecodeError) as exc:
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


def collect_severe_report(host_url: str, token: str, project_key: str) -> SonarReport:
    """Fetch the policy-defined severe findings and the latest analysis identity."""
    issues: list[SonarIssue] = []
    for _label, query in SEVERE_QUERIES:
        issues.extend(fetch_issues(host_url, token, project_key, query))
    analysis = fetch_latest_analysis(host_url, token, project_key)
    return SonarReport(project_key=project_key, analysis=analysis, issues=tuple(issues))


def render_markdown_report(report: SonarReport) -> str:
    """Render a stable, concise Markdown report without server-supplied messages."""
    lines = [
        "# Local SonarQube Severe Findings",
        "",
        f"- Project: `{report.project_key}`",
        f"- Latest analysis: `{report.analysis.date or 'not available'}`",
        f"- Revision: `{report.analysis.revision or 'not available'}`",
        f"- Severe findings: {len(report.issues)}",
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


def resolve_output_path(repo_root: Path, requested_path: Path) -> Path:
    """Allow an optional report only below this checkout's ignored ``tmp/`` root."""
    tmp_root = (repo_root / "tmp").resolve()
    candidate = requested_path if requested_path.is_absolute() else repo_root / requested_path
    resolved = candidate.resolve(strict=False)
    if resolved == tmp_root:
        raise SonarReportError("--output must name a file below tmp/")
    try:
        resolved.relative_to(tmp_root)
    except ValueError as exc:
        raise SonarReportError("--output must stay below the ignored tmp/ directory") from exc
    return resolved


def write_markdown_report(path: Path, report: SonarReport) -> None:
    """Atomically write a local report with owner-only permissions where supported."""
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
            output_file.write(render_markdown_report(report))
        temporary_path.replace(path)
    except OSError as exc:
        temporary_path.unlink(missing_ok=True)
        raise SonarReportError("could not write the local SonarQube report") from exc


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
        help="Exit 1 when any scoped severe finding is present.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        help="Write Markdown only under this checkout's ignored tmp/ directory.",
    )
    return parser.parse_args()


def main() -> int:
    """Run the component-safe report and return a conventional CLI exit code."""
    args = parse_args()
    token = os.environ.get("SONAR_TOKEN")
    if not token:
        print("SONAR_TOKEN is not set. Configure a local analysis token before reporting.", file=sys.stderr)
        return 2
    project_key = args.project_key.strip()
    if not project_key:
        print("--project-key must not be empty", file=sys.stderr)
        return 2
    try:
        host_url = normalize_host_url(args.host_url)
        if get_server_status(host_url) != "UP":
            print_redacted(f"SonarQube is not ready: {host_url} did not report UP.", file=sys.stderr)
            return 2
        report = collect_severe_report(host_url, token, project_key)
        if args.expected_revision and report.analysis.revision != args.expected_revision:
            print("SonarQube latest analysis revision does not match --expected-revision.", file=sys.stderr)
            return 2
        output_path = resolve_output_path(REPO_ROOT, args.output) if args.output else None
        if output_path is not None:
            write_markdown_report(output_path, report)
    except (RuntimeError, SonarReportError, ValueError) as exc:
        print_redacted(f"Local SonarQube report failed: {exc}", file=sys.stderr)
        return 2

    print("Local SonarQube severe-finding report completed.")
    print(f"Severe findings: {len(report.issues)}")
    print("Use --output tmp/<report>.md to retain scoped finding metadata.")
    if output_path is not None:
        print("Detailed report written under the ignored tmp/ directory.")
    return 1 if args.fail_on_findings and report.issues else 0


if __name__ == "__main__":
    raise SystemExit(main())
